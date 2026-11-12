#!/usr/bin/env python3
"""Slurm worker-side command execution bridge. Run only within an isolated workspace.

Task files are immutable JSON messages written to inbox/*.json. Each command executes
once under the current worker identity. This runner does not grant privileges and
should NEVER run as an identity that can modify protected historical research.
"""
import json
import os
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(os.environ.get('WORKER_BRIDGE_ROOT', str(Path.home() / 'worker_bridge'))).resolve()
INBOX = BASE / 'inbox'
OUTBOX = BASE / 'outbox'
WORK = BASE / 'workspace'
STOP = BASE / 'STOP'
TASK_RE = re.compile(r'[a-zA-Z0-9][a-zA-Z0-9_-]{0,79}\.json\Z')
MAX_TASK_BYTES = 128 * 1024
MAX_OUTPUT_CHARS = 500000

def json_exclusive(path, data):
    with path.open('x', encoding='utf8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write('\n')

def now():
    return datetime.now(timezone.utc).isoformat()

def run(task_path):
    key = task_path.stem
    result = OUTBOX / (key + '.json')
    if result.exists():
        return
    try:
        if task_path.stat().st_size > MAX_TASK_BYTES:
            raise ValueError('Task is too large')
        task = json.loads(task_path.read_text(encoding='utf8'))
        if set(task) - {'command', 'timeout_seconds', 'cwd'}:
            raise ValueError('Unknown task keys')
        cmd = task.get('command')
        if not isinstance(cmd, str) or not cmd or len(cmd) > 100000:
            raise ValueError('Expected command string')
        timeout = int(task.get('timeout_seconds', 300))
        if not 1 <= timeout <= 3600:
            raise ValueError('timeout_seconds must be in 1..3600')
        cwd_rel = task.get('cwd', '.')
        if not isinstance(cwd_rel, str):
            raise ValueError('cwd must be a string')
        cwd = (WORK / cwd_rel).resolve()
        if not cwd.is_relative_to(WORK) or not cwd.is_dir():
            raise ValueError('Working directory must exist inside writable workspace')
        started = now()
        try:
            output = subprocess.run(['/bin/bash', '-lc', cmd], cwd=str(cwd),
                capture_output=True, text=True, errors='replace', timeout=timeout,
                env={**os.environ, 'HOME': str(WORK)})
            response = {'task_id': key, 'started_at': started, 'finished_at': now(),
                'exit_code': output.returncode, 'stdout': output.stdout[:MAX_OUTPUT_CHARS],
                'stderr': output.stderr[:MAX_OUTPUT_CHARS],
                'stdout_truncated': len(output.stdout) > MAX_OUTPUT_CHARS,
                'stderr_truncated': len(output.stderr) > MAX_OUTPUT_CHARS}
        except subprocess.TimeoutExpired as exc:
            response = {'task_id': key, 'started_at': started, 'finished_at': now(),
                'timed_out': True, 'error': str(exc)}
    except Exception as exc:
        response = {'task_id': key, 'finished_at': now(), 'error': str(exc)}
    json_exclusive(result, response)

def main():
    for p in (INBOX, OUTBOX, WORK):
        p.mkdir(parents=True, exist_ok=True)
    print(json.dumps({'status': 'ready', 'inbox': str(INBOX),
        'outbox': str(OUTBOX), 'workspace': str(WORK)}), flush=True)
    while not STOP.exists():
        for task in sorted(INBOX.iterdir()):
            if task.is_file() and TASK_RE.fullmatch(task.name):
                run(task)
        time.sleep(2)

if __name__ == '__main__':
    main()
