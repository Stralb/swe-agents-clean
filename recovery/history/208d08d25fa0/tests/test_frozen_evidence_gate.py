"""Synthetic unit tests for historical *recorded* evidence consistency gates."""
from __future__ import annotations

import contextlib
import csv
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from analysis.frozen_evidence_gate import (
    EvidenceError, ROOT, audit_d_d7_ledger, main, read_baseline_inventory,
    replay_recorded_owp14, verify_staged_baselines,
)

PROVENANCE = ROOT / "provenance"
REQUIRED_NAMES = (
    "owp14_case_arm_counts_20261020.csv",
    "owp14_missing_baseline_sha256.csv",
    "owp14_intake_verified_20261020.json",
    "d_vs_d7_label_differences.csv",
)


class FrozenEvidenceGateTests(unittest.TestCase):
    def _mutable_provenance(self, folder: str) -> Path:
        target = Path(folder)
        for filename in REQUIRED_NAMES:
            (target / filename).write_bytes((PROVENANCE / filename).read_bytes())
        return target

    @staticmethod
    def _modify_csv(path: Path, mutate):
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            fields = reader.fieldnames
            rows = list(reader)
        mutate(rows)
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)

    def test_recorded_owp14_arithmetic_and_explicit_scientific_limit(self):
        record = replay_recorded_owp14(PROVENANCE)
        self.assertEqual(record["status"], "PASS_RECORDED_SUMMARY_ARITHMETIC_ONLY")
        self.assertFalse(record["independent_new_alert_delta_verified"])
        self.assertEqual((record["cases"], record["paired_cases"]), (14, 12))
        self.assertEqual(record["paired_full_frozen_cases"], 8)
        self.assertEqual(record["unpaired_missing_O_cases"], ["08461", "15151"])
        self.assertEqual(record["scans_by_arm"], {"O": 12, "W": 14, "P": 14})
        self.assertEqual(
            record["reported_new_alerts_by_arm"], {"O": 21, "W": 10, "P": 15}
        )
        self.assertEqual(
            record["reported_new_target_alerts_by_arm"], {"O": 7, "W": 4, "P": 5}
        )
        self.assertEqual(
            record["recorded_source_modes"], {
                "FULL_FROZEN_SNAPSHOT": 10,
                "FILTERED_SOURCE_PROVISIONAL": 4,
            }
        )
        self.assertEqual(record["previously_reproduced_historical_target"], 8)
        self.assertEqual(
            record["recorded_jsx_aware_syntax"], {
                "SYNTAX_PASS": 39, "SYNTAX_FAIL": 1,
            }
        )
        self.assertEqual(record["original_baseline_sarif_missing"], 14)
        self.assertEqual(record["historical_codeql_version_as_recorded"], "2.25.6")

    def test_paired_comparisons_do_not_implicitly_zero_missing_O(self):
        summary = replay_recorded_owp14(PROVENANCE)
        self.assertEqual(summary["recorded_paired_descriptive_contrasts"], {
            "W": {
                "fewer_recorded_new_alerts": 7,
                "equal_recorded_new_alerts": 5,
                "more_recorded_new_alerts": 0,
            },
            "P": {
                "fewer_recorded_new_alerts": 4,
                "equal_recorded_new_alerts": 8,
                "more_recorded_new_alerts": 0,
            },
        })

    def test_recorded_conflict_ledger_unresolved_not_silently_resolved(self):
        report = audit_d_d7_ledger(PROVENANCE)
        self.assertEqual(report["status"], "UNRESOLVED_D_VS_D7")
        self.assertEqual(report["changed_root_labels"], 43)
        self.assertEqual(report["route_changes"], 1)
        self.assertEqual(report["tier_only_changes"], 42)
        self.assertEqual(report["route_changed_root_ids"], ["CROOT-00649-01"])

    def test_duplicate_d_disagreement_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._mutable_provenance(tmp)
            self._modify_csv(
                root / "d_vs_d7_label_differences.csv",
                lambda rows: rows.append(dict(rows[0])),
            )
            with self.assertRaises(EvidenceError):
                audit_d_d7_ledger(root)

    def test_d_label_agreement_record_cannot_remain_in_disagreement_ledger(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._mutable_provenance(tmp)
            def mutate(rows):
                rows[0]["d7_route"] = rows[0]["d_final_route"]
                rows[0]["d7_tier"] = rows[0]["d_final_tier"]
            self._modify_csv(root / "d_vs_d7_label_differences.csv", mutate)
            with self.assertRaises(EvidenceError):
                audit_d_d7_ledger(root)

    def test_mutated_W_total_detected_against_separate_intake(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._mutable_provenance(tmp)
            def mutate(rows):
                rows[0]["W_new_claimed"] = "0"
                rows[0]["W_target_new_claimed"] = "0"
            self._modify_csv(root / "owp14_case_arm_counts_20261020.csv", mutate)
            with self.assertRaisesRegex(EvidenceError, "aggregate conflicts"):
                replay_recorded_owp14(root)

    def test_zero_substitution_for_missing_O_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._mutable_provenance(tmp)
            def mutate(rows):
                row = next(row for row in rows if row["case_id"] == "08461")
                row["O_new_claimed"] = "0"
                row["O_target_new_claimed"] = "0"
                row["O_syntax_JSX"] = "SYNTAX_PASS"
            self._modify_csv(root / "owp14_case_arm_counts_20261020.csv", mutate)
            with self.assertRaises(EvidenceError):
                replay_recorded_owp14(root)

    def test_changed_intake_syntax_count_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._mutable_provenance(tmp)
            path = root / "owp14_intake_verified_20261020.json"
            obj = json.loads(path.read_text())
            obj["functional"]["JSX_aware_syntax"]["pass"] = 40
            path.write_text(json.dumps(obj))
            with self.assertRaisesRegex(EvidenceError, "syntax pass"):
                replay_recorded_owp14(root)

    def test_source_equivalence_must_remain_unverified(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._mutable_provenance(tmp)
            def mutate(rows):
                rows[0]["source_content_equivalence_independently_verified"] = "YES"
            self._modify_csv(root / "owp14_missing_baseline_sha256.csv", mutate)
            with self.assertRaisesRegex(EvidenceError, "equivalence"):
                replay_recorded_owp14(root)

    def test_expected_baseline_manifest_must_not_claim_available(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._mutable_provenance(tmp)
            def mutate(rows):
                rows[0]["baseline_SARIF_available_in_input_zip"] = "YES"
            self._modify_csv(root / "owp14_missing_baseline_sha256.csv", mutate)
            with self.assertRaisesRegex(EvidenceError, "baseline presence"):
                read_baseline_inventory(root / "owp14_missing_baseline_sha256.csv")

    def test_untampered_manifest_has_14_distinct_case_hashes(self):
        inventory = read_baseline_inventory(
            PROVENANCE / "owp14_missing_baseline_sha256.csv"
        )
        self.assertEqual(len(inventory), 14)
        self.assertEqual(len({
            row["expected_before_sarif_sha256"] for row in inventory
        }), 14)

    def test_absent_original_baselines_are_reported_missing(self):
        inventory = read_baseline_inventory(
            PROVENANCE / "owp14_missing_baseline_sha256.csv"
        )
        with tempfile.TemporaryDirectory() as tmp:
            outcome = verify_staged_baselines(inventory, Path(tmp))
        self.assertEqual(outcome["status"], "BLOCKED_MISSING_OR_INVALID_BASELINES")
        self.assertEqual(outcome["counts"], {"MISSING": 14})
        self.assertEqual(outcome["verified"], 0)
        self.assertFalse(outcome["independent_new_alert_delta_verified"])

    @staticmethod
    def _artificial_baseline(body: bytes, count: int) -> dict:
        return {
            "case_id": "00001",
            "expected_before_sarif_sha256": hashlib.sha256(body).hexdigest(),
            "source_reported_before_results": str(count),
        }

    def test_synthetic_matching_baseline_hash_and_count(self):
        body = json.dumps({
            "version": "2.1.0",
            "runs": [{"results": [{"ruleId": "fake-1"}, {"ruleId": "fake-2"}]}],
        }).encode()
        row = self._artificial_baseline(body, 2)
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "CASE_00001_before.sarif").write_bytes(body)
            outcome = verify_staged_baselines([row], Path(tmp))
        self.assertEqual(outcome["verified"], 1)
        self.assertEqual(
            outcome["status"], "ALL_STAGED_BASELINES_HASH_AND_COUNT_VERIFIED"
        )
        self.assertFalse(outcome["independent_new_alert_delta_verified"])

    def test_matching_digest_does_not_hide_wrong_result_count(self):
        body = json.dumps({"runs": [{"results": [{"ruleId": "fake-1"}]}]}).encode()
        row = self._artificial_baseline(body, 2)
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "CASE_00001_before.sarif").write_bytes(body)
            outcome = verify_staged_baselines([row], Path(tmp))
        self.assertEqual(outcome["counts"], {"RESULT_COUNT_MISMATCH": 1})

    def test_matching_digest_does_not_hide_invalid_json(self):
        body = b"not even a JSON document"
        row = self._artificial_baseline(body, 0)
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "CASE_00001_before.sarif").write_bytes(body)
            outcome = verify_staged_baselines([row], Path(tmp))
        self.assertEqual(outcome["counts"], {"INVALID_SARIF": 1})

    def test_changed_synthetic_baseline_detected_from_sha256(self):
        expected = b'{"runs":[{"results":[]}]}'
        row = self._artificial_baseline(expected, 0)
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "CASE_00001_before.sarif").write_bytes(expected + b" ")
            outcome = verify_staged_baselines([row], Path(tmp))
        self.assertEqual(outcome["counts"], {"HASH_MISMATCH": 1})

    def test_baseline_symlink_refused(self):
        body = b'{"runs":[{"results":[]}]}'
        row = self._artificial_baseline(body, 0)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "actual.sarif").write_bytes(body)
            (root / "CASE_00001_before.sarif").symlink_to(root / "actual.sarif")
            outcome = verify_staged_baselines([row], root)
        self.assertEqual(outcome["counts"], {"REJECTED_SYMLINK": 1})

    def test_oversize_baseline_fails_without_reading(self):
        body = b'{"runs":[{"results":[]}]}'
        row = self._artificial_baseline(body, 0)
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "CASE_00001_before.sarif").write_bytes(body)
            outcome = verify_staged_baselines([row], Path(tmp), max_bytes=4)
        self.assertEqual(outcome["counts"], {"REJECTED_SIZE_LIMIT": 1})

    def test_cli_outputs_blockers_and_baseline_exit_two(self):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = main(["audit-recorded"])
        self.assertEqual(code, 0)
        report = json.loads(stdout.getvalue())
        self.assertEqual(report["scientific_parity"], "BLOCKED_ORIGINAL_DATA_NOT_PRESENT")
        with tempfile.TemporaryDirectory() as tmp:
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                code = main(["verify-baselines", tmp])
        self.assertEqual(code, 2)
        status = json.loads(stdout.getvalue())
        self.assertEqual(status["counts"], {"MISSING": 14})


if __name__ == "__main__":
    unittest.main()
