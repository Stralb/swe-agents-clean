"""Verify the original Wits case-13918 36-root -> 131-finding evidence mapping.

Default runs on committed provenance only: counts, exact canonical-finding
membership and source SHA manifest, not live Wits bytes or vulnerability truth.
With --d2-root-dir, the 36 *original* individual D2 source JSON packet bytes
must each pass the original AServerV6-reported full-file SHA-256, before the
source-derived IDs, versions and single-PC membership are recalculated.

This is a source-accounting gate. Canonical findings are scanner records,
not 131 independent vulnerabilities, exploits, agent choices or new patches.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import date
import hashlib
import json
from pathlib import Path
import re

BASE = Path(__file__).resolve().parents[1]
MANIFEST = BASE / "provenance" / "case13918_original_D2_36_packets_131_findings_20261023.json"
ARCHIVE_SHA256 = "5bf8ed6baece182d263be4ef1e23f39cb6eba87043c17dcce4f610444397791b"
ARCHIVE_BYTES = 63478
CHRONOLOGY = BASE / "provenance" / "d_chronology_incomplete_41_lockfile_census_20261023.json"
SOURCE_PREFIX = "D_COMPLETE_ROOT_PROVENANCE_v1_0/02_PACKETS/by_root_A/"


class FindingCensusError(ValueError):
    """Source bytes/provenance or original root-to-finding membership changed."""


def require(flag: bool, msg: str) -> None:
    if not flag:
        raise FindingCensusError(msg)


def ids_from_rule_source(packet: dict) -> list[str]:
    require(isinstance(packet, dict) and packet.get("pc_count") == 1,
            "Original D2 packet was not a one-PC root")
    pcs = packet.get("constituent_pcs")
    require(isinstance(pcs, list) and len(pcs) == 1,
            "D2 root constituent PC count changed")
    evidence = pcs[0].get("evidence")
    require(isinstance(evidence, dict), "D2 packet evidence missing")
    raw = evidence.get("Canonical Finding ID(s)")
    require(isinstance(raw, str) and bool(raw),
            "Canonical finding source field missing")
    labels = [x.strip() for x in raw.split(";")]
    require(all(re.fullmatch(r"CF-[0-9]{4}", x) for x in labels)
            and len(set(labels)) == len(labels),
            "Malformed or repeated canonical finding in original D2 packet")
    return labels


def check(manifest: dict | None = None, *,
          original_root_dir: Path | None = None,
          original_archive_manifest_path: Path | None = None) -> dict:
    x = json.loads(MANIFEST.read_text(encoding="utf-8")) if manifest is None else manifest
    require(x.get("schema_version") == 1 and x.get("status") ==
            "ALL_36_ORIGINAL_D2_ROOT_PACKETS_FULL_SHA256_VERIFIED_131_CANONICAL_FINDINGS_EXACT_SOURCE_MAPPING",
            "Wrong D2 original source-census status")
    scope = x["scope"]
    require(scope.get("case_id") == 13918
            and scope.get("repository") == "Pimzino/spec-workflow-mcp"
            and scope.get("pr") == 173 and
            scope.get("pr_merged_utc") == "2025-12-19T13:54:38Z"
            and scope.get("original_D1_sha256") ==
            "ff1432d1959b501f62a9aeb18dface0976db11dbc59d31a233a24a816236ddf3"
            and scope.get("original_D_export_index_sha256") ==
            "cfca8cd2425d7043e89cdb4e06576f3e6794c09736bb5c85b4c0e8332cc3f4e6"
            and scope.get("original_C6_root_census_full_sha256_recomputed_current_turn")
            is False, "Historical workflow/source provenance changed")
    acquisition = x["source_acquisition"]
    require(acquisition.get("AServerV6_read_artifact_chunk_max_length") == 32768
            and acquisition.get("each_original_packet_fits_one_chunk") is True
            and acquisition.get("each_packet_chunk_bytes_equal_total_original_bytes")
            is True and acquisition.get("sha256_is_complete_file_digest_each") is True
            and acquisition.get("per_root_Canonical_Finding_IDs_crosschecked_against_JSON_evidence")
            is True and acquisition.get("original_36_packet_raw_bytes_committed_to_Git")
            is False, "Unverified original D2 packet acquisition claim")

    for key in (
        "original_D_final_route_labels_recovered",
        "all_131_advisory_publication_dates_verified",
        "all_131_findings_independent_vulnerabilities",
        "all_36_roots_independent_agent_decisions",
        "all_root_packages_reachable_exploitable",
        "findings_equivalent_to_36_producing_changes",
        "cases13918_in_190_original_C2_pairs",
        "original_root_boundaries_modified",
    ):
        require(x["scientific_limits"].get(key) is False,
                "Unsupported scanner vulnerability or original annotation claim: " + key)

    controls = json.loads(CHRONOLOGY.read_text(encoding="utf-8"))
    require(controls["population"]["lockfile_case13918_roots"] == 36
            and controls["population"]["chronology_incomplete_roots"] == 41
            and controls["case13918"]["C2_matched_positive_member"] is False,
            "Frozen 41-root or original C2 matched-control populations drifted")

    archive = x["original_D2_archived_checksum_manifest"]
    require(archive.get("path") ==
            "D_COMPLETE_ROOT_PROVENANCE_v1_0/02_PACKETS/SHA256SUMS.txt"
            and archive.get("size_bytes") == ARCHIVE_BYTES
            and archive.get("sha256_independently_recomputed_this_session")
            == ARCHIVE_SHA256
            and archive.get("independently_recomputed_sha256_tested_against_abc")
            is True and archive.get("unique_checksum_entries") == 690
            and archive.get("original_by_root_A_case13918_entries") == 36
            and archive.get("matches_live_complete_source_SHA256_for_all_36_packets")
            == 36 and archive.get("checksum_mismatches") == 0
            and archive.get("checksum_entries_collisions") == 0
            and archive.get("original_36_packet_files_themselves_client_side_SHA256_recomputed_this_session")
            is False,
            "Original archived 690-entry D2 hash manifest or 36 hash matches changed")

    roots = x["per_root"]
    require(isinstance(roots, list) and len(roots) == 36,
            "Original 36 D2 root packet count changed")
    all_finding_ids = []
    all_file_bytes = 0
    sizes = []
    package_names = []
    staged_cve_ids = {}
    for i, p in enumerate(roots, start=1):
        root_id = f"CROOT-13918-{i:02d}"
        require(p.get("root_id") == root_id and
                p.get("original_d2_packet") ==
                SOURCE_PREFIX + root_id + ".json" and p.get("pc_count") == 1,
                "D2 root order, filename or one-PC membership changed")
        size, sha = p.get("original_d2_bytes"), p.get("original_d2_sha256")
        require(type(size) is int and 1 <= size <= 32768
                and isinstance(sha, str) and
                re.fullmatch(r"[a-f0-9]{64}", sha) is not None,
                "Incomplete full-file original D2 checksum / byte metadata")
        package = p.get("package_name")
        version = p.get("version")
        require(isinstance(package, str) and bool(package)
                and isinstance(version, str) and bool(version),
                "Original root package/version missing")
        labels = p.get("canonical_finding_ids")
        require(isinstance(labels, list) and len(labels) >= 1 and
                all(isinstance(c, str) and
                    re.fullmatch(r"CF-[0-9]{4}", c) is not None for c in labels)
                and len(set(labels)) == len(labels),
                "Repeated/malformed canonical finding source ID")
        all_finding_ids.extend(labels)
        all_file_bytes += size
        sizes.append(len(labels))
        package_names.append(package)

        if original_root_dir is not None:
            src = original_root_dir / (root_id + ".json")
            require(src.is_file() and not src.is_symlink(),
                    "Missing/symlinked original D2 packet: " + root_id)
            require(src.stat().st_size == size,
                    "Original D2 packet byte size changed: " + root_id)
            b = src.read_bytes()
            require(hashlib.sha256(b).hexdigest() == sha,
                    "Original D2 packet SHA-256 changed: " + root_id)
            try:
                packet = json.loads(b.decode("utf-8", errors="strict"))
            except (UnicodeError, json.JSONDecodeError) as exc:
                raise FindingCensusError("Unparsable original D2 JSON: " + root_id) from exc
            require(packet.get("root_id") == root_id and
                    packet.get("case_id") == 13918 and
                    packet.get("root_summary") ==
                    f"Include {package} version {version} in package-lock.json.",
                    "Original D2 root issue/package/version changed: " + root_id)
            require(ids_from_rule_source(packet) == labels,
                    "Canonical finding IDs differ from original D2 packet: " + root_id)
            source_rule_ids = packet["constituent_pcs"][0]["evidence"].get("Rule ID(s)", "")
            staged_cve_ids[root_id] = set(re.findall(r"CVE-[0-9]{4}-[0-9]+", source_rule_ids))

    require(len(all_finding_ids) == len(set(all_finding_ids)) == 131,
            "Canonical findings overlap or 131 denominator changed")
    require(set(all_finding_ids) ==
            {f"CF-{n:04d}" for n in range(929, 1060)},
            "Original CF-0929..CF-1059 source range is incomplete")
    largest = sorted(sizes, reverse=True)
    require(largest[:2] == [34, 17] and
            sum(size == 1 for size in sizes) == 10
            and all_file_bytes == 319315,
            "Source-level finding multiplicity or original bytes changed")
    # Distinct npm package names are not independent causal mechanisms.
    require(Counter(package_names)["fast-uri"] == 2 and
            Counter(package_names)["minimatch"] == 2 and
            Counter(package_names)["picomatch"] == 2 and
            len(set(package_names)) == 33,
            "Original dependency package/version grouping changed")

    repeated = x["cross_version_CVE_repetition"]
    expected_paired = {
        "fast-uri": (("CROOT-13918-07", "CROOT-13918-08"),
                     ("3.1.0", "2.4.0"),
                     {"CVE-2026-13676", "CVE-2026-16221",
                      "CVE-2026-18446", "CVE-2026-6321", "CVE-2026-6322"}),
        "minimatch": (("CROOT-13918-29", "CROOT-13918-30"),
                      ("9.0.5", "10.1.1"),
                      {"CVE-2026-26996", "CVE-2026-27903", "CVE-2026-27904"}),
        "picomatch": (("CROOT-13918-32", "CROOT-13918-33"),
                      ("4.0.3", "2.3.1"),
                      {"CVE-2026-33671", "CVE-2026-33672"}),
    }
    require(repeated.get("repeated_distinct_CVE_identifiers_across_6_roots") == 10
            and repeated.get("same_CVE_in_two_root_packets_not_two_distinct_CVEs")
            is True and len(repeated.get("observed_pairs", [])) == 3,
            "Original version-paired CVE repetition count changed")
    for pair in repeated["observed_pairs"]:
        pkg = pair["package_name"]
        require(pkg in expected_paired, "Unexpected duplicated dependency name")
        expected_roots, expected_versions, cves = expected_paired[pkg]
        require(tuple(pair["root_ids"]) == expected_roots and
                tuple(pair["versions"]) == expected_versions and
                set(pair["repeated_CVE_ids"]) == cves and
                len(pair["repeated_CVE_ids"]) == len(cves),
                "Version-paired CVE source identifiers drifted")
        if original_root_dir is not None:
            for root in expected_roots:
                require(cves.issubset(staged_cve_ids[root]),
                        "Version-paired CVEs absent from original D2 packet: " + root)

    publication = x["publication_sanity_checks_CVE_2025"]
    expected_publication = {
        "CROOT-13918-05": ("ajv", "CVE-2025-69873",
                            "GHSA-2g4f-4pwh-qvx6", "2026-02-11"),
        "CROOT-13918-11": ("lodash-es", "CVE-2025-13465",
                            "GHSA-xxjr-mmjv-4gpg", "2026-01-21"),
        "CROOT-13918-35": ("qs", "CVE-2025-15284",
                            "GHSA-6rw7-vpxm-498p", "2025-12-30"),
    }
    require(publication.get("pr_merged_utc") == "2025-12-19T13:54:38Z" and
            publication.get("post_merge_publication_all_three") is True and
            publication.get("first_publication_date_earlier_than_GHSA_ruled_out")
            is False and
            publication.get("all_other_2026_CVE_ids_publication_dates_individually_verified")
            is False and len(publication.get("records", [])) == 3,
            "Incorrect retrospective 2025-CVE publication-audit claim")
    for item in publication["records"]:
        root = item["root_id"]
        require(root in expected_publication and
                (item["package_name"], item["cve"], item["ghsa"],
                 item["public_advisory_date_utc"]) == expected_publication[root]
                and item["url"].startswith("https://github.com/")
                and item["ghsa"] in item["url"]
                and date.fromisoformat(item["public_advisory_date_utc"]) >
                date.fromisoformat("2025-12-19"),
                "Source-linked 2025-CVE public advisory publication drifted")
        if original_root_dir is not None:
            require(item["cve"] in staged_cve_ids[root],
                    "Published CVE not in original D2 source packet: " + root)
    require({v["root_id"] for v in publication["records"]} ==
            set(expected_publication),
            "Three 2025-labelled CVE roots have changed")

    n = x["counts"]
    require(n["roots"] == 36 and n["producing_changes"] == 36 and
            n["canonical_findings"] == 131 and
            n["canonical_finding_range"] == "CF-0929..CF-1059" and
            n["all_131_finding_ids_unique_and_contiguous"] is True and
            n["distinct_workflows"] == 1 and
            n["roots_with_single_canonical_finding"] == 10 and
            n["max_root_finding_count"] == 34 and
            n["largest_two_root_findings"] == 51 and
            n["largest_two_fraction_of_131"] == 51/131 and
            n["all_original_D2_packet_SHA256_checked_from_complete_single_chunk"]
            is True and n["total_original_D2_packet_bytes"] == 319315 and
            n["excluded_positive_case_13918_from_original_C2"] is True,
            "Original D2 root, producing-change and scanner finding counts drifted")

    archive_replayed = original_archive_manifest_path is not None
    if archive_replayed:
        p = original_archive_manifest_path
        require(p.is_file() and not p.is_symlink(),
                "Original SHA256SUMS archive file missing or symlinked")
        require(p.stat().st_size == ARCHIVE_BYTES,
                "Original 690-entry SHA256SUMS archive byte size mismatch")
        raw_manifest = p.read_bytes()
        require(hashlib.sha256(raw_manifest).hexdigest() == ARCHIVE_SHA256,
                "Original D2 SHA256SUMS archive source hash mismatch")
        try:
            text = raw_manifest.decode("utf-8", errors="strict")
        except UnicodeError as exc:
            raise FindingCensusError("Archive checksum manifest invalid UTF-8") from exc
        archived = {}
        for line in text.splitlines():
            hit = re.fullmatch(r"([a-f0-9]{64})  (\S+)", line)
            require(hit is not None, "Malformed original SHA256SUMS.txt entry")
            fingerprint, relative = hit.groups()
            require(relative not in archived,
                    "Duplicate filename in original archived D2 SHA256SUMS")
            archived[relative] = fingerprint
        require(len(archived) == 690,
                "Original archived D2 SHA manifest entry count changed")
        for r in roots:
            relative = r["original_d2_packet"].replace(
                "D_COMPLETE_ROOT_PROVENANCE_v1_0/02_PACKETS/", "", 1
            )
            require(archived.get(relative) == r["original_d2_sha256"],
                    "Archived original D2 root packet source digest mismatch: "
                    + r["root_id"])

    return {
        "status": ("PASS_36_SHA256_STAGED_ORIGINAL_PACKETS_131_CANONICAL_FINDINGS"
                   if original_root_dir is not None else
                   "PASS_RECORDED_36_PACKET_SOURCE_SHA_MANIFEST_AND_131_FINDING_IDS"),
        "original_Wits_D2_packet_bytes_reauthenticated_in_this_execution":
            original_root_dir is not None,
        "original_archived_690_entry_D2_SHA_manifest_reauthenticated_in_this_execution":
            archive_replayed,
        "current_Wits_D2_packet_hashes_matched_original_archive": 36,
        "roots": 36,
        "producing_changes": 36,
        "distinct_canonical_scanner_findings": 131,
        "distinct_npm_package_names": len(set(package_names)),
        "multiple_root_package_names": 3,
        "largest_two_roots_scanner_findings": 51,
        "case13918_in_original_190_matched_pairs": False,
        "CVE_identifiers_repeated_across_two_dependency_versions": 10,
        "public_advisory_dates_postmerge_for_2025_labelled_CVEs": 3,
        "advisory_publication_census_complete": False,
        "scanner_findings_equate_to_independent_vulnerabilities": False,
        "original_D_semantic_root_labels_recovered": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--d2-root-dir", type=Path,
                        help="Staged original 36 root JSON packets (not committed)")
    parser.add_argument("--archived-sha-manifest", type=Path,
                        help="Original Wits D2 SHA256SUMS.txt, staged outside Git")
    args = parser.parse_args(argv)
    print(json.dumps(check(original_root_dir=args.d2_root_dir,
                           original_archive_manifest_path=args.archived_sha_manifest),
                     sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
