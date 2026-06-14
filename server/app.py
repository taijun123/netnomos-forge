# -*- coding: utf-8 -*-
"""server.app — FastAPI 应用工厂（全懒加载，沙箱 import 本模块不报错）.

fastapi/uvicorn 仅在 create_app() 内部 import：沙箱（无 fastapi）可以安全
import server.app 并测试 pipeline/store；宿主机执行::

    uv run uvicorn server.app:create_app --factory --port 8000 --reload

实现 contracts API_* 全部 7 个端点；SSE 用 StreamingResponse + 内存队列
（store.subscribe 提供"历史回放 + 实时推送"合并流）；CORS 放开
http://localhost:5173（web 前端 dev server）。
"""
from __future__ import annotations

import json
import logging
import os
import threading
import uuid
from dataclasses import asdict
from pathlib import Path
from typing import Any

from forge.contracts import (
    API_CHAT_CONSTRAINED,
    API_DATA_SOURCES,
    API_REPORTS_GENERATE,
    API_RULESET_CARDS,
    API_RULESETS_LEARN,
    API_RULESETS_UPLOAD,
    API_WORKFLOW_EVENTS,
)
from server.pipeline import (
    SEQUENCE_PIPELINES,
    run_finance_pipeline,
    run_network_pipeline,
    run_office_demo_pipeline,
)
from server.store import JOB_DONE, JOB_FAILED, get_store

log = logging.getLogger("server.app")

# SSE 队列空轮询超时（秒）：超时发心跳注释行，保持连接
SSE_POLL_TIMEOUT = 2.0
# CORS 白名单
CORS_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]
UPLOADS_DIR = Path(__file__).resolve().parents[1] / "demo_artifacts" / "uploads"

_SCENARIO_PIPELINES = {
    "finance_v1": run_finance_pipeline,
    "network_cidds": run_network_pipeline,
    "network_pcap": run_network_pipeline,
    "office_demo": run_office_demo_pipeline,
}
LEARN_REQUEST_FIELDS = (
    "dataSourceId",
    "trainingDataSourceId",
    "validationDataSourceId",
    "question",
    "reportPrompt",
)


def _make_llm():
    """RoutedLLM：宿主机自动探测 ollama/codex，沙箱降级 mock（确定性）."""
    from forge.core.llm import RoutedLLM  # noqa: PLC0415
    return RoutedLLM()


def _start_job(
    scenario: str,
    sequence: str = "",
    request_params: dict[str, Any] | None = None,
) -> str:
    """后台线程跑管线，事件写入 store；返回 job_id."""
    store = get_store()
    job = store.create_job(scenario, sequence, request_params=request_params)
    pipeline = _SCENARIO_PIPELINES.get(scenario, run_finance_pipeline)

    def _run() -> None:
        try:
            result = pipeline(job, lambda ev: store.append_event(job.job_id, ev),
                              llm=_make_llm())
            # 登记规则集/卡片/报告，供 cards 与 chat 端点复用
            ruleset_id = store.put_ruleset(result.get("ruleset"),
                                           result.get("cards"))
            dual = result.get("dual")
            if dual is not None:
                store.last_dual[scenario] = dual
            vreport = result.get("vreport")
            violations = [asdict(v) for v in getattr(vreport, "violations", [])]
            if not violations and dual is not None:
                violations = [asdict(v) for v in dual.track_a.violations]
            ruleset = result.get("ruleset")
            request_snapshot = dict(job.request_params)
            office_state = result.get("office_state")
            if office_state is not None:
                store.last_office_state = office_state
            job_result = {
                "ruleset_id": ruleset_id,
                "dual": asdict(dual) if dual is not None else None,
                "cards": [asdict(c) for c in (result.get("cards") or [])],
                "rules": [asdict(r) for r in getattr(ruleset, "rules", [])],
                "violations": violations,
                "office": result.get("office"),
                "office_state": office_state,
                "agents": result.get("agents"),
                "ruleGroups": result.get("ruleGroups"),
                "dataSources": result.get("dataSources"),
                "data_source": result.get("data_source"),
                "dataSource": result.get("data_source"),
                "artifacts": result.get("artifacts"),
                "workflowEvents": result.get("workflowEvents"),
                "request": request_snapshot,
                "requestParams": request_snapshot,
            }
            store.finish_job(job.job_id, job_result)
        except Exception as exc:
            log.exception("管线失败：%s", exc)
            store.fail_job(job.job_id, str(exc))

    threading.Thread(target=_run, daemon=True).start()
    return job.job_id


def _safe_upload_name(filename: str) -> str:
    """Keep user filenames displayable while preventing path traversal."""
    raw = Path(filename or "uploaded.dat").name
    safe = "".join(ch if ch.isalnum() or ch in "._-()[] " else "_" for ch in raw).strip()
    return safe or "uploaded.dat"


