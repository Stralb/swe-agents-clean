from __future__ import annotations
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

analysis_dir = Path(os.environ['ANALYSIS_DIR']).resolve()
runroot = Path(os.environ['RUNROOT']).resolve()
repo = Path(os.environ['REPO']).resolve()
db = Path(os.environ['DB']).resolve()
python_bin = os.environ.get('PYTHON_BIN','python3')
worker = analysis_dir / 'worker.slurm'
logdir = runroot / 'logs'
logdir.mkdir(parents=True, exist_ok=True)

base_export = f'ALL,ANALYSIS_DIR={analysis_dir},RUNROOT={runroot},REPO={repo},DB={db},PYTHON_BIN={python_bin}'

def submit(name, stages, array=None, dependency=None, cpus=16, mem='64G', time='12:00:00'):
    exports = base_export + ',STAGES=' + ':'.join(stages)
    cmd = [
        'sbatch','--parsable',
        '--job-name',name,
        '--partition','biggpu',
        '--cpus-per-task',str(cpus),
        '--mem',mem,
        '--time',time,
        '--output',str(logdir / f'{name}-%A_%a.out'),
        '--error',str(logdir / f'{name}-%A_%a.err'),
        '--export',exports,
    ]
    if array is not None:
        cmd += ['--array', array]
    if dependency:
        cmd += ['--dependency', 'afterok:' + dependency]
    cmd.append(str(worker))
    out = subprocess.check_output(cmd, text=True).strip()
    print(f'SUBMITTED {name} {out}', flush=True)
    return out

# Phase 0: extraction then QC.
j0 = submit('fcdisc-p0-extract', ['extract'], array='0', cpus=16, mem='64G', time='08:00:00')
jq = submit('fcdisc-p0-quality', ['quality'], array='0', dependency=j0, cpus=8, mem='32G', time='03:00:00')

# Phase 1: primary MSR-style landscape/pattern/topology work in parallel.
j1 = submit(
    'fcdisc-p1-primary',
    ['landscape','signatures','patterns','topology'],
    array='0-3%4', dependency=jq, cpus=16, mem='64G', time='18:00:00'
)

# Phase 2: relationships, repository regimes, temporal structure, anomalies.
j2 = submit(
    'fcdisc-p2-structure',
    ['relationships','repository','temporal','anomalies'],
    array='0-3%4', dependency=j1, cpus=20, mem='72G', time='24:00:00'
)

# Phase 3: expensive secondary archetypes + optional text discovery.
j3 = submit(
    'fcdisc-p3-secondary',
    ['archetypes','text'],
    array='0-1%2', dependency=j2, cpus=32, mem='96G', time='2-12:00:00'
)

# Phase 4: deterministic report / checksums only after every phase passed.
j4 = submit('fcdisc-p4-report', ['report'], array='0', dependency=j3, cpus=8, mem='32G', time='04:00:00')

record = {
    'submitted_at': datetime.now(timezone.utc).isoformat(),
    'partition': 'biggpu',
    'runroot': str(runroot),
    'jobs': {
        'phase0_extract': j0,
        'phase0_quality': jq,
        'phase1_primary': j1,
        'phase2_structure': j2,
        'phase3_secondary': j3,
        'phase4_report': j4,
    }
}
(runroot/'00_manifest').mkdir(parents=True, exist_ok=True)
(runroot/'00_manifest'/'SUBMITTED_JOBS.json').write_text(json.dumps(record, indent=2), encoding='utf-8')
print('COORDINATOR_STATUS=SUBMITTED_FULL_DAG', flush=True)
print('FINAL_REPORT_JOB=' + j4, flush=True)
