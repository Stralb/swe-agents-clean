#!/bin/bash
#SBATCH --job-name=arno_rpl7_cancel_wait
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=1G
#SBATCH --time=00:05:00
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_20261030_rpl7_sched_fix_v6/cancel_%j.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_20261030_rpl7_sched_fix_v6/cancel_%j.err
set -euo pipefail
echo BEFORE
squeue -u "$USER" -o "%i|%T|%P|%R"
for j in 78438 78455; do
 state="$(scontrol show job "$j" | grep -o 'JobState=[A-Z]*' | head -n 1)"
 if test "$state" != "JobState=PENDING"; then
  echo "REFUSE_CANCEL_NOT_PENDING $j $state"
  exit 2
 fi
done
scancel --state=PENDING 78455 78438
echo AFTER
squeue -u "$USER" -o "%i|%T|%P|%R"
