"""Synthetic-only C3 blind-data integrity tests; no Wits research records."""
from __future__ import annotations
import contextlib
import csv
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from analysis.frozen_c3_blind_gate import C3GateError, FROZEN, HEADERS, main, verify_c3


def data():
    b = ["CTRL-0000000001", "CTRL-0000000002", "CTRL-0000000003"]
    m = [dict(zip(HEADERS["map"], (bid, str(i + 10), str(i + 20),
                  "A" if i == 0 else "B", "up/repo" + str(i),
                  "up/repo0" if i == 0 else "down/repo" + str(i))))
         for i, bid in enumerate(b)]
    manifest = [dict(zip(HEADERS["manifest"], (r["blind_id"], r["control_repository"],
                str(i+100), str(i+200)))) for i, r in enumerate(m)]
    source = {"map": m, "manifest": manifest}
    source["c2"] = [dict(positive_case_id=r["positive_case_id"],
        control_case_id=r["control_case_id"], match_tier=r["match_tier"],
        positive_repository=r["positive_repository"],
        control_repository=r["control_repository"]) for r in m]
    source["issue"] = [dict(zip(HEADERS["issue"], (
        r["blind_id"], r["repository"], r["issue_number"], "title", "text,\nwith quotes \"and\" commas")))
        for r in manifest]
    source["pr"] = [dict(zip(HEADERS["pr"], (
        r["blind_id"], r["repository"], r["pr_number"], "title", "patch\ntext")))
        for r in manifest]
    source["context"] = []
    for r in manifest:
        x = {h: "" for h in HEADERS["context"]}
        x.update(blind_id=r["blind_id"], repository=r["repository"])
        source["context"].append(x)
    for role in ("issue_template", "pr_template", "implementation_template"):
        source[role] = [{h: r["blind_id"] if h == "blind_id" else "" for h in HEADERS[role]}
                        for r in manifest]
    source["qc"] = {
        "qc_pass": True, "pair_count": 3, "control_count": 3,
        "blind_id_count": 3, "matching_data_separated": True,
        "positive_ids_present_only_in_locked_mapping": True,
        "scanner_runs_read": False, "scanner_findings_read": False,
    }
    return source


def make_fixture(root):
    records = data()
    c3, c2 = root / "frozen-c3", root / "c2.csv"
    c3.mkdir()
    pins = {}
    for role, (sub, filename, _size, _sha) in FROZEN.items():
        path = c2 if role == "c2" else c3 / sub / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        if role == "qc":
            path.write_text(json.dumps(records[role]), encoding="utf-8")
        else:
            with path.open("w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=list(records[role][0]))
                writer.writeheader()
                writer.writerows(records[role])
        pins[role] = (path.stat().st_size, hashlib.sha256(path.read_bytes()).hexdigest())
    qc = c3 / "99_QC" / "C3_AUDIT.json"
    obj = json.loads(qc.read_text())
    obj["pairs_sha256"] = pins["c2"][1]
    qc.write_text(json.dumps(obj))
    pins["qc"] = (qc.stat().st_size, hashlib.sha256(qc.read_bytes()).hexdigest())
    imp = c3 / "03_IMPLEMENTATION_BLIND"
    imp.mkdir()
    for r in records["map"]:
        (imp / (r["blind_id"] + ".txt")).write_text("synthetic")
    return c3, c2, pins


def mutate(c3, c2, pins, role, fn, refresh=True):
    sub, name, _, _ = FROZEN[role]
    path = c2 if role == "c2" else c3 / sub / name
    if role == "qc":
        obj = json.loads(path.read_text())
        fn(obj)
        path.write_text(json.dumps(obj))
    else:
        with path.open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            hdr = reader.fieldnames
            rows = list(reader)
        fn(rows)
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=hdr)
            writer.writeheader()
            writer.writerows(rows)
    if refresh:
        pins[role] = (path.stat().st_size, hashlib.sha256(path.read_bytes()).hexdigest())


