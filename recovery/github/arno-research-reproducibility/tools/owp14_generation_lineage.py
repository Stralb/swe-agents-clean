#!/usr/bin/env python3
"""Read-only integrity and patch-to-scan lineage audit for October O/W/P ZIPs.

No archive extraction, code execution, subprocess calls, network or filesystem writes.
Study-level interpretations are separated from archival hash and cohort assertions.
"""
from __future__ import annotations

import argparse
import ast
from collections import Counter, defaultdict
import csv
import hashlib
import io
import json
from pathlib import Path
import re
import sys
import zipfile


class LineageError(ValueError):
    """A checkable archive identity or recorded lineage invariant failed."""


def hash_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def entry(z: zipfile.ZipFile, suffix: str) -> str:
    matches = [v.filename for v in z.infolist() if v.filename == suffix or v.filename.endswith("/" + suffix)]
    if len(matches) != 1:
        raise LineageError(f"Expected exactly one file ending {suffix!r}; found {len(matches)}")
    return matches[0]


def indexed_archive(z: zipfile.ZipFile) -> int:
    """Require exact manifest coverage and every member's recorded size/digest."""
    infos = [i for i in z.infolist() if not i.is_dir()]
    names = [x.filename for x in infos]
    if len(names) != len(set(names)):
        raise LineageError("Duplicate ZIP member name")
    index_path = entry(z, "00_README_AND_MANIFEST/PART_INDEX.csv")
    rows = list(csv.DictReader(io.StringIO(z.read(index_path).decode("utf-8-sig"))))
    if not rows or not {"archive_path", "sha256", "bytes"}.issubset(rows[0]):
        raise LineageError("Incomplete index schema")
    paths = [r["archive_path"] for r in rows]
    if len(paths) != len(set(paths)) or set(paths) != set(names) - {index_path}:
        raise LineageError("Incomplete or duplicate manifest coverage")
    for row in rows:
        info = z.getinfo(row["archive_path"])
        if info.file_size != int(row["bytes"]):
            raise LineageError(f"Member size mismatch: {info.filename}")
        digest = hashlib.sha256()
        with z.open(info) as handle:
            for block in iter(lambda: handle.read(1 << 20), b""):
                digest.update(block)
        if digest.hexdigest() != row["sha256"].lower():
            raise LineageError(f"Member SHA mismatch: {info.filename}")
    return len(rows)


def owp_summary(z: zipfile.ZipFile, prefix: str) -> dict:
    payload = json.loads(z.read(entry(z, f"{prefix}/SUMMARY.json")))
    if not isinstance(payload, dict) or not isinstance(payload.get("cases"), dict):
        raise LineageError(f"Invalid {prefix} summary")
    return payload


def compare_inner_transfer(z: zipfile.ZipFile, prefix: str, summary: dict) -> dict:
    """Match an embedded original patch ZIP to every direct patch and its hash."""
    transfer_names = [i.filename for i in z.infolist() if i.filename.startswith("02_ALL_GENERATED_PATCHES/prevention_pilot_phase2/" + prefix + "/") and i.filename.endswith(".zip")]
    if len(transfer_names) != 1:
        raise LineageError(f"Expected exactly one nested patch archive in {prefix}")
    transfer = z.read(transfer_names[0])
    digest = hashlib.sha256(transfer).hexdigest()
    if digest != summary["verified_archive_sha256"]:
        raise LineageError(f"Nested transfer hash mismatch: {prefix}")
    matches = 0
    with zipfile.ZipFile(io.BytesIO(transfer)) as inner:
        nested_paths = inner.namelist()
        if len(nested_paths) != len(set(nested_paths)) or len(nested_paths) != len(summary["cases"]):
            raise LineageError(f"Unexpected nested patch count in {prefix}")
        expected_names = {item["filename"] for item in summary["cases"].values()}
        if set(nested_paths) != expected_names:
            raise LineageError(f"Nested patch name mismatch in {prefix}")
        for case, item in summary["cases"].items():
            cid = int(case)
            if int(item["case_id"]) != cid:
                raise LineageError("Preflight case identity mismatch")
            if item.get("patch_applied") is not True:
                raise LineageError(f"Patch not source-recorded applied: {prefix} {cid}")
            name = item["filename"]
            expected_filename = f"CASE_{cid:05d}_{item['arm']}.patch"
            if name != expected_filename:
                raise LineageError(f"Wrong patch basename: {name}")
            path = entry(z, f"{prefix}/CASE_{cid:05d}/{name}")
            direct = z.read(path)
            if direct != inner.read(name):
                raise LineageError(f"Embedded patch differs from direct patch: {name}")
            if hashlib.sha256(direct).hexdigest() != item["original_patch_sha256"]:
                raise LineageError(f"Preflight patch hash mismatch: {name}")
            if len(direct) != item["original_patch_bytes"]:
                raise LineageError(f"Preflight patch byte count mismatch: {name}")
            if item.get("applycheck_returncode", item.get("git_apply_check_returncode")) != 0:
                raise LineageError(f"Nonzero preflight patch check: {name}")
            if item.get("apply_returncode", item.get("git_apply_returncode")) != 0:
                raise LineageError(f"Nonzero preflight patch apply: {name}")
            matches += 1
    return {"nested_patch_zip_sha256": digest, "direct_patch_matches": matches}


