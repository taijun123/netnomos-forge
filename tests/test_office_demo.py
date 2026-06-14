from __future__ import annotations

import time
import unittest
from importlib.util import find_spec

from forge.contracts import WorkflowEvent
from server.pipeline import SEQUENCE_PIPELINES, run_office_demo_pipeline


class TestOfficeDemoPipeline(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.events: list[WorkflowEvent] = []
        cls.result = run_office_demo_pipeline(None, cls.events.append)

    def test_office_pipeline_shape(self):
        result = self.result
        self.assertEqual(result["ruleset"].scenario, "office_demo")
        self.assertEqual(len(result["agents"]), 6)
        self.assertGreaterEqual(len(result["ruleGroups"]), 3)
        self.assertGreaterEqual(len(result["dataSources"]), 2)
        self.assertGreaterEqual(len(result["artifacts"]), 3)
        self.assertEqual(result["office"]["scenario"], "office_demo")
        self.assertEqual(result["office_state"]["scenario"], "office_demo")
        self.assertEqual(len(result["workflowEvents"]), len(self.events))

    def test_office_combines_finance_and_network_rules(self):
        groups = {group["id"]: group for group in self.result["ruleGroups"]}
        self.assertIn("office-finance-controls", groups)
        self.assertIn("office-network-controls", groups)
        self.assertIn("office-output-constraints", groups)
        self.assertGreaterEqual(groups["office-finance-controls"]["ruleCount"], 7)
        self.assertGreaterEqual(groups["office-network-controls"]["ruleCount"], 1)
        rule_ids = {rule.rule_id for rule in self.result["ruleset"].rules}
        self.assertIn("R01", rule_ids)
        self.assertTrue(any(rule_id.startswith("hs") for rule_id in rule_ids))

    def test_sequence_aliases_point_to_office_demo(self):
        for sequence in ("office-overview", "learn-office", "validate-office", "report-office"):
            scenario, pipeline = SEQUENCE_PIPELINES[sequence]
            self.assertEqual(scenario, "office_demo")
            self.assertIs(pipeline, run_office_demo_pipeline)


class TestOfficeDemoApi(unittest.TestCase):
    def test_learn_job_and_chat_surface_office_state(self):
        if find_spec("fastapi") is None:
            self.skipTest("fastapi not installed")

        import server.app as appmod
        import server.store as storemod
        from fastapi.testclient import TestClient
        from forge.contracts import API_CHAT_CONSTRAINED, API_RULESETS_LEARN
        from server.pipeline import run_office_demo_pipeline

        old_store = storemod._STORE  # noqa: SLF001
        old_start_job = appmod._start_job  # noqa: SLF001
        storemod._STORE = storemod.JobStore()  # noqa: SLF001
        store = storemod.get_store()

        def sync_start_job(
            scenario: str,
            sequence: str = "",
            request_params: dict | None = None,
        ) -> str:
            job = store.create_job(scenario, sequence, request_params=request_params)
            result = run_office_demo_pipeline(
                job,
                lambda event: store.append_event(job.job_id, event),
                llm=None,
            )
            ruleset_id = store.put_ruleset(result["ruleset"], result["cards"])
            store.last_office_state = result["office_state"]
            request_snapshot = dict(job.request_params)
            store.finish_job(job.job_id, {
                "ruleset_id": ruleset_id,
                "cards": [],
                "rules": [],
                "violations": [],
                "office": result["office"],
                "office_state": result["office_state"],
                "agents": result["agents"],
                "ruleGroups": result["ruleGroups"],
                "dataSources": result["dataSources"],
                "artifacts": result["artifacts"],
                "workflowEvents": result["workflowEvents"],
                "request": request_snapshot,
                "requestParams": request_snapshot,
            })
            return job.job_id

        appmod._start_job = sync_start_job  # noqa: SLF001
        try:
            client = TestClient(appmod.create_app())
            response = client.post(
                API_RULESETS_LEARN,
                json={
                    "scenario": "office_demo",
                    "sequence": "learn-office",
                    "question": "show office state",
                },
            )
            self.assertEqual(response.status_code, 200, response.text)
            job_id = response.json()["jobId"]

            payload = None
            for _ in range(40):
                job_response = client.get(f"/api/jobs/{job_id}")
                self.assertEqual(job_response.status_code, 200, job_response.text)
                payload = job_response.json()
                if payload["status"] == "done":
                    break
                time.sleep(0.1)

            self.assertIsNotNone(payload)
            self.assertEqual(payload["status"], "done")
            result = payload["result"]
            self.assertEqual(result["office"]["scenario"], "office_demo")
            self.assertEqual(len(result["agents"]), 6)
            self.assertGreaterEqual(len(result["ruleGroups"]), 3)
            self.assertGreaterEqual(len(result["workflowEvents"]), 1)

            chat_response = client.post(
                API_CHAT_CONSTRAINED,
                json={"scenario": "office_demo", "message": "which groups are active?"},
            )
            self.assertEqual(chat_response.status_code, 200, chat_response.text)
            chat = chat_response.json()
            self.assertTrue(chat["constrained"])
            self.assertIn("content", chat)
            self.assertIn("reply", chat)
            self.assertTrue(chat["matchedRules"])
            self.assertTrue(chat["citations"])
        finally:
            appmod._start_job = old_start_job  # noqa: SLF001
            storemod._STORE = old_store  # noqa: SLF001


if __name__ == "__main__":
    unittest.main()
