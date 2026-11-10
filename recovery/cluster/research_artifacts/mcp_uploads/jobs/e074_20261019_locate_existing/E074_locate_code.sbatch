#!/bin/bash
#SBATCH --job-name=E074_locate_code
#SBATCH --partition=batch
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:05:00
set -euo pipefail
echo "E074_SEARCH_EXACT_KNOWN_ROOTS"
for base in "/home-mscluster/astrauss/RL-ARC-AGI-3-Project" "/home-mscluster/astrauss/arc26" "/home-mscluster/astrauss" "/home-mscluster/astrauss/research_artifacts/mcp_uploads"; do
 if [ -d "$base" ];then
  echo "BASE_PRESENT $base"
  if [ "$base" = /home-mscluster/astrauss ];then
   ls -lad "$base"/*E07* "$base"/*e07* "$base"/*E068* "$base"/*e068* "$base"/*E069* "$base"/*e069* "$base"/*HUMAN* "$base"/*human* 2>/dev/null || true
  else
   find "$base" -maxdepth 4 -type f \( -name "ingest_human.py" -o -name "history_ddqn.py" -o -name "e074_pipeline.py" -o -name "E074*.zip" -o -name "e072_audit.py" \) -print 2>/dev/null | head -n 70
  fi
 fi
done
echo "E074_SEARCH_FINISHED"