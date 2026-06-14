"""Hitting-set 学习器测试。"""

from __future__ import annotations

import unittest

from netnomos.learners.hittingset import HittingSetLearner
from netnomos.specs import HittingSetBackend


class HittingSetLearnerTest(unittest.TestCase):
    """覆盖 Python/原生后端和停滞超时行为。"""

    def test_enumeration_completes_without_timeout(self) -> None:
        """简单证据集应完整枚举并正常结束。"""
        learner = HittingSetLearner(max_clause_size=2, max_rules=16)
        covers, metadata = learner.enumerate_minimal_hitting_sets([
            {0},
            {1},
        ])

        self.assertEqual(covers, [{0, 1}])
        self.assertFalse(metadata["search_stopped_early"])
        self.assertEqual(metadata["stop_reason"], "complete")

    def test_stall_timeout_returns_partial_solutions(self) -> None:
        """停滞超时后应返回部分解并带上对应元数据。"""
        call_count = 0

        def clock() -> float:
            nonlocal call_count
            call_count += 1
            if call_count <= 24:
                return 0.0
            return 10.0

        learner = HittingSetLearner(
            max_clause_size=3,
            max_rules=64,
            stall_timeout=1.0,
            clock=clock,
        )
        covers, metadata = learner.enumerate_minimal_hitting_sets([
            {0, 1, 2},
            {0, 3, 4},
            {1, 3, 5},
            {2, 4, 5},
            {0, 5},
            {1, 4},
        ])

        self.assertGreaterEqual(len(covers), 1)
        self.assertTrue(metadata["search_stopped_early"])
        self.assertEqual(metadata["stop_reason"], "stall-timeout")
        self.assertEqual(metadata["stall_timeout_seconds"], 1.0)
        self.assertEqual(metadata["hitting_set_backend_used"], HittingSetBackend.PYTHON.value)

    def test_python_backend_can_be_selected_explicitly(self) -> None:
        """显式请求 Python 后端时不应切换到原生实现。"""
        learner = HittingSetLearner(
            max_clause_size=2,
            max_rules=16,
            backend=HittingSetBackend.PYTHON,
        )
        covers, metadata = learner.enumerate_minimal_hitting_sets([
            {0, 1},
            {1, 2},
        ])

        self.assertEqual({frozenset(item) for item in covers}, {frozenset({1}), frozenset({0, 2})})
        self.assertEqual(metadata["hitting_set_backend_requested"], HittingSetBackend.PYTHON.value)
        self.assertEqual(metadata["hitting_set_backend_used"], HittingSetBackend.PYTHON.value)

    @unittest.skipUnless(HittingSetLearner.native_backend_available(), "native hitting-set backend is unavailable")
    def test_native_backend_matches_python_backend(self) -> None:
        """原生后端和 Python 后端在同一输入上应得到等价结果。"""
        evidence_sets = [
            {0, 1, 2},
            {0, 3},
            {2, 3, 4},
            {1, 4},
        ]
        python_learner = HittingSetLearner(
            max_clause_size=3,
            max_rules=32,
            backend=HittingSetBackend.PYTHON,
        )
        native_learner = HittingSetLearner(
            max_clause_size=3,
            max_rules=32,
            backend=HittingSetBackend.NATIVE,
        )

        python_covers, python_metadata = python_learner.enumerate_minimal_hitting_sets(evidence_sets)
        native_covers, native_metadata = native_learner.enumerate_minimal_hitting_sets(evidence_sets)

        self.assertEqual({frozenset(item) for item in python_covers}, {frozenset(item) for item in native_covers})
        self.assertEqual(python_metadata["stop_reason"], native_metadata["stop_reason"])
        self.assertEqual(native_metadata["hitting_set_backend_used"], HittingSetBackend.NATIVE.value)


if __name__ == "__main__":
    unittest.main()
