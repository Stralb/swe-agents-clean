# Offline SARIF comparison tool

Run this from a local checkout or a deliberately isolated copy, not from the historical cluster evaluation directory:

```bash
python -m analysis.phase2_sarif_triage /path/to/BASE_CASE.sarif /path/to/PATCHED_CASE.sarif /path/to/diff_u0.patch
```

The tool reads three existing files, prints a JSON report to stdout, and does not run Git, CodeQL, shell commands, archive extraction or file writes. All tests operate on synthetic fixtures.

## What the report measures

- `MATCHED_UNIQUE_FINGERPRINT`: same rule + nonempty partial fingerprint appears exactly once in each SARIF set; this suggests but does not prove continuity.
- `UNMATCHED_UNIQUE_FINGERPRINT`: nonempty unique partial fingerprint on the patched side not found in the base. This is **candidate alert change**, not verified vulnerability introduction.
- `UNVERIFIABLE_NO_STABLE_FINGERPRINT`: no usable rule/fingerprint; do not convert a path/line fallback mismatch to a definite new finding.
- `AMBIGUOUS_DUPLICATE_FINGERPRINT`: a nonunique key in either file; requires separate instance-level review.
- `overlaps_added_or_modified_line`: whether *a top-level SARIF result location* overlaps a new-side unified-diff interval. It is a weak heuristic, not proof of patch causation.

Deletion-only hunks have no new-side added lines; quoted/ambiguous Git diff path headers are rejected. Full CodeQL dataflow path localization, arbitrary URI-base references and query-pack identity are not resolved. A null overlap cannot be interpreted as safety, because edited code can affect a result elsewhere.

## What it does not do

Nothing here performs a fresh CodeQL scan, proves a CodeQL alert to be a security vulnerability, checks functional correctness, or estimates retrospective oracle interventions' ability to prevent historical findings. The three-case O-only original scripts remain frozen and unsafe to run against original research outputs.

## Tests

```bash
python -m unittest discover -s tests -v
```

The hash regression test checks that both historical evaluator scripts remain byte-for-byte identical to the uploaded source. Other tests exercise scanner result matching, missing and duplicate fingerprints, changed-line matching, path encoding, deletion-only diffs and fail-closed quoted-header handling.
