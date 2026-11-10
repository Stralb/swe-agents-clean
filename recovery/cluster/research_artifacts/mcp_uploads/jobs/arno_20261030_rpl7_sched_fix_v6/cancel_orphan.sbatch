#!/bin/bash
#SBATCH --job-name=arno_rpl7_remove_orphan
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=1G
#SBATCH --time=00:04:00
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_20261030_rpl7_sched_fix_v6/orphan_%j.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_20261030_rpl7_sched_fix_v6/orphan_%j.err
set -euo pipefail
state="$(scontrol show job 78459 | grep -o 'JobState=[A-Z]*' | head -n 1)"
echo "OLD_SUMMARY_STATE=$state"
if test "$state" != "JobState=PENDING"; then
 echo "Refusing to cancel nonpending job"
 exit 2
fi
scancel --state=PENDING 78459
echo "STALE_FAILED_DEPENDENCY_SUMMARY_CANCELLED"
