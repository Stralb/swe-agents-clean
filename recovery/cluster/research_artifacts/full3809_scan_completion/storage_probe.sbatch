#!/bin/bash
#SBATCH --time=00:05:00
#SBATCH --cpus-per-task=1
#SBATCH --mem=1G

echo "HOST=$(hostname)"
echo "PARTITION=${SLURM_JOB_PARTITION:-unknown}"
echo

echo "===== ENVIRONMENT ====="
env | grep -E 'SLURM_TMPDIR|TMPDIR|SCRATCH|LOCAL' || true

echo
echo "===== ALL FILESYSTEMS ====="
df -hT || true

echo
echo "===== LOCAL/NON-NFS FILESYSTEMS ====="
df -hT -x nfs -x nfs4 -x cifs -x fuse.sshfs || true

echo
echo "===== COMMON SCRATCH PATHS ====="
for p in \
  /tmp \
  /var/tmp \
  /scratch \
  /localscratch \
  /local \
  /lscratch \
  /mnt \
  /data
do
    if [ -e "$p" ]; then
        echo
        echo "--- $p ---"
        ls -ld "$p" 2>/dev/null || true
        df -hT "$p" 2>/dev/null || true
    fi
done
