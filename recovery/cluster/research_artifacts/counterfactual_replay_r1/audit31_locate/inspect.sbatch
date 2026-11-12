#!/bin/bash
#SBATCH --job-name=audit31_loc
#SBATCH --partition=batch
#SBATCH --time=00:05:00
#SBATCH --cpus-per-task=1
#SBATCH --mem=1G
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/counterfactual_replay_r1/audit31_locate/result.txt
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/counterfactual_replay_r1/audit31_locate/error.txt

ROOT="$HOME/research_artifacts/counterfactual_replay_r1"

echo "=== STEP6 LOCATIONS ==="
cat "$ROOT/STEP6_LOCATIONS.txt"

echo
echo "=== ORIGINAL LOCATOR SCRIPT ==="
sed -n '1,240p' "$ROOT/find_step6.sbatch"

echo
echo "=== EXISTENCE CHECK ==="
while IFS= read -r line; do
    for p in $line; do
        case "$p" in
            /*)
                if [ -e "$p" ]; then
                    ls -ldh "$p"
                fi
                ;;
        esac
    done
done < "$ROOT/STEP6_LOCATIONS.txt"
