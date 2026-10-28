"""llama.cpp lifecycle and client.

One rule this module exists to enforce: never run the OCR model and the reasoning
model at the same time on this box. `load_phase()` is the only sanctioned way to
switch, and it restarts the reasoning server between long runs because of the
documented RSS leak (HANDOVER §8).
"""
from __future__ import annotations

import base64
import json
import os
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from . import config


# ---------------------------------------------------------------- http helpers

def _url(port: int, path: str) -> str:
    return f"http://127.0.0.1:{port}{path}"


def health(port: int = config.REASON_PORT, timeout: float = 2.0) -> bool:
    try:
        with urllib.request.urlopen(_url(port, "/health"), timeout=timeout) as r:
            return 200 <= r.status < 300
    except Exception:
        return False


def wait_ready(port: int, timeout: float = 240.0) -> bool:
    t0 = time.time()
    while time.time() - t0 < timeout:
        if health(port):
            return True
        time.sleep(1.0)
    return False


def chat(
    messages: list[dict],
    *,
    port: int = config.REASON_PORT,
    max_tokens: int = 768,
    temperature: float = config.TEMPERATURE,
    enable_thinking: bool = True,
    timeout: float = 900.0,
    model: str = "local",
) -> dict:
    """One completion. Returns text, reasoning, finish, ctok — the generation-time truth."""
    body = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "chat_template_kwargs": {"enable_thinking": enable_thinking},
    }
    req = urllib.request.Request(
        _url(port, "/v1/chat/completions"),
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            d = json.loads(r.read())
    except urllib.error.HTTPError as e:  # surface the server's message, not a bare 500
        raise RuntimeError(f"llama-server HTTP {e.code}: {e.read()[:400]!r}") from e
    ch = d["choices"][0]
    msg = ch.get("message") or {}
    return {
        "text": msg.get("content") or "",
        "reasoning": msg.get("reasoning_content") or "",
        "finish": ch.get("finish_reason"),
        "ctok": (d.get("usage") or {}).get("completion_tokens", 0),
    }


def chat_image(
    image_path: str | Path,
    prompt: str,
    *,
    port: int = config.OCR_PORT,
    max_tokens: int = 2048,
    temperature: float = 0.0,
    timeout: float = 1800.0,
) -> dict:
    """Vision completion against a MiniCPM-OCR server (mmproj loaded)."""
    p = Path(image_path)
    data = base64.b64encode(p.read_bytes()).decode()
    ext = p.suffix.lstrip(".").lower() or "png"
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/{ext};base64,{data}"}},
            ],
        }
    ]
    return chat(
        messages,
        port=port,
        max_tokens=max_tokens,
        temperature=temperature,
        enable_thinking=False,
        timeout=timeout,
    )


# ---------------------------------------------------------------- process mgmt

def _proc_cmdline(pid: int) -> str:
    try:
        raw = Path(f"/proc/{pid}/cmdline").read_bytes()
    except OSError:
        return ""
    return raw.replace(b"\0", b" ").decode("utf-8", "replace")


def pids_for_port(port: int) -> list[int]:
    found: list[int] = []
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        pid = int(entry.name)
        cmd = _proc_cmdline(pid)
        if "llama-server" in cmd and f"--port {port}" in cmd:
            found.append(pid)
    return found


def rss_mb(pid: int) -> float:
    try:
        for line in Path(f"/proc/{pid}/status").read_text().splitlines():
            if line.startswith("VmRSS:"):
                return int(line.split()[1]) / 1024
    except OSError:
        pass
    return 0.0


def server_rss_mb(port: int) -> float:
    return sum(rss_mb(p) for p in pids_for_port(port))


def stop_server(port: int, timeout: float = 20.0) -> None:
    pids = pids_for_port(port)
    for pid in pids:
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            pass
    t0 = time.time()
    while time.time() - t0 < timeout:
        if not pids_for_port(port):
            return
        time.sleep(0.5)
    for pid in pids_for_port(port):
        try:
            os.kill(pid, signal.SIGKILL)
        except OSError:
            pass


