# -*- coding: utf-8 -*-
"""test_pipeline — 编排管线端到端测试（不起 HTTP，直接调 pipeline 函数）.

覆盖：
- 财务管线端到端（沙箱真实跑通：生成→注入→validate→修正→双轨报告）；
- 事件序列：stage 顺序 / agent 映射符合 contracts.STAGE_AGENT / 首尾 status；
- 网络管线（learn 降级加载 golden 规则文件，B 轨 LeJIT 生成后终检筛选）；
- server.app 在沙箱 import 不炸（create_app 懒加载，无 fastapi 时跳过构造）；
- server.store 的订阅回放与哨兵语义。
"""
from __future__ import annotations

import tempfile
import unittest
from importlib.util import find_spec
from pathlib import Path
from unittest.mock import patch

from forge.contracts import STAGE_AGENT, WorkflowEvent
from server.pipeline import run_finance_pipeline, run_network_pipeline
from server.store import JOB_DONE, JobStore

# 财务管线期望的 stage 推进顺序（首次出现序）
FINANCE_STAGE_ORDER = ["upload", "prepare", "learn", "explain",
                       "validate", "project", "report", "diff"]
NETWORK_STAGE_ORDER = ["upload", "prepare", "learn", "explain", "report", "diff"]


def _first_positions(events: list[WorkflowEvent]) -> dict[str, int]:
    pos: dict[str, int] = {}
    for i, ev in enumerate(events):
        pos.setdefault(ev.stage, i)
    return pos


def _custom_finance_frame(cogs: int = 4321):
    from forge.scenarios.finance_v1.faults import build_clean_package

    df = build_clean_package()
    mask = df["PeriodIndex"].astype(int) == 3
    df.loc[mask, "COGS"] = cogs
    df.loc[mask, "GrossProfit"] = df.loc[mask, "Revenue"].astype(int) - cogs
    df.loc[mask, "InventoryNetInflow"] = df.loc[mask, "Purchases"].astype(int) - cogs
    return df


