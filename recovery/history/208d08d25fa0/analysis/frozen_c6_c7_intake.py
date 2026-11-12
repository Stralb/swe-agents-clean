"""Offline, fail-closed intake of the source-declared frozen C7 bundle.

Verifies source-byte identity, safe archive structure and 190-pair membership.
Does NOT recreate completed semantic labels, p-values or C7 pathways.
Neither the original files nor any Wits/HF/Library sources are opened by CI.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import stat
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[1]
C7_ARCHIVE_NAME = "C7_CONTROL_PATHWAY_INTEGRATION_v1.0.tar.gz"
C7_ARCHIVE_BYTES = 106359
C7_ARCHIVE_SHA256 = "976b523c3df347c82a81998a31585536e5dc826c9b61f55220190fa75b5f8273"
C7_FILE_SIZES = {
    "C7_MATCHED_PATHWAY_MASTER_190.csv": 112254,
    "C7_PATHWAY_STRATA_COMPARISON.csv": 5831,
    "C7_VALIDATED_PROVENANCE_OVERLAY.csv": 1377,
    "C7_SYNTHESIS_FINDINGS.csv": 2539,
    "C7_REPORT.md": 7027,
}
MAX_MEMBERS = 150
MAX_MEMBER_BYTES = 16 * 1024 * 1024
MAX_TOTAL_DECOMPRESSED_BYTES = 64 * 1024 * 1024
POSITIVE_ALIASES = {"positive_case_id", "positive_id"}
CONTROL_ALIASES = {"control_case_id", "negative_case_id", "matched_control_case_id"}


class C6C7IntakeError(ValueError):
    """Frozen source-byte, path-safety or pair-table evidence contract failed."""


def require(cond: bool, why: str) -> None:
    if not cond:
        raise C6C7IntakeError(why)


def source_inventory() -> dict:
    """Metadata observed in researcher Library, NOT independently hashed bytes."""
    return {
        "status": "SOURCE_LOCATED_NOT_INDEPENDENTLY_REPLAYED",
        "source_location": "Researcher Library: /Arno Research Stuff/",
        "c4_completed_first_pass": "C4_CONTROL_SEMANTIC_MASTER_190_FIRST_PASS.csv",
        "c5_completed_frozen": "C5_CONTROL_MASTER_190_FROZEN.csv",
        "c6_master": "C6_MATCHED_PAIR_MASTER_190.csv",
        "c6_contingencies": "C6_PAIRED_CONTINGENCY_LONG.csv",
        "c6_primary_results": "C6_PRIMARY_OMNIBUS_RESULTS.csv",
        "c6_same_repository_sensitivity": "C6_TIER_A_SAME_REPO_SENSITIVITY.csv",
        "c6_source_reported_pairs": 190,
        "c6_source_reported_review_complete_pairs": 189,
        "c6_review_missingness_correction": "one control review endpoint 404: missing, not no-review",
        "c6_raw_master_available_in_this_runtime": False,
        "c6_statistical_tests_recomputed": False,
        "c7_package": C7_ARCHIVE_NAME,
        "c7_expected_package_sha256": C7_ARCHIVE_SHA256,
        "c7_package_bytes_from_library_catalog": C7_ARCHIVE_BYTES,
        "c7_pair_master": "C7_MATCHED_PATHWAY_MASTER_190.csv",
        "c7_source_reported_pairs": 190,
        "c7_source_reported_mapped_pcs": 416,
        "c7_raw_master_available_in_this_runtime": False,
        "c7_package_bytes_independently_verified": False,
        "scanner_results_reproduced": False,
        "statistical_results_reproduced": False,
        "causal_effects_estimated": False,
        "note": "Source location and reported outputs are not independent replication.",
    }


def _stat(path: Path) -> tuple[int, int, int, int, int]:
    s = path.stat()
    return (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)


def _external_regular(path: Path, expected_size: int) -> tuple[Path, tuple]:
    path = path.absolute()
    require(path != ROOT and ROOT not in path.parents,
            "Frozen source must be staged outside the Git checkout")
    require(all(not p.is_symlink() for p in (path, *path.parents)),
            "Refusing symlink in staged archive path")
    require(path.is_file() and stat.S_ISREG(path.stat().st_mode),
            "Missing or non-regular source archive")
    initial = _stat(path)
    require(initial[2] == expected_size and initial[2] > 0,
            "C7 archive size differs from source catalog")
    return path, initial


def _safe_member(name: str) -> str:
    require(name and "\\" not in name and "\x00" not in name,
            "Unsafe archive member name")
    path = PurePosixPath(name)
    require(not path.is_absolute() and
            all(part not in {"", ".", ".."} for part in name.split("/")) and
            all(ord(char) >= 32 for char in name),
            "Unsafe archive member path")
    return name


def _source_rows(data: bytes, description: str) -> list[dict[str, str]]:
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise C6C7IntakeError(description + " invalid UTF-8") from exc
    with io.StringIO(text, newline="") as stream:
        reader = csv.DictReader(stream, strict=True)
        require(reader.fieldnames is not None and
                len(set(reader.fieldnames)) == len(reader.fieldnames),
                description + " ambiguous CSV header")
        rows = list(reader)
    require(bool(rows) and all(None not in row and
            all(v is not None for v in row.values()) for row in rows),
            description + " malformed CSV")
    return rows


def _pair_membership(rows: list[dict[str, str]], expected_pairs: int) -> None:
    require(len(rows) == expected_pairs, "C7 master pair denominator differs")
    columns = set(rows[0])
    pcols = sorted(columns & POSITIVE_ALIASES)
    ccols = sorted(columns & CONTROL_ALIASES)
    require(len(pcols) == 1 and len(ccols) == 1,
            "C7 pair identifier schema not established; do not guess columns")
    pcol, ccol = pcols[0], ccols[0]
    pos, control = set(), set()
    for row in rows:
        p, c = row[pcol].strip(), row[ccol].strip()
        require(p.isascii() and p.isdecimal() and str(int(p)) == p and
                c.isascii() and c.isdecimal() and str(int(c)) == c,
                "C7 malformed pair ID")
        require(p not in pos and c not in control,
                "C7 reused positive or control case")
        pos.add(p)
        control.add(c)
    require(len(pos) == len(control) == expected_pairs,
            "C7 paired membership is incomplete")


def verify_staged_c7(archive: Path, *, expected_sha256: str = C7_ARCHIVE_SHA256,
                     expected_bytes: int = C7_ARCHIVE_BYTES,
                     required_sizes: dict[str, int] | None = None,
                     expected_pairs: int = 190) -> dict:
    """Synthetic unit tests can override pins. Public CLI cannot."""
    if required_sizes is None:
        required_sizes = C7_FILE_SIZES
    require(re.fullmatch(r"[a-f0-9]{64}", expected_sha256) is not None,
            "Missing/invalid expected C7 source fingerprint")
    archive, stat_before = _external_regular(archive, expected_bytes)
    body = archive.read_bytes()
    require(hashlib.sha256(body).hexdigest() == expected_sha256,
            "C7 package SHA-256 does not match archived expected fingerprint")
    require(_stat(archive) == stat_before, "Source archive changed during hash check")

    files = {}
    total_size = 0
    try:
        with tarfile.open(fileobj=io.BytesIO(body), mode="r:gz") as tf:
            members = tf.getmembers()
            require(0 < len(members) <= MAX_MEMBERS, "Unsafe archive member count")
            seen_names = set()
            for m in members:
                name = _safe_member(m.name.rstrip("/") if m.isdir() else m.name)
                require(name not in seen_names, "Duplicate archive entry name")
                seen_names.add(name)
                require(m.isfile() or m.isdir(),
                        "Archive contains links, devices or unsupported members")
                if m.isdir():
                    continue
                require(0 <= m.size <= MAX_MEMBER_BYTES,
                        "Oversized archive member")
                total_size += m.size
                require(total_size <= MAX_TOTAL_DECOMPRESSED_BYTES,
                        "Archive decompression limit exceeded")
                base = PurePosixPath(name).name
                if base in required_sizes:
                    require(base not in files, "Duplicate required basename across archive paths")
                    require(m.size == required_sizes[base],
                            "Archived C7 file length differs from original catalog")
                    stream = tf.extractfile(m)
                    require(stream is not None, "Cannot stream source member")
                    data = stream.read(m.size + 1)
                    require(len(data) == m.size,
                            "Archived member read truncated")
                    files[base] = data
    except (tarfile.TarError, EOFError, OSError) as exc:
        raise C6C7IntakeError("Invalid C7 tar stream") from exc
    require(_stat(archive) == stat_before, "Source archive changed during parse")
    require(set(files) == set(required_sizes),
            "C7 archive missing a required source file")
    _pair_membership(_source_rows(files["C7_MATCHED_PATHWAY_MASTER_190.csv"],
                                  "C7 pair master"), expected_pairs)
    for name in ("C7_PATHWAY_STRATA_COMPARISON.csv",
                 "C7_VALIDATED_PROVENANCE_OVERLAY.csv",
                 "C7_SYNTHESIS_FINDINGS.csv"):
        _source_rows(files[name], name)
    return {
        "status": "PASS_HASH_VERIFIED_C7_ARCHIVE_AND_PAIR_ROSTER_ONLY",
        "source_sha256_verified": True,
        "source_bytes_verified": len(body),
        "source_required_files_verified": len(files),
        "unique_positive_pairs": expected_pairs,
        "unique_control_pairs": expected_pairs,
        "historical_c6_results_reproduced": False,
        "statistical_p_values_recomputed": False,
        "per_pc_pathway_mapping_reproduced": False,
        "historical_scanner_outcomes_reproduced": False,
        "note": "C7 source archive and 190 case memberships only; neither C6 matched test nor C7 semantic pathway assignments are reproduced.",
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="action", required=True)
    sub.add_parser("audit-recorded", help="Source locator metadata only")
    v = sub.add_parser("verify-staged-c7", help="Source-pinned local C7 archive")
    v.add_argument("archive", type=Path)
    options = ap.parse_args(argv)
    try:
        answer = source_inventory() if options.action == "audit-recorded" else verify_staged_c7(options.archive)
        code = 0
    except (C6C7IntakeError, OSError, csv.Error, ValueError, TypeError, KeyError) as exc:
        answer = {"status": "BLOCKED_C6_C7_SOURCE_OR_SCHEMA",
                  "error": str(exc), "independent_statistical_reproduction": False}
        code = 2
    print(json.dumps(answer, sort_keys=True, indent=2))
    return code


if __name__ == "__main__":
    sys.exit(main())
