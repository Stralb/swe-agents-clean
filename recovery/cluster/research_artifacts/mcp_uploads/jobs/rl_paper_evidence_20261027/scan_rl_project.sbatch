#!/bin/bash
#SBATCH --job-name=rlpaper-scan
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:08:00
set -euo pipefail
umask 077
P=/home-mscluster/astrauss/RL-ARC-AGI-3-Project
echo "TOP LEVEL"
ls -la "$P" | head -65
echo "SRC TREE"
find "$P/src" -maxdepth 3 -type f | head -100
echo "RESULTS TOP"
find "$P/results" -mindepth 1 -maxdepth 2 -type d | head -130
echo "REPORTS AND DATA FILES"
find "$P" -maxdepth 4 -type f \( -iname '*summary*.json' -o -iname '*result*.csv' -o -iname '*manifest*.json' -o -iname '*paper*.tex' -o -iname 'rlj.sty' -o -iname 'rlj.bst' -o -iname '*evaluation*.csv' -o -iname '*comparison*.csv' \) | head -130
echo "ROOT GIT"
if test -d "$P/.git";then git -C "$P" log -1 --oneline; fi
echo SCAN_COMPLETE
