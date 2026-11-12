from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.distributed.spool import (
    DistributedSpool,
)


class RequeueStaleRaceTests(
    unittest.TestCase
):
    def test_disappearing_claim_is_ignored(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(
                temporary
            )

            spool = DistributedSpool(
                root
            )

            pool = "codeql_security"
            task_id = "scanner-job-123"

            claimed = (
                spool.queue_path(
                    pool,
                    "claimed",
                )
                / (
                    f"{task_id}__"
                    "codeql-worker.json"
                )
            )

            claimed.write_text(
                json.dumps(
                    {
                        "task_id": task_id,
                    }
                ),
                encoding="utf-8",
            )

            original_stat = Path.stat
            triggered = False

            def disappearing_stat(
                candidate: Path,
                *args,
                **kwargs,
            ):
                nonlocal triggered

                if (
                    candidate == claimed
                    and not triggered
                ):
                    triggered = True

                    try:
                        candidate.unlink()
                    except FileNotFoundError:
                        pass

                    raise FileNotFoundError(
                        str(candidate)
                    )

                return original_stat(
                    candidate,
                    *args,
                    **kwargs,
                )

            with patch.object(
                Path,
                "stat",
                disappearing_stat,
            ):
                changed = (
                    spool.requeue_stale(
                        pool,
                        stale_seconds=0,
                    )
                )

            self.assertTrue(
                triggered
            )

            self.assertEqual(
                changed,
                0,
            )


if __name__ == "__main__":
    unittest.main(
        verbosity=2,
    )
