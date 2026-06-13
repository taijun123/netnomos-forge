# -*- coding: utf-8 -*-
"""forge.core.explainer — 规则卡 RAG 增强（engine.explain 之后的增强环节）.

不改 engine.explain 签名：server pipeline 先调 engine.explain 拿基础规则卡，
再用本模块做两件事：
1. RAG 增强：从核心知识库与场景知识库加载 Markdown / JSON 片段，按规则字段、
   业务上下文、标签与正文命中排序，把受预算约束的片段拼进中文解释 prompt，
   交给 LLMClient(role="explain") 润色；MockBackend / 无 LLM 时保留模板解释，
   只补充 citation（知识库出处），保证沙箱可用且确定性。
2. filter_coincidence：启发式标记疑似巧合规则（常量过于具体且 support 低），
   置 RuleCard.is_coincidence=True 供前端置灰。

纯标准库实现，任何环境可 import。
"""
from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from forge.contracts import Rule, RuleCard, RuleSet, SCENARIO_DIR

log = logging.getLogger("forge.core.explainer")

KNOWLEDGE_DIR = Path(__file__).parent / "knowledge"

# 巧合过滤：常见"真实领域常量"白名单（物理上下界 / 知名端口 / 平凡值），
# 命中白名单的常量不视为"过于具体"。
COMMON_CONSTANTS = {0, 1, 2, 42, 53, 80, 123, 137, 138, 443, 8000, 65535, 10000}
# 支持度低于该阈值且含可疑常量 → 疑似巧合
COINCIDENCE_SUPPORT_THRESHOLD = 0.98
# 支持度极低 → 直接疑似巧合（无论常量）
LOW_SUPPORT_THRESHOLD = 0.5


@dataclass
class KnowledgeSection:
    """知识库选段：文档标题 + 小节标题 + 正文 + 可选元数据."""
    doc_title: str
    heading: str
    body: str
    source: str = ""
    tags: tuple[str, ...] = ()
    path: str = ""

    @property
    def citation(self) -> str:
        return f"{self.doc_title} · {self.heading}"


def _env_int(name: str, default: int, *, minimum: int = 0) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return max(minimum, int(raw))
    except ValueError:
        log.warning("环境变量 %s=%r 不是整数，使用默认值 %s", name, raw, default)
        return default


def _split_env_paths(raw: str | None) -> list[Path]:
    if not raw:
        return []
    return [Path(p.strip()) for p in raw.split(os.pathsep) if p.strip()]


def _dedupe_paths(paths: Iterable[str | Path]) -> list[Path]:
    seen: set[str] = set()
    out: list[Path] = []
    for item in paths:
        path = Path(item)
        key = str(path.resolve(strict=False))
        if key not in seen:
            seen.add(key)
            out.append(path)
    return out


