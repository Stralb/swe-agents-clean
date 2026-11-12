#!/bin/bash
#SBATCH --job-name=E108_random5_round3
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
printf '%s  %s\n' 24ed9d333af915f3cd394b75acc928102fb62098cedf25c73076d7032f941014 "$D/policy_r2.py" | sha256sum -c -
printf '%s  %s\n' fa64f8ac36680154ba65f44694d7428e4214ffbdb0c6a4e88b19d8f7a57a116d "$D/policy_r1_v1.py" | sha256sum -c -
printf '%s  %s\n' 2ca9930232d63597b77b988b833cd60f5dad0999273b327ec2792c347a9c8edd "$D/policy_r3.py" | sha256sum -c -
"$PY" -B "$D/policy_r3.py"
"$PY" -B "$D/random_round_runner.py" --round 3 --candidate policy_r3.py --candidate-sha 2ca9930232d63597b77b988b833cd60f5dad0999273b327ec2792c347a9c8edd --previous policy_r2.py --previous-sha 24ed9d333af915f3cd394b75acc928102fb62098cedf25c73076d7032f941014 --budget 512 --seeds 28901 28902 28903 --workers 2
echo E108_RANDOM_ROUND3_DONE
