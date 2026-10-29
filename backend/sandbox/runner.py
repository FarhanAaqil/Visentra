"""Parent side of the model sandbox.

Every job starts a fresh ``python -I -B worker.py`` process with a minimal
environment, feeds it one JSON request on stdin and waits for one JSON reply,
killing it if the wall-clock budget runs out. The API process itself never
deserialises or executes an uploaded model.
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from backend.config import settings

WORKER = Path(__file__).resolve().parent / "worker.py"
_PASSTHROUGH_ENV = ("PATH", "SYSTEMROOT", "TEMP", "TMP", "LD_LIBRARY_PATH")


class SandboxError(RuntimeError):
    pass


def _command() -> list[str]:
    return [sys.executable, "-I", "-B", str(WORKER)]


def _env() -> dict[str, str]:
    env = {k: os.environ[k] for k in _PASSTHROUGH_ENV if k in os.environ}
    env["OMP_NUM_THREADS"] = "2"
    return env


def _request(op: str, model_path: Path, **extra: Any) -> bytes:
    job = {
        "op": op,
        "model": str(model_path),
        "framework": "onnx",
        "memory_mb": settings.sandbox_memory_mb,
        "cpu_s": int(settings.sandbox_timeout_s),
        **extra,
    }
    return json.dumps(job).encode()


def _parse(stdout: bytes, stderr: bytes, returncode: int | None) -> dict[str, Any]:
    try:
        reply = json.loads(stdout.decode() or "{}")
    except json.JSONDecodeError as e:
        raise SandboxError(f"worker returned malformed output (exit {returncode})") from e
    if not reply.get("ok"):
        tail = stderr.decode(errors="replace").strip().splitlines()[-1:] or [""]
        raise SandboxError(reply.get("error") or f"worker exited with {returncode}: {tail[0]}")
    return reply


async def run(op: str, model_path: Path, **extra: Any) -> dict[str, Any]:
    proc = await asyncio.create_subprocess_exec(
        *_command(),
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=_env(),
        cwd=str(model_path.parent),
    )
    try:
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(_request(op, model_path, **extra)), timeout=settings.sandbox_timeout_s
        )
    except TimeoutError as e:
        proc.kill()
        await proc.wait()
        raise SandboxError(f"sandbox exceeded its {settings.sandbox_timeout_s:.0f}s budget") from e
    return _parse(stdout, stderr, proc.returncode)


def run_sync(op: str, model_path: Path, **extra: Any) -> dict[str, Any]:
    """Blocking variant for scripts and the benchmark harness."""
    try:
        done = subprocess.run(
            _command(),
            input=_request(op, model_path, **extra),
            capture_output=True,
            env=_env(),
            cwd=str(model_path.parent),
            timeout=settings.sandbox_timeout_s,
            check=False,
        )
    except subprocess.TimeoutExpired as e:
        raise SandboxError(f"sandbox exceeded its {settings.sandbox_timeout_s:.0f}s budget") from e
    return _parse(done.stdout, done.stderr, done.returncode)
