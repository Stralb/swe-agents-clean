from __future__ import annotations

import json
import os
import signal
import subprocess
from typing import Any


def run_cmd(cmd, cwd=None, timeout=None, env=None):
    """Run a command and return a dict compatible with scanner callers.

    Compatibility keys:
      returncode: process exit code
      stdout: captured stdout
      stderr: captured stderr
      ok: True when returncode == 0 and not timed out
      timeout: True when command timed out
      timed_out: alias for timeout
      status: "ok", "error", or "timeout"
    """
    proc = subprocess.Popen(
        cmd,
        cwd=cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )

    try:
        stdout, stderr = proc.communicate(timeout=timeout)
        rc = proc.returncode
        timed_out = False
    except subprocess.TimeoutExpired:
        timed_out = True
        try:
            os.killpg(proc.pid, signal.SIGTERM)
            stdout, stderr = proc.communicate(timeout=20)
        except Exception:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except Exception:
                pass
            try:
                stdout, stderr = proc.communicate(timeout=10)
            except Exception:
                stdout, stderr = "", ""

        rc = -9
        stderr = (stderr or "") + f"\nCommand timed out after {timeout} seconds and process group was killed."

    stdout = stdout or ""
    stderr = stderr or ""

    if timed_out:
        status = "timeout"
    elif rc == 0:
        status = "ok"
    else:
        status = "error"

    return {
        "returncode": rc,
        "stdout": stdout,
        "stderr": stderr,
        "ok": rc == 0 and not timed_out,
        "timeout": timed_out,
        "timed_out": timed_out,
        "status": status,
    }


def parse_json_maybe(text: str | bytes | None, default: Any = None) -> Any:
    if text is None:
        return default

    if isinstance(text, bytes):
        text = text.decode("utf-8", errors="replace")

    text = text.strip()
    if not text:
        return default

    try:
        return json.loads(text)
    except Exception:
        return default
