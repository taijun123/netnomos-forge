# -*- coding: utf-8 -*-
"""server.store — 内存任务/规则集/数据源存储（纯标准库，线程安全）.

演示工程不引入数据库：所有任务（Job）、规则集、规则卡、双轨报告、数据源
登记都保存在进程内存里；SSE 订阅者通过 queue.Queue 拿到事件的"回放 + 实时"
合并流（先补发历史事件，再持续推送新事件，任务结束推哨兵 None）。
"""
from __future__ import annotations

import queue
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from forge.contracts import WorkflowEvent

# 任务状态
JOB_PENDING = "pending"
JOB_RUNNING = "running"
JOB_DONE = "done"
JOB_FAILED = "failed"


@dataclass
class Job:
    """一次管线运行：事件序列 + 结果（DualReport / RuleSet 等聚合 dict）."""
    job_id: str
    scenario: str
    sequence: str = ""                 # 前端 MockSequenceId（learn-finance 等）
    request_params: dict[str, Any] = field(default_factory=dict)
    status: str = JOB_PENDING
    created_at: float = field(default_factory=time.time)
    events: list[WorkflowEvent] = field(default_factory=list)
    result: dict[str, Any] | None = None
    error: str | None = None


class JobStore:
    """线程安全的内存存储：任务 / 规则集 / 规则卡 / 数据源 / 最近报告."""

    def __init__(self):
        self._lock = threading.RLock()
        self._jobs: dict[str, Job] = {}
        self._subscribers: dict[str, list[queue.Queue]] = {}
        self.rulesets: dict[str, Any] = {}        # ruleset_id -> RuleSet
        self.cards: dict[str, list] = {}          # ruleset_id -> list[RuleCard]
        self.data_sources: dict[str, dict] = {}   # data_source_id -> 元信息
        self.last_dual: dict[str, Any] = {}       # scenario -> DualReport（chat 校验复用）
        self.last_office_state: dict[str, Any] | None = None

    # ------------------------------------------------------------------ Job
    def create_job(
        self,
        scenario: str,
        sequence: str = "",
        request_params: dict[str, Any] | None = None,
    ) -> Job:
        with self._lock:
            job = Job(job_id=uuid.uuid4().hex[:12], scenario=scenario,
                      sequence=sequence, request_params=dict(request_params or {}),
                      status=JOB_RUNNING)
            self._jobs[job.job_id] = job
            return job

    def get_job(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def find_recent_running_job(
        self,
        scenario: str,
        sequence: str = "",
        request_params: dict[str, Any] | None = None,
        max_age_seconds: float = 5.0,
    ) -> Job | None:
        target_params = dict(request_params or {})
        now = time.time()
        with self._lock:
            matches = [
                job for job in self._jobs.values()
                if job.status == JOB_RUNNING
                and job.scenario == scenario
                and job.sequence == sequence
                and job.request_params == target_params
                and now - job.created_at <= max_age_seconds
            ]
            if not matches:
                return None
            return max(matches, key=lambda job: job.created_at)

    def append_event(self, job_id: str, event: WorkflowEvent) -> None:
        """登记事件并广播给所有订阅者."""
        with self._lock:
            job = self._jobs[job_id]
            job.events.append(event)
            subs = list(self._subscribers.get(job_id, []))
        for q in subs:
            q.put(event)

    def finish_job(self, job_id: str, result: dict[str, Any] | None = None) -> None:
        self._close(job_id, JOB_DONE, result=result)

    def fail_job(self, job_id: str, error: str) -> None:
        self._close(job_id, JOB_FAILED, error=error)

    def _close(self, job_id: str, status: str, result=None, error=None) -> None:
        with self._lock:
            job = self._jobs[job_id]
            job.status = status
            if result is not None:
                job.result = result
            if error is not None:
                job.error = error
            subs = list(self._subscribers.get(job_id, []))
        for q in subs:
            q.put(None)   # 哨兵：流结束

    # ------------------------------------------------------------------ SSE 订阅
    def subscribe(self, job_id: str) -> queue.Queue:
        """订阅任务事件：先回放历史事件，再实时接收；任务已结束则补哨兵."""
        q: queue.Queue = queue.Queue()
        with self._lock:
            job = self._jobs.get(job_id)
            if job is not None:
                for ev in job.events:
                    q.put(ev)
                if job.status in (JOB_DONE, JOB_FAILED):
                    q.put(None)
                else:
                    self._subscribers.setdefault(job_id, []).append(q)
            else:
                q.put(None)
        return q

    def unsubscribe(self, job_id: str, q: queue.Queue) -> None:
        with self._lock:
            subs = self._subscribers.get(job_id, [])
            if q in subs:
                subs.remove(q)

    # ------------------------------------------------------------------ 资产登记
    def put_ruleset(self, ruleset, cards=None) -> str:
        with self._lock:
            ruleset_id = uuid.uuid4().hex[:12]
            self.rulesets[ruleset_id] = ruleset
            if cards is not None:
                self.cards[ruleset_id] = cards
            return ruleset_id

    def put_data_source(self, meta: dict) -> str:
        with self._lock:
            ds_id = uuid.uuid4().hex[:12]
            self.data_sources[ds_id] = meta
            return ds_id


_STORE: JobStore | None = None
_STORE_LOCK = threading.Lock()


def get_store() -> JobStore:
    """进程级单例（uvicorn --reload 下每个进程各一份，演示足够）."""
    global _STORE
    with _STORE_LOCK:
        if _STORE is None:
            _STORE = JobStore()
        return _STORE
