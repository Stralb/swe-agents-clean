#!/bin/bash
#SBATCH --job-name=arno_diag_io
#SBATCH --partition=batch
#SBATCH --time=00:10:00
#SBATCH --cpus-per-task=1
#SBATCH --mem=1G
set -u
echo "read-only process I/O diagnostic for job 79732"
timeout 40s srun --jobid=79732 --overlap -N1 -n1 bash -lc 'date; df -T /tmp /home-mscluster/astrauss/research_artifacts; stat -f -c "%n %T" /tmp /home-mscluster/astrauss/research_artifacts; cat /proc/816705/wchan; cat /proc/816705/io; ls -l /proc/816705/fd 2>/dev/null | tail -n 25; sleep 4; cat /proc/816705/io' || true
echo "diagnostic end"
