import os
import shutil
import sys

from src.settings import load_settings

settings = load_settings()
print(f"Config: {settings.config_path}")
print(f"DB: {settings.db_path}")
print(f"GitHub token present: {bool(settings.github_token)}")

required = ["git"]
scanners = settings.config.get("scanners", {})
if scanners.get("codeql", True):
    required.append("codeql")
if scanners.get("gitleaks", True):
    required.append("gitleaks")
if scanners.get("osv", True):
    required.append("osv-scanner")
# gh is helpful but the app uses the REST API directly.
optional = ["gh", "identify-cli", "github-linguist", "trivy"]
missing = []
for tool in required + optional:
    path = shutil.which(tool)
    print(f"{tool}: {path or 'NOT FOUND'}" + (" (optional)" if tool in optional else ""))
    if tool in required and not path:
        missing.append(tool)

strict = os.getenv("STRICT_TOOLS", "true").strip().lower() in {"1", "true", "yes", "on"}
if strict and missing:
    print(f"Missing required enabled tools: {', '.join(missing)}", file=sys.stderr)
    sys.exit(2)
