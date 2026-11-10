#!/bin/bash
#SBATCH --job-name=E108_round4_framefix
#SBATCH --partition=stampede
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=00:35:00
set -euo pipefail
umask 077
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 PYTHONUNBUFFERED=1
D=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/e108_20261020_random_rounds
PY=/home-mscluster/astrauss/arc_rl_mechanics_killtest/.venv/bin/python
printf '%s  %s\n' c2abb7f4e770cfa0adb01a19573c2eaade11e4d221cc8734c92593107ede516c "$D/rerun_round4_snapshots.py" | sha256sum -c -
printf '%s  %s\n' b8c6a2ad760500ac51e7c789721c1dd4db00f28f5b09df259ef2cf6d52378d8e "$D/snapshot_adapter.py" | sha256sum -c -
"$PY" -B "$D/rerun_round4_snapshots.py" --round 4 --candidate policy_r4.py --candidate-sha fb1b8482deb5b56b58bf6f674fccf42731ce2969a7db5a4398e8f271599204aa --previous policy_r3.py --previous-sha 2ca9930232d63597b77b988b833cd60f5dad0999273b327ec2792c347a9c8edd --budget 512 --seeds 28901 28902 28903 --workers 2
