"""Synthetic ZIP tests; never execute historical research source."""
import csv
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

from tools.verify_source_snapshot import RecoveryIntegrityError, verify, INDEX, STATUS

SOURCE = "historical/miner/snapshot/src/a.py"
ARCHIVE_SUMMARY = "provenance/source_recovery_archive_summary_20261020.csv"
EXCLUSIONS = "provenance/source_recovery_exclusions_20261020.csv"


def make_fixture(path, content=b"x=1\n", *, destination=SOURCE, extra=None, wrong_hash=False):
    row = {
        "repo_destination": destination,
        "sha256": hashlib.sha256(content).hexdigest(),
        "bytes": len(content),
        "source_set": "MINER_LIVE",
        "source_archive_sha256": "abc",
    }
    if wrong_hash:
        row["sha256"] = "0" * 64
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(row))
    writer.writeheader()
    writer.writerow(row)
    with ZipFile(path, "w") as archive:
        archive.writestr(destination, content)
        archive.writestr(INDEX, buffer.getvalue())
        archive.writestr(STATUS, json.dumps({"total_source_files": 1}))
        archive.writestr(ARCHIVE_SUMMARY, "a,b\n")
        archive.writestr(EXCLUSIONS, "a,b\n")
        if extra:
            archive.writestr(extra, "stray")


class SourceSnapshotVerifierTest(unittest.TestCase):
    def test_valid_fixture(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "sample.zip"
            make_fixture(path)
            actual = verify(path)
            self.assertEqual(actual["status"], "PASS")
            self.assertEqual(actual["source_files"], 1)

    def test_sha_mismatch_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "sample.zip"
            make_fixture(path, wrong_hash=True)
            with self.assertRaisesRegex(RecoveryIntegrityError, "SHA mismatch"):
                verify(path)

    def test_unindexed_source_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "sample.zip"
            make_fixture(path, extra="historical/unknown.py")
            with self.assertRaisesRegex(RecoveryIntegrityError, "Unindexed"):
                verify(path)

    def test_active_source_path_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "sample.zip"
            make_fixture(path, destination="src/unsafe.py")
            with self.assertRaisesRegex(RecoveryIntegrityError, "Unexpected promoted"):
                verify(path)

    def test_path_traversal_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "sample.zip"
            make_fixture(path, extra="../escape.txt")
            with self.assertRaisesRegex(RecoveryIntegrityError, "Invalid member path"):
                verify(path)


if __name__ == "__main__":
    unittest.main()