def screening_groups(z: zipfile.ZipFile) -> dict:
    groups: dict[str,dict[str,str]] = defaultdict(dict)
    for name in z.namelist():
        parts = name.split("/")
        if len(parts) < 4 or not parts[2].startswith("screen65_") or not name.endswith(".patch"):
            continue
        case = parts[-1]
        if not re.fullmatch(r"CASE_\d{5}\.patch", case):
            raise LineageError(f"Unknown 65-case patch basename: {case}")
        groups[parts[2]][case] = hashlib.sha256(z.read(name)).hexdigest()
    if len(groups) != 3 or any(len(group) != 65 for group in groups.values()):
        raise LineageError("Expected three 65-case screening patch sets")
    patches = list(groups.values())
    if set(patches[0]) != set(patches[1]) or set(patches[0]) != set(patches[2]):
        raise LineageError("65-case stage membership changed")
    unchanged = sum(len({group[name] for group in patches}) < 3 for name in patches[0])
    return {"distinct_cases": 65, "patches_across_three_stages": 195,
            "stage_names": sorted(groups),
            "cases_with_identical_patch_bytes_in_any_two_stages": unchanged}


def driver_source_summary(z: zipfile.ZipFile) -> dict:
    categories = Counter()
    invalid = []
    for info in z.infolist():
        if info.filename.endswith(".py"):
            categories["python"] += 1
            try:
                ast.parse(z.read(info).decode("utf-8"), filename=info.filename)
            except (SyntaxError, UnicodeDecodeError) as error:
                invalid.append({"relative_job_path": info.filename.split("/jobs/", 1)[-1],
                                "line": getattr(error, "lineno", None), "kind": type(error).__name__})
        elif info.filename.endswith(".sbatch"):
            categories["slurm"] += 1
        elif info.filename.endswith(".out"):
            categories["stdout_logs"] += 1
        elif info.filename.endswith(".err"):
            categories["stderr_logs"] += 1
    if categories != Counter({"python":41,"slurm":63,"stdout_logs":248,"stderr_logs":248}):
        raise LineageError(f"Unexpected driver archive composition: {categories}")
    # Preserve bad historical evidence, rather than treating all historical code as runnable.
    if len(invalid) != 1 or invalid[0]["relative_job_path"] != "owp14_20261018_v4/eval_668_uploaded_scannerfix.py":
        raise LineageError(f"Unexpected Python syntax failures: {invalid}")
    frozen = z.read(entry(z, "owp14_20261018_v1/freeze14.py")).decode("utf-8")
    parsed = ast.parse(frozen)
    spec = next((node.value for node in parsed.body if isinstance(node, ast.Assign) and
                 any(isinstance(target, ast.Name) and target.id == "SPECS" for target in node.targets)), None)
    if spec is None or len(ast.literal_eval(spec)) != 14:
        raise LineageError("Missing or changed O/W/P target-spec mapping")
    source_marker = '"generations_started":0'
    if source_marker not in frozen or '"historical_issue_body_verified_asof_pr":False' not in frozen:
        raise LineageError("Freeze report no longer carries explicit generation/provenance limits")
    if '"O":b""' not in frozen or '"P":property_text.encode()' not in frozen or '"W":(' not in frozen:
        raise LineageError("Unexpected O/W/P prompt-composition code")
    return {"python_files":categories["python"],"python_syntax_pass":40,
            "python_syntax_fail":len(invalid),"broken_script":invalid[0],
            "slurm_scripts":categories["slurm"],
            "stdout_logs":categories["stdout_logs"],"stderr_logs":categories["stderr_logs"],
            "packet_template_defined":True,"target_specs":14,
            "complete_model_session_transcripts_in_uploaded_archive":False,
            "generation_cohort_comparability_verified":False,
            "original_issue_asof_pr_verified":False,
            "case_00668_old_frozen_packet_exception":True}


