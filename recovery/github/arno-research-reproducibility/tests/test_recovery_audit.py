"""Standalone synthetic tests; do not require private research data or network."""
import csv
import hashlib
import io
import json
import tarfile
import tempfile
import unittest
from pathlib import Path

from tools.recovery_audit import AuditError, read_csv_from_tar, require_unique, sha256_file, verify_manifest


def tar_with_csv(path: Path, member: str, rows: list[dict]) -> None:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    blob = buffer.getvalue().encode()
    with tarfile.open(path, "w:gz") as target:
        info = tarfile.TarInfo(member)
        info.size = len(blob)
        target.addfile(info, io.BytesIO(blob))


class RecoveryAuditTests(unittest.TestCase):
    def test_archive_member_reader(self):
        with tempfile.TemporaryDirectory() as folder:
            archive = Path(folder) / "sample.tar.gz"
            tar_with_csv(archive, "frozen/C6_ROOT_CENSUS.csv", [{"Root ID": "x", "PC Count": "1"}])
            rows = read_csv_from_tar(archive, "C6_ROOT_CENSUS.csv")
            self.assertEqual(rows, [{"Root ID": "x", "PC Count": "1"}])
            with self.assertRaises(AuditError):
                read_csv_from_tar(archive, "OTHER.csv")

    def test_duplicate_ids_rejected(self):
        with self.assertRaises(AuditError):
            require_unique([{"ID": "x"}, {"ID": "x"}], "ID")

    def test_manifest_hash_passes_and_detects_tampering(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            artifact = base / "a.txt"
            artifact.write_text("original", encoding="utf8")
            digest = sha256_file(artifact)
            manifest = base / "sources.csv"
            with manifest.open("w", newline="", encoding="utf8") as stream:
                writer = csv.DictWriter(stream, fieldnames=["artifact_id", "filename", "sha256", "bytes"])
                writer.writeheader()
                writer.writerow({"artifact_id": "a", "filename": "a.txt", "sha256": digest, "bytes": artifact.stat().st_size})
            self.assertEqual(verify_manifest(manifest, base)["counts"], {"PASS": 1})
            artifact.write_text("changed", encoding="utf8")
            self.assertEqual(verify_manifest(manifest, base)["counts"], {"MISMATCH": 1})

    def test_manifest_path_restriction(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "manifest.csv"
            path.write_text("artifact_id,filename,sha256,bytes\na,../elsewhere,abc,10\n", encoding="utf8")
            with self.assertRaises(AuditError):
                verify_manifest(path, Path(folder))


if __name__ == "__main__":
    unittest.main()
