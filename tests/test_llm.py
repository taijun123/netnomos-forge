# -*- coding: utf-8 -*-
"""forge.core.llm 单元测试（纯 stdlib，沙箱可跑）."""
from __future__ import annotations

import unittest
from unittest.mock import patch

from forge.core.llm import CodexBackend, MockBackend, OllamaBackend, RoutedLLM


class _StubBackend:
    """测试桩：可控的可用性与行为."""

    def __init__(self, name: str, is_available: bool, reply: str | None = None,
                 raise_on_call: bool = False):
        self.name = name
        self._is_available = is_available
        self.reply = reply or f"[{name}] reply"
        self.raise_on_call = raise_on_call
        self.calls: list[dict] = []

    def available(self) -> bool:
        return self._is_available

    def complete(self, prompt, role, system=None, model="m", options=None):
        self.calls.append({"prompt": prompt, "role": role, "model": model,
                           "options": options})
        if self.raise_on_call:
            raise RuntimeError("boom")
        return self.reply


class TestMockBackend(unittest.TestCase):
    def test_deterministic(self):
        mock = MockBackend()
        a = mock.complete("解释规则 Proto=UDP -> Flags=noflags", role="explain")
        b = mock.complete("解释规则 Proto=UDP -> Flags=noflags", role="explain")
        self.assertEqual(a, b)
        self.assertIn("[mock:explain]", a)

    def test_always_available(self):
        self.assertTrue(MockBackend().available())


class TestRoutedLLM(unittest.TestCase):
    def test_force_mock(self):
        llm = RoutedLLM(force_backend="mock")
        out = llm.complete("你好", role="draft")
        self.assertIn("[mock:draft]", out)

    def test_routing_uses_contract_model_and_options(self):
        """induce 角色应取 DEFAULT_LLM_ROUTING 的 model/options 调 ollama."""
        ollama = _StubBackend("ollama", is_available=True)
        llm = RoutedLLM(backends={"ollama": ollama, "codex": _StubBackend("codex", False),
                                  "mock": MockBackend()})
        llm.complete("诱骗提示词", role="induce")
        self.assertEqual(len(ollama.calls), 1)
        self.assertEqual(ollama.calls[0]["model"], "qwen2.5:14b-instruct")
        self.assertEqual(ollama.calls[0]["options"], {"temperature": 0.2, "seed": 42})

    def test_explain_defaults_to_ollama(self):
        """运行时默认路由：规则解释也优先走本地 ollama，不走 codex。"""
        ollama = _StubBackend("ollama", is_available=True)
        codex = _StubBackend("codex", is_available=True)
        llm = RoutedLLM(backends={"ollama": ollama, "codex": codex,
                                  "mock": MockBackend()})
        llm.complete("解释 Proto=UDP -> Flags=noflags", role="explain")
        self.assertEqual(len(ollama.calls), 1)
        self.assertEqual(len(codex.calls), 0)
        self.assertEqual(ollama.calls[0]["model"], "gemma3:27b")
        self.assertEqual(ollama.calls[0]["options"], {
            "temperature": 0.15,
            "seed": 11,
            "num_ctx": 8192,
            "num_predict": 360,
        })

    def test_ollama_host_can_come_from_env(self):
        """宿主机 Ollama 地址可由环境变量覆盖，便于远端/非默认端口部署."""
        with patch.dict("os.environ", {"FORGE_OLLAMA_HOST": "http://127.0.0.1:11435"}):
            llm = RoutedLLM()
        self.assertEqual(llm.backends["ollama"].host, "http://127.0.0.1:11435")

    def test_auto_fallback_to_mock_with_log(self):
        """ollama 不通且 codex 不存在 → 自动降级 mock 并打日志."""
        llm = RoutedLLM(backends={
            "ollama": _StubBackend("ollama", is_available=False),
            "codex": _StubBackend("codex", is_available=False),
            "mock": MockBackend(),
        })
        with self.assertLogs("forge.core.llm", level="WARNING") as cm:
            self.assertEqual(llm.resolve_backend("explain"), "mock")
        self.assertTrue(any("降级" in line for line in cm.output))
        out = llm.complete("解释一下", role="explain")
        self.assertIn("[mock:explain]", out)

    def test_runtime_failure_falls_back_to_mock(self):
        """真实后端调用期抛错 → 兜底 mock，调用方仍拿到字符串."""
        llm = RoutedLLM(backends={
            "ollama": _StubBackend("ollama", is_available=True, raise_on_call=True),
            "codex": _StubBackend("codex", is_available=False),
            "mock": MockBackend(),
        })
        out = llm.complete("起草报告", role="draft")
        self.assertIn("[mock:draft]", out)

    def test_real_backend_probes_safely_in_sandbox(self):
        """沙箱内真实探测应安全返回 False/True 而非抛异常."""
        self.assertIsInstance(OllamaBackend(probe_timeout=0.5).available(), bool)
        self.assertIsInstance(CodexBackend().available(), bool)


if __name__ == "__main__":
    unittest.main()
