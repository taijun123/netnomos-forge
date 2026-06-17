# -*- coding: utf-8 -*-
"""forge.core.llm — LLM 路由客户端（实现 contracts.LLMClient 协议）.

三后端：
- OllamaBackend：HTTP 调本地 ollama（http://localhost:11434/api/generate），
  model/options 取自 contracts.DEFAULT_LLM_ROUTING；
- CodexBackend：subprocess 调 ``codex exec`` 命令行（带超时保护）；
- MockBackend：确定性模板回复，沙箱/单测专用，零外部依赖。

RoutedLLM 按角色（induce/draft/explain）路由；默认运行时策略为 Ollama
优先（不修改 contracts.py 的冻结契约），Ollama 不通时自动降级 mock。Codex CLI
后端需显式设置 FORGE_ENABLE_CODEX_BACKEND=1 才参与降级链。
"""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
from typing import Any

from forge.contracts import DEFAULT_LLM_ROUTING, LLMRole

log = logging.getLogger("forge.core.llm")

# 后端不可用时的降级顺序（mock 永远可用，作为兜底）
_FALLBACK_ORDER = ["ollama", "codex", "mock"]


def _env_truthy(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _ollama_first_routing() -> dict[str, dict[str, Any]]:
    """Return a runtime routing overlay that keeps contracts.py immutable."""
    routing = {role: dict(spec) for role, spec in DEFAULT_LLM_ROUTING.items()}
    draft_route = routing.get("draft", {})
    draft_model = os.getenv(
        "FORGE_OLLAMA_DRAFT_MODEL",
        draft_route.get("model", "qwen2.5:14b-instruct"),
    )
    draft_route["model"] = draft_model
    explain = routing.setdefault("explain", {})
    explain_model = os.getenv("FORGE_OLLAMA_EXPLAIN_MODEL", "gemma3:27b")
    explain.update({
        "backend": "ollama",
        "model": explain_model,
        "options": explain.get("options") or {
            "temperature": 0.15,
            "seed": 11,
            "num_ctx": 8192,
            "num_predict": 360,
        },
    })
    return routing


class MockBackend:
    """确定性模板后端：相同输入永远产生相同输出（沙箱/测试用）."""

    name = "mock"

    def available(self) -> bool:  # mock 永远可用
        return True

    def complete(self, prompt: str, role: str, system: str | None = None,
                 model: str = "mock", options: dict[str, Any] | None = None) -> str:
        head = prompt.strip().splitlines()[0][:120] if prompt.strip() else ""
        sys_note = f"；system 长度 {len(system)}" if system else ""
        return f"[mock:{role}] 确定性回复（输入摘要：{head}{sys_note}）"


class OllamaBackend:
    """本地 ollama HTTP 后端."""

    name = "ollama"

    def __init__(self, host: str = "http://localhost:11434", timeout: float | None = None,
                 probe_timeout: float | None = None,
                 autostart: bool = False):
        self.host = host.rstrip("/")
        self.timeout = timeout or float(os.getenv("FORGE_OLLAMA_TIMEOUT", "120"))
        self.probe_timeout = probe_timeout or float(os.getenv("FORGE_OLLAMA_PROBE_TIMEOUT", "2"))
        self.autostart = autostart
        raw_keep_alive = os.getenv("FORGE_OLLAMA_KEEP_ALIVE", "0").strip()
        self.keep_alive: int | str = int(raw_keep_alive) if raw_keep_alive.isdigit() else raw_keep_alive
        self._available: bool | None = None  # 探测结果缓存

    def available(self) -> bool:
        if self._available is None:
            try:
                import requests
                resp = requests.get(f"{self.host}/api/tags", timeout=self.probe_timeout)
                self._available = resp.status_code == 200
            except Exception:
                self._available = False
            if not self._available and self.autostart:
                try:
                    from forge.utils.ollama_lifecycle import ensure_ollama_running  # noqa: PLC0415

                    ensure_ollama_running(self.host)
                    import requests
                    resp = requests.get(f"{self.host}/api/tags", timeout=self.probe_timeout)
                    self._available = resp.status_code == 200
                except Exception:
                    self._available = False
        return self._available

    def complete(self, prompt: str, role: str, system: str | None = None,
                 model: str = "qwen2.5:14b-instruct",
                 options: dict[str, Any] | None = None) -> str:
        import requests
        if str(role) == "explain":
            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})
            payload = {
                "model": model,
                "messages": messages,
                "stream": False,
                "keep_alive": self.keep_alive,
                "options": options or {},
            }
            resp = requests.post(f"{self.host}/api/chat", json=payload, timeout=self.timeout)
            resp.raise_for_status()
            return str(resp.json().get("message", {}).get("content", ""))
        payload: dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "keep_alive": self.keep_alive,
            "options": options or {},
        }
        if system:
            payload["system"] = system
        resp = requests.post(f"{self.host}/api/generate", json=payload, timeout=self.timeout)
        resp.raise_for_status()
        return str(resp.json().get("response", ""))