def create_app():
    """FastAPI 工厂（fastapi 懒加载）。"""
    from forge.utils.logging_config import setup_logging  # noqa: PLC0415

    setup_logging(
        level=os.getenv("LOG_LEVEL", "INFO"),
        log_dir=os.getenv("LOG_DIR", "logs"),
        json_format=os.getenv("LOG_JSON", "false").lower() == "true",
        max_bytes=int(os.getenv("LOG_MAX_BYTES", str(10 * 1024 * 1024))),
        backup_count=int(os.getenv("LOG_BACKUP_COUNT", "5")),
        console_level=os.getenv("LOG_CONSOLE_LEVEL"),
    )
    global log
    log = logging.getLogger("server.app")
    log.info("NetNomos Forge app initializing")

    try:
        from fastapi import FastAPI, HTTPException, Request          # noqa: PLC0415
        from fastapi.middleware.cors import CORSMiddleware           # noqa: PLC0415
        from fastapi.responses import StreamingResponse              # noqa: PLC0415
    except Exception as exc:  # pragma: no cover - 沙箱无 fastapi
        raise RuntimeError(
            "无法导入 fastapi。当前环境（如沙箱）无外网 pip，请在宿主机操作：\n"
            "  1. cd <workspace>/netnomos-forge && uv sync\n"
            "  2. uv run uvicorn server.app:create_app --factory --port 8000 --reload\n"
            "（或直接执行 scripts/host/run_server.ps1）") from exc

    # With postponed annotations, FastAPI resolves "Request" from endpoint
    # globals, not this factory's locals.
    globals()["Request"] = Request

    app = FastAPI(title="netnomos-forge orchestrator", version="0.1.0")
    app.add_middleware(
        CORSMiddleware, allow_origins=CORS_ORIGINS, allow_credentials=True,
        allow_methods=["*"], allow_headers=["*"])
    store = get_store()

    # ------------------------------------------------------------- 数据源上传
    @app.post(API_DATA_SOURCES)
    async def upload_data_source(request: Request) -> dict[str, Any]:
        """登记或上传数据源。

        - JSON：{scenario, filename?, note?}，只登记元信息；
        - multipart/form-data：scenario、note、file，保存文件到 demo_artifacts/uploads。
        """
        content_type = request.headers.get("content-type", "")
        if "multipart/form-data" in content_type:
            form = await request.form()
            upload = form.get("file")
            scenario = str(form.get("scenario") or "finance_v1")
            note = str(form.get("note") or "")
            if upload is None or not hasattr(upload, "read"):
                raise HTTPException(400, "缺少上传文件 file")
            filename = _safe_upload_name(str(getattr(upload, "filename", "") or "uploaded.dat"))
            data = await upload.read()
            if not data:
                raise HTTPException(400, "上传文件为空")
            target_dir = UPLOADS_DIR / scenario
            target_dir.mkdir(parents=True, exist_ok=True)
            stored_name = f"{uuid.uuid4().hex[:8]}-{filename}"
            target_path = target_dir / stored_name
            target_path.write_bytes(data)
            ds_id = store.put_data_source({
                "scenario": scenario,
                "filename": filename,
                "stored_filename": stored_name,
                "path": str(target_path),
                "size": len(data),
                "content_type": str(getattr(upload, "content_type", "") or ""),
                "note": note,
            })
            return {
                "dataSourceId": ds_id,
                "filename": filename,
                "path": str(target_path),
                "size": len(data),
            }

        try:
            payload = await request.json()
        except Exception:
            payload = {}
        ds_id = store.put_data_source({
            "scenario": payload.get("scenario", "finance_v1"),
            "filename": payload.get("filename", ""),
            "note": payload.get("note", ""),
        })
        return {"dataSourceId": ds_id, "filename": payload.get("filename", "")}

    # ------------------------------------------------------------- 规则集上传
    @app.post(API_RULESETS_UPLOAD)
    async def upload_ruleset(request: Request) -> dict[str, Any]:
        """上传/选择规则集：{scenario, rules_path?}。

        rules_path 为 NetNomos 格式 rules.json 的服务器本地路径（演示用）；
        缺省时按场景加载默认规则（财务 manual_rules.json 为人工领域规则；
        网络 golden_cidds 为 NetNomos 自发现归档规则）。
        """
        from forge.contracts import RuleSet                       # noqa: PLC0415
        from forge.core.engine import ForgeRuleEngine             # noqa: PLC0415
        from server.pipeline import FIN_MANUAL_RULES, GOLDEN_CIDDS_RULES  # noqa: PLC0415

        try:
            payload = await request.json()
        except Exception:
            payload = {}
        scenario = payload.get("scenario", "finance_v1")
        default = (FIN_MANUAL_RULES if scenario == "finance_v1"
                   else GOLDEN_CIDDS_RULES)
        rules_path = payload.get("rules_path") or str(default)
        engine = ForgeRuleEngine.from_scenario(
            "finance_v1" if scenario == "finance_v1" else "network_cidds")
        try:
            if scenario == "finance_v1":
                ruleset = engine.add_manual_rules(
                    RuleSet(scenario=scenario, rules=[]), rules_path)
            else:
                ruleset = engine.load_netnomos_rules(rules_path)
        except FileNotFoundError as exc:
            raise HTTPException(404, f"规则文件不存在：{rules_path}") from exc
        cards = engine.explain(ruleset, llm=None)
        ruleset_id = store.put_ruleset(ruleset, cards)
        return {"rulesetId": ruleset_id, "ruleCount": len(ruleset.rules)}

    # ------------------------------------------------------------- 触发 learn
    @app.post(API_RULESETS_LEARN)
    async def learn(request: Request) -> dict[str, Any]:
        """触发学习管线（后台线程），返回 job_id；事件经 SSE 流消费。"""
        try:
            payload = await request.json()
        except Exception:
            payload = {}
        scenario = payload.get("scenario", "finance_v1")
        if scenario not in _SCENARIO_PIPELINES:
            raise HTTPException(400, f"未知场景：{scenario}")
        request_params = {
            key: payload[key]
            for key in LEARN_REQUEST_FIELDS
            if key in payload and payload[key] is not None
        }
        job_id = _start_job(scenario, payload.get("sequence", ""),
                            request_params=request_params)
        return {"jobId": job_id, "status": "running", "request": request_params}

    # ------------------------------------------------------------- 规则卡
    @app.get(API_RULESET_CARDS)
    async def ruleset_cards(ruleset_id: str) -> dict[str, Any]:
        if ruleset_id not in store.rulesets:
            raise HTTPException(404, f"规则集不存在：{ruleset_id}")
        cards = store.cards.get(ruleset_id, [])
        return {"rulesetId": ruleset_id,
                "cards": [asdict(c) for c in cards]}

    # ------------------------------------------------------------- 双轨报告
    @app.post(API_REPORTS_GENERATE)
    async def generate_report(request: Request) -> dict[str, Any]:
        """同步生成双轨报告（演示数据规模小，秒级）；事件同样写入 job 流。"""
        try:
            payload = await request.json()
        except Exception:
            payload = {}
        scenario = payload.get("scenario", "finance_v1")
        pipeline = _SCENARIO_PIPELINES.get(scenario)
        if pipeline is None:
            raise HTTPException(400, f"未知场景：{scenario}")
        job = store.create_job(scenario, "report")
        try:
            result = pipeline(job, lambda ev: store.append_event(job.job_id, ev),
                              llm=_make_llm())
        except Exception as exc:
            store.fail_job(job.job_id, str(exc))
            raise HTTPException(500, f"报告生成失败：{exc}") from exc
        if scenario == "office_demo":
            office_state = result.get("office_state")
            if office_state is not None:
                store.last_office_state = office_state
            payload = {
                "office": result.get("office"),
                "office_state": office_state,
                "agents": result.get("agents"),
                "ruleGroups": result.get("ruleGroups"),
                "dataSources": result.get("dataSources"),
                "artifacts": result.get("artifacts"),
                "workflowEvents": result.get("workflowEvents"),
            }
            store.finish_job(job.job_id, payload)
            return {"jobId": job.job_id, **payload}
        dual = result["dual"]
        store.last_dual[scenario] = dual
        store.finish_job(job.job_id, {"dual": asdict(dual)})
        return {"jobId": job.job_id, "report": asdict(dual)}

    # ------------------------------------------------------------- SSE 事件流
    @app.get(API_WORKFLOW_EVENTS)
    async def workflow_events(sequence: str = "", job_id: str = ""):
        """SSE：?job_id= 续接已有任务；?sequence=learn-finance 等启动新管线。

        事件格式与 contracts.WorkflowEvent.to_sse() 一致
        （event: workflow + JSON data），前端 events.ts 直接消费。
        """
        if not job_id:
            scenario = SEQUENCE_PIPELINES.get(
                sequence, ("finance_v1", None))[0]
            job_id = _start_job(scenario, sequence)
        q = store.subscribe(job_id)

        def _stream():
            import queue as _queue                      # noqa: PLC0415
            try:
                yield (f"event: job\ndata: "
                       f"{json.dumps({'jobId': job_id, 'job_id': job_id}, ensure_ascii=False)}\n\n")
                while True:
                    try:
                        item = q.get(timeout=SSE_POLL_TIMEOUT)
                    except _queue.Empty:
                        yield ": ping\n\n"              # 心跳，保持连接
                        job = store.get_job(job_id)
                        if job is None or job.status in (JOB_DONE, JOB_FAILED):
                            break
                        continue
                    if item is None:                    # 哨兵：任务结束
                        break
                    yield item.to_sse()
            finally:
                store.unsubscribe(job_id, q)

        return StreamingResponse(
            _stream(), media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    # ------------------------------------------------------------- Job 查询
    @app.get("/api/jobs/{job_id}")
    async def get_job(job_id: str) -> dict[str, Any]:
        """前端运行态辅助接口：查询 SSE job 的状态、历史事件与最终产物。

        这是 Web 工作台的 job 结果查询接口，不改变 contracts.py 冻结的核心契约。
        """
        job = store.get_job(job_id)
        if job is None:
            raise HTTPException(404, f"任务不存在：{job_id}")
        return {
            "jobId": job.job_id,
            "job_id": job.job_id,
            "scenario": job.scenario,
            "sequence": job.sequence,
            "status": job.status,
            "createdAt": job.created_at,
            "created_at": job.created_at,
            "request": job.request_params,
            "requestParams": job.request_params,
            "events": [asdict(ev) for ev in job.events],
            "result": job.result,
            "error": job.error,
        }

    # ------------------------------------------------------------- 受约束聊天
    @app.post(API_CHAT_CONSTRAINED)
    async def chat_constrained(request: Request) -> dict[str, Any]:
        """受约束聊天：llm 起草回复 → 对回复中数值做财务规则校验。

        校验口径：回复中出现的数值必须命中最近一次 B 轨报告的槽位白名单
        （即程序回填的合规数值）；白名单之外的数字标记为"未经核实"，
        并附上修正建议。mock 后端下同样可用（回复为确定性模板）。
        """
        from forge.core.reporter import extract_number_tokens  # noqa: PLC0415

        try:
            payload = await request.json()
        except Exception:
            payload = {}
        message = str(payload.get("message", ""))
        scenario = payload.get("scenario", "finance_v1")
        if scenario == "office_demo":
            from forge.scenarios.office_demo import summarize_office_chat  # noqa: PLC0415
            chat = summarize_office_chat(message, store.last_office_state)
            content = chat["content"]
            return {
                "messageId": uuid.uuid4().hex[:12],
                "content": content,
                "reply": content,
                "constrained": True,
                "matchedRules": chat["matchedRules"],
                "citations": chat["citations"],
                "flagged_numbers": [],
                "checks": ["office_demo response grounded in cached backend state"],
                "backend": "office_demo",
            }
        llm = _make_llm()
        system = ("你是财务合规助理。回答问题时引用的数值必须可溯源；"
                  "不确定的数字请不要编造。")
        try:
            reply = llm.complete(message, role="draft", system=system)
        except Exception as exc:
            reply = f"[降级回复] LLM 不可用（{exc}），请改用规则库查询。"

        # 数值白名单：最近一次 B 轨槽位
        dual = store.last_dual.get(scenario)
        whitelist: set[str] = set()
        if dual is not None:
            for value in dual.track_b.slots.values():
                whitelist |= extract_number_tokens(str(value))
        flagged = sorted(t for t in extract_number_tokens(reply)
                         if t not in whitelist)
        checks = ([f"数值 {t} 不在 B 轨合规槽位白名单中，已标记为未经核实"
                   for t in flagged]
                  if whitelist else
                  ["尚未生成 B 轨报告，暂无数值白名单（先调用 "
                   f"{API_REPORTS_GENERATE}）"])
        if flagged and whitelist:
            reply += ("\n\n> ⚠ 合规提示：以上回复中数值 "
                      + "、".join(flagged)
                      + " 未命中合规报告槽位白名单，请以 B 轨报告为准。")
        return {"reply": reply, "flagged_numbers": flagged,
                "checks": checks,
                "backend": llm.resolve_backend("draft")}

    @app.get("/api/health")
    async def health() -> dict[str, Any]:
        return {"status": "ok", "jobs": len(store._jobs)}  # noqa: SLF001

    return app


def _self_check() -> str:  # pragma: no cover - 手动冒烟
    """命令行冒烟：python -m server.app（不起 HTTP，仅验证管线）."""
    from server.store import get_store as _gs
    store = _gs()
    job = store.create_job("finance_v1", "smoke")
    events = []
    result = run_finance_pipeline(job, events.append)
    return json.dumps({
        "events": len(events),
        "violations": len(result["vreport"].violations),
        "diff_html_bytes": len(result["dual"].diff_html),
    }, ensure_ascii=False)


if __name__ == "__main__":  # pragma: no cover
    print(_self_check())
