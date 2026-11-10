#!/bin/bash
#SBATCH --job-name=arno_diag_readonly
#SBATCH --partition=batch
#SBATCH --time=00:10:00
#SBATCH --cpus-per-task=1
#SBATCH --mem=1G
set -u
echo "read-only process diagnostic for existing job 79732"
timeout 25s srun --jobid=79732 --overlap -N1 -n1 bash -lc 'date; ps -u astrauss -o pid,stat,pcpu,etime,wchan:25,args; ls -lh /tmp/arno_sidecar_v4_79732/' || true
echo "diagnostic end"
