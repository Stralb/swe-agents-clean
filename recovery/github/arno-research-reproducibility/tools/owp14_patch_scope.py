#!/usr/bin/env python3
"""Read-only structural measurements of archived O/W/P unified diffs.

Reports changed patch lines/files, not functional correctness, security impact,
causation, or independent model generations. Output is stdout only.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
import re
import statistics
import sys
import zipfile

STAGES = {
    "O": "owp14_user12_o_preflight_job71153",
    "W": "owp14_user14_w_preflight_job71208",
    "P": "owp14_user14_p_preflight_job71201",
}
COLS = ["case", "arm", "patch_sha256", "patch_bytes", "added", "removed",
        "changed_lines", "diff_files", "changed_paths", "changed_tests"]
TEST_PATH = re.compile(r"(^|/)(?:test|tests|__tests__|spec|specs)(/|$)|\.(?:test|spec)\.", re.I)


def diff_stats(blob: bytes) -> tuple[int, int, int]:
    """Count +/- lines and file headers, excluding Git metadata headers."""
    lines = blob.decode("utf-8", errors="replace").splitlines()
    files = sum(line.startswith("diff --git ") for line in lines)
    added = sum(line.startswith("+") and not line.startswith("+++") for line in lines)
    removed = sum(line.startswith("-") and not line.startswith("---") for line in lines)
    if not files:
        raise ValueError("Patch lacks a Git diff header")
    return added, removed, files


def patch_rows(archive: Path) -> list[dict]:
    out = []
    with zipfile.ZipFile(archive) as z:
        for arm, stage in STAGES.items():
            root = f"02_ALL_GENERATED_PATCHES/prevention_pilot_phase2/{stage}"
            meta = json.loads(z.read(root + "/SUMMARY.json"))
            if meta.get("stage") != "COMPLETE":
                raise ValueError(f"Incomplete archived stage {stage}")
            for case, rec in meta["cases"].items():
                cid = int(case)
                suffix = f"CASE_{cid:05d}_{arm}.patch"
                name = f"{root}/CASE_{cid:05d}/{suffix}"
                blob = z.read(name)
                digest = hashlib.sha256(blob).hexdigest()
                if rec["original_patch_sha256"] != digest or rec["original_patch_bytes"] != len(blob):
                    raise ValueError(f"Patch bytes or digest mismatch for {cid} {arm}")
                if rec.get("patch_applied") is not True:
                    raise ValueError(f"Preflight not applied for {cid} {arm}")
                added, removed, files = diff_stats(blob)
                paths = set(rec["changed_paths"])
                if files != len(paths):
                    raise ValueError(f"Diff-file count differs from preflight changed paths for {cid} {arm}")
                out.append({"case":f"{cid:05d}","arm":arm,
                            "patch_sha256":digest,"patch_bytes":len(blob),
                            "added":added,"removed":removed,
                            "changed_lines":added+removed,"diff_files":files,
                            "changed_paths":len(paths),
                            "changed_tests":sum(bool(TEST_PATH.search(p)) for p in paths)})
    out.sort(key=lambda r:(r["case"],r["arm"]))
    if len(out) != 40 or {r["arm"] for r in out} != {"O","W","P"}:
        raise ValueError("Unexpected O/W/P patch membership")
    return out


def summary(rows: list[dict]) -> dict:
    bycase:dict[str,dict[str,dict]] = {}
    for r in rows:
        bycase.setdefault(r["case"],{})[r["arm"]] = r
    paired = [case for case in bycase if set(bycase[case]) == {"O","W","P"}]
    if len(paired) != 12:
        raise ValueError(f"Expected exactly 12 paired cases, got {len(paired)}")
    output = {"paired_case_count":len(paired),"arm_counts":{},"comparisons":{}}
    for arm in "OWP":
        selected = [r for r in rows if r["arm"] == arm]
        selected_pair = [bycase[c][arm] for c in paired]
        output["arm_counts"][arm] = {"patches":len(selected),
          "all_patch_bytes":sum(r["patch_bytes"] for r in selected),
          "all_changed_lines":sum(r["changed_lines"] for r in selected),
          "paired_median_patch_bytes":statistics.median(r["patch_bytes"] for r in selected_pair),
          "paired_median_changed_lines":statistics.median(r["changed_lines"] for r in selected_pair)}
    for arm in "WP":
        output["comparisons"][arm + "_relative_to_O"] = {
          field:{"smaller":sum(bycase[c][arm][field] < bycase[c]["O"][field] for c in paired),
                 "same":sum(bycase[c][arm][field] == bycase[c]["O"][field] for c in paired),
                 "larger":sum(bycase[c][arm][field] > bycase[c]["O"][field] for c in paired)}
          for field in ("patch_bytes", "changed_lines", "changed_paths", "changed_tests")}
    output["interpretation"] = "STRUCTURAL_PATCH_SCOPE_ONLY_NOT_FUNCTIONAL_OR_CAUSAL_INFERENCE"
    return output


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("archive", type=Path)
    p.add_argument("--format", choices=("csv","json"),default="csv")
    args = p.parse_args(argv)
    try:
        rows = patch_rows(args.archive)
        if args.format == "json":
            print(json.dumps({"summary":summary(rows),"rows":rows},indent=2))
        else:
            w=csv.DictWriter(sys.stdout,fieldnames=COLS)
            w.writeheader();w.writerows(rows)
    except (OSError,zipfile.BadZipFile,KeyError,ValueError) as error:
        print("Audit failed: " + str(error),file=sys.stderr)
        return 1
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
