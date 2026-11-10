#!/bin/bash
#SBATCH --job-name=rlpaper-locate
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:06:00
set -euo pipefail
umask 077
echo "PROJECT-DIRECTORIES"
for dir in /home-mscluster/astrauss/arc26 /home-mscluster/astrauss/RL-ARC-AGI-3-Project /home-mscluster/astrauss/research_artifacts /home-mscluster/astrauss/arc_rl_persistence_e007; do
 if test -d "$dir";then
  echo "FOUND $dir"
  find "$dir" -maxdepth 3 -type d \( -iname '*ppo*' -o -iname '*dqn*' -o -iname '*paper*' -o -iname '*rlc*' -o -iname '*v7*' -o -iname '*v8*' -o -iname '*e071*' -o -iname '*e070*' -o -iname '*eval*' \) -print | head -100
 fi
done
echo "TOPLEVEL HOME"
find /home-mscluster/astrauss -mindepth 1 -maxdepth 2 -type d \( -iname '*arc*' -o -iname '*rl*' -o -iname '*ppo*' -o -iname '*dqn*' \) -print | head -80
echo "MCP-RESULTS-TAIL"
find /home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs -mindepth 1 -maxdepth 1 -type d \( -iname '*ppo*' -o -iname '*dqn*' -o -iname '*e0*' -o -iname '*v8*' -o -iname '*paper*' \) -print | head -80
echo "RL_PAPER_LOCATE_COMPLETE"
