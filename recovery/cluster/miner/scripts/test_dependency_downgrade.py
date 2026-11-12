from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from src.scanners.dependency_diff import detect_dependency_regressions


def main() -> None:
    print("Dependency downgrade self-test")
    files = [{"filename": "requirements.txt", "patch": "-django==4.2.10\n+django==1.2\n"}]
    findings = detect_dependency_regressions(files)
    if not findings:
        raise SystemExit("FAIL: dependency diff did not detect django 4.2.10 -> 1.2 downgrade")
    print("OK: dependency-diff detected downgrade:", findings[0]["description"])

    osv = shutil.which("osv-scanner")
    if not osv:
        print("SKIP: osv-scanner not found on PATH")
        return

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "requirements.txt").write_text("django==1.2\n", encoding="utf-8")
        report = root / "osv-report.json"
        result = subprocess.run([osv, "--format", "json", str(root)], text=True, capture_output=True, timeout=120)
        report.write_text(result.stdout or "{}", encoding="utf-8")
        if result.stdout:
            data = json.loads(result.stdout)
            vuln_count = 0
            for res in data.get("results", []) or []:
                for pkg in res.get("packages", []) or []:
                    vuln_count += len(pkg.get("vulnerabilities", []) or [])
            if vuln_count <= 0:
                raise SystemExit("FAIL: OSV ran but reported no vulnerabilities for django==1.2")
            print(f"OK: OSV reported {vuln_count} vulnerable dependency finding(s) for django==1.2")
        else:
            raise SystemExit(f"FAIL: OSV produced no JSON output. stderr={result.stderr[:500]}")


if __name__ == "__main__":
    main()
