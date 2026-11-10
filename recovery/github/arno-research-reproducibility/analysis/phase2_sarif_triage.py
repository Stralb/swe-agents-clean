#!/usr/bin/env python3
"""Conservative, read-only CodeQL SARIF delta triage.

This tool does not execute scanners, generate patches, write files, or establish
causation. Unmatched fingerprints are candidates, not proven introduced alerts.
"""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit

HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")


def changed_new_lines(diff: str) -> dict[str, set[int]]:
    """Parse added/modified new-side lines in a simple unquoted Git diff.

    Quoted headers are refused rather than guessed; deletion-only hunks have
    no new-side line overlap. No git command or file mutation is performed.
    """
    paths: dict[str, set[int]] = {}
    path: str | None = None
    deleted = False
    for text in diff.splitlines():
        if text.startswith("diff --git "):
            path, deleted = None, False
        elif text.startswith("+++ "):
            header = text[4:]
            deleted = header == "/dev/null"
            if deleted:
                path = None
            elif header.startswith("b/") and not header.startswith('b/"') and "\t" not in header:
                path = header[2:]
                paths.setdefault(path, set())
            else:
                raise ValueError(f"Unsupported Git patch path: {header!r}")
        elif text.startswith("@@ "):
            match = HUNK.match(text)
            if match is None:
                raise ValueError(f"Unsupported hunk header: {text!r}")
            if deleted:
                continue
            if path is None:
                raise ValueError("Hunk encountered without a new-side path")
            start = int(match.group(1))
            count = int(match.group(2)) if match.group(2) is not None else 1
            paths[path].update(range(start, start + count))
    return paths


def normalized_uri(uri: str) -> str:
    uri = unquote(uri).replace("\\", "/")
    if uri.startswith("file://"):
        uri = urlsplit(uri).path
    while uri.startswith("./"):
        uri = uri[2:]
    return uri


def primary_locations(result: dict) -> list[tuple[str, int]]:
    """Read top-level SARIF locations only, NOT a data-flow trace."""
    found = []
    for location in result.get("locations", []):
        physical = location.get("physicalLocation", {})
        artifact = physical.get("artifactLocation", {})
        uri = normalized_uri(str(artifact.get("uri", "")))
        line = int(physical.get("region", {}).get("startLine", 0) or 0)
        if uri and line > 0:
            found.append((uri, line))
    return found


def fingerprint_key(result: dict) -> tuple | None:
    rule = result.get("ruleId")
    fields = result.get("partialFingerprints") or {}
    if not rule or not isinstance(fields, dict) or not fields:
        return None
    normalized = tuple(sorted((str(k), str(v)) for k, v in fields.items()))
    return (str(rule), normalized)


def location_overlap(locations: list[tuple[str, int]], new_lines: dict[str, set[int]]) -> bool:
    for uri, line in locations:
        for path, lines in new_lines.items():
            if line in lines and (uri == path or uri.endswith("/" + path)):
                return True
    return False


def sarif_results(document: dict) -> list[dict]:
    runs = document.get("runs", [])
    if not isinstance(runs, list):
        raise ValueError("SARIF runs must be a list")
    results = []
    for run in runs:
        rows = run.get("results", [])
        if not isinstance(rows, list):
            raise ValueError("SARIF result set must be a list")
        results.extend(rows)
    return results


def compare(base_doc: dict, patched_doc: dict, patch_diff: str) -> dict:
    base = sarif_results(base_doc)
    patched = sarif_results(patched_doc)
    lines = changed_new_lines(patch_diff)
    base_keys = Counter(key for item in base if (key := fingerprint_key(item)) is not None)
    patch_keys = Counter(key for item in patched if (key := fingerprint_key(item)) is not None)
    evidence = []
    counts: Counter[str] = Counter()
    for item in patched:
        key = fingerprint_key(item)
        if key is None:
            classification = "UNVERIFIABLE_NO_STABLE_FINGERPRINT"
        elif base_keys[key] > 1 or patch_keys[key] > 1:
            classification = "AMBIGUOUS_DUPLICATE_FINGERPRINT"
        elif base_keys[key] == 1:
            classification = "MATCHED_UNIQUE_FINGERPRINT"
        else:
            classification = "UNMATCHED_UNIQUE_FINGERPRINT"
        locations = primary_locations(item)
        overlap = location_overlap(locations, lines)
        counts[classification] += 1
        evidence.append({
            "rule_id": item.get("ruleId", ""),
            "classification": classification,
            "primary_locations": [{"uri": uri, "line": line} for uri, line in locations],
            "overlaps_added_or_modified_line": overlap,
        })
    return {
        "status": "SCANNER_TRIAGE_ONLY_NOT_CAUSAL_PROOF",
        "base_result_count": len(base),
        "patched_result_count": len(patched),
        "classifications": dict(sorted(counts.items())),
        "results": evidence,
        "limitations": [
            "CodeQL partial fingerprints require run-to-run identity validation.",
            "A changed-line overlap is neither necessary nor sufficient for causal attribution.",
            "Unmatched results without stable fingerprints are indeterminate.",
            "Only top-level result locations are inspected; CodeQL flow locations are not resolved.",
            "Quoted Git diff paths and unresolved URI-base mappings need separate review.",
            "Functional correctness and the O/W/P intervention effect are not assessed.",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base_sarif", type=Path)
    parser.add_argument("patched_sarif", type=Path)
    parser.add_argument("unified_diff", type=Path)
    args = parser.parse_args(argv)
    base = json.loads(args.base_sarif.read_text(encoding="utf-8"))
    patched = json.loads(args.patched_sarif.read_text(encoding="utf-8"))
    patch = args.unified_diff.read_text(encoding="utf-8")
    print(json.dumps(compare(base, patched, patch), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