def _as_tags(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        raw = re.split(r"[,;，；\s]+", value)
        return tuple(t.strip() for t in raw if t.strip())
    if isinstance(value, (list, tuple, set)):
        return tuple(str(t).strip() for t in value if str(t).strip())
    return (str(value).strip(),) if str(value).strip() else ()


def _read_textish(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        return "\n".join(_read_textish(item) for item in value if _read_textish(item)).strip()
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value).strip()


def _load_markdown_sections(md: Path) -> list[KnowledgeSection]:
    text = md.read_text(encoding="utf-8")
    doc_title = md.stem
    m = re.search(r"^#\s+(.+)$", text, flags=re.M)
    if m:
        doc_title = m.group(1).strip()

    sections: list[KnowledgeSection] = []
    parts = re.split(r"^##\s+", text, flags=re.M)
    if len(parts) == 1:
        body = text.strip()
        if body:
            sections.append(KnowledgeSection(
                doc_title=doc_title,
                heading="概览",
                body=body,
                source=md.name,
                tags=_as_tags(md.stem.replace("_", " ")),
                path=str(md),
            ))
        return sections

    for part in parts[1:]:
        lines = part.splitlines()
        if not lines:
            continue
        heading = lines[0].strip()
        body = "\n".join(lines[1:]).strip()
        if not body:
            continue
        sections.append(KnowledgeSection(
            doc_title=doc_title,
            heading=heading,
            body=body,
            source=md.name,
            tags=_as_tags(md.stem.replace("_", " ")),
            path=str(md),
        ))
    return sections


def _json_records(payload: Any) -> tuple[dict[str, Any], list[Any]]:
    if isinstance(payload, list):
        return {}, payload
    if not isinstance(payload, dict):
        return {}, []
    root_meta = {
        "doc_title": payload.get("doc_title") or payload.get("document") or payload.get("title"),
        "source": payload.get("source") or payload.get("url"),
        "tags": payload.get("tags"),
    }
    for key in ("sections", "items", "records", "knowledge"):
        value = payload.get(key)
        if isinstance(value, list):
            return root_meta, value
    if any(key in payload for key in ("body", "content", "text", "summary")):
        return root_meta, [payload]
    return root_meta, []


def _load_json_sections(json_path: Path) -> list[KnowledgeSection]:
    try:
        payload = json.loads(json_path.read_text(encoding="utf-8"))
    except Exception as exc:
        log.warning("知识库 JSON 读取失败：%s（%s）", json_path, exc)
        return []

    root_meta, records = _json_records(payload)
    sections: list[KnowledgeSection] = []
    root_doc = root_meta.get("doc_title") or json_path.stem
    root_source = root_meta.get("source") or json_path.name
    root_tags = _as_tags(root_meta.get("tags")) + _as_tags(json_path.stem.replace("_", " "))
    for index, item in enumerate(records, start=1):
        if not isinstance(item, dict):
            log.warning("知识库 JSON 跳过非对象记录：%s #%s", json_path, index)
            continue
        body = _read_textish(
            item.get("body")
            or item.get("content")
            or item.get("text")
            or item.get("summary")
        )
        if not body:
            log.warning("知识库 JSON 跳过空正文记录：%s #%s", json_path, index)
            continue
        doc_title = _read_textish(
            item.get("doc_title")
            or item.get("document")
            or item.get("doc")
            or root_doc
        )
        heading = _read_textish(
            item.get("heading")
            or item.get("title")
            or item.get("name")
            or item.get("topic")
            or f"section-{index}"
        )
        source = _read_textish(item.get("source") or item.get("url") or root_source)
        tags = root_tags + _as_tags(item.get("tags"))
        sections.append(KnowledgeSection(
            doc_title=doc_title or json_path.stem,
            heading=heading or f"section-{index}",
            body=body,
            source=source,
            tags=tags,
            path=str(json_path),
        ))
    return sections


def _load_sections(knowledge_dir: Path) -> list[KnowledgeSection]:
    """加载 knowledge/*.md 与 knowledge/*.json，返回 RAG 检索单元."""
    sections: list[KnowledgeSection] = []
    if not knowledge_dir.is_dir():
        return sections
    for md in sorted(knowledge_dir.glob("*.md")):
        sections.extend(_load_markdown_sections(md))
    for json_path in sorted(knowledge_dir.glob("*.json")):
        sections.extend(_load_json_sections(json_path))
    return sections


def _collect_constants(formula) -> list[float]:
    """递归收集公式 dict 中的数值常量."""
    found: list[float] = []

    def walk(node):
        if isinstance(node, dict):
            if node.get("kind") == "constant":
                v = node.get("value")
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    found.append(float(v))
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(formula)
    return found


class RuleExplainer:
    """规则卡 RAG 增强器：build_prompt / enhance / filter_coincidence."""

    def __init__(
        self,
        knowledge_dir: str | Path | None = None,
        *,
        knowledge_dirs: Iterable[str | Path] | None = None,
        top_k: int | None = None,
        max_section_chars: int | None = None,
        max_context_chars: int | None = None,
    ):
        paths: list[str | Path] = []
        if knowledge_dirs is not None:
            paths.extend(knowledge_dirs)
        if knowledge_dir is not None:
            paths.append(knowledge_dir)
        if not paths:
            paths.append(KNOWLEDGE_DIR)
        paths.extend(_split_env_paths(os.getenv("FORGE_RAG_KNOWLEDGE_DIRS")))
        self.knowledge_dirs = _dedupe_paths(paths)
        self.knowledge_dir = self.knowledge_dirs[0]  # backward-compatible attribute
        self.top_k = top_k if top_k is not None else _env_int("FORGE_RAG_TOP_K", 3, minimum=1)
        self.max_section_chars = (
            max_section_chars
            if max_section_chars is not None
            else _env_int("FORGE_RAG_MAX_SECTION_CHARS", 1200, minimum=200)
        )
        self.max_context_chars = (
            max_context_chars
            if max_context_chars is not None
            else _env_int("FORGE_RAG_MAX_CONTEXT_CHARS", 3600, minimum=500)
        )
        self._sections: list[KnowledgeSection] | None = None

    @classmethod
    def for_scenario(cls, scenario: str, **kwargs) -> "RuleExplainer":
        name = getattr(scenario, "value", str(scenario))
        extra_dirs = list(kwargs.pop("knowledge_dirs", []))
        return cls(
            knowledge_dirs=[
                KNOWLEDGE_DIR,
                SCENARIO_DIR / name / "knowledge",
                *extra_dirs,
            ],
            **kwargs,
        )

    @property
    def sections(self) -> list[KnowledgeSection]:
        if self._sections is None:
            self._sections = []
            for knowledge_dir in self.knowledge_dirs:
                self._sections.extend(_load_sections(knowledge_dir))
            if not self._sections:
                joined = "；".join(str(p) for p in self.knowledge_dirs)
                log.warning("知识库为空：%s（规则卡将无 citation）", joined)
        return self._sections

    # ------------------------------------------------------------ RAG-lite 检索
    def _keywords(self, rule: Rule, context: str = "") -> list[str]:
        """从规则与上下文提取检索关键词（字段名 / 公式 token / 类别中文）."""
        kind_zh = {
            "implication": "蕴含", "identity": "恒等式", "bound": "上下界",
            "exclusion": "排除", "range": "范围", "ratio": "比率",
        }.get(rule.kind, rule.kind)
        formula_text = json.dumps(rule.formula, ensure_ascii=False, sort_keys=True)
        blob = f"{rule.rule_id} {rule.text} {rule.kind} {context} {formula_text}"
        tokens = re.split(r"[^0-9A-Za-z_\u4e00-\u9fff]+", blob)
        kws = [t for t in tokens if len(t) >= 2]
        if kind_zh:
            kws.append(kind_zh)
        # 财务字段 → 中文同义词，提升中文知识库命中率
        zh_alias = {
            "Inventory": "存货", "COGS": "营业成本", "Purchases": "采购",
            "GrossProfit": "毛利", "Revenue": "营业收入", "TotalAssets": "资产",
            "TotalLiabilities": "负债", "TotalEquity": "权益", "Cash": "现金",
            "AccountsReceivable": "应收", "Proto": "协议", "Flags": "Flags",
            "Packets": "Packets", "Bytes": "Bytes", "Pt": "端口", "DNS": "DNS",
        }
        lowered = blob.lower()
        for en, zh in zh_alias.items():
            if en.lower() in lowered:
                kws.append(zh)
        return kws

    def _score_section(self, sec: KnowledgeSection, keywords: set[str]) -> int:
        heading = sec.heading.lower()
        body = sec.body.lower()
        title = sec.doc_title.lower()
        tags = " ".join(sec.tags).lower()
        source = sec.source.lower()
        score = 0
        for kw in keywords:
            key = kw.lower()
            if not key:
                continue
            if key in heading:
                score += 8 * heading.count(key)
            if key in title:
                score += 4 * title.count(key)
            if key in tags:
                score += 6 * tags.count(key)
            if key in source:
                score += 2 * source.count(key)
            if key in body:
                score += body.count(key)
        return score

    def retrieve(self, rule: Rule, context: str = "", k: int | None = None) -> list[KnowledgeSection]:
        """关键词/标签加权打分，返回最相关的知识库小节."""
        limit = self.top_k if k is None else k
        if limit <= 0:
            return []
        kws = set(self._keywords(rule, context))
        scored: list[tuple[int, int, KnowledgeSection]] = []
        for i, sec in enumerate(self.sections):
            score = self._score_section(sec, kws)
            if score > 0:
                scored.append((score, i, sec))
        scored.sort(key=lambda row: (-row[0], row[1]))  # 同分时取靠前小节，确定性
        return [sec for _, _, sec in scored[:limit]]

    # ------------------------------------------------------------ prompt 构造
    @staticmethod
    def _clip(text: str, max_chars: int) -> str:
        if len(text) <= max_chars:
            return text
        return text[:max_chars].rstrip() + "\n..."

    def _knowledge_block(self, sections: list[KnowledgeSection]) -> str:
        if not sections:
            return "（知识库未命中相关段落）"
        blocks: list[str] = []
        used = 0
        for sec in sections:
            body = self._clip(sec.body, self.max_section_chars)
            source = f"\n来源：{sec.source}" if sec.source else ""
            tags = f"\n标签：{', '.join(sec.tags)}" if sec.tags else ""
            block = f"【知识选段 · {sec.citation}】{source}{tags}\n{body}"
            remaining = self.max_context_chars - used
            if remaining <= 0:
                break
            if len(block) > remaining:
                block = self._clip(block, remaining)
            blocks.append(block)
            used += len(block)
        return "\n\n".join(blocks) if blocks else "（知识库未命中相关段落）"

    def build_prompt(self, rule: Rule, context: str = "") -> str:
        """构造规则卡解释 prompt：英文控制，最终输出简体中文。"""
        knowledge = self._knowledge_block(self.retrieve(rule, context))
        return (
            "You edit audit/compliance rule cards. Plan in English silently; "
            "final answer must be Simplified Chinese only.\n\n"
            f"Rule ID: {rule.rule_id}\n"
            f"Rule formula/display: {rule.text}\n"
            f"Rule kind: {rule.kind or 'unknown'}\n"
            f"Rule source: {'learned from data' if rule.source == 'learned' else 'manual/domain rule'}\n"
            f"Support: {rule.support if rule.support is not None else 'unknown'}\n"
            + (f"Business context: {context}\n" if context else "")
            + f"\nRetrieved evidence:\n{knowledge}\n\n"
            "Output requirements:\n"
            "- Simplified Chinese only.\n"
            "- 2 to 4 short business-facing sentences.\n"
            "- Explain rule meaning and violation impact.\n"
            "- No markdown, English labels, or preface.\n"
            "- If it looks like sampling coincidence, append: 【疑似巧合】."
        )

    # ------------------------------------------------------------ 卡片增强
    def enhance(self, cards: list[RuleCard], ruleset: RuleSet,
                llm=None, context: str = "",
                max_llm_cards: int | None = None) -> list[RuleCard]:
        """对 engine.explain 产出的规则卡做 RAG 增强（就地修改并返回）.

        - 有真实 LLM：build_prompt → llm.complete(role="explain") 润色解释；
          MockBackend 回复（以 "[mock:" 开头）视为降级，保留模板解释；
        - 无论是否润色，都回填 citation（知识库出处），并跑 filter_coincidence。
        """
        rules_by_id = {r.rule_id: r for r in ruleset.rules}
        llm_calls = 0
        for card in cards:
            rule = rules_by_id.get(card.rule_id)
            if rule is None:
                continue
            secs = self.retrieve(rule, context)
            if secs and not card.citation:
                card.citation = "；".join(s.citation for s in secs)
            if llm is None:
                continue
            if max_llm_cards is not None and llm_calls >= max_llm_cards:
                continue
            try:
                llm_calls += 1
                text = llm.complete(self.build_prompt(rule, context),
                                    role="explain",
                                    system=(
                                        "Follow the requested output format exactly. "
                                        "The final answer must be Simplified Chinese only."
                                    )).strip()
            except Exception as exc:
                log.warning("LLM 增强失败（%s），保留模板解释", exc)
                continue
            if not text or text.startswith("[mock:"):
                continue  # mock 降级：保持确定性模板解释
            if "疑似巧合" in text:
                card.is_coincidence = True
                text = text.replace("【疑似巧合】", "").strip()
            if text:
                card.explanation_zh = text
        return self.filter_coincidence(cards, ruleset)

    # ------------------------------------------------------------ 巧合过滤
    def filter_coincidence(self, cards: list[RuleCard],
                           ruleset: RuleSet | None = None) -> list[RuleCard]:
        """启发式标记疑似巧合规则（就地修改并返回）.

        判定条件（任一命中即标记）：
        1. support 极低（< LOW_SUPPORT_THRESHOLD）；
        2. 公式含"过于具体"的常量（不在 COMMON_CONSTANTS 白名单、且非小整数）
           且 support < COINCIDENCE_SUPPORT_THRESHOLD。
        人工规则（source="manual"）永不标记——专家注入视为领域共识。
        """
        rules_by_id = {r.rule_id: r for r in (ruleset.rules if ruleset else [])}
        for card in cards:
            rule = rules_by_id.get(card.rule_id)
            if rule is None or rule.source == "manual":
                continue
            sup = rule.support
            suspicious = False
            if sup is not None and sup < LOW_SUPPORT_THRESHOLD:
                suspicious = True
            else:
                consts = _collect_constants(rule.formula)
                odd = [c for c in consts
                       if c not in COMMON_CONSTANTS and abs(c) > 10]
                if odd and sup is not None and sup < COINCIDENCE_SUPPORT_THRESHOLD:
                    suspicious = True
            if suspicious and not card.is_coincidence:
                card.is_coincidence = True
                if "疑似巧合" not in card.tags:
                    card.tags.append("疑似巧合")
        return cards
