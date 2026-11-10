from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

COMMON_EXPORTS = '''
cd /home-mscluster/$USER/new/malicious-issue-miner-rate-smart
source .venv/bin/activate
if [ -f .env.cluster ]; then source .env.cluster; fi
export PYTHONPATH=.
export CONFIG=${CONFIG:-config.yml}
export DB_PATH=${DB_PATH:-$PWD/data/miner.db}
export PATH="/home-mscluster/$USER/tools/go/bin:/home-mscluster/$USER/tools/bin:/home-mscluster/$USER/tools/node/bin:/home-mscluster/$USER/tools/codeql:$PATH"
export CODEQL_TMPDIR=${CODEQL_TMPDIR:-/tmp/$USER/codeql-$SLURM_JOB_ID}
export MINER_CODEQL_TMPDIR="$CODEQL_TMPDIR"
export GOCACHE=${GOCACHE:-/tmp/$USER/go-cache-$SLURM_JOB_ID}
export GOMODCACHE=${GOMODCACHE:-/tmp/$USER/go-modcache-$SLURM_JOB_ID}
mkdir -p "$CODEQL_TMPDIR" "$GOCACHE" "$GOMODCACHE"
echo "JOB=$SLURM_JOB_ID NODE=$(hostname) DB=$DB_PATH"
'''

COMMANDS = {
    "collect-pr-first": '''
export RETRIEVAL_MODE=downstream_first
export REQUIRE_HIGH_YIELD_SURFACE=false
export ISSUE_MIN_BODY_CHARS=0
export EXCLUDE_DOCS_SCOPE_ONLY=true
export ACTIVE_REPO_SEED=true
make collect
make methodology-profile
''',
    "evaluate-cheap": "make evaluate-cheap\nmake methodology-profile\nmake methodology-status\n",
    "evaluate-codeql": '''
codeql pack download codeql/go-queries || true
export CODEQL_RAM_MB=${CODEQL_RAM_MB:-48000}
export CODEQL_THREADS=${CODEQL_THREADS:-2}
make evaluate-codeql
make methodology-profile
make methodology-status
''',
    "status": "make methodology-status\nmake region-yield\n",
}


def main() -> None:
    ap = argparse.ArgumentParser(description="Write/submit cluster-safe Slurm jobs for the miner")
    ap.add_argument("mode", choices=COMMANDS)
    ap.add_argument("--partition", default=os.getenv("SLURM_PARTITION", "biggpu"))
    ap.add_argument("--time", default=os.getenv("SLURM_TIME", "08:00:00"))
    ap.add_argument("--mem", default=os.getenv("SLURM_MEM", "32G"))
    ap.add_argument("--cpus", default=os.getenv("SLURM_CPUS", "4"))
    ap.add_argument("--submit", action="store_true")
    args = ap.parse_args()
    out = ROOT / f"run_{args.mode.replace('-', '_')}.slurm"
    log = f"/home-mscluster/%u/miner_{args.mode}_%j.log"
    text = f"""#!/bin/bash
#SBATCH --job-name=miner-{args.mode}
#SBATCH --partition={args.partition}
#SBATCH --time={args.time}
#SBATCH --cpus-per-task={args.cpus}
#SBATCH --mem={args.mem}
#SBATCH --output={log}

set -euo pipefail
{COMMON_EXPORTS}
{COMMANDS[args.mode]}
"""
    out.write_text(text, encoding="utf-8")
    print(out)
    if args.submit:
        subprocess.run(["sbatch", str(out)], check=True)


if __name__ == "__main__":
    main()
