"""Read-only case-154 target-line chronology check, not a label rewrite.

The historical Wits Pass-A exporter records 02:38:57Z as this root's
'cumulative_diff_anchor' and labels ORIGINAL_ISSUE eligible_prechange=NO.
Read-only public GitHub snapshots establish that exact scanner-targeted line
was ABSENT at 02:38:57 and 02:45:52 and PRESENT at 02:55:56.
The linked issue was CREATED at 02:39:26 (before the actual target line).

The original issue body AS-OF the target commit and the agent's private
instruction stream have NOT been authenticated. A false NO temporal
classification is identified for source chronology, not automatically
replaced by YES.

Default mode checks reviewed/pinned source evidence only. Optional
--repo-dir independently checks git-show source content for all five immutable
SHAs, without writing or fetching from a network.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "provenance" / "case154_original_anchor_vs_target_line_timeline_20261023.json"
SOURCE_D2_SHA = "002e258d355ecd4ffcf63ecdc7bb2e2aa4d414cb11e1807283c0f0be2c9b1558"
EXPECTED_STAGES = [
    ("true_pr_base", "56c07dc86b6aa01ac800da8f25309133228a783c",
     "5e9e848a37af3d38872d800fcb49f3c7592abee2", False),
    ("original_exported_early_anchor_feature_commit",
     "ffe8f6fee30164d7e0e0a6d52c435d93ce8fbeb4",
     "2e66a86480f6be02039646bab1092f1a8ec43a8c", False),
    ("intermediate_feature_commit",
     "23f2db3c2e91373b70fb3d7a923c0f0f7842d1e5",
     "c712bc0e18bc74f7ac16cb7b018400dd3905031a", False),
    ("target_regex_introduction_commit",
     "8af3a292202668f2d3e254fee60cc959a7c126dd",
     "49c77445a4c862a6e1e6f5d6ed8ffe713dd1e7c5", True),
    ("pr_head_commit", "a5024f810ed3e4558648b6e056b38d204b0d9f94",
     "77ef7955dd3f0bc9a5c41f03759f647c604524fd", True),
]
EXPECTED_GIT_TIMES = {
    "original_exported_early_anchor_feature_commit": "2025-11-04T02:38:57Z",
    "intermediate_feature_commit": "2025-11-04T02:45:52Z",
    "target_regex_introduction_commit": "2025-11-04T02:55:56Z",
    "pr_head_commit": "2025-11-04T03:02:16Z",
}
FROZEN_ROOT_LINE = r"const phpTagRegex = /^(?:\s*|#!\/.*?\n|\uFEFF)*<\?(?:php|=)?/i;"
ISSUE_CREATED = "2025-11-04T02:39:26Z"
PR_OPENED = "2025-11-04T02:40:13Z"


class RootIntroductionError(ValueError):
    """Root-specific source chronology or claim provenance invalid."""


def require(flag: bool, msg: str) -> None:
    if not flag:
        raise RootIntroductionError(msg)


def seconds_between(a: str, b: str) -> int:
    start = datetime.fromisoformat(a.replace("Z", "+00:00"))
    end = datetime.fromisoformat(b.replace("Z", "+00:00"))
    require(start.utcoffset() == end.utcoffset() ==
            timezone.utc.utcoffset(None),
            "Original event timestamps must be in UTC")
    seconds = (end - start).total_seconds()
    require(seconds.is_integer(), "Expected exact whole-second ISO timestamps")
    return int(seconds)


def git_source(repo: Path, commit_sha: str, filename: str) -> bytes:
    require(repo.is_dir() and not repo.is_symlink(),
            "Staged public git repository must be a real local directory")
    require(re.fullmatch(r"[0-9a-f]{40}", commit_sha) is not None and
            filename == "src/indexer/codeintel.ts",
            "Requested staged git object/path is not on approved source list")
    proc = subprocess.run(
        ["git", "-C", str(repo), "show", commit_sha + ":" + filename],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        timeout=15, check=False,
    )
    require(proc.returncode == 0,
            "Could not read expected existing source snapshot from local Git: "
            + commit_sha)
    return proc.stdout


def git_blob_sha1(data: bytes) -> str:
    return hashlib.sha1(
        b"blob " + str(len(data)).encode("ascii") + bytes((0,)) + data
    ).hexdigest()


def audit(*, record: dict | None = None, staged_git: Path | None = None,
          original_wits_D2_root: Path | None = None) -> dict:
    x = json.loads(SOURCE.read_text(encoding="utf-8")) if record is None else record
    require(x.get("schema_version") == 1 and x.get("status") ==
            "VERIFIED_D2_ARCHIVED_ROOT_SOURCE_AND_PUBLIC_GIT_INTRODUCTION_CONFLICT__ISSUE_ELIGIBILITY_NEEDS_REVIEW"
            and x.get("case_id") == 154 and
            x.get("root_id") == "CROOT-00154-01" and
            x.get("repository") == "CAPHTECH/kiri" and
            x.get("issue_number") == 25 and x.get("pr_number") == 26,
            "Wrong original 154-root population/claim status")
    require(x.get("target_file") == "src/indexer/codeintel.ts" and
            x.get("target_immutable_token") == "const phpTagRegex = /" and
            x.get("target_exact_source") == FROZEN_ROOT_LINE,
            "Scanner-primary target source snippet changed")
    source = x["source_provenance"]
    d2 = source["Wits_root_packet"]
    require(d2.get("path") ==
            "D_COMPLETE_ROOT_PROVENANCE_v1_0/02_PACKETS/by_root_A/CROOT-00154-01.json"
            and d2.get("size_bytes") == 5023 and
            d2.get("sha256") == SOURCE_D2_SHA and
            d2.get("archived_D2_SHA256SUMS_matches") is True and
            d2.get("pc_id") == "P50-PC-0070" and
            d2.get("root_summary_contains_exact_target_regex") is True,
            "Original D2 case154 root source packet proof changed")
    require(source["Wits_original_D2_archived_manifest"].get(
        "sha256_independently_checked") ==
        "5bf8ed6baece182d263be4ef1e23f39cb6eba87043c17dcce4f610444397791b",
        "Original archived 690-entry D2 checksum source changed")

    pa = source["Wits_later_Pass_A"]
    require(pa.get("full_original_jsonl_bytes") == 25549416
            and pa.get("full_file_SHA256_checked_in_this_case") is False
            and pa.get("first_root_record_bytes") == 79159
            and pa.get("first_root_record_fully_parsed_from_first_3_Wits_chunks")
            is True and pa.get("chronology_channel_status") == "COMPLETE"
            and pa.get("introduction_method") == "cumulative_diff_anchor"
            and pa.get("introduction_status") == "resolved"
            and pa.get("introduction_confidence") == "high"
            and pa.get("original_issue_prechange_eligibility") == "NO"
            and pa.get("introduction_chronology_prechange_eligibility") == "N/A"
            and pa.get("recorded_root_introduction_timestamp_utc") ==
            EXPECTED_GIT_TIMES["original_exported_early_anchor_feature_commit"]
            and pa.get("analysis_rules_original_labels_present") is False
            and pa.get("analysis_rules_only_prechange_yes_may_support_H_or_T1_T4")
            is True and pa.get("evidence_item_counts") ==
            {"YES": 11, "NO": 4, "UNKNOWN": 3, "N/A": 3},
            "Historical Pass-A chronology/eligibility record modified")
    gh = source["GitHub_public_source"]
    require(gh.get("issue_created_at_utc") == ISSUE_CREATED
            and gh.get("pr_created_at_utc") == PR_OPENED
            and gh.get("pr_merged_at_utc") == "2025-11-04T03:05:24Z"
            and gh.get("GitHub_compare_early_to_second_one_commit") is True
            and gh.get("GitHub_compare_second_to_target_one_commit") is True
            and gh.get("direct_git_commit_source_snapshots_retrieved_for_all_five_stages")
            is True and
            gh.get("issue_metadata_read_from_public_GitHub_issue") is True,
            "Public issue/PR source chronology drifted")
    events = x["observations"]
    require(len(events) == len(EXPECTED_STAGES),
            "Missing original Git source comparison stage")
    for event, (name, sha, blob, present) in zip(events, EXPECTED_STAGES):
        require((event.get("stage"), event.get("sha"),
                 event.get("source_blob_sha1"),
                 event.get("source_target_line_present")) ==
                (name, sha, blob, present),
                "Original Git SHA / target regex source-presence audit changed: " + name)
        require(event.get("commit_utc") == EXPECTED_GIT_TIMES.get(name),
                "Git commit time or source anchor changed")
    arithmetic = x["arithmetic"]
    anchor = EXPECTED_GIT_TIMES["original_exported_early_anchor_feature_commit"]
    target = EXPECTED_GIT_TIMES["target_regex_introduction_commit"]
    require(seconds_between(anchor, ISSUE_CREATED) == 29
            and seconds_between(ISSUE_CREATED, PR_OPENED) == 47
            and seconds_between(ISSUE_CREATED, target) == 990
            and seconds_between(anchor, target) == 1019
            and arithmetic == {
                "exporter_anchor_precedes_issue_creation_seconds": 29,
                "confirmed_target_commit_follows_issue_creation_seconds": 990,
                "confirmed_target_commit_follows_exporter_early_anchor_seconds": 1019,
                "issue_creation_precedes_PR_open_seconds": 47,
            }, "Case154 original-root chronology arithmetic changed")
    limits = x["scientific_assessment"]
    for key in (
        "original_cumulative_diff_anchor_is_valid_first_target_line_commit",
        "issue_before_PR_implies_issue_before_every_root_change",
        "this_specific_root_issue_created_after_target_line_implementation",
        "original_issue_body_exact_version_asof_target_commit_authenticated",
        "model_received_or_read_issue_body_before_target_commit_authenticated",
        "Wits_original_issue_item_NO_temporal_classification_justified_by_target_commit_timestamp",
        "Wits_original_issue_item_prechange_YES_now_definitively_proven",
        "historical_D_final_D7_semantic_labels_authenticated",
        "all_342_root_intro_timestamps_independently_checked",
        "historical_Wits_data_or_classifications_mutated",
    ):
        require(limits.get(key) is False,
                "Unsupported causal/timing proof or mutation claim: " + key)
    require(limits.get(
        "this_specific_root_issue_created_before_confirmed_target_line_commit"
    ) is True, "Original issue-target sequence not proven")

    if original_wits_D2_root is not None:
        f = original_wits_D2_root
        require(f.is_file() and not f.is_symlink()
                and f.stat().st_size == 5023, "Original staged Wits D2 source invalid")
        buf = f.read_bytes()
        require(hashlib.sha256(buf).hexdigest() == SOURCE_D2_SHA,
                "Original staged Wits D2 root SHA differs from archive")
        packet = json.loads(buf.decode("utf-8"))
        require(packet.get("root_id") == "CROOT-00154-01"
                and packet.get("pc_count") == 1
                and FROZEN_ROOT_LINE in packet.get("root_summary", ""),
                "Wits root mechanism source target mismatch")

    if staged_git is not None:
        for name, sha, blob, present in EXPECTED_STAGES:
            data = git_source(staged_git, sha, x["target_file"])
            require(git_blob_sha1(data) == blob,
                    "Staged original Git source blob SHA mismatch: " + name)
            require((FROZEN_ROOT_LINE.encode("utf-8") in data) is present,
                    "Staged original scanner-primary line presence mismatch: " + name)

    return {
        "status": ("PASS_LOCAL_GIT_TARGET_COMMIT_SOURCE_REPLAY"
                   if staged_git is not None else
                   "PASS_RECORDED_PUBLIC_GIT_AND_ORIGINAL_WITS_D2_TARGET_LINE_CONFLICT"),
        "original_public_Git_snapshots_reread_now": staged_git is not None,
        "original_Wits_D2_source_rehashed_now": original_wits_D2_root is not None,
        "source_reported_early_anchor_before_issue_seconds": 29,
        "actual_target_line_commit_after_issue_seconds": 990,
        "early_cumulative_diff_anchor_is_not_target_line_introduction": True,
        "linked_issue_temporally_exists_before_target_line": True,
        "exact_issue_body_asof_target_verified": False,
        "agent_received_that_issue_verified": False,
        "original_NO_to_YES_label_changed": False,
        "original_D_semantic_route_labels_recovered": False,
    }


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-dir", type=Path,
                        help="Already-staged local public CAPHTECH/kiri Git checkout")
    parser.add_argument("--wits-d2-root", type=Path,
                        help="Authorized exact original CROOT-00154-01.json")
    args = parser.parse_args()
    print(json.dumps(audit(staged_git=args.repo_dir,
                           original_wits_D2_root=args.wits_d2_root),
                     indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
