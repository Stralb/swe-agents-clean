#!/usr/bin/env python3
"""Append-only correction for the Arno private research DB.

Run on Wits under the original owner's account. No experiment regeneration.
Preflight verifies source bytes and constructs normalized records in memory;
--execute creates a NEW SQLite database by SQLite online backup, then inserts.
The historical v1 database and all source artifacts are opened read-only.
"""
import argparse
import csv
import hashlib
import json
import os
import shutil
import sqlite3
import sys
import time
import zipfile
import zlib
from collections import Counter
from pathlib import Path

ROOT = Path.home() / "research_artifacts"
JOBS = ROOT / "mcp_uploads/jobs"
SOURCE_DB = JOBS / "arno_unified_evidence_20261031_v1/output/ARNO_UNIFIED_FULL_EVIDENCE_DB.sqlite"
OUTPUT_DIR = JOBS / "arno_evidence_v2_20261101_corrective"
DEST = OUTPUT_DIR / "ARNO_UNIFIED_FULL_EVIDENCE_DB_v2.sqlite"
TEMP = OUTPUT_DIR / "ARNO_UNIFIED_FULL_EVIDENCE_DB_v2.sqlite.partial"
P123 = JOBS / "arno_v6_20261030_p1p2p3_blinded_runs_v2"
EVAL = JOBS / "arno_20261030_rpl7_matched_evaluation"
SCANS = JOBS / "arno_20261030_rpl7_patch_codeql_scans/results"
BASELINES = JOBS / "arno_20261030_rpl7_fresh_codeql_baselines/results"
RETURNED = ROOT / "mcp_uploads/arno_rpl7_patch_upload_20261030/RECEIPT_RPL7_RUN_04B827A1E668.zip"
AC = JOBS / "arno_ac6_v6_20261030"
EXPECTED_RETURNED_SHA = "c88bc9da10a830ffccd6c318a4da446440ed7aeb16ad4ef07f37c725edd3e9e6"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def file_digest(path):
    d = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(8 * 1024 * 1024), b""):
            d.update(block)
    return d.hexdigest()


def require(actual, expected, name):
    if actual != expected:
        raise ValueError(f"{name}: expected={expected!r}, actual={actual!r}")