class C3BlindSyntheticTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.c3, self.c2, self.pins = make_fixture(Path(tmp.name))

    def check(self):
        return verify_c3(self.c3, self.c2, fingerprints=self.pins, expected_count=3)

    def test_valid_roundtrip_no_source_modifications(self):
        before = self.c2.read_bytes()
        result = self.check()
        self.assertEqual(result["pairs_and_blind_ids"], 3)
        self.assertEqual(result["unannotated_original_templates"], 3)
        self.assertTrue(result["implementation_packet_names_verified"])
        self.assertFalse(result["statistical_results_reproduced"])
        self.assertEqual(before, self.c2.read_bytes())

    def test_modified_sha_fails(self):
        mutate(self.c3, self.c2, self.pins, "issue", lambda r: r[0].update(issue_title="titie"), refresh=False)
        with self.assertRaisesRegex(C3GateError, "SHA-256"):
            self.check()

    def test_wrong_byte_length_fails(self):
        self.pins["pr"] = (999, self.pins["pr"][1])
        with self.assertRaisesRegex(C3GateError, "byte length"):
            self.check()

    def test_mismatched_control_positive_rejected(self):
        mutate(self.c3, self.c2, self.pins, "map", lambda r: r[0].update(positive_case_id="99"))
        with self.assertRaisesRegex(C3GateError, "locked mapping disagrees"):
            self.check()

    def test_matching_tier_changed_rejected(self):
        mutate(self.c3, self.c2, self.pins, "map", lambda r: r[0].update(match_tier="B"))
        with self.assertRaisesRegex(C3GateError, "locked mapping disagrees"):
            self.check()

    def test_reused_blind_id_rejected(self):
        mutate(self.c3, self.c2, self.pins, "map", lambda r: r[0].update(blind_id=r[1]["blind_id"]))
        with self.assertRaisesRegex(C3GateError, "duplicate/malformed blind ID"):
            self.check()

    def test_manifest_repository_wrong(self):
        mutate(self.c3, self.c2, self.pins, "manifest", lambda r: r[0].update(repository="elsewhere/repo"))
        with self.assertRaisesRegex(C3GateError, "manifest repository differs"):
            self.check()

    def test_issue_number_wrong(self):
        mutate(self.c3, self.c2, self.pins, "issue", lambda r: r[0].update(issue_number="9999"))
        with self.assertRaisesRegex(C3GateError, "number mismatch"):
            self.check()

    def test_pr_number_wrong(self):
        mutate(self.c3, self.c2, self.pins, "pr", lambda r: r[0].update(pr_number="9999"))
        with self.assertRaisesRegex(C3GateError, "number mismatch"):
            self.check()

    def test_context_blind_id_wrong(self):
        mutate(self.c3, self.c2, self.pins, "context", lambda r: r[0].update(blind_id="CTRL-FFFFFFFFFF"))
        with self.assertRaisesRegex(C3GateError, "unmatched blind IDs"):
            self.check()

    def test_template_cannot_be_silently_annotated(self):
        mutate(self.c3, self.c2, self.pins, "issue_template",
               lambda r: r[0].update(instruction_specificity="explicit"))
        with self.assertRaisesRegex(C3GateError, "not blank"):
            self.check()

    def test_pr_template_cannot_be_silently_annotated(self):
        mutate(self.c3, self.c2, self.pins, "pr_template", lambda r: r[0].update(goal_alignment="aligned"))
        with self.assertRaisesRegex(C3GateError, "not blank"):
            self.check()

    def test_implementation_template_cannot_be_silently_annotated(self):
        mutate(self.c3, self.c2, self.pins, "implementation_template",
               lambda r: r[0].update(actual_implementation_summary="bug"))
        with self.assertRaisesRegex(C3GateError, "not blank"):
            self.check()

    def test_extra_implementation_packet_rejected(self):
        (self.c3 / "03_IMPLEMENTATION_BLIND" / "extra.txt").write_text("fixture")
        with self.assertRaisesRegex(C3GateError, "filenames disagree"):
            self.check()

    def test_missing_implementation_packet_rejected(self):
        next((self.c3 / "03_IMPLEMENTATION_BLIND").iterdir()).unlink()
        with self.assertRaisesRegex(C3GateError, "filenames disagree"):
            self.check()

    def test_report_cannot_claim_scanner_reads(self):
        mutate(self.c3, self.c2, self.pins, "qc", lambda r: r.update(scanner_findings_read=True))
        with self.assertRaisesRegex(C3GateError, "QC blinding contract"):
            self.check()

    def test_only_aggregates_returned(self):
        out = json.dumps(self.check())
        self.assertNotIn("CTRL-", out)
        self.assertNotIn("up/repo", out)
        self.assertNotIn("patch", out)

    def test_public_cli_rejects_synthetic_without_override(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = main([str(self.c3), str(self.c2)])
        self.assertEqual(code, 2)
        self.assertFalse(json.loads(out.getvalue())["scientific_reproduction_complete"])


if __name__ == "__main__":
    unittest.main()