class CodexBackend:
    """codex CLI 后端：``codex exec <prompt>``，带超时保护."""

    name = "codex"

    def __init__(self, binary: str = "codex", timeout: float = 180.0):
        self.binary = binary
        self.timeout = timeout
        self._available: bool | None = None

    def available(self) -> bool:
        if self._available is None:
            self._available = (
                _env_truthy("FORGE_ENABLE_CODEX_BACKEND")
                and shutil.which(self.binary) is not None
            )
        return self._available

    def complete(self, prompt: str, role: str, system: str | None = None,
                 model: str = "default", options: dict[str, Any] | None = None) -> str:
        full_prompt = f"{system}\n\n{prompt}" if system else prompt
        try:
            proc = subprocess.run(
                [self.binary, "exec", full_prompt],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self.timeout,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(f"codex exec 超时（>{self.timeout}s），请检查 codex CLI 状态") from exc
        if proc.returncode != 0:
            raise RuntimeError(f"codex exec 退出码 {proc.returncode}：{proc.stderr[:500]}")
        return (proc.stdout or "").strip()


class RoutedLLM:
    """按角色路由的 LLM 客户端（contracts.LLMClient 实现）.

    用法::

        llm = RoutedLLM()                      # 自动探测，默认优先 ollama，沙箱降级 mock
        llm = RoutedLLM(force_backend="mock")  # 强制 mock（确定性，测试用）
        text = llm.complete("解释这条规则", role="explain")
    """

    def __init__(self, routing: dict[str, dict[str, Any]] | None = None,
                 force_backend: str | None = None,
                 ollama_host: str | None = None,
                 backends: dict[str, Any] | None = None,
                 ollama_autostart: bool = False):
        self.routing = routing or _ollama_first_routing()
        self.force_backend = force_backend
        resolved_ollama_host = (
            ollama_host
            or os.getenv("FORGE_OLLAMA_HOST")
            or os.getenv("OLLAMA_HOST")
            or "http://localhost:11434"
        )
        # backends 参数允许测试注入桩后端
        self.backends: dict[str, Any] = backends or {
            "ollama": OllamaBackend(host=resolved_ollama_host,
                                     autostart=ollama_autostart),
            "codex": CodexBackend(),
            "mock": MockBackend(),
        }

    # -- 路由 ---------------------------------------------------------------
    def resolve_backend(self, role: LLMRole | str) -> str:
        """返回该角色实际使用的后端名（含自动降级）."""
        if self.force_backend:
            return self.force_backend
        route = self.routing.get(str(role), {})
        preferred = route.get("backend", "mock")
        candidates = [preferred] + [b for b in _FALLBACK_ORDER if b != preferred]
        for name in candidates:
            backend = self.backends.get(name)
            if backend is not None and backend.available():
                if name != preferred:
                    log.warning("LLM 角色 %s 首选后端 %s 不可用，自动降级为 %s",
                                role, preferred, name)
                return name
        return "mock"  # 理论上不可达：mock 永远可用

    # -- contracts.LLMClient ------------------------------------------------
    def complete(self, prompt: str, role: LLMRole, system: str | None = None) -> str:
        route = self.routing.get(str(role), {})
        name = self.resolve_backend(role)
        backend = self.backends[name]
        model = route.get("model", "default")
        options = route.get("options", {})
        try:
            return backend.complete(prompt, role=str(role), system=system,
                                    model=model, options=options)
        except Exception as exc:
            if name == "mock":
                raise
            # 真实后端运行期失败（超时/网络抖动）→ 再降一级到 mock，保证调用方拿到结果
            log.warning("LLM 后端 %s 调用失败（%s），降级为 mock", name, exc)
            return self.backends["mock"].complete(prompt, role=str(role), system=system)
