#!/bin/bash
#SBATCH --job-name=telegram_typecheck_final
#SBATCH --partition=bigbatch
#SBATCH --dependency=afterok:72020
#SBATCH --cpus-per-task=2
#SBATCH --mem=4G
#SBATCH --time=00:10:00
set -euo pipefail
export PATH="$HOME/tools/node/bin:$HOME/.bun/bin:$PATH"
src="$HOME/research_artifacts/mcp_uploads/jobs/two_provider_atomic_20261020_v1"
root="$HOME/research_artifacts/prevention_pilot_phase2/provider_variants_20261020/08152"
python3 "$src/test_type_patch.py"
cd "$root/baseline/REPO"
bun run typecheck
bun test src/telegram/voice.test.ts
