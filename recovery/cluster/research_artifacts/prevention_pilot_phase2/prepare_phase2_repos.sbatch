#!/bin/bash
#SBATCH --job-name=prep_prev3
#SBATCH --partition=bigbatch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=01:00:00
#SBATCH --output=prepare_phase2_%j.out
#SBATCH --error=prepare_phase2_%j.err

set -euo pipefail

OUT="/home-mscluster/astrauss/research_artifacts/prevention_pilot_phase2"
WORK="${SLURM_TMPDIR:-/tmp/$USER/prevention_phase2_$SLURM_JOB_ID}"

mkdir -p "$WORK"
mkdir -p "$OUT/repos"
cd "$WORK"

echo "=== CASE 3504 ==="
git clone --quiet https://github.com/pingdotgg/t3code.git t3code
cd t3code
git cat-file -e 32c6012dabdbd0eb178b25ea4225d889ec8f6475^{commit}
git archive \
  --format=tar.gz \
  --output="$OUT/repos/O3504_prePR.tar.gz" \
  32c6012dabdbd0eb178b25ea4225d889ec8f6475
cd "$WORK"

echo "=== CASE 10819 ==="
git clone --quiet https://github.com/evilz/vscode-reveal.git vscode-reveal
cd vscode-reveal
git cat-file -e 43a63372b24961e2345b6e491952e56164b3322a^{commit}
git archive \
  --format=tar.gz \
  --output="$OUT/repos/O10819_prePR.tar.gz" \
  43a63372b24961e2345b6e491952e56164b3322a
cd "$WORK"

echo "=== CASE 629 ==="
git clone --quiet https://github.com/ZHANGTIANYAO1/teamspeak-music-bot.git teamspeak-music-bot
cd teamspeak-music-bot
git cat-file -e f8743a904f50a065c9fcf5139e46005b5fff2e46^{commit}
git archive \
  --format=tar.gz \
  --output="$OUT/repos/O629_prePR.tar.gz" \
  f8743a904f50a065c9fcf5139e46005b5fff2e46

echo
echo "=== OUTPUTS ==="
ls -lh "$OUT/repos"

echo
echo "=== SHA256 ==="
sha256sum "$OUT"/repos/*.tar.gz | tee "$OUT/repos/SHA256SUMS.txt"

echo
echo "DONE"
