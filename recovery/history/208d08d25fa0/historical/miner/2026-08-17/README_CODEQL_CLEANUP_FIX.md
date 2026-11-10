# CodeQL cleanup/error handling fix

This build fixes the WSL/CodeQL temp-directory cleanup failure:

```text
OSError: [Errno 39] Directory not empty: 'python'
```

## Changes

- CodeQL scans now use a Linux-local temp parent by default:
  - `CODEQL_TMPDIR ?= /tmp/miner-codeql-tmp`
  - exported as `MINER_CODEQL_TMPDIR`
- `src/scanners/codeql_scanner.py` now uses a cleanup-tolerant CodeQL temp context.
- A post-scan temp cleanup race no longer converts a completed CodeQL scan into a scanner failure.
- JavaScript/TypeScript CodeQL preflight now reports missing `node` clearly before database creation.
- Tests added for:
  - configured CodeQL temp parent
  - cleanup failure resilience
  - JS/TS preflight requiring Node
  - Python CodeQL preflight not requiring Node

## Recommended rerun

```bash
cd /mnt/c/Users/MSS/Downloads/malicious-issue-miner-rate-smart

make scan \
  MODE=full \
  MAX_CASES=500 \
  CODEQL_TRIGGER=all_codeql \
  CODEQL_LANGUAGE=auto \
  CODEQL_MAX_PER_RUN=50 \
  CODEQL_WORKERS=1 \
  FORCE_RESCAN=true
```

Optional explicit temp path:

```bash
CODEQL_TMPDIR=/tmp/miner-codeql-tmp make scan MODE=full CODEQL_TRIGGER=all_codeql CODEQL_LANGUAGE=auto FORCE_RESCAN=true
```

## Test result

```text
105 passed, 1 skipped
```
