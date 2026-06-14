# -*- coding: utf-8 -*-
"""forge.core.generator — ConstrainedGenerator（实现 contracts.GeneratorAPI）.

封装仓库内 LeJIT 源码目录的受约束行生成：
- train()：优先走 Python API（lejit.config.LeJITConfig + lejit.pipeline.LeJITPipeline，
  与 lejit/cli.py 完全相同的入口），lejit/torch 不可导入时降级为
  ``uv run lejit train --config ... --output ...`` 子进程（在 LeJIT 仓库目录执行）；
- generate()/complete()：封装 LeJITPipeline.generate/complete，输出 list[dict]。

沙箱内没有 torch/transformers，因此全部懒加载；两条路都失败时抛带中文指引的
RuntimeError（宿主机脚本见 scripts/host/train_network_lejit.ps1、generate_network.ps1）。
"""
from __future__ import annotations

import json
import logging
import shutil
import subprocess
from pathlib import Path
from typing import Any

from forge.contracts import RuleSet, Scenario, SCENARIO_DIR

log = logging.getLogger("forge.core.generator")

# 目录约定：LeJIT 随本仓库放在 netnomos-forge/LeJIT
FORGE_ROOT = Path(__file__).resolve().parents[2]          # netnomos-forge/
RULESETS_DIR = FORGE_ROOT / "forge" / "rulesets"
LEJIT_DIR = FORGE_ROOT / "LeJIT"

# 子进程训练超时（秒）；CPU 小模型 3 epoch 量级，宿主机 GPU 远快于此
SUBPROCESS_TIMEOUT = 60 * 60

_LEJIT_HINT = (
    "无法运行 LeJIT：Python API（lejit/torch/transformers）不可导入，且 `uv run lejit` "
    "子进程不可用。沙箱无外网 pip，无法安装 torch，请在宿主机操作：\n"
    "  1. cd <workspace>/netnomos-forge/LeJIT && uv sync\n"
    "  2. 执行 scripts/host/train_network_lejit.ps1 训练，"
    "scripts/host/generate_network.ps1 生成；\n"
    "  3. 或在宿主机 Python 中直接调用 ConstrainedGenerator.train(...)。"
)


def _scenario_name(scenario: str | Scenario) -> str:
    return scenario.value if isinstance(scenario, Scenario) else str(scenario)


def _dump_toml(payload: dict[str, Any]) -> str:
    """极简 TOML 序列化（只支持本模块用到的标量/列表/嵌套表结构）."""

    def fmt(value: Any) -> str:
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, (int, float)):
            return repr(value)
        if isinstance(value, str):
            return json.dumps(value)  # TOML 基本字符串与 JSON 兼容
        if isinstance(value, list):
            return "[" + ", ".join(fmt(v) for v in value) + "]"
        raise TypeError(f"无法序列化为 TOML: {type(value)!r}")

    lines: list[str] = []

    def walk(table: dict[str, Any], prefix: str) -> None:
        scalars = {k: v for k, v in table.items() if not isinstance(v, dict) and v is not None}
        subtables = {k: v for k, v in table.items() if isinstance(v, dict)}
        if prefix and scalars:
            lines.append(f"[{prefix}]")
        for key, value in scalars.items():
            lines.append(f"{key} = {fmt(value)}")
        if scalars:
            lines.append("")
        for key, value in subtables.items():
            walk(value, f"{prefix}.{key}" if prefix else key)

    walk(payload, "")
    return "\n".join(lines) + "\n"


