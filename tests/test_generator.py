# -*- coding: utf-8 -*-
"""forge.core.generator 单元测试（LeJIT 懒加载；沙箱无 torch，重活全部跳过/打桩）."""
from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest

try:  # Python 3.11+ 才有 tomllib；沙箱 3.10 降级为纯文本断言
    import tomllib
except ImportError:  # pragma: no cover
    tomllib = None
from pathlib import Path
from unittest import mock

from forge.contracts import Rule, RuleSet
from forge.core.generator import ConstrainedGenerator, _dump_toml

HAS_LEJIT = bool(importlib.util.find_spec("lejit") and importlib.util.find_spec("torch"))

FORMULA = {"kind": "compare", "op": "<=",
           "left": {"kind": "symbol", "name": "Bytes"},
           "right": {"kind": "constant", "value": 1500}}


def make_ruleset(rules_path: str | None = None) -> RuleSet:
    return RuleSet(scenario="network_cidds", rules=[
        Rule(rule_id="N001", formula=FORMULA, text="Bytes <= 1500", kind="bound"),
    ], rules_path=rules_path)


class TestDumpToml(unittest.TestCase):
    PAYLOAD = {
        "dataset": {"dataset_spec": "C:/a b/spec.json", "rules_path": "/r.json"},
        "model": {"mode": "config", "architecture": "gpt2",
                  "config_overrides": {"n_layer": 6, "n_embd": 256}},
        "training": {"epochs": 3, "learning_rate": 5e-4, "seed": 42},
        "decoding": {"temperature": 1.0, "do_sample": True},
        "run": {"n_samples": 100},
    }

    def test_text_structure(self):
        text = _dump_toml(self.PAYLOAD)
        self.assertIn("[dataset]", text)
        self.assertIn('dataset_spec = "C:/a b/spec.json"', text)
        self.assertIn("[model.config_overrides]", text)
        self.assertIn("n_layer = 6", text)
        self.assertIn("do_sample = true", text)

    @unittest.skipUnless(tomllib, "需要 Python 3.11+ 的 tomllib 才能解析回读")
    def test_roundtrip_via_tomllib(self):
        parsed = tomllib.loads(_dump_toml(self.PAYLOAD))
        self.assertEqual(parsed["dataset"]["dataset_spec"], "C:/a b/spec.json")
        self.assertEqual(parsed["model"]["config_overrides"]["n_layer"], 6)
        self.assertIs(parsed["decoding"]["do_sample"], True)
        self.assertAlmostEqual(parsed["training"]["learning_rate"], 5e-4)

    def test_none_values_skipped(self):
        text = _dump_toml({"dataset": {"limit": None, "x": 1}})
        self.assertNotIn("limit", text)
        self.assertIn("x = 1", text)


class TestBuildConfigPayload(unittest.TestCase):
    def test_missing_rules_path_raises(self):
        with self.assertRaises(FileNotFoundError) as ctx:
            ConstrainedGenerator.build_config_payload("network_cidds", make_ruleset(None))
        self.assertIn("rules_path", str(ctx.exception))

    def test_payload_paths_absolute(self):
        with tempfile.TemporaryDirectory() as tmp:
            rules_json = Path(tmp) / "rules.json"
            rules_json.write_text(json.dumps([{"rule_id": "N001", "formula": FORMULA,
                                               "display": "Bytes <= 1500",
                                               "support": 1.0, "source": {}}]),
                                  encoding="utf-8")
            payload = ConstrainedGenerator.build_config_payload(
                "network_cidds", make_ruleset(str(rules_json)),
                epochs=1, n_samples=5)
        ds = payload["dataset"]
        self.assertTrue(Path(ds["dataset_spec"]).is_absolute())
        self.assertTrue(Path(ds["rules_path"]).is_absolute())
        self.assertTrue(Path(ds["input_path"]).is_absolute())
        self.assertTrue(ds["input_path"].endswith("cidds_wk2_normal_10k.csv"))
        self.assertEqual(payload["training"]["epochs"], 1)
        self.assertEqual(payload["run"]["n_samples"], 5)
        # 默认从零训练小 GPT-2
        self.assertEqual(payload["model"]["mode"], "config")

    def test_base_model_switches_to_pretrained(self):
        with tempfile.TemporaryDirectory() as tmp:
            rules_json = Path(tmp) / "rules.json"
            rules_json.write_text("[]", encoding="utf-8")
            payload = ConstrainedGenerator.build_config_payload(
                "network_cidds", make_ruleset(str(rules_json)), base_model="gpt2-medium")
        self.assertEqual(payload["model"]["mode"], "pretrained")
        self.assertEqual(payload["model"]["name_or_path"], "gpt2-medium")


class TestTrainFallbacks(unittest.TestCase):
    @unittest.skipIf(HAS_LEJIT, "宿主机已装 lejit，缺依赖报错路径不适用")
    def test_train_without_lejit_and_uv_raises_with_hint(self):
        """Python API 不可导入且 uv 不可用 → 中文指引 RuntimeError."""
        with tempfile.TemporaryDirectory() as tmp:
            rules_json = Path(tmp) / "rules.json"
            rules_json.write_text("[]", encoding="utf-8")
            with mock.patch("forge.core.generator.shutil.which", return_value=None):
                with self.assertRaises(RuntimeError) as ctx:
                    ConstrainedGenerator.train("network_cidds", make_ruleset(str(rules_json)),
                                               bundle_dir=Path(tmp) / "bundle")
        msg = str(ctx.exception)
        self.assertIn("uv sync", msg)
        self.assertIn("LeJIT", msg)

    def test_from_bundle_missing_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(FileNotFoundError) as ctx:
                ConstrainedGenerator.from_bundle("network_cidds",
                                                 bundle_dir=Path(tmp) / "nope")
        self.assertIn("train", str(ctx.exception))

    def test_generate_without_pipeline_raises_friendly(self):
        gen = ConstrainedGenerator("network_cidds", bundle_dir="/no/such/bundle")
        with self.assertRaises((RuntimeError, FileNotFoundError)):
            gen.generate(3)


@unittest.skipUnless(HAS_LEJIT, "需要 lejit + torch（宿主机 uv sync 后执行）")
class TestGeneratorEndToEnd(unittest.TestCase):
    """宿主机端到端：极小训练 + 生成（沙箱自动跳过）."""

    def test_train_generate_complete(self):
        golden = Path(__file__).resolve().parents[1] / "forge" / "rulesets" / \
            "network_cidds" / "golden" / "rules.json"
        if not golden.exists():
            self.skipTest("缺少黄金规则集，请先运行 scripts/host/run_network_learn.ps1")
        with tempfile.TemporaryDirectory() as tmp:
            gen = ConstrainedGenerator.train(
                "network_cidds", make_ruleset(str(golden)),
                bundle_dir=Path(tmp) / "bundle", epochs=1, limit=200, n_samples=3)
            rows = gen.generate(3)
            self.assertEqual(len(rows), 3)
            self.assertIsInstance(rows[0], dict)
            completed = gen.complete([{k: v for k, v in list(rows[0].items())[:2]}])
            self.assertGreaterEqual(len(completed), 1)


if __name__ == "__main__":
    unittest.main()
