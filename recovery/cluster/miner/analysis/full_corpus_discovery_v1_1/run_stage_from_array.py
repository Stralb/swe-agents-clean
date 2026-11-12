from __future__ import annotations
import os
import subprocess
from pathlib import Path

stages = [x for x in os.environ.get('STAGES','').split(':') if x]
task = int(os.environ.get('SLURM_ARRAY_TASK_ID','0'))
if task < 0 or task >= len(stages):
    raise SystemExit(f'BAD_ARRAY_TASK_ID task={task} stages={stages}')
stage = stages[task]
analysis_dir = Path(os.environ['ANALYSIS_DIR'])
runroot = Path(os.environ['RUNROOT'])
repo = Path(os.environ['REPO'])
python_bin = os.environ.get('PYTHON_BIN','python3')
cmd = [python_bin, str(analysis_dir/'discovery.py'), '--stage', stage, '--runroot', str(runroot)]
if stage == 'extract':
    cmd += ['--db', os.environ['DB'], '--repo', str(repo)]
print('RUNNING_STAGE=' + stage, flush=True)
print('COMMAND=' + ' '.join(cmd), flush=True)
subprocess.run(cmd, check=True)