def verify_scanner_link(zscan: zipfile.ZipFile, preflight: dict[str,dict]) -> dict:
    folders = {"O":"owp14_user12_o_codeql_job71159", "W":"owp14_user14_w_codeql_job71209", "P":"owp14_user14_p_codeql_job71204"}
    compared = 0
    mode = Counter()
    version = Counter()
    seen_sha = defaultdict(set)
    for arm, summary in preflight.items():
        for cid, item in summary["cases"].items():
            rec = json.loads(zscan.read(entry(zscan, f"{folders[arm]}/CASE_{int(cid):05d}/RESULT.json")))
            if rec["patch_sha256"] != item["original_patch_sha256"]:
                raise LineageError(f"Patch/scan SHA mismatch for {cid} {arm}")
            if rec["frozen_source_sha256"] != item["frozen_input_sha256"]:
                raise LineageError(f"Packet source archive hash mismatch for {cid} {arm}")
            if rec["stage"] != "SCAN_COMPLETE" or rec["arm"] != arm or int(rec["case_id"]) != int(cid):
                raise LineageError(f"Unexpected scan status for {cid} {arm}")
            version[rec.get("current_codeql_version")] += 1
            mode[rec.get("baseline_mode")] += 1
            if rec.get("baseline_version_match") is not True:
                raise LineageError(f"Archived baseline version not matched: {cid} {arm}")
            seen_sha[int(cid)].add(rec["baseline_sarif_sha256"])
            compared += 1
    if compared != 40 or len(seen_sha) != 14 or any(len(v) != 1 for v in seen_sha.values()):
        raise LineageError("Unpaired baselines or incorrect scan count")
    return {"patch_to_scanner_sha_matches": compared, "distinct_case_baselines": len(seen_sha),
            "archived_baseline_modes": dict(mode), "scanner_versions":dict(version),
            "baseline_files_present_in_scan_zip":any(n.endswith("/before.sarif") or n.endswith("/before_newversion.sarif") for n in zscan.namelist())}


def audit(patches: Path, drivers: Path, scanner: Path | None = None) -> dict:
    with zipfile.ZipFile(patches) as zp, zipfile.ZipFile(drivers) as zd:
        checks = {"patches":indexed_archive(zp), "drivers":indexed_archive(zd)}
        bases = {"O":"owp14_user12_o_preflight_job71153", "W":"owp14_user14_w_preflight_job71208", "P":"owp14_user14_p_preflight_job71201"}
        summaries = {arm:owp_summary(zp, prefix) for arm,prefix in bases.items()}
        if {arm:len(s["cases"]) for arm,s in summaries.items()} != {"O":12,"W":14,"P":14}:
            raise LineageError("O/W/P cohort size differs")
        if any(s["stage"] != "COMPLETE" for s in summaries.values()):
            raise LineageError("Historical patch preflight incomplete")
        transfers = {arm:compare_inner_transfer(zp,bases[arm],s) for arm,s in summaries.items()}
        cohort = {arm:set(map(int,s["cases"])) for arm,s in summaries.items()}
        if len(cohort["O"] | cohort["W"] | cohort["P"]) != 14 or cohort["W"] != cohort["P"] or not cohort["O"] <= cohort["W"]:
            raise LineageError("Unexpected patch case membership")
        patch_groups = Counter(n.split("/")[2] for n in zp.namelist() if n.endswith(".patch"))
        screen = screening_groups(zp)
        drivers_result = driver_source_summary(zd)
        scanner_result = None
        if scanner is not None:
            with zipfile.ZipFile(scanner) as zs:
                scanner_result = verify_scanner_link(zs,summaries)
        return {
            "status":"ARCHIVE_AND_PATCH_SCAN_LINEAGE_VERIFIED_ONLY",
            "archive_sha256":{"patches":hash_file(patches),"drivers":hash_file(drivers)},
            "indexed_members_verified":checks,
            "patch_file_counts":dict(sorted(patch_groups.items())),
            "owp":{
                "case_count":len(cohort["W"]),"patch_count":sum(len(v) for v in cohort.values()),
                "arms":{arm:len(v) for arm,v in cohort.items()},
                "missing_O_cases":sorted(cohort["W"]-cohort["O"]),
                "nested_transfers":transfers},
            "screening":screen,
            "drivers":drivers_result,
            "scanner_join":scanner_result,
            "limitations":[
                "This archive contains prompt construction code and Slurm logs, not complete coding-agent session transcripts.",
                "Historical pre-PR issue text and independent generation cohorts are explicitly not verified.",
                "W contains an exact historical CodeQL warning; this is a retrospective oracle, not a prospective predictor.",
                "P contains task-specific safety/property information; neither arm has matched token budget or model settings established.",
                "No independent original-issue functional acceptance, warning delta recomputation, or vulnerability prevention is demonstrated.",
                "All source-root originals and baseline SARIF remain external and require digest-verified separate recovery.",
            ],
        }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("patches",type=Path)
    p.add_argument("drivers",type=Path)
    p.add_argument("--scanner",type=Path,default=None)
    a = p.parse_args(argv)
    try:
        report = audit(a.patches,a.drivers,a.scanner)
    except (LineageError, zipfile.BadZipFile, OSError, KeyError, ValueError, SyntaxError) as ex:
        print(json.dumps({"status":"FAIL","message":str(ex)},indent=2))
        return 1
    print(json.dumps(report,indent=2,sort_keys=True))
    return 0


if __name__=="__main__":
    sys.exit(main())
