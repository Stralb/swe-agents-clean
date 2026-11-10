#!/bin/bash
#SBATCH --job-name=E108_random5_round4
#SBATCH --partition=stampede
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=00:35:00
set -euo pipefail
umask 077
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 PYTHONUNBUFFERED=1
PY=/home-mscluster/astrauss/arc_rl_mechanics_killtest/.venv/bin/python
D=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/e108_20261020_random_rounds
printf '%s  %s\n' fa2fc448aadd255d76fe469341485d904db85f854164e1dbbaa8d87125b5fb62 "$D/random_round_runner.py" | sha256sum -c -
printf '%s  %s\n' 75d70edce5f18da4802b1ad4f1f71ed308863b00e208c4273fceec7a049e7e44 "$D/random_cycle_runner.py" | sha256sum -c -
printf '%s  %s\n' fb1b8482deb5b56b58bf6f674fccf42731ce2969a7db5a4398e8f271599204aa "$D/policy_r4.py" | sha256sum -c -
"$PY" -B "$D/random_cycle_runner.py" --round 4 --candidate policy_r4.py --candidate-sha fb1b8482deb5b56b58bf6f674fccf42731ce2969a7db5a4398e8f271599204aa --previous policy_r3.py --previous-sha 2ca9930232d63597b77b988b833cd60f5dad0999273b327ec2792c347a9c8edd --budget 512 --seeds 28901 28902 28903 --workers 2
echo E108_RANDOM_ROUND4_DONE
