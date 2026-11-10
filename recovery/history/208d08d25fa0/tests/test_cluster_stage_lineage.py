"""Offline synthetic and negative tests of frozen study-stage evidence.

Synthetic CSVs are created only in disposable temp directories. Test cases
never load the 841 KB private C1 cohort or 56 KB private C2 matched pairs.
"""
from __future__ import annotations

import contextlib
import copy
import csv
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from analysis.cluster_stage_lineage import (
    StageEvidenceError, audit_recorded, load_recorded,
    main, verify_local_c1_c2,
)


def sample_inputs(root: Path, *, tier: str = "A",
                  control_id: str = "2", sig_override: str | None = None):
    rows = [
        {"case_id": "1", "repository": "synthetic/repo-a", "is_positive": "1",
         "complete_opportunity_signature": "codeql;semgrep"},
        {"case_id": "2", "repository": "synthetic/repo-a", "is_positive": "0",
         "complete_opportunity_signature": "codeql;semgrep;trivy"},
        {"case_id": "3", "repository": "synthetic/repo-b", "is_positive": "0",
         "complete_opportunity_signature": "codeql;semgrep"},
    ]
    c1 = root / "synthetic-c1.csv"
    with c1.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    target = next(z for z in rows if z["case_id"] == control_id)
    c2 = root / "synthetic-c2.csv"
    matches = [{
        "positive_case_id": "1", "control_case_id": target["case_id"],
        "match_tier": tier, "same_repository": "1" if tier == "A" else "0",
        "positive_repository": "synthetic/repo-a",
        "control_repository": target["repository"],
        "opportunity_relation": "superset" if tier == "A" else "exact",
        "positive_opportunity_signature": "codeql;semgrep",
        "control_opportunity_signature": (
            sig_override if sig_override is not None
            else target["complete_opportunity_signature"]
        ),
        "abs_pr_time_days": "8.5",
    }]
    with c2.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(matches[0]))
        w.writeheader()
        w.writerows(matches)
    data = copy.deepcopy(load_recorded())
    for key, path, section, digest, size in (
        ("C1", c1, "c1_scanner_opportunity", "input_sha256", "input_bytes"),
        ("C2", c2, "c2_matching", "matched_pairs_sha256", "matched_pairs_bytes"),
    ):
        data[section][digest] = hashlib.sha256(path.read_bytes()).hexdigest()
        data[section][size] = path.stat().st_size
    return c1, c2, data


