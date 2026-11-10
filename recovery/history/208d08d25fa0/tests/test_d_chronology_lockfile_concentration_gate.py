"""Synthetic/recorded D-root lockfile concentration gates, no Wits files in CI."""
from __future__ import annotations

import contextlib
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest

from analysis.d_chronology_lockfile_concentration_gate import (
    D1_SHA, DEXPORT_SHA, MANIFEST, LockfileChronologyError, audit, main,
)


def fixture():
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


class LockfileRootChronologyTests(unittest.TestCase):
    def test_frozen_case_and_workflow_denominators(self):
        result = audit()
        self.assertEqual(result["chronology_incomplete_export_roots"], 41)
        self.assertEqual(result["chronology_incomplete_root_workflows"], 6)
        self.assertEqual(result["root_producing_change_count_for_41"], 41)
        self.assertEqual(result["case13918_lockfile_roots"], 36)
        self.assertEqual(result["other_five_lockfile_roots"], 5)
        self.assertFalse(result["case13918_in_190_original_positive_matched_members"])
        self.assertEqual(result["frozen_D_final_D7_disagreement_overlap"], 0)

    def test_source_expected_sha256_pins(self):
        self.assertEqual(D1_SHA,
                         "ff1432d1959b501f62a9aeb18dface0976db11dbc59d31a233a24a816236ddf3")
        self.assertEqual(DEXPORT_SHA,
                         "cfca8cd2425d7043e89cdb4e06576f3e6794c09736bb5c85b4c0e8332cc3f4e6")

    def test_original_C6_records_36_singleton_lockfile_root_groups(self):
        src = fixture()
        root = src["case13918"]["C6_root_construction"]
        self.assertEqual((root["root_count"], root["pc_per_root"]), (36, 1))
        self.assertEqual(root["merge_rationale"], "singleton PC")
        self.assertEqual(root["final_source"], "A_B_AGREEMENT")
        self.assertFalse(src["sources"]["c6_original_root_census"]
                         ["full_source_sha256_recomputed_during_current_c6_targeted_read"])

    def test_C6_root_grouping_does_not_prove_independent_agent_choices(self):
        src = fixture()
        src["limitations"][
            "C6_root_group_agreement_proves_independent_agent_mechanism_choices"
        ] = True
        with self.assertRaisesRegex(LockfileChronologyError,
                                    "agent-choice reliability"):
            audit(supplied_manifest=src)

    def test_tampered_C6_merging_rationale_rejected(self):
        src = fixture()
        src["case13918"]["C6_root_construction"]["merge_rationale"] = (
            "all-one-lockfile-event")
        with self.assertRaisesRegex(LockfileChronologyError,
                                    "singleton-root construction"):
            audit(supplied_manifest=src)

    def test_recorded_output_does_not_claim_private_bytes_rehashed_in_ci(self):
        result = audit()
        self.assertFalse(result["original_D1_and_export_index_bytes_SHA_checked_in_this_execution"])
        self.assertFalse(result["frozen_original_H_T_M_labels_authenticated"])
        self.assertFalse(result["semantic_T_routes_adjudicated"])

    def test_no_spurious_independent_root_statistic_claim(self):
        x = fixture()
        x["limitations"]["root_level_and_workflow_level_observations_iid"] = True
        with self.assertRaisesRegex(LockfileChronologyError, "independence"):
            audit(supplied_manifest=x)

    def test_wrong_342_root_source_sha_refused(self):
        x = fixture()
        x["sources"]["d1_root_index"]["sha256"] = "0"*64
        with self.assertRaisesRegex(LockfileChronologyError, "provenance"):
            audit(supplied_manifest=x)

    def test_no_assumed_d_route_adjudication(self):
        x = fixture()
        x["limitations"]["mechanical_root_labels_adjudicated"] = True
        with self.assertRaisesRegex(LockfileChronologyError, "Unsupported H/T/M"):
            audit(supplied_manifest=x)

    def test_swapped_lockfile_root_workflow_rejected(self):
        x = fixture()
        x["case13918"]["all_root_ids"][0] = "CROOT-13918-88"
        with self.assertRaisesRegex(LockfileChronologyError, "36 root index"):
            audit(supplied_manifest=x)

    def test_duplicate_single_case_root_rejected(self):
        x = fixture()
        x["other_five_roots"][0]["root_id"] = "CROOT-09942-01"
        with self.assertRaisesRegex(LockfileChronologyError, "Single-root original packet"):
            audit(supplied_manifest=x)

    def test_transferred_figure_to_C6_match_rejected(self):
        x = fixture()
        x["case13918"]["C2_matched_positive_member"] = True
        with self.assertRaisesRegex(LockfileChronologyError, "C1/C2 excluded"):
            audit(supplied_manifest=x)

    def test_unsupported_proven_resolver_origin_rejected(self):
        x = fixture()
        x["limitations"]["all_41_dependencies_proven_to_be_resolver_generated"] = True
        with self.assertRaisesRegex(LockfileChronologyError, "scanner or independence"):
            audit(supplied_manifest=x)

    def test_wrong_external_url_count_rejected(self):
        x = fixture()
        x["other_five_roots"][0]["external"] = "NOT_APPLICABLE"
        with self.assertRaisesRegex(LockfileChronologyError, "Single-root original packet"):
            audit(supplied_manifest=x)

    def test_wrong_public_pr_base_head_size_rejected(self):
        x = fixture()
        x["case13918"]["public_base_head_file_changes"]["package_lock"]["changes"] -= 1
        with self.assertRaisesRegex(LockfileChronologyError, "PR base/head"):
            audit(supplied_manifest=x)

    def test_staged_private_sources_must_both_be_present(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "dummy.csv"
            source.write_bytes(b"fake")
            with self.assertRaisesRegex(LockfileChronologyError, "Both original"):
                audit(d1_path=source)

    def test_staged_source_short_bytes_fail_before_csv_parsing(self):
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder)
            a, b = p/"D1_ROOT_INDEX_342.csv", p/"D_EVIDENCE_INDEX_342.csv"
            a.write_bytes(b"Root ID,Case ID\n")
            b.write_bytes(b"root_id,case_id\n")
            with self.assertRaisesRegex(LockfileChronologyError, "byte count mismatch"):
                audit(d1_path=a, evidence_index_path=b)

    def test_symlinked_source_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)
            a,b,target=p/"D1_ROOT_INDEX_342.csv",p/"D_EVIDENCE_INDEX_342.csv",p/"target"
            target.write_bytes(b"fake")
            a.symlink_to(target)
            b.write_bytes(b"fake")
            with self.assertRaisesRegex(LockfileChronologyError, "symlink"):
                audit(d1_path=a, evidence_index_path=b)

    def test_ci_cli_contains_aggregate_only(self):
        out=io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(main([]),0)
        obj=json.loads(out.getvalue())
        self.assertEqual(obj["chronology_incomplete_export_roots"],41)
        self.assertNotIn("Pimzino/spec-workflow-mcp",out.getvalue())


if __name__ == "__main__":
    unittest.main()
