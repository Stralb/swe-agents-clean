#!/bin/bash
#SBATCH --job-name=fleet_provider_tests
#SBATCH --partition=bigbatch
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:10:00
set -euo pipefail
export PATH="$HOME/tools/node/bin:$PATH"
d="$HOME/research_artifacts/prevention_pilot_phase2/provider_variants_20261020/31207"
cd "$d/baseline/REPO"
node --check ai/scripts/diagnostics/fleetHealthcheck.mjs
node --test ai/scripts/diagnostics/fleetHealthcheck.test.mjs
if command -v docker >/dev/null 2>&1; then docker compose -f ai/deploy/docker-compose.yml -f ai/deploy/docker-compose.local-agent-os.yml config -q; else echo NO_DOCKER_COMPOSE; fi