class FrozenClusterStageLineageTests(unittest.TestCase):
    def test_full_recorded_source_arithmetic_status(self):
        report = audit_recorded(load_recorded())
        self.assertEqual(report["status"],
                         "PASS_RECORDED_C1_C2_PHASE1_C_ROOT_ARITHMETIC_ONLY")
        self.assertEqual(report["final_c1_positive_cases_source_reported"], 192)
        self.assertEqual(report["final_c1_negative_pool_source_reported"], 3617)
        self.assertEqual(report["frozen_c2_pairs_source_reported"], 190)
        self.assertEqual(report["frozen_c2_same_repo_pairs"], 115)
        self.assertEqual(report["frozen_c2_cross_repo_pairs"], 75)
        self.assertEqual(report["phase1_changes_source_reported"], 455)
        self.assertEqual(report["phase1_workflows_source_reported"], 191)
        self.assertEqual(report["root_count_source_reported"], 342)
        self.assertEqual(report["root_distribution_size_weighted_sum"], 455)
        self.assertFalse(report["empirical_security_results_reproduced"])
        self.assertFalse(report["final_sqlite_bytes_independently_verified"])

    def test_intermediate_review_stages_are_not_192_frozen_positives(self):
        output = audit_recorded(load_recorded())
        self.assertEqual(output["intermediate_needs_review"], {
            "2026-08-17-hf-snapshot": 138,
            "2026-08-21-continuation": 198,
        })
        self.assertNotIn(192, output["intermediate_needs_review"].values())

    def test_455_finding_family_and_root_distribution_arithmetic(self):
        doc = load_recorded()
        self.assertEqual(sum(doc["phase1_producing_change_population"][
            "finding_family"].values()), 455)
        self.assertEqual(sum(doc["phase1_producing_change_population"][
            "introduction_status"].values()), 455)
        self.assertEqual(
            sum(int(k) * v for k, v in doc["c_root_census"][
                "root_size_distribution"].items()), 455)
        self.assertEqual(
            sum(doc["c_root_census"]["root_size_distribution"].values()), 342)

    def test_c1_to_c2_source_fingerprint_crosswalk(self):
        doc = load_recorded()
        self.assertEqual(
            doc["c1_scanner_opportunity"]["input_sha256"],
            doc["c2_matching"]["input_c1_expected_sha256"],
        )
        self.assertEqual(
            doc["c1_scanner_opportunity"]["db_sha256_reported"],
            doc["final_discovery_database"][
                "archived_source_and_manifest_expected_sha256"],
        )

    def test_tampered_tier_denominator_does_not_pass(self):
        doc = copy.deepcopy(load_recorded())
        doc["c2_matching"]["same_repo_tier_a"] = 114
        with self.assertRaisesRegex(StageEvidenceError, "matching-tier"):
            audit_recorded(doc)

    def test_tampered_positive_pool_does_not_pass(self):
        doc = copy.deepcopy(load_recorded())
        doc["c1_scanner_opportunity"]["potential_negatives"] = 3618
        with self.assertRaisesRegex(StageEvidenceError, "population partition"):
            audit_recorded(doc)

    def test_tampered_root_distribution_does_not_pass(self):
        doc = copy.deepcopy(load_recorded())
        doc["c_root_census"]["root_size_distribution"]["12"] = 2
        with self.assertRaises(StageEvidenceError):
            audit_recorded(doc)

    def test_41_unresolved_introduction_status_not_treated_as_verified(self):
        doc = copy.deepcopy(load_recorded())
        self.assertEqual(doc["phase1_producing_change_population"][
            "introduction_status"]["unresolved"], 41)
        doc["phase1_producing_change_population"][
            "introduction_status"]["unresolved"] = 0
        with self.assertRaisesRegex(StageEvidenceError, "partial-resolution"):
            audit_recorded(doc)

    def test_premature_claim_of_hf_revision_or_causal_proof_fails(self):
        for group, key in (
            ("final_discovery_database", "huggingface_private_revision_verified"),
            ("scope", "observational_causal_claim_justified"),
            ("scope", "independent_final_positive_set_reconstructed"),
        ):
            doc = copy.deepcopy(load_recorded())
            doc[group][key] = True
            with self.subTest(group=group, key=key):
                with self.assertRaises(StageEvidenceError):
                    audit_recorded(doc)

    def test_synthetic_c1_c2_tier_a_and_frozen_membership(self):
        with tempfile.TemporaryDirectory() as tmp:
            c1, c2, doc = sample_inputs(Path(tmp))
            output = verify_local_c1_c2(
                c1, c2, doc, expected_counts=(3, 1, 1, 1)
            )
        self.assertEqual(output["status"],
                         "PASS_BYTE_VERIFIED_STAGED_C1_C2_PAIR_MEMBERSHIP_ONLY")
        self.assertEqual(output["c1_cases"], 3)
        self.assertEqual(output["c1_positive_cases"], 1)
        self.assertEqual(output["c2_same_repo_pairs"], 1)
        self.assertEqual(output["unmatched_positive_count"], 0)
        self.assertTrue(output["source_c1_sha256_verified"])
        self.assertFalse(output["verified_study_security_outcomes"])
        self.assertFalse(output["ran_historical_scanners"])
        self.assertFalse(output["reran_original_matching_optimizer"])
        self.assertNotIn("positive_case_id", output)

    def test_synthetic_c1_c2_tier_b_cross_repo_exact(self):
        with tempfile.TemporaryDirectory() as tmp:
            c1, c2, doc = sample_inputs(Path(tmp), tier="B", control_id="3")
            output = verify_local_c1_c2(
                c1, c2, doc, expected_counts=(3, 1, 1, 0)
            )
        self.assertEqual(output["c2_cross_repo_pairs"], 1)

    def test_staged_c1_byte_mutation_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            c1, c2, doc = sample_inputs(Path(tmp))
            c1.write_bytes(c1.read_bytes() + b"\n")
            with self.assertRaises(StageEvidenceError):
                verify_local_c1_c2(c1, c2, doc,
                                   expected_counts=(3, 1, 1, 1))

    def test_staged_c2_hash_mutation_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            c1, c2, doc = sample_inputs(Path(tmp))
            blob = c2.read_bytes()
            c2.write_bytes(blob.replace(b"8.5", b"9.5"))
            with self.assertRaisesRegex(StageEvidenceError, "SHA-256"):
                verify_local_c1_c2(c1, c2, doc,
                                   expected_counts=(3, 1, 1, 1))

    def test_c2_not_allowed_to_relabel_tier_by_same_repo(self):
        with tempfile.TemporaryDirectory() as tmp:
            c1, c2, doc = sample_inputs(Path(tmp), tier="B", control_id="2")
            with self.assertRaisesRegex(StageEvidenceError, "same_repository bit"):
                verify_local_c1_c2(c1, c2, doc,
                                   expected_counts=(3, 1, 1, 0))

    def test_c2_scanner_opportunity_must_match_c1(self):
        with tempfile.TemporaryDirectory() as tmp:
            c1, c2, doc = sample_inputs(
                Path(tmp), sig_override="gitleaks;semgrep"
            )
            with self.assertRaisesRegex(StageEvidenceError, "opportunity differs"):
                verify_local_c1_c2(c1, c2, doc,
                                   expected_counts=(3, 1, 1, 1))

    def test_c2_wrong_original_time_caliper_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            c1, c2, doc = sample_inputs(Path(tmp))
            c2.write_bytes(c2.read_bytes().replace(b"8.5", b"98."))
            doc["c2_matching"]["matched_pairs_sha256"] = hashlib.sha256(
                c2.read_bytes()
            ).hexdigest()
            with self.assertRaisesRegex(StageEvidenceError, "ninety-day"):
                verify_local_c1_c2(c1, c2, doc,
                                   expected_counts=(3, 1, 1, 1))

    def test_symlinked_private_file_rejected_even_if_hash_matches(self):
        with tempfile.TemporaryDirectory() as tmp:
            c1, c2, doc = sample_inputs(Path(tmp))
            symlink = Path(tmp) / "alias.csv"
            symlink.symlink_to(c1)
            with self.assertRaisesRegex(StageEvidenceError, "symlink"):
                verify_local_c1_c2(symlink, c2, doc,
                                   expected_counts=(3, 1, 1, 1))

    def test_missing_private_files_block_and_never_replay_frozen_results(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = main(["verify-staged-c1-c2",
                             str(Path(tmp) / "missing-c1.csv"),
                             str(Path(tmp) / "missing-c2.csv")])
        self.assertEqual(code, 2)
        self.assertEqual(
            json.loads(output.getvalue())["status"],
            "BLOCKED_STAGE_PROVENANCE_OR_INPUT",
        )

    def test_cli_source_recorded_arithmetic_not_empirical(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = main(["audit-recorded"])
        self.assertEqual(code, 0)
        report = json.loads(out.getvalue())
        self.assertEqual(
            report["status"],
            "PASS_RECORDED_C1_C2_PHASE1_C_ROOT_ARITHMETIC_ONLY",
        )
        self.assertFalse(report["empirical_security_results_reproduced"])


if __name__ == "__main__":
    unittest.main()
