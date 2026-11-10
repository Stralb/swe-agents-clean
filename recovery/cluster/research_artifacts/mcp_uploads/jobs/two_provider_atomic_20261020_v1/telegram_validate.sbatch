#!/bin/bash
#SBATCH --job-name=telegram_provider_test
#SBATCH --partition=bigbatch
#SBATCH --cpus-per-task=2
#SBATCH --mem=6G
#SBATCH --time=00:25:00
set -euo pipefail
export PATH="$HOME/tools/node/bin:$HOME/.bun/bin:$PATH"
d="$HOME/research_artifacts/prevention_pilot_phase2/provider_variants_20261020/08152"
cd "$d/baseline/REPO"
if timeout 420s bun install --frozen-lockfile > "$d/install.log" 2>&1; then echo INSTALL_PASS; else echo INSTALL_FAIL; fi
if bun run typecheck > "$d/typecheck.log" 2>&1; then echo TYPECHECK_PASS; else echo TYPECHECK_FAIL; fi
if bun test src/telegram/voice.test.ts > "$d/voice_tests.log" 2>&1; then echo VOICE_TESTS_PASS; else echo VOICE_TESTS_FAIL; fi
git diff --binary HEAD > "$d/CASE_08152_PROVIDER_LOCKED.patch"
sha256sum "$d/CASE_08152_PROVIDER_LOCKED.patch"
