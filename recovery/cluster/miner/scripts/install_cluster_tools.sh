#!/usr/bin/env bash
set -euo pipefail

TOOLS_ROOT="${TOOLS_ROOT:-/home-mscluster/$USER/tools}"
BIN_DIR="$TOOLS_ROOT/bin"
mkdir -p "$BIN_DIR"

export PATH="$BIN_DIR:$TOOLS_ROOT/go/bin:$PATH"

cd "$TOOLS_ROOT"

echo "===== identify ====="
if command -v identify-cli >/dev/null 2>&1; then
  identify-cli --version || true
else
  if [ -x "/home-mscluster/$USER/new/malicious-issue-miner-rate-smart/.venv/bin/python" ]; then
    "/home-mscluster/$USER/new/malicious-issue-miner-rate-smart/.venv/bin/python" -m pip install identify
  else
    python3 -m pip install --user identify
  fi
  command -v identify-cli || true
  identify-cli --version || true
fi

echo "===== GitHub Linguist ====="
if command -v github-linguist >/dev/null 2>&1; then
  github-linguist --version || true
else
  if command -v gem >/dev/null 2>&1; then
    gem install --user-install github-linguist --no-document || true
    GEM_USER_BIN="$(ruby -e 'puts Gem.user_dir' 2>/dev/null)/bin"
    if [ -d "$GEM_USER_BIN" ]; then
      echo "Add this to PATH if github-linguist is not found: export PATH=\"$GEM_USER_BIN:\$PATH\""
      export PATH="$GEM_USER_BIN:$PATH"
    fi
    command -v github-linguist || true
    github-linguist --version || true
  else
    echo "Ruby gem is not available. Ask cluster support for ruby+gem, or skip Linguist and use identify fallback." >&2
  fi
fi

echo "===== Trivy ====="
if command -v trivy >/dev/null 2>&1; then
  trivy --version || true
else
  curl -sfL https://raw.githubusercontent.com/aquasecurity/trivy/main/contrib/install.sh | sh -s -- -b "$BIN_DIR"
  command -v trivy
  trivy --version
fi

echo "===== PATH LINE ====="
echo "export PATH=\"$BIN_DIR:$TOOLS_ROOT/go/bin:\$PATH\""