class TestFinancePipeline(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.events: list[WorkflowEvent] = []
        cls.result = run_finance_pipeline(None, cls.events.append)

    # -- 事件序列 ---------------------------------------------------------------
    def test_event_stage_order(self):
        pos = _first_positions(self.events)
        order = [pos[s] for s in FINANCE_STAGE_ORDER]
        self.assertEqual(order, sorted(order),
                         f"stage 首现顺序错误：{[(e.stage, e.status) for e in self.events]}")

    def test_event_agent_mapping_matches_contracts(self):
        for ev in self.events:
            self.assertIn(ev.stage, STAGE_AGENT)
            self.assertEqual(ev.agent, STAGE_AGENT[ev.stage],
                             f"stage={ev.stage} 的 agent 映射不符")

    def test_event_descriptions_show_processors(self):
        descriptions = "\n".join(ev.description for ev in self.events)
        self.assertIn("stage=learn processor=NetNomos hitting-set/Z3", descriptions)
        self.assertIn("stage=explain processor=RuleExplainer/RAG/gemma3 optional",
                      descriptions)
        self.assertIn("stage=report processor=A轨裸模型+B轨约束", descriptions)

    def test_event_head_tail_status(self):
        self.assertEqual((self.events[0].stage, self.events[0].status),
                         ("control", "running"))
        self.assertEqual((self.events[-1].stage, self.events[-1].status),
                         ("control", "done"))
        # 每个业务 stage 至少有一条 done
        done_stages = {e.stage for e in self.events if e.status == "done"}
        for stage in FINANCE_STAGE_ORDER:
            self.assertIn(stage, done_stages)

    # -- 端到端产物 ---------------------------------------------------------------
    def test_dual_report_track_a_wrong_values(self):
        dual = self.result["dual"]
        self.assertIn("3,000", dual.track_a.markdown)
        self.assertIn('class="err', dual.diff_html)
        self.assertIn("应为 2,000", dual.diff_html)

    def test_dual_report_track_b_corrected(self):
        dual = self.result["dual"]
        slots = dual.track_b.slots
        self.assertEqual(int(str(slots["cogs_corrected"]).replace(",", "")), 2000)
        self.assertTrue(dual.track_b.intervention_log)
        self.assertFalse(any(line.startswith("【终检告警】")
                             for line in dual.track_b.intervention_log))
        self.assertNotIn("{{", dual.track_b.markdown)

    def test_validate_hits_all_faults(self):
        vreport = self.result["vreport"]
        truth = self.result["truth"]
        expected_rules = {f["rule_id"] for f in truth["faults"].values()}
        self.assertTrue(expected_rules.issubset(set(vreport.by_rule)),
                        f"应命中 {expected_rules}，实际 {set(vreport.by_rule)}")

    def test_ruleset_and_cards(self):
        ruleset = self.result["ruleset"]
        ids = {r.rule_id for r in ruleset.rules}
        self.assertTrue({"R01", "R02", "R03", "R04", "R05", "R06", "R07"} <= ids)
        cards = self.result["cards"]
        self.assertEqual(len(cards), len(ruleset.rules))
        # RAG 增强：人工恒等式规则卡带知识库 citation
        r01_card = next(c for c in cards if c.rule_id == "R01")
        self.assertTrue(r01_card.citation)
        self.assertFalse(r01_card.is_coincidence)   # 人工规则不被巧合过滤误伤


    def test_validate_finance_uses_uploaded_data_source(self):
        import server.pipeline as pipeline
        import server.store as storemod

        old_store = storemod._STORE                  # noqa: SLF001
        old_uploads_dir = pipeline.FINANCE_UPLOADS_DIR
        storemod._STORE = storemod.JobStore()        # noqa: SLF001

        with tempfile.TemporaryDirectory() as tmpdir:
            upload_root = Path(tmpdir) / "finance_v1"
            upload_root.mkdir(parents=True)
            pipeline.FINANCE_UPLOADS_DIR = upload_root
            uploaded_path = upload_root / "custom-finance.csv"
            _custom_finance_frame().to_csv(uploaded_path, index=False)
            try:
                store = storemod.get_store()
                data_source_id = store.put_data_source({
                    "scenario": "finance_v1",
                    "filename": uploaded_path.name,
                    "path": str(uploaded_path),
                    "size": uploaded_path.stat().st_size,
                    "note": "custom-cogs",
                })
                job = store.create_job(
                    "finance_v1",
                    "validate-finance",
                    request_params={
                        "dataSourceId": data_source_id,
                        "validationDataSourceId": data_source_id,
                    },
                )
                events: list[WorkflowEvent] = []
                result = run_finance_pipeline(job, events.append)

                vreport = result["vreport"]
                slots = result["dual"].track_b.slots
                self.assertEqual(vreport.total_rows, 8)
                self.assertEqual(vreport.data_path, str(uploaded_path.resolve()))
                self.assertEqual(vreport.by_rule, {"R01": 1})
                self.assertEqual(result["data_source"]["validation"], {
                    "id": data_source_id,
                    "filename": uploaded_path.name,
                })
                self.assertEqual(slots["data_source"], str(uploaded_path.resolve()))
                self.assertEqual(slots["cogs_reported"], "4,321")
                self.assertEqual(slots["cogs_corrected"], "2,000")
                self.assertEqual(slots["f1_diff"], "+2,321")
                self.assertNotEqual(slots["cogs_reported"], "3,000")
                descriptions = "\n".join(event.description for event in events)
                self.assertIn(f"dataSourceId={data_source_id}", descriptions)
            finally:
                pipeline.FINANCE_UPLOADS_DIR = old_uploads_dir
                storemod._STORE = old_store           # noqa: SLF001


class TestNetworkPipeline(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.events: list[WorkflowEvent] = []
        cls.result = run_network_pipeline(None, cls.events.append)

    def test_event_stage_order_and_agents(self):
        pos = _first_positions(self.events)
        order = [pos[s] for s in NETWORK_STAGE_ORDER]
        self.assertEqual(order, sorted(order))
        for ev in self.events:
            self.assertEqual(ev.agent, STAGE_AGENT[ev.stage])
        self.assertEqual((self.events[0].stage, self.events[0].status),
                         ("control", "running"))
        self.assertEqual((self.events[-1].stage, self.events[-1].status),
                         ("control", "done"))
        descriptions = "\n".join(ev.description for ev in self.events)
        self.assertIn("stage=learn processor=NetNomos hitting-set/Z3", descriptions)
        self.assertIn("stage=explain processor=RuleExplainer/RAG/gemma3 optional",
                      descriptions)
        self.assertNotIn("沙箱降级读预置合规样本", descriptions)
        self.assertIn("stage=report processor=A轨裸模型+B轨约束", descriptions)

    def test_dual_netflow(self):
        dual = self.result["dual"]
        self.assertGreaterEqual(len(dual.track_a.violations), 3)
        self.assertEqual(dual.track_b.violations, [])
        self.assertIn('class="err', dual.diff_html)

    def test_ruleset_loaded(self):
        self.assertTrue(self.result["ruleset"].rules)
        self.assertTrue(self.result["cards"])

    def test_learn_network_sequence_skips_dual_report(self):
        import server.store as storemod

        store = storemod.JobStore()
        job = store.create_job("network_cidds", "learn-network")
        events: list[WorkflowEvent] = []
        with patch("forge.core.reporter.DualReporter.make_dual_network",
                   side_effect=AssertionError("dual report should not run")):
            result = run_network_pipeline(job, events.append)

        self.assertIsNone(result["dual"])
        self.assertIsNone(result["vreport"])
        self.assertEqual(result["violations"], [])
        stages = [event.stage for event in events]
        self.assertIn("learn", stages)
        self.assertIn("explain", stages)
        self.assertNotIn("report", stages)
        self.assertNotIn("diff", stages)

    def test_validate_network_uses_uploaded_data_source(self):
        import server.pipeline as pipeline
        import server.store as storemod

        old_store = storemod._STORE                  # noqa: SLF001
        old_uploads_dir = pipeline.NETWORK_UPLOADS_DIR
        storemod._STORE = storemod.JobStore()        # noqa: SLF001

        with tempfile.TemporaryDirectory() as tmpdir:
            upload_root = Path(tmpdir) / "network_cidds"
            upload_root.mkdir(parents=True)
            pipeline.NETWORK_UPLOADS_DIR = upload_root
            uploaded_path = upload_root / "uploaded-netflow.csv"
            uploaded_path.write_text(
                "\n".join([
                    "DateFirstSeen,Duration,Proto,SrcIpAddr,SrcPt,DstIpAddr,DstPt,Packets,Bytes,Flows,Flags,Tos",
                    "2017-03-23 09:22:45.870,0.004,UDP,192.168.220.12,51413,DNS,53,2,196,1,.AP.SF,0",
                    "2017-03-23 09:27:54.781,0.000,UDP,192.168.220.9,137,192.168.220.255,137,1,92,1,......,0",
                ]),
                encoding="utf-8",
            )
            try:
                store = storemod.get_store()
                data_source_id = store.put_data_source({
                    "scenario": "network_cidds",
                    "filename": uploaded_path.name,
                    "path": str(uploaded_path),
                    "size": uploaded_path.stat().st_size,
                    "note": "test-upload",
                })
                job = store.create_job(
                    "network_cidds",
                    "validate-network",
                    request_params={
                        "dataSourceId": data_source_id,
                        "validationDataSourceId": data_source_id,
                    },
                )
                events: list[WorkflowEvent] = []
                result = run_network_pipeline(job, events.append)

                self.assertIsNone(result["dual"])
                self.assertEqual(result["vreport"].total_rows, 2)
                self.assertEqual({v.rule_id for v in result["violations"]}, {"N01"})
                descriptions = "\n".join(event.description for event in events)
                self.assertIn(f"dataSourceId={data_source_id}", descriptions)
                self.assertNotIn("stage=report", descriptions)
                self.assertNotIn("diff", {event.stage for event in events})
            finally:
                pipeline.NETWORK_UPLOADS_DIR = old_uploads_dir
                storemod._STORE = old_store           # noqa: SLF001

    def test_report_network_sequence_runs_dual_once_with_uploaded_track_a(self):
        import server.pipeline as pipeline
        import server.store as storemod
        from forge.contracts import TrackReport
        from forge.core.reporter import DualReporter

        class ExplodingLLM:
            def complete(self, *args, **kwargs):
                raise AssertionError("uploaded report-network must not call LLM for track A")

        old_store = storemod._STORE                  # noqa: SLF001
        old_uploads_dir = pipeline.NETWORK_UPLOADS_DIR
        storemod._STORE = storemod.JobStore()        # noqa: SLF001

        with tempfile.TemporaryDirectory() as tmpdir:
            upload_root = Path(tmpdir) / "network_cidds"
            upload_root.mkdir(parents=True)
            pipeline.NETWORK_UPLOADS_DIR = upload_root
            uploaded_path = upload_root / "report-netflow.csv"
            uploaded_path.write_text(
                "\n".join([
                    "DateFirstSeen,Duration,Proto,SrcIpAddr,SrcPt,DstIpAddr,DstPt,Packets,Bytes,Flows,Flags,Tos",
                    "2017-03-23 09:22:45.870,0.004,UDP,192.168.220.12,51413,DNS,53,2,196,1,.AP.SF,0",
                    "2017-03-23 09:27:54.781,0.000,UDP,192.168.220.9,137,192.168.220.255,137,1,92,1,......,0",
                ]),
                encoding="utf-8",
            )
            try:
                store = storemod.get_store()
                data_source_id = store.put_data_source({
                    "scenario": "network_cidds",
                    "filename": uploaded_path.name,
                    "path": str(uploaded_path),
                    "size": uploaded_path.stat().st_size,
                    "note": "report-upload",
                })
                job = store.create_job(
                    "network_cidds",
                    "report-network",
                    request_params={
                        "dataSourceId": data_source_id,
                        "validationDataSourceId": data_source_id,
                    },
                )
                fake_b = TrackReport(
                    track="B",
                    markdown="B track",
                    slots={"rows": [
                        {"Proto": "UDP", "SrcIpAddr": "a", "SrcPt": 1, "DstIpAddr": "DNS", "DstPt": 53,
                         "Packets": 2, "Bytes": 196, "Flags": "......"},
                        {"Proto": "UDP", "SrcIpAddr": "b", "SrcPt": 137, "DstIpAddr": "c", "DstPt": 137,
                         "Packets": 1, "Bytes": 92, "Flags": "......"},
                    ]},
                    violations=[],
                    intervention_log=["fake"],
                )
                calls: list[dict] = []
                original_make_dual = DualReporter.make_dual_network

                def spy_make_dual(self, *args, **kwargs):
                    calls.append(dict(kwargs))
                    return original_make_dual(self, *args, **kwargs)

                events: list[WorkflowEvent] = []
                with patch.object(DualReporter, "make_dual_network", spy_make_dual), \
                        patch.object(DualReporter, "track_b_network", return_value=fake_b):
                    result = run_network_pipeline(job, events.append, llm=ExplodingLLM())

                self.assertEqual(len(calls), 1)
                self.assertIsNotNone(calls[0].get("track_a_rows"))
                self.assertEqual(result["dual"].track_a.slots["rows"][0]["Flags"], ".AP.SF")
                self.assertEqual({v.rule_id for v in result["violations"]}, {"N01"})
                descriptions = "\n".join(event.description for event in events)
                self.assertIn("stage=report", descriptions)
            finally:
                pipeline.NETWORK_UPLOADS_DIR = old_uploads_dir
                storemod._STORE = old_store           # noqa: SLF001

    def test_network_upload_rejects_wrong_scenario(self):
        import server.pipeline as pipeline
        import server.store as storemod

        old_store = storemod._STORE                  # noqa: SLF001
        old_uploads_dir = pipeline.NETWORK_UPLOADS_DIR
        storemod._STORE = storemod.JobStore()        # noqa: SLF001

        with tempfile.TemporaryDirectory() as tmpdir:
            upload_root = Path(tmpdir) / "network_cidds"
            upload_root.mkdir(parents=True)
            pipeline.NETWORK_UPLOADS_DIR = upload_root
            uploaded_path = upload_root / "wrong-scenario.csv"
            uploaded_path.write_text(
                "Proto,Packets,Bytes\nUDP,1,92\n",
                encoding="utf-8",
            )
            try:
                store = storemod.get_store()
                data_source_id = store.put_data_source({
                    "scenario": "finance_v1",
                    "filename": uploaded_path.name,
                    "path": str(uploaded_path),
                    "size": uploaded_path.stat().st_size,
                })
                job = store.create_job(
                    "network_cidds",
                    "validate-network",
                    request_params={"validationDataSourceId": data_source_id},
                )
                with self.assertRaises(RuntimeError) as ctx:
                    run_network_pipeline(job, lambda _event: None)
                self.assertIn("network_cidds", str(ctx.exception))
            finally:
                pipeline.NETWORK_UPLOADS_DIR = old_uploads_dir
                storemod._STORE = old_store           # noqa: SLF001

    def test_custom_network_learn_without_runtime_fails_clearly(self):
        import server.pipeline as pipeline
        import server.store as storemod

        old_store = storemod._STORE                  # noqa: SLF001
        old_uploads_dir = pipeline.NETWORK_UPLOADS_DIR
        storemod._STORE = storemod.JobStore()        # noqa: SLF001

        with tempfile.TemporaryDirectory() as tmpdir:
            upload_root = Path(tmpdir) / "network_cidds"
            upload_root.mkdir(parents=True)
            pipeline.NETWORK_UPLOADS_DIR = upload_root
            uploaded_path = upload_root / "training.csv"
            uploaded_path.write_text(
                "Proto,Packets,Bytes\nUDP,1,92\n",
                encoding="utf-8",
            )
            try:
                store = storemod.get_store()
                data_source_id = store.put_data_source({
                    "scenario": "network_cidds",
                    "filename": uploaded_path.name,
                    "path": str(uploaded_path),
                    "size": uploaded_path.stat().st_size,
                })
                job = store.create_job(
                    "network_cidds",
                    "learn-network",
                    request_params={
                        "dataSourceId": data_source_id,
                        "trainingDataSourceId": data_source_id,
                    },
                )
                events: list[WorkflowEvent] = []
                with patch("server.pipeline.find_spec", return_value=None):
                    with self.assertRaises(RuntimeError) as ctx:
                        run_network_pipeline(job, events.append)
                self.assertIn("NetNomos runtime", str(ctx.exception))
                self.assertTrue(any(
                    event.stage == "learn" and event.status == "blocked"
                    for event in events
                ))
            finally:
                pipeline.NETWORK_UPLOADS_DIR = old_uploads_dir
                storemod._STORE = old_store           # noqa: SLF001


class TestServerApp(unittest.TestCase):
    """server.app 沙箱 import 安全 + create_app 懒加载."""

    def test_import_does_not_require_fastapi(self):
        import server.app as appmod   # 沙箱无 fastapi 也必须 import 成功
        self.assertTrue(callable(appmod.create_app))

    def test_create_app_or_chinese_hint(self):
        import server.app as appmod
        if find_spec("fastapi") is None:
            with self.assertRaises(RuntimeError) as ctx:
                appmod.create_app()
            self.assertIn("uv sync", str(ctx.exception))
        else:
            app = appmod.create_app()
            paths = {r.path for r in app.routes}
            from forge.contracts import (
                API_CHAT_CONSTRAINED, API_DATA_SOURCES, API_REPORTS_GENERATE,
                API_RULESET_CARDS, API_RULESETS_LEARN, API_RULESETS_UPLOAD,
                API_WORKFLOW_EVENTS)
            for p in (API_CHAT_CONSTRAINED, API_DATA_SOURCES,
                      API_REPORTS_GENERATE, API_RULESET_CARDS,
                      API_RULESETS_LEARN, API_RULESETS_UPLOAD,
                      API_WORKFLOW_EVENTS, "/api/jobs/{job_id}"):
                self.assertIn(p, paths)

    def test_start_job_reuses_recent_running_duplicate(self):
        import threading
        import time

        import server.app as appmod
        import server.store as storemod
        from forge.contracts import RuleSet

        old_store = storemod._STORE                  # noqa: SLF001
        old_pipeline = appmod._SCENARIO_PIPELINES["network_cidds"]  # noqa: SLF001
        storemod._STORE = storemod.JobStore()        # noqa: SLF001
        entered = threading.Event()
        release = threading.Event()

        def slow_pipeline(job, emit, llm=None):
            entered.set()
            release.wait(timeout=2)
            return {"ruleset": RuleSet(scenario="network_cidds", rules=[]),
                    "cards": [], "dual": None, "vreport": None}

        appmod._SCENARIO_PIPELINES["network_cidds"] = slow_pipeline  # noqa: SLF001
        try:
            with patch("forge.utils.ollama_lifecycle.cleanup_ollama_after_job"):
                first = appmod._start_job("network_cidds", "learn-network", {"x": "y"})
                self.assertTrue(entered.wait(timeout=1))
                second = appmod._start_job("network_cidds", "learn-network", {"x": "y"})
                self.assertEqual(first, second)
                release.set()
                store = storemod.get_store()
                deadline = time.time() + 2
                while time.time() < deadline and store.get_job(first).status != JOB_DONE:
                    time.sleep(0.02)
                self.assertEqual(store.get_job(first).status, JOB_DONE)
        finally:
            release.set()
            appmod._SCENARIO_PIPELINES["network_cidds"] = old_pipeline  # noqa: SLF001
            storemod._STORE = old_store              # noqa: SLF001

    def test_data_sources_multipart_upload_persists_file(self):
        if find_spec("fastapi") is None:
            self.skipTest("fastapi not installed")

        import server.app as appmod
        import server.store as storemod
        from fastapi.testclient import TestClient
        from forge.contracts import API_DATA_SOURCES

        old_store = storemod._STORE                  # noqa: SLF001
        old_uploads_dir = appmod.UPLOADS_DIR         # noqa: SLF001
        storemod._STORE = storemod.JobStore()        # noqa: SLF001

        with tempfile.TemporaryDirectory() as tmpdir:
            appmod.UPLOADS_DIR = Path(tmpdir)        # noqa: SLF001
            try:
                client = TestClient(appmod.create_app())
                response = client.post(
                    API_DATA_SOURCES,
                    data={"scenario": "network_cidds", "note": "fixture"},
                    files={"file": ("../sample?.csv", b"a,b\n1,2\n", "text/csv")},
                )
                self.assertEqual(response.status_code, 200, response.text)
                payload = response.json()
                stored_path = Path(payload["path"])
                self.assertTrue(stored_path.exists())
                self.assertEqual(stored_path.read_bytes(), b"a,b\n1,2\n")
                self.assertEqual(stored_path.parent, Path(tmpdir) / "network_cidds")
                self.assertEqual(payload["filename"], "sample_.csv")
                self.assertEqual(payload["size"], 8)

                store = storemod.get_store()
                meta = store.data_sources[payload["dataSourceId"]]
                self.assertEqual(meta["scenario"], "network_cidds")
                self.assertEqual(meta["filename"], "sample_.csv")
                self.assertEqual(meta["note"], "fixture")
                self.assertEqual(meta["size"], 8)
                self.assertTrue(meta["path"].endswith(payload["path"]))
            finally:
                appmod.UPLOADS_DIR = old_uploads_dir  # noqa: SLF001
                storemod._STORE = old_store           # noqa: SLF001

    def test_finance_upload_then_learn_preserves_data_source_and_uses_uploaded_csv(self):
        if find_spec("fastapi") is None:
            self.skipTest("fastapi not installed")

        from dataclasses import asdict

        import server.app as appmod
        import server.pipeline as pipeline
        import server.store as storemod
        from fastapi.testclient import TestClient
        from forge.contracts import API_DATA_SOURCES, API_RULESETS_LEARN

        old_store = storemod._STORE                  # noqa: SLF001
        old_uploads_dir = appmod.UPLOADS_DIR         # noqa: SLF001
        old_finance_uploads_dir = pipeline.FINANCE_UPLOADS_DIR
        old_start_job = appmod._start_job            # noqa: SLF001
        storemod._STORE = storemod.JobStore()        # noqa: SLF001
        store = storemod.get_store()

        def sync_start_job(
            scenario: str,
            sequence: str = "",
            request_params: dict | None = None,
        ) -> str:
            self.assertEqual(scenario, "finance_v1")
            job = store.create_job(scenario, sequence,
                                   request_params=request_params)
            result = run_finance_pipeline(
                job,
                lambda event: store.append_event(job.job_id, event),
                llm=None,
            )
            ruleset_id = store.put_ruleset(result["ruleset"], result["cards"])
            request_snapshot = dict(job.request_params)
            store.finish_job(job.job_id, {
                "ruleset_id": ruleset_id,
                "dual": asdict(result["dual"]),
                "cards": [asdict(card) for card in result["cards"]],
                "rules": [asdict(rule) for rule in result["ruleset"].rules],
                "violations": [asdict(v) for v in result["vreport"].violations],
                "vreport": asdict(result["vreport"]),
                "data_source": result["data_source"],
                "request": request_snapshot,
                "requestParams": request_snapshot,
            })
            return job.job_id

        with tempfile.TemporaryDirectory() as tmpdir:
            appmod.UPLOADS_DIR = Path(tmpdir)         # noqa: SLF001
            pipeline.FINANCE_UPLOADS_DIR = Path(tmpdir) / "finance_v1"
            appmod._start_job = sync_start_job        # noqa: SLF001
            try:
                client = TestClient(appmod.create_app())
                csv_bytes = _custom_finance_frame().to_csv(index=False).encode("utf-8")
                upload_response = client.post(
                    API_DATA_SOURCES,
                    data={"scenario": "finance_v1", "note": "custom-cogs"},
                    files={"file": ("custom-finance.csv", csv_bytes, "text/csv")},
                )
                self.assertEqual(upload_response.status_code, 200, upload_response.text)
                upload_payload = upload_response.json()
                data_source_id = upload_payload["dataSourceId"]

                learn_response = client.post(
                    API_RULESETS_LEARN,
                    json={
                        "scenario": "finance_v1",
                        "sequence": "learn-finance",
                        "dataSourceId": data_source_id,
                    },
                )
                self.assertEqual(learn_response.status_code, 200, learn_response.text)
                learn_payload = learn_response.json()
                expected_request = {"dataSourceId": data_source_id}
                self.assertEqual(learn_payload["request"], expected_request)

                job_response = client.get(f"/api/jobs/{learn_payload['jobId']}")
                self.assertEqual(job_response.status_code, 200, job_response.text)
                job_payload = job_response.json()
                self.assertEqual(job_payload["request"], expected_request)
                self.assertEqual(job_payload["requestParams"], expected_request)
                self.assertEqual(job_payload["result"]["request"], expected_request)
                self.assertEqual(job_payload["result"]["requestParams"], expected_request)
                self.assertEqual(job_payload["result"]["data_source"]["validation"], {
                    "id": data_source_id,
                    "filename": "custom-finance.csv",
                })
                self.assertEqual(job_payload["result"]["vreport"]["by_rule"], {"R01": 1})
                self.assertEqual(
                    job_payload["result"]["vreport"]["data_path"],
                    str(Path(upload_payload["path"]).resolve()),
                )
                slots = job_payload["result"]["dual"]["track_b"]["slots"]
                self.assertEqual(slots["cogs_reported"], "4,321")
                self.assertEqual(slots["cogs_corrected"], "2,000")
                self.assertNotEqual(slots["cogs_reported"], "3,000")
            finally:
                appmod._start_job = old_start_job     # noqa: SLF001
                appmod.UPLOADS_DIR = old_uploads_dir  # noqa: SLF001
                pipeline.FINANCE_UPLOADS_DIR = old_finance_uploads_dir
                storemod._STORE = old_store           # noqa: SLF001

    def test_learn_post_and_job_result_endpoint(self):
        if find_spec("fastapi") is None:
            self.skipTest("fastapi not installed")

        import server.app as appmod
        import server.store as storemod
        from fastapi.testclient import TestClient
        from forge.contracts import API_RULESETS_LEARN

        old_store = storemod._STORE                  # noqa: SLF001
        old_start_job = appmod._start_job            # noqa: SLF001
        storemod._STORE = storemod.JobStore()        # noqa: SLF001
        store = storemod.get_store()

        def fake_start_job(
            scenario: str,
            sequence: str = "",
            request_params: dict | None = None,
        ) -> str:
            job = store.create_job(scenario, sequence,
                                   request_params=request_params)
            event = WorkflowEvent.make("control", "done", "mock job complete")
            store.append_event(job.job_id, event)
            request_snapshot = dict(job.request_params)
            store.finish_job(job.job_id, {
                "ruleset_id": "ruleset-smoke",
                "dual": None,
                "cards": [],
                "rules": [],
                "violations": [],
                "request": request_snapshot,
                "requestParams": request_snapshot,
            })
            return job.job_id

        appmod._start_job = fake_start_job           # noqa: SLF001
        try:
            client = TestClient(appmod.create_app())
            learn_request = {
                "scenario": "network_cidds",
                "sequence": "learn-network",
                "dataSourceId": "ds-main",
                "trainingDataSourceId": "ds-train",
                "validationDataSourceId": "ds-val",
                "question": "which rules were learned?",
                "reportPrompt": "write an audit report",
            }
            response = client.post(
                API_RULESETS_LEARN,
                json=learn_request,
            )
            self.assertEqual(response.status_code, 200, response.text)
            response_payload = response.json()
            job_id = response_payload["jobId"]
            expected_request = {
                key: learn_request[key]
                for key in (
                    "dataSourceId",
                    "trainingDataSourceId",
                    "validationDataSourceId",
                    "question",
                    "reportPrompt",
                )
            }
            self.assertEqual(response_payload["request"], expected_request)

            job_response = client.get(f"/api/jobs/{job_id}")
            self.assertEqual(job_response.status_code, 200, job_response.text)
            payload = job_response.json()
            self.assertEqual(payload["job_id"], job_id)
            self.assertEqual(payload["jobId"], job_id)
            self.assertEqual(payload["scenario"], "network_cidds")
            self.assertEqual(payload["sequence"], "learn-network")
            self.assertEqual(payload["status"], JOB_DONE)
            self.assertIsNone(payload["error"])
            self.assertEqual(payload["events"][0]["stage"], "control")
            self.assertEqual(payload["result"]["ruleset_id"], "ruleset-smoke")
            self.assertEqual(payload["request"], expected_request)
            self.assertEqual(payload["requestParams"], expected_request)
            self.assertEqual(payload["result"]["request"], expected_request)
            self.assertEqual(payload["result"]["requestParams"], expected_request)
        finally:
            appmod._start_job = old_start_job        # noqa: SLF001
            storemod._STORE = old_store              # noqa: SLF001


class TestJobStore(unittest.TestCase):
    """内存任务存储：事件回放 + 实时推送 + 哨兵."""

    def test_subscribe_replays_history_and_sentinel(self):
        store = JobStore()
        job = store.create_job("finance_v1", "learn-finance")
        ev1 = WorkflowEvent.make("upload", "running", "测试事件一")
        store.append_event(job.job_id, ev1)
        q = store.subscribe(job.job_id)                  # 回放历史
        self.assertEqual(q.get_nowait().id, ev1.id)
        ev2 = WorkflowEvent.make("upload", "done", "测试事件二")
        store.append_event(job.job_id, ev2)              # 实时推送
        self.assertEqual(q.get_nowait().id, ev2.id)
        store.finish_job(job.job_id, {"ok": True})
        self.assertIsNone(q.get_nowait())                # 哨兵
        self.assertEqual(store.get_job(job.job_id).status, JOB_DONE)

    def test_subscribe_finished_job_gets_replay_then_sentinel(self):
        store = JobStore()
        job = store.create_job("network_cidds")
        store.append_event(job.job_id, WorkflowEvent.make("learn", "done", "完"))
        store.finish_job(job.job_id)
        q = store.subscribe(job.job_id)
        self.assertEqual(q.get_nowait().stage, "learn")
        self.assertIsNone(q.get_nowait())

    def test_find_recent_running_job_reuses_exact_request(self):
        store = JobStore()
        job = store.create_job(
            "network_cidds",
            "learn-network",
            request_params={"dataSourceId": "abc"},
        )
        match = store.find_recent_running_job(
            "network_cidds",
            "learn-network",
            {"dataSourceId": "abc"},
        )
        self.assertIsNotNone(match)
        self.assertEqual(match.job_id, job.job_id)
        self.assertIsNone(store.find_recent_running_job(
            "network_cidds",
            "learn-network",
            {"dataSourceId": "other"},
        ))
        store.finish_job(job.job_id)
        self.assertIsNone(store.find_recent_running_job(
            "network_cidds",
            "learn-network",
            {"dataSourceId": "abc"},
        ))

    def test_event_sse_format(self):
        ev = WorkflowEvent.make("report", "running", "B 轨槽位回填")
        sse = ev.to_sse()
        self.assertTrue(sse.startswith("event: workflow\ndata: "))
        self.assertIn('"stage": "report"', sse)


if __name__ == "__main__":
    unittest.main()
