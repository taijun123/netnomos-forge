# -*- coding: utf-8 -*-
"""Runtime preflight checks for local demo workflows.

The checks are intentionally best-effort. By default they report local runtime
state without starting Ollama or warming models; explicit ``--warm`` keeps the
older model readiness behavior. Failures are returned as status messages so a
workflow can continue through its deterministic fallback path.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

DEFAULT_MODELS = ("qwen2.5:14b-instruct", "gemma3:27b")
_CACHE: dict[str, Any] = {"at": 0.0, "result": None}


def _truthy(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int, minimum: int = 0) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return max(minimum, int(raw))
    except ValueError:
        return default


def _ollama_host() -> str:
    host = os.getenv("FORGE_OLLAMA_HOST") or os.getenv("OLLAMA_HOST") or "http://127.0.0.1:11434"
    host = host.strip().rstrip("/")
    if "://" not in host:
        host = f"http://{host}"
    return host


def _models_from_env() -> list[str]:
    raw = os.getenv("FORGE_PREFLIGHT_MODELS")
    if not raw:
        return list(DEFAULT_MODELS)
    models = [item.strip() for item in raw.split(",") if item.strip()]
    return models or list(DEFAULT_MODELS)


def _http_json(url: str, *, method: str = "GET", payload: dict[str, Any] | None = None,
               timeout: float = 5.0) -> dict[str, Any]:
    data = None
    headers: dict[str, str] = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = Request(url, data=data, headers=headers, method=method)
    with urlopen(req, timeout=timeout) as resp:  # noqa: S310 - local Ollama endpoint
        text = resp.read().decode("utf-8", errors="replace")
    return json.loads(text or "{}")


def _ollama_ready(host: str, timeout: float = 2.0) -> bool:
    try:
        _http_json(f"{host}/api/tags", timeout=timeout)
        return True
    except Exception:
        return False


def _start_ollama(messages: list[str]) -> bool:
    if not _truthy("FORGE_PREFLIGHT_START_OLLAMA", True):
        messages.append("Ollama 未连通，按配置不自动启动。")
        return False
    binary = shutil.which("ollama")
    if not binary:
        messages.append("未找到 ollama 命令；LLM 将使用可用兜底后端。")
        return False
    log_dir = Path(os.getenv("FORGE_PREFLIGHT_LOG_DIR", "logs"))
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        out = (log_dir / "ollama-preflight.out.log").open("ab")
        err = (log_dir / "ollama-preflight.err.log").open("ab")
        kwargs: dict[str, Any] = {
            "stdout": out,
            "stderr": err,
            "stdin": subprocess.DEVNULL,
        }
        if os.name == "nt":
            kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        subprocess.Popen([binary, "serve"], **kwargs)  # noqa: S603 - local configured binary
        messages.append("Ollama 未运行，已尝试后台启动 ollama serve。")
        return True
    except Exception as exc:
        messages.append(f"Ollama 自动启动失败：{exc}；LLM 将使用可用兜底后端。")
        return False


def _wait_for_ollama(host: str, messages: list[str]) -> bool:
    deadline = time.time() + _env_int("FORGE_PREFLIGHT_OLLAMA_WAIT_SECONDS", 30, minimum=1)
    while time.time() < deadline:
        if _ollama_ready(host):
            messages.append(f"Ollama 服务可用：{host}")
            return True
        time.sleep(1)
    messages.append(f"Ollama 服务仍不可用：{host}；LLM 将使用可用兜底后端。")
    return False


def _installed_models(host: str) -> set[str]:
    payload = _http_json(f"{host}/api/tags", timeout=5)
    return {str(item.get("model") or item.get("name") or "") for item in payload.get("models", [])}


def _loaded_models(host: str) -> set[str]:
    try:
        payload = _http_json(f"{host}/api/ps", timeout=5)
    except Exception:
        return set()
    return {str(item.get("model") or item.get("name") or "") for item in payload.get("models", [])}


def _pull_model(model: str, messages: list[str]) -> None:
    if not _truthy("FORGE_PREFLIGHT_AUTO_PULL", False):
        messages.append(f"Ollama 模型未安装：{model}；未启用自动 pull。")
        return
    binary = shutil.which("ollama")
    if not binary:
        messages.append(f"Ollama 模型未安装：{model}；缺少 ollama 命令，无法自动 pull。")
        return
    timeout = _env_int("FORGE_PREFLIGHT_PULL_TIMEOUT", 1800, minimum=60)
    proc = subprocess.run(  # noqa: S603 - local configured binary
        [binary, "pull", model],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )
    if proc.returncode == 0:
        messages.append(f"Ollama 模型自动 pull 完成：{model}")
    else:
        tail = (proc.stderr or proc.stdout or "")[-300:]
        messages.append(f"Ollama 模型自动 pull 失败：{model}：{tail}")


def _warm_model(host: str, model: str, messages: list[str]) -> bool:
    keep_alive = os.getenv("FORGE_PREFLIGHT_KEEP_ALIVE", "30m")
    timeout = _env_int("FORGE_PREFLIGHT_MODEL_TIMEOUT", 360, minimum=10)
    payload = {
        "model": model,
        "prompt": "READY",
        "stream": False,
        "keep_alive": keep_alive,
        "options": {"num_predict": 1, "temperature": 0},
    }
    try:
        _http_json(f"{host}/api/generate", method="POST", payload=payload, timeout=timeout)
        messages.append(f"Ollama 模型已预热：{model}（keep_alive={keep_alive}）")
        return True
    except Exception as exc:
        messages.append(f"Ollama 模型预热失败：{model}：{exc}")
        return False


def _gpu_messages() -> list[str]:
    binary = shutil.which("nvidia-smi")
    if not binary:
        return ["未找到 nvidia-smi；跳过 GPU/显存探测。"]
    try:
        proc = subprocess.run(  # noqa: S603 - local nvidia-smi
            [
                binary,
                "--query-gpu=index,name,memory.used,memory.total,utilization.gpu",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
        )
    except Exception as exc:
        return [f"GPU/显存探测失败：{exc}"]
    if proc.returncode != 0:
        return [f"GPU/显存探测失败：{(proc.stderr or proc.stdout).strip()[:300]}"]
    lines = [line.strip() for line in (proc.stdout or "").splitlines() if line.strip()]
    if not lines:
        return ["nvidia-smi 未返回 GPU 信息。"]
    formatted = []
    for line in lines:
        parts = [part.strip() for part in line.split(",")]
        if len(parts) >= 5:
            idx, name, used, total, util = parts[:5]
            formatted.append(f"GPU{idx} {name}: {used}/{total} MiB, util {util}%")
        else:
            formatted.append(line)
    return ["GPU/显存状态：" + "；".join(formatted)]


def run_runtime_preflight(
    *,
    scenario: str = "workflow",
    warm_models: bool = False,
    include_gpu: bool = True,
    use_cache: bool = True,
) -> dict[str, Any]:
    """Run best-effort local runtime checks and return structured messages."""
    if os.getenv("PYTEST_CURRENT_TEST") and not _truthy("FORGE_PREFLIGHT_IN_TESTS", False):
        return {
            "ok": True,
            "scenario": scenario,
            "messages": ["runtime preflight: pytest 环境跳过 Ollama/GPU 重预热。"],
        }

    cache_seconds = _env_int("FORGE_PREFLIGHT_CACHE_SECONDS", 20, minimum=0)
    now = time.time()
    if use_cache and cache_seconds and _CACHE["result"] and now - float(_CACHE["at"]) < cache_seconds:
        cached = dict(_CACHE["result"])
        cached["messages"] = ["runtime preflight: 复用最近一次环境检查结果。"] + list(cached["messages"])
        return cached

    messages: list[str] = [f"runtime preflight: scenario={scenario}，开始检查 Ollama / 模型 / GPU。"]
    host = _ollama_host()
    ok = True

    if warm_models:
        if not _ollama_ready(host):
            _start_ollama(messages)
        ollama_ok = _wait_for_ollama(host, messages)
        ok = ok and ollama_ok
    else:
        ollama_ok = _ollama_ready(host)
        if ollama_ok:
            messages.append(f"Ollama service available at {host}; model warmup skipped.")
        else:
            messages.append(
                f"Ollama service is not running at {host}; warmup skipped, LLM jobs will start it on demand."
            )

    if ollama_ok and warm_models:
        models = _models_from_env()
        try:
            installed = _installed_models(host)
        except Exception as exc:
            installed = set()
            messages.append(f"Ollama 模型列表读取失败：{exc}")
            ok = False
        loaded_before = _loaded_models(host)
        for model in models:
            if model not in installed:
                _pull_model(model, messages)
                try:
                    installed = _installed_models(host)
                except Exception:
                    installed = set()
            if model not in installed:
                ok = False

        loaded_before = _loaded_models(host)
        for model in models:
            if model in loaded_before:
                messages.append(f"Ollama 模型已在内存中：{model}")

        warm_passes = _env_int("FORGE_PREFLIGHT_WARM_PASSES", 2, minimum=1)
        for pass_index in range(warm_passes):
            loaded_now = _loaded_models(host)
            missing = [model for model in models if model in installed and model not in loaded_now]
            if not missing:
                break
            if pass_index > 0:
                messages.append(
                    "Ollama 驻留模型二次对齐："
                    + "、".join(missing)
                )
            for model in missing:
                ok = _warm_model(host, model, messages) and ok

        loaded_after = sorted(_loaded_models(host))
        if loaded_after:
            messages.append("Ollama 当前驻留模型：" + "、".join(loaded_after))
        missing_after = [model for model in models if model not in loaded_after]
        if missing_after:
            ok = False
            messages.append(
                "Ollama 目标模型仍未全部驻留："
                + "、".join(missing_after)
                + "；后续 LLM 调用会按需加载或走兜底链路。"
            )

    if include_gpu:
        messages.extend(_gpu_messages())

    result = {"ok": ok, "scenario": scenario, "messages": messages}
    _CACHE.update({"at": now, "result": result})
    return result


def emit_preflight_events(emit, *, scenario: str, warm_models: bool = False) -> dict[str, Any]:
    """Emit workflow-compatible control events for runtime preflight."""
    from forge.contracts import WorkflowEvent  # noqa: PLC0415

    result = run_runtime_preflight(scenario=scenario, warm_models=warm_models)
    for message in result["messages"]:
        emit(WorkflowEvent.make("control", "done", message))
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check local NetNomos Forge runtime dependencies.")
    parser.add_argument("--scenario", default="host", help="Label shown in the preflight output.")
    parser.add_argument("--warm", action="store_true", help="Start Ollama if needed and warm demo models.")
    parser.add_argument("--no-warm", action="store_true", help="Do not warm Ollama models.")
    parser.add_argument("--no-gpu", action="store_true", help="Skip nvidia-smi probing.")
    parser.add_argument("--no-cache", action="store_true", help="Ignore in-process cache.")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero if Ollama/model preflight is degraded.")
    args = parser.parse_args(argv)

    result = run_runtime_preflight(
        scenario=args.scenario,
        warm_models=args.warm and not args.no_warm,
        include_gpu=not args.no_gpu,
        use_cache=not args.no_cache,
    )
    for message in result["messages"]:
        print(message)
    return 0 if result["ok"] or not args.strict else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
