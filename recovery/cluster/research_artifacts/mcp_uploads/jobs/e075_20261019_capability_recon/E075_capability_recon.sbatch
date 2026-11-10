#!/bin/bash
#SBATCH --job-name=E075_capability_recon
#SBATCH --partition=batch
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:06:00
set -euo pipefail
P=/home-mscluster/astrauss/RL-ARC-AGI-3-Project
printf "RESEARCH_BRANCHES_PRESENT\n"
for e in 025 027 029 030 031 032 033 034 035 036 037 038 039; do
 for d in "$P/src/e$e" "$P/scripts/e$e" "$P/results/e$e"; do
  if [ -d "$d" ];then echo "ROOT $d"; find "$d" -maxdepth 2 -type f \( -name "*.py" -o -name "*.json" -o -name "*.md" \) -printf "%P\n" | head -n 22;fi
 done
done
printf "RECENT_RESULT_FILES\n"
find "$P" -maxdepth 4 -type f \( -iname "*e035*json" -o -iname "*e036*json" -o -iname "*e037*json" -o -iname "*e039*json" -o -iname "*e034*json" -o -iname "*RESEARCH_DECISION*.md" -o -iname "*E035*NOTES*.md" \) -print | head -n 95
printf "RELEVANT_CONTROLLER_CANDIDATES\n"
grep -R -n -m 1 -E "class .*Agent|class .*Controller|class .*Scientist|class .*Procedure|hypothes|event.repeat|goal.infer" "$P/src/e034" "$P/src/e035" "$P/src/e036" "$P/src/e037" "$P/src/e038" "$P/src/e039" 2>/dev/null | head -n 100 || true
printf "E075_CAPABILITY_RECON_DONE\n"