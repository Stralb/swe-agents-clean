#!/bin/bash
#SBATCH --job-name=rlpaper-scan2
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:08:00
set -euo pipefail
P=/home-mscluster/astrauss/RL-ARC-AGI-3-Project
echo "ROOT FILES"; ls "$P" | tail -60
echo "RESULT SUBDIRS"; find "$P/results" -mindepth 1 -maxdepth 2 -type d | sed -n '1,180p'
echo "CONFIG FILES"; find "$P/configs" -maxdepth 2 -type f | sed -n '1,120p'
echo "RUNNER FILES"; find "$P" -maxdepth 2 -type f \( -iname '*summary*' -o -iname '*eval*.json' -o -iname '*report*.md' -o -iname '*manifest*.json' \) | sed -n '1,130p'
echo "EXPERIMENT OUTPUT SAMPLE"; find "$P/results" -maxdepth 3 -type f | sed -n '1,90p'
echo SCAN2_DONE
