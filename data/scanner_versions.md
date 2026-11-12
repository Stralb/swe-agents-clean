# Scanner versions and configuration

Recorded values for the scanners used in the study.

| Scanner | Version or ruleset | Where recorded |
| --- | --- | --- |
| CodeQL CLI | 2.25.6 | Replay environment |
| CodeQL JavaScript query pack | `codeql/javascript-queries` 2.3.11 | Original scan logs |
| Trivy CLI | 0.72.0 | Original scan records |
| Trivy vulnerability database | format version 2, updated 2026-07-22 | Original scan records |
| Semgrep | ruleset `p/security-audit` | `config.yml` |
| OSV-Scanner | live vulnerability lookup | `miner/scanners/osv_scanner.py` |
| Gitleaks | default rules | `miner/scanners/gitleaks_scanner.py` |
| Dependency downgrade | internal checker | `miner/scanners/dependency_diff.py` |

CodeQL runs JavaScript/TypeScript with `build_mode: none` and the `javascript-security-extended` suite, with a 1,800-second timeout. Trivy runs `trivy fs` with vulnerability scanning only, in offline mode. The Semgrep, OSV-Scanner and Gitleaks executable versions were not captured in the scan output.
