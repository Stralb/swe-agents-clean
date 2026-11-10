#!/bin/bash
#SBATCH --job-name=verify_prev3
#SBATCH --partition=bigbatch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=00:20:00
#SBATCH --output=verify_phase2_%j.out
#SBATCH --error=verify_phase2_%j.err

set -euo pipefail

BASE="/home-mscluster/astrauss/research_artifacts/prevention_pilot_phase2"
cd "$BASE"

echo "=== CHECKSUMS ==="
sha256sum -c repos/SHA256SUMS.txt

echo
echo "=== ARCHIVE INTEGRITY ==="
for f in repos/O10819_prePR.tar.gz repos/O3504_prePR.tar.gz repos/O629_prePR.tar.gz; do
    echo "--- $f ---"
    gzip -t "$f"
    echo "files: $(tar -tzf "$f" | wc -l)"
    echo ".git entries: $(tar -tzf "$f" | grep -Ec '(^|/)\.git(/|$)' || true)"
done

cat > PHASE2_BASES.txt <<'BASES'
O3504
repo=pingdotgg/t3code
base_sha=32c6012dabdbd0eb178b25ea4225d889ec8f6475
target_rule=js/redos

O10819
repo=evilz/vscode-reveal
base_sha=43a63372b24961e2345b6e491952e56164b3322a
target_rule=js/file-system-race

O629
repo=ZHANGTIANYAO1/teamspeak-music-bot
base_sha=f8743a904f50a065c9fcf5139e46005b5fff2e46
target_rule=js/biased-cryptographic-random
BASES

echo
echo "=== BASE MANIFEST ==="
cat PHASE2_BASES.txt

echo
echo "VERIFICATION PASSED"