def csv_rows(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def load_preflight():
    manifest = json.loads((P123 / "MANIFEST.json").read_text())
    by_run = {r["run_id"]: r for r in manifest["runs"]}
    require(len(by_run), 21, "P1/P2/P3 input count")
    result_rows = csv_rows(EVAL / "RUN_RESULTS.csv")
    require(len(result_rows), 21, "P1/P2/P3 output count")
    require(file_digest(RETURNED), EXPECTED_RETURNED_SHA, "original returned archive")
    payload = []
    totals = Counter()
    with zipfile.ZipFile(RETURNED) as original:
        require(len(original.infolist()), 42, "original output ZIP members")
        require(original.testzip(), None, "original output ZIP CRC")
        for row in result_rows:
            run, case, arm = row["run_id"], row["case_id"], row["condition"]
            info = by_run[run]
            require(info["condition"], arm, "P123 condition")
            input_path = P123 / "run_zips" / (run + ".zip")
            require(file_digest(input_path), info["sha256"], "generation input ZIP")
            with zipfile.ZipFile(input_path) as z:
                prompt, issue = z.read("PROMPT.md"), z.read("ISSUE.md")
            require(digest(prompt), info["prompt_sha256"], "prompt")
            require(digest(issue), info["issue_sha256"], "issue")
            location = SCANS / ("CASE_" + case) / run
            patch_path = location / ("PATCH_" + run + ".patch")
            receipt_path = location / ("RECEIPT_" + run + ".json")
            after_path = location / "after.sarif"
            before_path = BASELINES / ("CASE_" + case) / "baseline.sarif"
            result_path = location / "RESULT.json"
            patch = patch_path.read_bytes()
            receipt = receipt_path.read_bytes()
            after = after_path.read_bytes()
            before = before_path.read_bytes()
            result = json.loads(result_path.read_text())
            require(patch, original.read(patch_path.name), "returned patch equality")
            require(receipt, original.read(receipt_path.name), "returned receipt equality")
            require(digest(patch), row["patch_sha256"], "generated patch hash")
            require(digest(after), row["scan_sarif_sha256"], "after SARIF")
            require(digest(before), result["baseline_sarif_sha256"], "before SARIF")
            require(result["sanitized_repo_tree_sha256"], info["repo_tree_sha256"], "source tree")
            require(int(result["new_conservative_line_agnostic"]),
                    int(row["new_warning_line_agnostic"]), "new conservative alert count")
            if row["status"] != "CODEQL_SCAN_COMPLETE":
                raise ValueError("A scan previously recorded as complete is not complete: " + run)
            totals[arm] += int(row["new_warning_line_agnostic"])
            payload.append({
                "run": run, "case": int(case), "arm": arm,
                "cohort": "OCT2026_P123_NEW_RETROSPECTIVE",
                "source": row["source_kind"], "tree_sha": row["repo_tree_sha256"],
                "source_zip_sha": info["sha256"],
                "patch_sha": row["patch_sha256"], "after_sha": row["scan_sarif_sha256"],
                "before_sha": result["baseline_sarif_sha256"],
                "baseline": int(row["baseline_warning_count"]),
                "after": int(row["after_warning_count"]),
                "new": int(row["new_warning_line_agnostic"]),
                "receipt_status": row["receipt_status"],
                "functional": row["functional_status"],
                "agent_status": row["receipt_status"],
                "assets": [
                    ("PROMPT", prompt, str(input_path)),
                    ("ISSUE", issue, str(input_path)),
                    ("PATCH", patch, str(patch_path)),
                    ("RECEIPT", receipt, str(receipt_path)),
                    ("CODEQL_BEFORE_SARIF", before, str(before_path)),
                    ("CODEQL_AFTER_SARIF", after, str(after_path)),
                    ("SCANNER_RUN_RESULT", result_path.read_bytes(), str(result_path)),
                ],
            })
    require(dict(totals), {"P1": 15, "P2": 10, "P3": 10}, "P123 alert totals")
    require(len({r["patch_sha"] for r in payload}), 21, "unique P123 patch hashes")

    acrows = csv_rows(AC / "summary_v6e/RUNS.csv")
    require(len(acrows), 12, "A/C runs")
    acalerts = Counter()
    for row in acrows:
        case, arm, run = row["case_id"], row["arm"], row["run_id"]
        location = AC / "results_v6c" / ("CASE_" + case) / arm
        patch_path, receipt_path = location / "PATCH.patch", location / "RECEIPT.json"
        after_path, result_path = location / "after.sarif", location / "RESULT.json"
        before_path = BASELINES / ("CASE_" + case) / "baseline.sarif"
        patch, receipt, after = patch_path.read_bytes(), receipt_path.read_bytes(), after_path.read_bytes()
        before, result = before_path.read_bytes(), result_path.read_bytes()
        require(digest(patch), row["patch_sha256"], "AC patch")
        require(digest(receipt), row["receipt_sha256"], "AC receipt")
        require(digest(after), row["after_sarif_sha256"], "AC after SARIF")
        require(digest(result), row["result_json_sha256"], "AC result")
        bresult = json.loads((before_path.parent / "RESULT.json").read_text())
        require(int(bresult["result_count"]), int(row["baseline_total"]), "AC baseline total")
        require(digest(before), bresult["sarif_sha256"], "AC baseline hash")
        require(row["status"], "CODEQL_SCAN_COMPLETE", "AC scan status")
        payload.append({
            "run": run, "case": int(case), "arm": arm,
            "cohort": "OCT2026_AC_SIX_CASE_EXPLORATORY",
            "source": row["source_kind"], "tree_sha": row["repo_tree_sha256"],
            "source_zip_sha": row["source_zip_sha256"],
            "patch_sha": row["patch_sha256"], "after_sha": row["after_sarif_sha256"],
            "before_sha": digest(before),
            "baseline": int(row["baseline_total"]),
            "after": int(row["after_total"]),
            "new": int(row["new_warnings"]),
            "receipt_status": row["agent_generation_status"],
            "functional": row["functional_status"],
            "agent_status": row["agent_generation_status"],
            "assets": [
                ("PATCH", patch, str(patch_path)),
                ("RECEIPT", receipt, str(receipt_path)),
                ("CODEQL_BEFORE_SARIF", before, str(before_path)),
                ("CODEQL_AFTER_SARIF", after, str(after_path)),
                ("SCANNER_RUN_RESULT", result, str(result_path)),
            ],
        })
        acalerts[arm] += int(row["new_warnings"])
    require(len(payload), 33, "combined imported evidence rows")
    return payload, {"P123": dict(totals), "AC": dict(acalerts)}


def new_schema(conn):
    conn.executescript("""
    CREATE TABLE arno_v2_run_evidence(
      run_id TEXT PRIMARY KEY, case_id INTEGER NOT NULL, cohort TEXT NOT NULL,
      arm TEXT NOT NULL, source_status TEXT NOT NULL, source_tree_sha256 TEXT,
      input_zip_sha256 TEXT, patch_sha256 TEXT NOT NULL,
      before_sarif_sha256 TEXT, after_sarif_sha256 TEXT,
      before_count INTEGER, after_count INTEGER, introduced_count INTEGER,
      receipt_status TEXT, generation_status TEXT, functional_status TEXT);
    CREATE TABLE arno_v2_evidence_bytes(
      run_id TEXT NOT NULL REFERENCES arno_v2_run_evidence(run_id),
      role TEXT NOT NULL, source_path TEXT NOT NULL, sha256 TEXT NOT NULL,
      original_bytes INTEGER NOT NULL, zlib_blob BLOB NOT NULL,
      verification TEXT NOT NULL, PRIMARY KEY(run_id,role));
    CREATE TABLE arno_v2_archive_patch_crosswalk(
      archive_name TEXT, member_path TEXT, case_id TEXT,
      patch_sha256 TEXT, original_bytes INTEGER, indexed_in_master INTEGER,
      matched_master_tables TEXT, byte_status TEXT NOT NULL,
      PRIMARY KEY(archive_name,member_path));
    CREATE TABLE arno_v2_legacy_patch_crosswalk(
      evidence_key TEXT PRIMARY KEY, cohort TEXT NOT NULL,
      case_id INTEGER, patch_sha256 TEXT, storage_table TEXT,
      bytes_verified INTEGER NOT NULL, caveat TEXT);
    CREATE TABLE arno_v2_coverage_gaps(
      gap_id TEXT PRIMARY KEY, cohort TEXT NOT NULL, run_id TEXT,
      case_id INTEGER, missing_item TEXT NOT NULL, status TEXT NOT NULL,
      explanation TEXT NOT NULL);
    CREATE TABLE arno_v2_validation_ledger(
      validation TEXT PRIMARY KEY, count INTEGER, note TEXT);
    """)


def add_run(conn, item):
    run, case = item["run"], item["case"]
    conn.execute("INSERT INTO arno_v2_run_evidence VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
        run, case, item["cohort"], item["arm"], item["source"], item["tree_sha"],
        item["source_zip_sha"], item["patch_sha"], item["before_sha"], item["after_sha"],
        item["baseline"], item["after"], item["new"], item["receipt_status"],
        item["agent_status"], item["functional"]))
    for role, raw, source in item["assets"]:
        h = digest(raw)
        conn.execute("INSERT INTO arno_v2_evidence_bytes VALUES(?,?,?,?,?,?,?)", (
            run, role, source, h, len(raw), sqlite3.Binary(zlib.compress(raw, 6)),
            "ORIGINAL_BYTES_HASHED_AND_EMBEDDED"))
        conn.execute("""INSERT INTO study_artifacts
          (artifact_id,case_id,run_id,role,source_table,source_locator,sha256,storage_status,original_bytes)
          VALUES(?,?,?,?,?,?,?,?,?)""", (
            "V2:" + run + ":" + role, case, run, role, "arno_v2_evidence_bytes",
            run + "/" + role, h, "EMBEDDED_ZLIB_VERIFIED", len(raw)))

    existing = conn.execute("SELECT patch_sha256 FROM study_runs WHERE run_id=?", (run,)).fetchone()
    if existing:
        require(existing[0], item["patch_sha"], "existing P1 patch hash")
        return "previously_indexed"
    patch = next(raw for role, raw, _ in item["assets"] if role == "PATCH")
    sarif = next(raw for role, raw, _ in item["assets"] if role == "CODEQL_AFTER_SARIF")
    family = "OCT2026_NEW_P123" if item["cohort"].endswith("RETROSPECTIVE") else "OCT2026_AC_EXPLORATORY"
    treatment = "P123_" + item["arm"] if family == "OCT2026_NEW_P123" else "AC_" + item["arm"]
    conn.execute("INSERT INTO arno_experiment_runs VALUES(?,?,?,?,?,?,?,?)", (
        run, case, None, family, treatment, None,
        json.dumps({"import_version": "v2", "cohort": item["cohort"],
                    "generator_attested": False, "functional_validated": False}),
        "CODEQL_SCAN_COMPLETE_FUNCTIONAL_NOT_VERIFIED"))
    pid, sid = run + "::PATCH", run + "::CODEQL"
    conn.execute("INSERT INTO arno_generated_patches VALUES(?,?,?,?,?,?,?)", (
        pid, run, item["patch_sha"], sqlite3.Binary(patch), None,
        "RETURNED_PATCH_SHA256_VERIFIED_GENERATOR_NOT_ATTESTED",
        "Preserve experimental condition; scanner warnings are not confirmed vulnerabilities"))
    conn.execute("INSERT INTO arno_experiment_scans VALUES(?,?,?,?,?,?,?,?)", (
        sid, run, "CodeQL", None, None, sqlite3.Binary(sarif),
        json.dumps({"baseline": item["baseline"], "after": item["after"],
                    "introduced": item["new"], "baseline_sha256": item["before_sha"],
                    "after_sha256": item["after_sha"]}), 1))
    conn.execute("""INSERT INTO study_runs
      (run_id,case_id,experimental_family,treatment,run_status,source_snapshot_type,
       patch_id,patch_sha256,patch_embedded,scan_id,raw_scan_embedded,scan_execution_verified,
       before_count,after_count,number_new,number_new_target,before_sarif_sha256,
       after_sarif_sha256,historical_revision_equivalence,functional_status,
       patch_provenance_status,raw_patch_source_table,raw_scan_source_table,metrics_source_table)
      VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (
        run, case, family, treatment, "CODEQL_SCAN_COMPLETE_FUNCTIONAL_NOT_VERIFIED",
        item["source"], pid, item["patch_sha"], 1, sid, 1, 1,
        item["baseline"], item["after"], item["new"], None, item["before_sha"],
        item["after_sha"], "NOT_ATTESTED", item["functional"],
        "RETURNED_PATCH_SHA256_VERIFIED_GENERATOR_NOT_ATTESTED",
        "arno_generated_patches", "arno_experiment_scans", "arno_v2_run_evidence"))
    return "newly_imported"


def reconcile_legacy(conn):
    archive = conn.execute("""SELECT archive_name,member_path,case_id,sha256,
       original_bytes,indexed_in_master,matched_master_tables
       FROM arno_archive_vault_members WHERE role='PATCH'""").fetchall()
    require(len(archive), 255, "archive patch-member count")
    for name, member, case, h, size, matched, tables in archive:
        conn.execute("INSERT INTO arno_v2_archive_patch_crosswalk VALUES(?,?,?,?,?,?,?,?)", (
            name, member, case, h, size, matched, tables,
            "MASTER_MATCH_MEMBER_BYTES_NOT_REEXTRACTED" if matched
            else "ARCHIVE_ONLY_MEMBER_BYTES_NOT_REEXTRACTED"))
    require(sum(not r[5] for r in archive), 150, "archive-only patch members")

    repairs = conn.execute("""SELECT case_id,final_patch_sha256,final_patch_zlib
       FROM arno_seven_final_repair_case_evidence""").fetchall()
    require(len(repairs), 7, "final researcher-directed repairs")
    for case, h, compressed in repairs:
        require(digest(zlib.decompress(compressed)), h, "researcher-directed repair")
        conn.execute("INSERT INTO arno_v2_legacy_patch_crosswalk VALUES(?,?,?,?,?,?,?)", (
            "FINAL_REPAIR_" + str(case), "POSTHOC_RESEARCHER_DIRECTED_REPAIR",
            case, h, "arno_seven_final_repair_case_evidence", 1,
            "Not independent prospective prevention; source blob verified"))

    for arm in ("A", "B", "C"):
        conn.execute("INSERT INTO arno_v2_coverage_gaps VALUES(?,?,?,?,?,?,?)", (
            "CASE22223_" + arm, "CASE22223_INPUT_PILOTS", None, 22223,
            "Independently reconciled exact output patch and scanner receipt",
            "UNVERIFIED", "Pilot input exists; do not equate with the six-case A/C output arm"))
    ac_runs = conn.execute("""SELECT run_id,case_id FROM arno_v2_run_evidence
       WHERE cohort='OCT2026_AC_SIX_CASE_EXPLORATORY'""").fetchall()
    for run, case in ac_runs:
        conn.execute("INSERT INTO arno_v2_coverage_gaps VALUES(?,?,?,?,?,?,?)", (
            "PROMPT_" + run, "OCT2026_AC_SIX_CASE_EXPLORATORY", run, case,
            "Original prompt bytes and exact run/input packet pairing",
            "NOT_YET_ATTESTED", "AC input archives exist; prompt alignment needs separate reconciliation"))
    for key, n, note in (
        ("ARCHIVE_PATCH_MEMBERS", 255, "150 unmatched; no individual archive-member extraction attested"),
        ("RESEARCHER_DIRECTED_REPAIRS", 7, "all seven final patch blobs decompressed and SHA checked"),
        ("CASE22223_INPUT_ONLY_PILOTS", 3, "A/B/C inputs preserved, scan linkage remains unverified")):
        conn.execute("INSERT INTO arno_v2_validation_ledger VALUES(?,?,?)", (key, n, note))


def execute(payload, summary):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    if DEST.exists() or TEMP.exists():
        raise FileExistsError("Refusing to overwrite a previous v2 database or partial copy")
    size = SOURCE_DB.stat().st_size
    if shutil.disk_usage(OUTPUT_DIR).free < size + 5 * 1024**3:
        raise OSError("Insufficient disk headroom to create an independent v2 DB")
    print("Copying frozen v1 through SQLite online backup", flush=True)
    source = sqlite3.connect("file:" + str(SOURCE_DB) + "?mode=ro", uri=True)
    target = sqlite3.connect(TEMP)
    started = time.monotonic()
    try:
        source.backup(target, pages=20000)
        source.close()
        target.execute("PRAGMA foreign_keys=ON")
        new_schema(target)
        changes = Counter()
        for item in payload:
            changes[add_run(target, item)] += 1
        require(changes["newly_imported"], 26, "new P2/P3 and A/C runs")
        require(changes["previously_indexed"], 7, "already-indexed P1 runs")
        reconcile_legacy(target)
        require(target.execute("SELECT COUNT(*) FROM study_runs").fetchone()[0], 94,
                "new total study_runs")
        require(target.execute("SELECT COUNT(*) FROM arno_v2_run_evidence").fetchone()[0],
                33, "new evidence run index")
        problems = target.execute("PRAGMA foreign_key_check").fetchall()
        require(problems, [], "foreign-key validation")
        target.execute("INSERT INTO study_metadata VALUES(?,?)", (
            "v2_corrective_status", "26_NEW_RUNS_IMPORTED_WITH_PARTIAL_ARCHIVE_AND_AC_PROMPT_GAPS"))
        target.commit()
        validation = target.execute("PRAGMA quick_check").fetchone()[0]
        require(validation, "ok", "SQLite quick_check")
        target.close()
        report = {"status": "PASS_WITH_RECORDED_GAPS", "newly_imported_runs": 26,
                  "previously_indexed_P1": 7, "total_study_runs": 94,
                  "preflight_scanner_totals": summary,
                  "archive_members_crosswalked": 255, "archive_only": 150,
                  "archive_members_individually_reverified": 0,
                  "posthoc_repairs_verified": 7, "case22223_ABCs_unverified": 3,
                  "AC_prompt_bytes_joined": False,
                  "source_v1_bytes": size, "output_v2_bytes": TEMP.stat().st_size,
                  "runtime_seconds": round(time.monotonic() - started, 1),
                  "source_path": str(SOURCE_DB), "output_path": str(DEST)}
        temp_report = OUTPUT_DIR / "V2_INTEGRATION_QA.json.partial"
        temp_report.write_text(json.dumps(report, indent=2))
        os.replace(TEMP, DEST)
        os.replace(temp_report, OUTPUT_DIR / "V2_INTEGRATION_QA.json")
        print(json.dumps(report, indent=2), flush=True)
    except BaseException:
        target.close()
        source.close()
        raise


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true", help="create NEW 42 GB v2 DB")
    args = parser.parse_args()
    payload, summary = load_preflight()
    print(json.dumps({"preflight": "PASS", "runs_with_verified_patch_and_scan_bytes": len(payload),
                      "P123_21": True, "AC_12": True, "scanner_totals": summary,
                      "original_unchanged": True}, indent=2), flush=True)
    if args.execute:
        execute(payload, summary)


if __name__ == "__main__":
    main()