def _start(cmd: list[str], port: int, log_name: str) -> None:
    config.LOGS_DIR.mkdir(parents=True, exist_ok=True)
    log = open(config.LOGS_DIR / log_name, "ab", buffering=0)
    subprocess.Popen(
        cmd,
        cwd=str(config.LLAMA_DIR),
        stdout=log,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
    )
    if not wait_ready(port):
        raise RuntimeError(f"server on :{port} did not become healthy; see logs/{log_name}")


def reason_cmd(ctx: int | None = None, parallel: int | None = None) -> list[str]:
    ctx = ctx or config.REASON_CTX
    parallel = parallel or config.REASON_PARALLEL
    return [
        str(config.LLAMA_SERVER),
        "-m", str(config.REASON_GGUF),
        "-c", str(ctx),
        "-np", str(parallel),
        "-t", str(config.THREADS),
        "--jinja",
        "--no-reasoning-preserve",
        "--port", str(config.REASON_PORT),
    ]


def ocr_cmd(ctx: int | None = None) -> list[str]:
    ctx = ctx or config.OCR_CTX
    return [
        str(config.LLAMA_SERVER),
        "-m", str(config.OCR_GGUF),
        "--mmproj", str(config.OCR_MMPROJ),
        "-c", str(ctx),
        "-t", str(config.THREADS),
        "--n-gpu-layers", "0",
        "--jinja",
        "--port", str(config.OCR_PORT),
    ]


def ensure_reason(ctx: int | None = None, parallel: int | None = None) -> None:
    if health(config.REASON_PORT):
        return
    if not config.REASON_GGUF.exists():
        raise FileNotFoundError(f"reasoning weights missing: {config.REASON_GGUF}")
    _start(reason_cmd(ctx, parallel), config.REASON_PORT, "server_reason.log")


def ensure_ocr(ctx: int | None = None) -> None:
    if health(config.OCR_PORT):
        return
    for p in (config.OCR_GGUF, config.OCR_MMPROJ):
        if not p.exists():
            raise FileNotFoundError(f"OCR weights missing: {p}")
    _start(ocr_cmd(ctx), config.OCR_PORT, "server_ocr.log")


def restart_reason(ctx: int | None = None, parallel: int | None = None) -> None:
    stop_server(config.REASON_PORT)
    ensure_reason(ctx, parallel)


def load_phase(phase: str, *, ctx: int | None = None, parallel: int | None = None) -> None:
    """phase ∈ {'reason','ocr','none'}. Stops whatever is not needed."""
    if phase == "reason":
        stop_server(config.OCR_PORT)
        ensure_reason(ctx, parallel)
    elif phase == "ocr":
        stop_server(config.REASON_PORT)
        ensure_ocr(ctx)
    elif phase == "none":
        stop_server(config.REASON_PORT)
        stop_server(config.OCR_PORT)
    else:
        raise ValueError(f"unknown phase: {phase}")


def guard_rss(port: int = config.REASON_PORT, limit_mb: float | None = None) -> bool:
    """Restart the server if it has leaked past the limit. Returns True if restarted."""
    limit = limit_mb or config.RSS_LIMIT_MB
    if server_rss_mb(port) > limit:
        restart_reason()
        return True
    return False


def status() -> dict:
    return {
        "reason": {
            "port": config.REASON_PORT,
            "healthy": health(config.REASON_PORT),
            "pids": pids_for_port(config.REASON_PORT),
            "rss_mb": round(server_rss_mb(config.REASON_PORT), 1),
            "gguf": str(config.REASON_GGUF),
        },
        "ocr": {
            "port": config.OCR_PORT,
            "healthy": health(config.OCR_PORT),
            "pids": pids_for_port(config.OCR_PORT),
            "rss_mb": round(server_rss_mb(config.OCR_PORT), 1),
            "gguf": str(config.OCR_GGUF),
            "weights_present": config.OCR_GGUF.exists() and config.OCR_MMPROJ.exists(),
        },
    }


if __name__ == "__main__":
    print(json.dumps(status(), indent=2))
    sys.exit(0)
