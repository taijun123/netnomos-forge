# -*- coding: utf-8 -*-
"""On-demand Ollama lifecycle helpers for local demo jobs."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import threading
import time
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

DEFAULT_MODELS = ("qwen2.5:14b-instruct", "gemma3:27b")

_LOCK = threading.RLock()
_STARTED_BY_DEMO = False
_OLLAMA_PROC: subprocess.Popen | None = None


def _truthy(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _ollama_host(host: str | None = None) -> str:
    resolved = host or os.getenv("FORGE_OLLAMA_HOST") or os.getenv("OLLAMA_HOST") or "http://127.0.0.1:11434"
    resolved = resolved.strip().rstrip("/")
    if "://" not in resolved:
        resolved = f"http://{resolved}"
    return resolved


def _http_json(url: str, *, timeout: float = 2.0) -> dict[str, Any]:
    req = Request(url, method="GET")
    with urlopen(req, timeout=timeout) as resp:  # noqa: S310 - local Ollama endpoint
        text = resp.read().decode("utf-8", errors="replace")
    return json.loads(text or "{}")


def ollama_ready(host: str | None = None, *, timeout: float = 2.0) -> bool:
    try:
        _http_json(f"{_ollama_host(host)}/api/tags", timeout=timeout)
        return True
    except Exception:
        return False


def _start_env() -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("OLLAMA_NUM_PARALLEL", "1")
    env.setdefault("OLLAMA_MAX_LOADED_MODELS", "1")
    env.setdefault("OLLAMA_KEEP_ALIVE", "0")
    return env


def ensure_ollama_running(
    host: str | None = None,
    *,
    wait_seconds: float | None = None,
    log_dir: str | Path | None = None,
) -> bool:
    """Start ``ollama serve`` only when the local endpoint is unavailable."""
    global _OLLAMA_PROC, _STARTED_BY_DEMO

    resolved_host = _ollama_host(host)
    if ollama_ready(resolved_host):
        return True
    if not _truthy("FORGE_OLLAMA_AUTOSTART", True):
        return False

    binary = shutil.which("ollama")
    if not binary:
        return False

    with _LOCK:
        if ollama_ready(resolved_host):
            return True
        if _OLLAMA_PROC is None or _OLLAMA_PROC.poll() is not None:
            target_log_dir = Path(log_dir or os.getenv("FORGE_OLLAMA_LOG_DIR", "logs"))
            target_log_dir.mkdir(parents=True, exist_ok=True)
            out = (target_log_dir / "ollama-demo.out.log").open("ab")
            err = (target_log_dir / "ollama-demo.err.log").open("ab")
            kwargs: dict[str, Any] = {
                "stdout": out,
                "stderr": err,
                "stdin": subprocess.DEVNULL,
                "env": _start_env(),
            }
            if os.name == "nt":
                kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            _OLLAMA_PROC = subprocess.Popen([binary, "serve"], **kwargs)  # noqa: S603
            _STARTED_BY_DEMO = True

    deadline = time.time() + (wait_seconds if wait_seconds is not None else float(os.getenv("FORGE_OLLAMA_WAIT_SECONDS", "30")))
    while time.time() < deadline:
        if ollama_ready(resolved_host):
            return True
        time.sleep(0.5)
    return ollama_ready(resolved_host)


def stop_loaded_models(models: tuple[str, ...] | list[str] | None = None) -> None:
    if not ollama_ready(timeout=1.0):
        return
    binary = shutil.which("ollama")
    if not binary:
        return
    for model in models or DEFAULT_MODELS:
        try:
            subprocess.run(  # noqa: S603
                [binary, "stop", model],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=30,
            )
        except Exception:
            pass


def _shutdown_started_process_tree() -> None:
    global _OLLAMA_PROC
    proc = _OLLAMA_PROC
    if proc is None:
        return
    if proc.poll() is not None:
        _OLLAMA_PROC = None
        return
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True, timeout=15)
        else:
            proc.terminate()
            proc.wait(timeout=15)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass
    finally:
        _OLLAMA_PROC = None


def _shutdown_all_ollama_processes() -> None:
    if os.name == "nt":
        for image in ("ollama app.exe", "llama-server.exe", "ollama.exe"):
            try:
                subprocess.run(["taskkill", "/IM", image, "/F"], capture_output=True, timeout=15)
            except Exception:
                pass
    else:
        for pattern in ("llama-server", "ollama serve"):
            try:
                subprocess.run(["pkill", "-f", pattern], capture_output=True, timeout=15)
            except Exception:
                pass


def cleanup_ollama_after_job(
    *,
    models: tuple[str, ...] | list[str] | None = None,
    stop_service: bool | None = None,
) -> None:
    """Unload demo models, and optionally stop the Ollama service."""
    global _STARTED_BY_DEMO

    stop_loaded_models(models)
    should_stop_service = (
        _STARTED_BY_DEMO
        if stop_service is None
        else stop_service
    ) or _truthy("FORGE_OLLAMA_SHUTDOWN_AFTER_JOB", False)
    if not should_stop_service:
        return
    with _LOCK:
        _shutdown_started_process_tree()
        if _truthy("FORGE_OLLAMA_SHUTDOWN_AFTER_JOB", False):
            _shutdown_all_ollama_processes()
        _STARTED_BY_DEMO = False