class ConstrainedGenerator:
    """contracts.GeneratorAPI 实现：基于 LeJIT bundle 的受约束生成器."""

    def __init__(self, scenario: str, bundle_dir: str | Path,
                 device: str = "cpu", pipeline: Any = None,
                 n_samples_default: int = 10):
        self.scenario = scenario
        self.bundle_dir = Path(bundle_dir)
        self.device = device
        self._pipeline = pipeline           # 懒加载的 LeJITPipeline
        self.n_samples_default = n_samples_default

    # -- 配置构造 -------------------------------------------------------------
    @staticmethod
    def build_config_payload(scenario: str | Scenario, rules: RuleSet,
                             base_model: str | None = None, **kw) -> dict[str, Any]:
        """组装 LeJITConfig 等价的 dict（全部绝对路径，避免 cwd 歧义）.

        kw 透传项：epochs/batch_size/learning_rate/seed → training；
        n_samples/samples_per_prompt → run；temperature/top_p → decoding；
        limit → dataset。
        """
        name = _scenario_name(scenario)
        scen_dir = SCENARIO_DIR / name
        dataset_spec = scen_dir / "dataset_spec.json"
        if not dataset_spec.exists():
            raise FileNotFoundError(f"场景 {name} 缺少 dataset_spec.json：{dataset_spec}")
        if not rules.rules_path or not Path(rules.rules_path).exists():
            raise FileNotFoundError(
                "RuleSet.rules_path 为空或文件不存在：LeJIT 需要 NetNomos 格式 rules.json，"
                "请先用 ForgeRuleEngine.learn() 或 engine.save_ruleset() 落盘")
        # 数据路径：按 dataset_spec.json 所在目录解析相对 source.path（与 engine 一致）
        spec_payload = json.loads(dataset_spec.read_text(encoding="utf-8"))
        raw = (spec_payload.get("source") or {}).get("path")
        input_path = None
        if raw:
            p = Path(raw)
            input_path = str(p if p.is_absolute() else (scen_dir / p).resolve())
        model: dict[str, Any] = (
            {"mode": "pretrained", "architecture": "gpt2", "name_or_path": base_model}
            if base_model else
            {"mode": "config", "architecture": "gpt2",
             "config_overrides": {"n_positions": 512, "n_ctx": 512,
                                  "n_embd": 256, "n_layer": 6, "n_head": 8}}
        )
        training = {"epochs": kw.get("epochs", 3), "batch_size": kw.get("batch_size", 16),
                    "learning_rate": kw.get("learning_rate", 5e-4),
                    "seed": kw.get("seed", 42), "logging_steps": 10, "save_steps": 100}
        return {
            "dataset": {
                "dataset_spec": str(dataset_spec.resolve()),
                "input_path": input_path,
                "rules_path": str(Path(rules.rules_path).resolve()),
                "limit": kw.get("limit"),
            },
            "model": model,
            "serialization": {"numeric_precision": 6},
            "training": training,
            "decoding": {"temperature": kw.get("temperature", 1.0),
                         "do_sample": True,
                         **({"top_p": kw["top_p"]} if "top_p" in kw else {})},
            "run": {"n_samples": kw.get("n_samples", 100), "batch_size": 1,
                    "samples_per_prompt": kw.get("samples_per_prompt", 1)},
        }

    # -- GeneratorAPI ----------------------------------------------------------
    @classmethod
    def train(cls, scenario: str | Scenario, rules: RuleSet,
              base_model: str | None = None, **kw) -> "ConstrainedGenerator":
        """训练 LeJIT bundle → forge/rulesets/<scenario>/lejit_bundle/.

        路径一：lejit Python API（首选）；路径二：``uv run lejit train`` 子进程。
        """
        name = _scenario_name(scenario)
        bundle_dir = Path(kw.pop("bundle_dir", RULESETS_DIR / name / "lejit_bundle"))
        device = kw.pop("device", "cpu")
        payload = cls.build_config_payload(name, rules, base_model=base_model, **kw)
        bundle_dir.parent.mkdir(parents=True, exist_ok=True)

        # 路径一：Python API（与 lejit/cli.py train 分支一致）
        try:
            from lejit.config import LeJITConfig      # noqa: PLC0415
            from lejit.pipeline import LeJITPipeline  # noqa: PLC0415
        except Exception as exc:
            log.warning("lejit Python API 不可导入（%s），尝试 uv 子进程", exc)
        else:
            config = LeJITConfig.model_validate(payload)
            pipeline = LeJITPipeline.build_from_config(config)  # 路径已绝对化，无需 base_dir
            pipeline.train(bundle_dir)
            log.info("LeJIT 训练完成（Python API）→ %s", bundle_dir)
            return cls(name, bundle_dir, device=device, pipeline=pipeline,
                       n_samples_default=payload["run"]["n_samples"])

        # 路径二：uv 子进程（在 LeJIT 仓库目录执行，保证依赖环境正确）
        return cls._train_via_subprocess(name, payload, bundle_dir, device)

    @classmethod
    def _train_via_subprocess(cls, name: str, payload: dict[str, Any],
                              bundle_dir: Path, device: str) -> "ConstrainedGenerator":
        if shutil.which("uv") is None or not LEJIT_DIR.exists():
            raise RuntimeError(_LEJIT_HINT)
        config_path = bundle_dir.parent / "lejit_train.toml"
        config_path.write_text(_dump_toml(payload), encoding="utf-8")
        cmd = ["uv", "run", "lejit", "train",
               "--config", str(config_path), "--output", str(bundle_dir)]
        log.info("LeJIT 子进程训练：%s（cwd=%s）", " ".join(cmd), LEJIT_DIR)
        try:
            proc = subprocess.run(cmd, cwd=LEJIT_DIR, capture_output=True,
                                  text=True, encoding="utf-8", errors="replace",
                                  timeout=SUBPROCESS_TIMEOUT)
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(f"LeJIT 训练子进程超时（>{SUBPROCESS_TIMEOUT}s）") from exc
        if proc.returncode != 0:
            raise RuntimeError(
                f"LeJIT 训练子进程失败（退出码 {proc.returncode}）：\n"
                f"{proc.stderr[-1000:]}\n{_LEJIT_HINT}")
        return cls(name, bundle_dir, device=device,
                   n_samples_default=payload["run"]["n_samples"])

    @classmethod
    def from_bundle(cls, scenario: str | Scenario,
                    bundle_dir: str | Path | None = None,
                    device: str = "cpu") -> "ConstrainedGenerator":
        """加载已训练 bundle（不重训）."""
        name = _scenario_name(scenario)
        bundle_dir = Path(bundle_dir or RULESETS_DIR / name / "lejit_bundle")
        if not bundle_dir.exists():
            raise FileNotFoundError(
                f"LeJIT bundle 不存在：{bundle_dir}，请先 train()"
                f"（宿主机可执行 scripts/host/train_network_lejit.ps1）")
        return cls(name, bundle_dir, device=device)

    def _get_pipeline(self):
        if self._pipeline is None:
            try:
                from lejit.pipeline import LeJITPipeline  # noqa: PLC0415
            except Exception as exc:
                raise RuntimeError(_LEJIT_HINT) from exc
            if not self.bundle_dir.exists():
                raise FileNotFoundError(
                    f"LeJIT bundle 不存在：{self.bundle_dir}，请先 train()")
            self._pipeline = LeJITPipeline.load(self.bundle_dir, device=self.device)
        return self._pipeline

    def generate(self, n: int = 10) -> list[dict[str, Any]]:
        """生成 n 行满足规则约束的合成数据."""
        frame = self._get_pipeline().generate(n_samples=n, device=self.device)
        return frame.to_dict(orient="records")

    def complete(self, prefixes: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """按给定前缀字段补全整行（每个前缀补一行）."""
        import pandas as pd  # noqa: PLC0415
        prompts = pd.DataFrame(prefixes)
        frame = self._get_pipeline().complete(prompts, samples_per_prompt=1,
                                              device=self.device)
        return frame.to_dict(orient="records")
