"""Offline, read-only C3 blinded evidence and C2 mapping integrity check.

Requires *separately authorised* complete files outside Git. Checks SHA-256,
stored labels/rosters and blind separation; not semantic annotation or science.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
import re
import stat
import sys

ROOT = Path(__file__).resolve().parents[1]
BLIND = re.compile(r"CTRL-[0-9A-F]{10}\Z")
FROZEN = {
    "c2": ("", "C2_MATCHED_PAIRS_FROZEN.csv", 56175, "4568dcadd50e827004b13c9a435c7034babce8ebf96d6a9bee49b66c9b11be2b"),
    "map": ("90_LOCKED_MATCHING", "C3_BLIND_ID_MAP_LOCKED.csv", 14079, "214b1babe98fb0f50215b84dfaa11c9bcbfa2f3c6d1d39d06242c9daff622c55"),
    "manifest": ("", "C3_CONTROL_MANIFEST_BLINDED.csv", 9070, "4aa967a944ccd6b0c09483727c0c9ab7adac91cab1172d7696d3d3a22a1b9e4e"),
    "issue": ("01_ISSUE_BLIND", "C3_ISSUE_BLIND_190.csv", 534907, "22bce034d4d4e0c7eb57363752c6bd7f71e045474eaa3c676df158249ede02d2"),
    "pr": ("02_PR_BLIND", "C3_PR_BLIND_190.csv", 577084, "5281d81eb84c21d0a425d24263f716a91b7343c781eac4b2158477d1aa2fbc47"),
    "context": ("04_CONTEXT_SEPARATE", "C3_CONTEXT_RAW_190.csv", 1090666, "0224053cf034f97ff3ff5850bac1bfa18942c3c0f7de0431ed13832c0aff7bfb"),
    "issue_template": ("", "C3_ANNOTATION_TEMPLATE_ISSUE.csv", 4090, "ed036abda536eec5a418386f0c562bf506664fc9db986bf7cf1f63b57abeba0c"),
    "pr_template": ("", "C3_ANNOTATION_TEMPLATE_PR.csv", 4281, "364c78cf3daefb248e4741ea585ff69f390d8ca656c33ed46e20dbb697b226f4"),
    "implementation_template": ("", "C3_ANNOTATION_TEMPLATE_IMPLEMENTATION.csv", 3889, "e3cc1109c9f78f5449dc5ec7f8d99d3dd611702b2efb8da1881cae674684bb30"),
    "qc": ("99_QC", "C3_AUDIT.json", 871, "b8a2abbf7cfa31c5e086c4348aaf78b8604ac6f53d1cb14b7de57eb8cd797cff"),
}
HEADERS = {
    "map": ["blind_id", "control_case_id", "positive_case_id", "match_tier", "positive_repository", "control_repository"],
    "manifest": ["blind_id", "repository", "issue_number", "pr_number"],
    "issue": ["blind_id", "repository", "issue_number", "issue_title", "issue_body"],
    "pr": ["blind_id", "repository", "pr_number", "pr_title", "pr_body"],
    "context": ["blind_id", "repository", "issue_created_at", "pr_created_at", "pr_merged_at", "issue_to_pr_hours", "pr_to_merge_hours", "issue_author", "pr_author", "same_issue_pr_author", "issue_author_association", "pr_author_association", "pr_additions", "pr_deletions", "pr_changed_files", "review_rows_available", "ai_provenance_rows_json"],
    "issue_template": ["blind_id", "upstream_request_summary", "issue_purpose_category", "instruction_specificity", "human_review_note"],
    "pr_template": ["blind_id", "pr_stated_goal_summary", "pr_purpose_category", "goal_alignment", "alignment_note", "human_review_note"],
    "implementation_template": ["blind_id", "actual_implementation_summary", "actual_implementation_category", "human_review_note"],
}
C2_FIELDS = {"positive_case_id", "control_case_id", "match_tier", "positive_repository", "control_repository"}


class C3GateError(ValueError):
    """Frozen input invalid. Never return original issue/PR text."""


def _ensure(cond, message):
    if not cond:
        raise C3GateError(message)


def _stat(p):
    s = p.stat()
    return s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns


def _safe(p, role, directory=False):
    p = p.absolute()
    _ensure(ROOT not in (p, *p.parents), "Original C3 source cannot be inside Git")
    _ensure(all(not x.is_symlink() for x in (p, *p.parents)), role + ": symlink path")
    _ensure(p.is_dir() if directory else (p.is_file() and stat.S_ISREG(p.stat().st_mode)),
            role + ": missing or nonregular")
    return p


def _bytes(p, role, fingerprint):
    p = _safe(p, role)
    size, digest = fingerprint
    _ensure(type(size) is int and 0 < size <= 2 * 1024 * 1024 and
            isinstance(digest, str) and bool(re.fullmatch(r"[0-9a-f]{64}", digest)),
            role + ": invalid fingerprint")
    before = _stat(p)
    _ensure(before[2] == size, role + ": byte length mismatch")
    raw = p.read_bytes()
    _ensure(hashlib.sha256(raw).hexdigest() == digest, role + ": SHA-256 mismatch")
    _ensure(_stat(p) == before, role + ": input changed during verification")
    return raw


def _csv(raw, role):
    try:
        with io.StringIO(raw.decode("utf-8-sig"), newline="") as source:
            reader = csv.DictReader(source, strict=True)
            columns = reader.fieldnames
            _ensure(columns is not None and len(columns) == len(set(columns)),
                    role + ": malformed header")
            if role == "c2":
                _ensure(C2_FIELDS <= set(columns), "C2 source missing required fields")
            else:
                _ensure(columns == HEADERS[role], role + ": blinded schema mismatch")
            rows = list(reader)
    except (csv.Error, UnicodeError) as exc:
        raise C3GateError(role + ": malformed CSV") from exc
    _ensure(rows and all(None not in r and
            all(isinstance(v, str) for v in r.values()) for r in rows),
            role + ": malformed row")
    return rows


def _id(value, role):
    _ensure(isinstance(value, str) and value.isascii() and value.isdecimal()
            and str(int(value)) == value, role + ": noncanonical numeric ID")
    return value


def _blind(rows, role, n):
    indexed = {}
    for r in rows:
        bid = r["blind_id"]
        _ensure(bool(BLIND.fullmatch(bid)) and bid not in indexed,
                role + ": duplicate/malformed blind ID")
        indexed[bid] = r
    _ensure(len(indexed) == n, role + ": wrong blinded population")
    return indexed


def verify_c3(root: Path, c2_path: Path, *,
              fingerprints: dict | None = None, expected_count: int = 190,
              check_implementation_names: bool = True) -> dict:
    """Fixture-specific overrides are for synthetic tests only; CLI uses frozen pins."""
    _ensure(type(expected_count) is int and expected_count >= 1, "invalid cohort")
    root = _safe(root, "C3 root", directory=True)
    pins = {k: (v[2], v[3]) for k, v in FROZEN.items()} if fingerprints is None else fingerprints
    tables = {}
    report = None
    for role, (directory, name, _size, _digest) in FROZEN.items():
        path = c2_path if role == "c2" else root / directory / name
        raw = _bytes(path, role, pins[role])
        if role == "qc":
            try:
                report = json.loads(raw)
            except (UnicodeError, ValueError) as exc:
                raise C3GateError("C3 QC malformed JSON") from exc
        else:
            tables[role] = _csv(raw, role)
    pair_by_control, positives = {}, set()
    for r in tables["c2"]:
        ctrl, pos = _id(r["control_case_id"], "C2"), _id(r["positive_case_id"], "C2")
        _ensure(ctrl not in pair_by_control and pos not in positives and ctrl != pos,
                "C2 nonunique pairs")
        _ensure(r["match_tier"] in ("A", "B"), "C2 invalid tier")
        pair_by_control[ctrl] = r
        positives.add(pos)
    _ensure(len(pair_by_control) == expected_count, "C2 matched cohort size changed")
    map_by_id = _blind(tables["map"], "locked", expected_count)
    seen_ctrl, seen_positive = set(), set()
    for r in map_by_id.values():
        ctrl, pos = _id(r["control_case_id"], "C3"), _id(r["positive_case_id"], "C3")
        _ensure(ctrl in pair_by_control and ctrl not in seen_ctrl and pos not in seen_positive,
                "C3 reused/unmatched control or positive")
        seen_ctrl.add(ctrl)
        seen_positive.add(pos)
        reference = pair_by_control[ctrl]
        for field in ("positive_case_id", "match_tier", "positive_repository", "control_repository"):
            _ensure(r[field] == reference[field], "C3 locked mapping disagrees with C2")
    _ensure(seen_ctrl == set(pair_by_control), "C3 dropped C2 controls")
    manifest = _blind(tables["manifest"], "manifest", expected_count)
    _ensure(set(manifest) == set(map_by_id), "manifest blind IDs inconsistent")
    for bid, r in manifest.items():
        _ensure(r["repository"] == map_by_id[bid]["control_repository"],
                "manifest repository differs from control")
        _id(r["issue_number"], "issue")
        _id(r["pr_number"], "PR")
    for role, number in (("issue", "issue_number"), ("pr", "pr_number"), ("context", None)):
        rows = _blind(tables[role], role, expected_count)
        _ensure(set(rows) == set(map_by_id), role + ": unmatched blind IDs")
        for bid, r in rows.items():
            _ensure(r["repository"] == manifest[bid]["repository"], role + ": repository mismatch")
            if number:
                _ensure(r[number] == manifest[bid][number], role + ": number mismatch")
    for role in ("issue_template", "pr_template", "implementation_template"):
        rows = _blind(tables[role], role, expected_count)
        _ensure(set(rows) == set(map_by_id), role + ": unmatched template population")
        _ensure(all(not r[field].strip() for r in rows.values()
                    for field in HEADERS[role] if field != "blind_id"),
                role + ": frozen annotation template is not blank")
    _ensure(isinstance(report, dict) and report.get("qc_pass") is True and
            report.get("pair_count") == expected_count and
            report.get("control_count") == expected_count and
            report.get("blind_id_count") == expected_count and
            report.get("matching_data_separated") is True and
            report.get("positive_ids_present_only_in_locked_mapping") is True and
            report.get("scanner_runs_read") is False and
            report.get("scanner_findings_read") is False and
            report.get("pairs_sha256") == pins["c2"][1],
            "C3 frozen QC blinding contract changed")
    impl_checked = False
    if check_implementation_names:
        impl = _safe(root / "03_IMPLEMENTATION_BLIND", "blind implementation", directory=True)
        names = set()
        for p in impl.iterdir():
            _ensure(p.is_file() and not p.is_symlink() and p.suffix == ".txt",
                    "implementation packet invalid entry")
            names.add(p.stem)
        _ensure(names == set(map_by_id), "implementation packet filenames disagree")
        impl_checked = True
    return {
        "status": "PASS_FROZEN_C3_SOURCE_BYTES_AND_BLINDED_MEMBERSHIP_ONLY",
        "source_sha256_verified": len(FROZEN),
        "pairs_and_blind_ids": len(map_by_id),
        "issue_packets": len(tables["issue"]),
        "pr_packets": len(tables["pr"]),
        "separate_context_rows": len(tables["context"]),
        "unannotated_original_templates": 3,
        "original_annotation_cells_filled": 0,
        "implementation_packet_names_verified": impl_checked,
        "implementation_packet_content_hashed": False,
        "crossfile_mismatches": 0,
        "source_sqlite_authenticated": False,
        "security_findings_recomputed": False,
        "completed_annotations_authenticated": False,
        "statistical_results_reproduced": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("c3_root", type=Path)
    parser.add_argument("c2_matched_pairs", type=Path)
    args = parser.parse_args(argv)
    try:
        result = verify_c3(args.c3_root, args.c2_matched_pairs)
        status = 0
    except (C3GateError, OSError, ValueError, TypeError, KeyError) as exc:
        result = {"status": "BLOCKED_C3_EVIDENCE_GATE",
                  "error": str(exc), "scientific_reproduction_complete": False}
        status = 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return status


if __name__ == "__main__":
    sys.exit(main())
