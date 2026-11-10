"""Make a *derived* private archive of source-authenticated S5PAIR-001 replay files.

The original inputs are read-only. This never runs a patch, scanner or model;
reported results remain historical observations, not validation. Blinded run
identities must not be unblinded or mapped to cases without a separate source.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import re
import stat
import tempfile
import zipfile
from pathlib import Path
from typing import Any

from .research import canonical_json
from .store import EvidenceError, _hash_file

STUDY_ID = "S5PAIR001_STEP4_BLINDED"
SOURCE_PREFIX = "counterfactual_replay_r1/step4_blinded"
BASE_ROLES = [
    "input/BLINDED_MANIFEST.csv", "input/README.txt", "input/BASE_SHA256.txt",
    "results/BLINDED_CODEQL_SUMMARY.csv", "results/BLINDED_CODEQL_FINDINGS.csv",
    "results/STEP4_QC.json", "input/base.tar.gz", "results/_base.sarif",
]
SCANNER_RESULTS = "results/runs/{run_id}/results.sarif"
PATTERN = re.compile(r"G[0-9]{3}\Z")
HEX_SHA = re.compile(r"[0-9a-f]{64}\Z")


def _read_local(root: Path, relative: str, max_bytes: int = 128 * 1024 * 1024) -> bytes:
    # Refuse symlinks in every path element; do not read beyond the source tree.
    file_path = root
    for part in Path(relative).parts:
        if part in {"", ".", ".."}:
            raise EvidenceError("Unsafe relative path")
        file_path = file_path / part
        if file_path.is_symlink():
            raise EvidenceError(f"Symlink encountered: {file_path}")
    try:
        st = file_path.lstat()
    except FileNotFoundError as e:
        raise EvidenceError(f"Required replay artifact missing: {relative}") from e
    if not stat.S_ISREG(st.st_mode) or st.st_size > max_bytes:
        raise EvidenceError(f"Unexpected file type/size: {relative}")
    with file_path.open("rb") as fp:
        raw = fp.read(max_bytes + 1)
    st2 = file_path.lstat()
    if len(raw) != st.st_size or len(raw) > max_bytes or (st.st_ino, st.st_size, st.st_mtime_ns) != (st2.st_ino, st2.st_size, st2.st_mtime_ns):
        raise EvidenceError(f"Replay file changed during read: {relative}")
    return raw


def _maybe_read(root: Path, relative: str, *, required: bool) -> bytes | None:
    try:
        return _read_local(root, relative)
    except EvidenceError:
        if required:
            raise
        if (root / relative).exists() or (root / relative).is_symlink():
            # Invalid present file must not be concealed as missing.
            raise
        return None


def _csv(raw: bytes, name: str) -> list[dict[str, str]]:
    try:
        s = raw.decode("utf-8-sig")
    except UnicodeError as e:
        raise EvidenceError(f"Non-UTF8 evidence CSV: {name}") from e
    reader = csv.DictReader(io.StringIO(s, newline=""))
    if not reader.fieldnames or any(not x for x in reader.fieldnames) or len(set(reader.fieldnames)) != len(reader.fieldnames):
        raise EvidenceError("Invalid or duplicate CSV headers in " + name)
    result = list(reader)
    if any(None in r for r in result):
        raise EvidenceError("CSV contains rows with extra columns in " + name)
    return result


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def prepare_s5pair(source: str | Path, output: str | Path, *,
                   allow_missing_scans: bool = False,
                   allow_missing_base: bool = False) -> dict[str, Any]:
    """Read only exact source files; create new derived archive and run map.

    Source layout: a root containing input/ and results/. Output must not exist,
    nor may it reside inside the source. Source manifest hashes are checked for
    every patch/report, but no scientific result is recomputed.
    """
    src = Path(source).absolute()
    out = Path(output).absolute()
    if src.is_symlink() or not src.is_dir():
        raise EvidenceError("Source must be an existing non-symlink replay directory")
    if out == src or src in out.parents:
        raise EvidenceError("Output must be outside the original source tree")
    if out.exists() or out.is_symlink():
        raise EvidenceError("Output must be NEW; refusing overwrite")
    manifest_raw = _read_local(src, "input/BLINDED_MANIFEST.csv", 1024 * 1024)
    rows = _csv(manifest_raw, "BLINDED_MANIFEST.csv")
    required_fields = {"run_id", "patch_sha256", "report_sha256", "patch_bytes", "patch_apply_check", "report_run_id_check"}
    if not rows or not required_fields.issubset(rows[0]):
        raise EvidenceError("BLINDED_MANIFEST columns are incomplete")
    run_ids = [r["run_id"] for r in rows]
    if len(set(run_ids)) != len(run_ids) or any(not PATTERN.fullmatch(x) for x in run_ids):
        raise EvidenceError("Invalid or duplicate blinded run IDs")
    summary_raw = _read_local(src, "results/BLINDED_CODEQL_SUMMARY.csv", 1024 * 1024)
    summaries = _csv(summary_raw, "BLINDED_CODEQL_SUMMARY.csv")
    scans = {r["run_id"]: r for r in summaries}
    if len(scans) != len(summaries) or set(scans) != set(run_ids):
        raise EvidenceError("Blinded scanner summary has missing/duplicate/extra run IDs")
    qc_raw = _read_local(src, "results/STEP4_QC.json", 1024 * 1024)
    qc = json.loads(qc_raw)
    if not isinstance(qc, dict) or qc.get("runs_expected") != len(rows) or qc.get("runs_summarized") != len(rows):
        raise EvidenceError("Replay QC run counts disagree with manifest")
    base_info_raw = _read_local(src, "input/BASE_SHA256.txt", 8192)
    base_info = dict(line.split("=", 1) for line in base_info_raw.decode("ascii").splitlines() if "=" in line)
    if not HEX_SHA.fullmatch(base_info.get("archive_sha256", "")) or not re.fullmatch(r"[0-9a-f]{40}", base_info.get("base_commit", "")):
        raise EvidenceError("Base source hashes incomplete")
    if qc.get("base_archive_sha256") != base_info["archive_sha256"]:
        raise EvidenceError("QC base SHA conflicts with original base SHA")
    contents: dict[str, bytes] = {}
    absent: list[dict[str, str]] = []
    for rel in BASE_ROLES:
        optional = rel == "input/base.tar.gz" and allow_missing_base or rel == "results/_base.sarif" and allow_missing_scans
        data = _maybe_read(src, rel, required=not optional)
        if data is not None:
            contents[rel] = data
        else:
            absent.append({"relative_path": rel, "reason": "source file unavailable"})
    if "input/base.tar.gz" in contents and _sha(contents["input/base.tar.gz"]) != base_info["archive_sha256"]:
        raise EvidenceError("Frozen base archive SHA does not match BASE_SHA256.txt")
    meta = []
    runs = []
    for row in rows:
        rid = row["run_id"]
        patch_rel = f"input/patches/{rid}.patch"
        report_rel = f"input/reports/{rid}.txt"
        patch = _read_local(src, patch_rel, 20 * 1024 * 1024)
        report = _read_local(src, report_rel, 10 * 1024 * 1024)
        if any(not HEX_SHA.fullmatch(row.get(k, "")) for k in ("patch_sha256", "report_sha256")):
            raise EvidenceError(f"Malformed patch/report hash for {rid}")
        if len(patch) != int(row["patch_bytes"]) or _sha(patch) != row["patch_sha256"] or _sha(report) != row["report_sha256"]:
            raise EvidenceError(f"Generated patch/report bytes differ from source manifest: {rid}")
        if not report.decode("utf-8-sig", errors="replace").startswith(f"RUN_ID: {rid}\n"):
            raise EvidenceError(f"Run report identity mismatch for {rid}")
        contents[patch_rel] = patch
        contents[report_rel] = report
        scan_rel = SCANNER_RESULTS.format(run_id=rid)
        sarif = _maybe_read(src, scan_rel, required=not allow_missing_scans)
        if sarif is not None:
            contents[scan_rel] = sarif
        else:
            absent.append({"relative_path": scan_rel, "run_id": rid, "reason": "scanner SARIF unavailable"})
        roles = {
            "generated_patch": patch_rel, "generation_report": report_rel,
            "original_hash_manifest": "input/BLINDED_MANIFEST.csv",
            "scanner_summary": "results/BLINDED_CODEQL_SUMMARY.csv",
            "blinded_step4_qc": "results/STEP4_QC.json",
            "base_hash_record": "input/BASE_SHA256.txt",
        }
        if sarif is not None:
            roles["scanner_after"] = scan_rel
        if "results/_base.sarif" in contents:
            roles["scanner_before"] = "results/_base.sarif"
        if "input/base.tar.gz" in contents:
            roles["base_snapshot"] = "input/base.tar.gz"
        if "results/BLINDED_CODEQL_FINDINGS.csv" in contents:
            roles["scanner_findings_summary"] = "results/BLINDED_CODEQL_FINDINGS.csv"
        runs.append({
            "run_id": rid,
            "arm": "BLINDED_UNMAPPED",
            "base_commit_sha": base_info["base_commit"],
            "case_id": None,
            "model": None,
            "seed": None,
            "files": roles,
            "source_recorded_scanner": scans[rid],
            "source_recorded_patch_checks": {k: row[k] for k in ("patch_apply_check", "report_run_id_check")},
            "condition_unblinding_source": None,
            "functional_correctness_status": "NOT_INDEPENDENTLY_VERIFIED",
        })
        meta.append({"run_id": rid, "expected_patch_sha256": row["patch_sha256"],
                     "expected_report_sha256": row["report_sha256"],
                     "patch_bytes": len(patch), "scanner_sarif_bytes": len(sarif) if sarif is not None else None})
    output_parent = out.parent
    output_parent.mkdir(parents=True, exist_ok=True)
    out.mkdir(mode=0o700)
    try:
        archive = out / "S5PAIR001_STEP4_BLINDED_SOURCE_EVIDENCE_DERIVED.zip"
        with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=6, allowZip64=True) as z:
            for rel, raw in sorted(contents.items()):
                info = zipfile.ZipInfo(rel)
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o600 << 16
                z.writestr(info, raw, compress_type=zipfile.ZIP_DEFLATED)
        archive_sha, archive_bytes = _hash_file(archive)
        crosswalk = {
            "schema_version": 1,
            "source_archive_sha256": archive_sha,
            "study_id": STUDY_ID,
            "protocol_revision": "S5PAIR-001-STEP4A-source-recorded-blinded-no-conditions",
            "source_provenance": {
                "connector_source_relative_path": SOURCE_PREFIX,
                "source_manifest_sha256": _sha(manifest_raw),
                "source_qc_sha256": _sha(qc_raw),
                "bundle_is_new_derivative_not_original": True,
                "scanner_and_functional_results_only_source_reported": True,
            },
            "runs": runs,
        }
        (out / "RUN_CROSSWALK_BLINDED.json").write_text(canonical_json(crosswalk) + "\n", encoding="utf-8")
        (out / "INGEST_AUDIT.json").write_text(json.dumps({
            "state": "SOURCE_BYTES_VERIFIED_FOR_PRESENT_MEMBERS_NOT_SCIENCE_REPLAYED",
            "source": SOURCE_PREFIX, "run_count": len(runs),
            "derived_archive_sha256": archive_sha, "derived_archive_bytes": archive_bytes,
            "source_file_count": len(contents), "source_file_hashes":
                {k: _sha(v) for k,v in sorted(contents.items())},
            "source_recorded_scanner_qc": qc,
            "pending_source_artifacts": absent,
            "per_run": meta,
            "missing_prompts": len(runs),
            "unblinded_conditions": 0,
            "conditions_inferred_from_names": False,
            "full_functional_test_validation": False,
        }, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
        return {"status": "DERIVED_ARCHIVE_PREPARED_READ_ONLY_SOURCE", "run_count": len(runs),
                "stored_source_members": len(contents), "archive_sha256": archive_sha,
                "archive_bytes": archive_bytes, "missing_source_files": len(absent),
                "output": str(out)}
    except BaseException:
        import shutil
        shutil.rmtree(out)
        raise


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Prepare private S5PAIR-001 evidence from a local read-only source copy")
    parser.add_argument("source", help="Path to source directory containing input/ and results/")
    parser.add_argument("output", help="New output directory outside source")
    parser.add_argument("--allow-missing-scans", action="store_true", help="Partial capture only, with explicit gaps")
    parser.add_argument("--allow-missing-base", action="store_true", help="Partial capture only, with explicit gap")
    args = parser.parse_args(argv)
    try:
        result = prepare_s5pair(args.source,args.output,allow_missing_scans=args.allow_missing_scans,
                                allow_missing_base=args.allow_missing_base)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except (EvidenceError, OSError, ValueError) as e:
        print(json.dumps({"status": "ERROR", "reason": str(e)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
