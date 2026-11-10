from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src.distributed.codeql_pipeline import (
    remove_completed_task_markers,
    task_present,
)
from src.distributed.spool import (
    DistributedSpool,
)


class CodeQLSpoolLifecycleTests(
    unittest.TestCase
):
    def setUp(
        self,
    ) -> None:
        self.temporary = (
            tempfile.TemporaryDirectory()
        )

        self.root = Path(
            self.temporary.name
        )

        self.spool = DistributedSpool(
            self.root
        )

        self.pool = "codeql_security"

    def tearDown(
        self,
    ) -> None:
        self.temporary.cleanup()

    def write_json(
        self,
        path: Path,
        value: dict[str, object],
    ) -> None:
        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        path.write_text(
            json.dumps(
                value
            ),
            encoding="utf-8",
        )

    def test_imported_result_is_present(
        self,
    ) -> None:
        task_id = "scanner-job-100"

        imported = (
            self.spool.queue_path(
                self.pool,
                "results",
            )
            / "imported"
            / f"{task_id}.json"
        )

        self.write_json(
            imported,
            {
                "task_id": task_id,
            },
        )

        self.assertTrue(
            task_present(
                self.spool,
                task_id,
            )
        )

    def test_claim_discards_pending_when_imported(
        self,
    ) -> None:
        task_id = "scanner-job-101"

        pending = (
            self.spool.queue_path(
                self.pool,
                "pending",
            )
            / f"{task_id}.json"
        )

        imported = (
            self.spool.queue_path(
                self.pool,
                "results",
            )
            / "imported"
            / f"{task_id}.json"
        )

        self.write_json(
            pending,
            {
                "task_id": task_id,
                "payload": {
                    "case_id": 1,
                },
            },
        )

        self.write_json(
            imported,
            {
                "task_id": task_id,
            },
        )

        claim = self.spool.claim(
            self.pool,
            "test-worker",
        )

        self.assertIsNone(
            claim
        )

        self.assertFalse(
            pending.exists()
        )

    def test_requeue_removes_imported_claim(
        self,
    ) -> None:
        task_id = "scanner-job-102"

        claimed = (
            self.spool.queue_path(
                self.pool,
                "claimed",
            )
            / (
                f"{task_id}__"
                "test-worker.json"
            )
        )

        imported = (
            self.spool.queue_path(
                self.pool,
                "results",
            )
            / "imported"
            / f"{task_id}.json"
        )

        self.write_json(
            claimed,
            {
                "task_id": task_id,
            },
        )

        self.write_json(
            imported,
            {
                "task_id": task_id,
            },
        )

        changed = self.spool.requeue_stale(
            self.pool,
            stale_seconds=0,
        )

        self.assertEqual(
            changed,
            1,
        )

        self.assertFalse(
            claimed.exists()
        )

        pending = (
            self.spool.queue_path(
                self.pool,
                "pending",
            )
            / f"{task_id}.json"
        )

        self.assertFalse(
            pending.exists()
        )

    def test_import_cleanup_removes_all_markers(
        self,
    ) -> None:
        task_id = "scanner-job-103"

        pending = (
            self.spool.queue_path(
                self.pool,
                "pending",
            )
            / f"{task_id}.json"
        )

        first_claim = (
            self.spool.queue_path(
                self.pool,
                "claimed",
            )
            / (
                f"{task_id}__"
                "worker-one.json"
            )
        )

        second_claim = (
            self.spool.queue_path(
                self.pool,
                "claimed",
            )
            / (
                f"{task_id}__"
                "worker-two.json"
            )
        )

        for path in (
            pending,
            first_claim,
            second_claim,
        ):
            self.write_json(
                path,
                {
                    "task_id": task_id,
                },
            )

        removed = (
            remove_completed_task_markers(
                self.spool,
                task_id,
            )
        )

        self.assertEqual(
            removed,
            3,
        )

        self.assertFalse(
            pending.exists()
        )

        self.assertFalse(
            first_claim.exists()
        )

        self.assertFalse(
            second_claim.exists()
        )


if __name__ == "__main__":
    unittest.main(
        verbosity=2,
    )
