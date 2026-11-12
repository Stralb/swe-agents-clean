from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from src.distributed import mining_pipeline
from src.distributed.spool import DistributedSpool


def write_environment(
    root: Path,
    *,
    shards: int,
) -> None:
    (
        root
        / ".env.cluster"
    ).write_text(
        (
            "MINING_ENABLED=1\n"
            f"MINING_SHARDS={shards}\n"
            "MINING_PASS_INTERVAL_SECONDS=3600\n"
            "MINING_TASK_MAX_SECONDS=600\n"
            "MINING_TASK_MAX_REPOS=250\n"
            "MINING_TASK_MAX_PRS=500\n"
            "MINING_TASK_MAX_CASES=1000\n"
        ),
        encoding="utf-8",
    )


class MiningRuntimeGuardTests(
    unittest.TestCase
):
    def test_live_file_overrides_stale_environment(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)

            write_environment(
                root,
                shards=32,
            )

            with (
                mock.patch.object(
                    mining_pipeline,
                    "ROOT",
                    root,
                ),
                mock.patch.dict(
                    os.environ,
                    {
                        "MINING_SHARDS": "4",
                    },
                    clear=False,
                ),
            ):
                settings = (
                    mining_pipeline
                    ._current_mining_settings()
                )

            self.assertEqual(
                settings["shard_count"],
                32,
            )

            self.assertEqual(
                settings["max_seconds"],
                600,
            )

    def test_new_batch_uses_live_settings(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)

            write_environment(
                root,
                shards=8,
            )

            spool = DistributedSpool(
                root / "spool"
            )

            with mock.patch.object(
                mining_pipeline,
                "ROOT",
                root,
            ):
                created = (
                    mining_pipeline
                    .enqueue_jobs(spool)
                )

            self.assertEqual(
                created,
                8,
            )

            files = list(
                (
                    spool.root
                    / "mining"
                    / "pending"
                ).glob("*.json")
            )

            self.assertEqual(
                len(files),
                8,
            )

            payloads = [
                json.loads(
                    path.read_text(
                        encoding="utf-8"
                    )
                )
                for path in files
            ]

            self.assertEqual(
                {
                    item["payload"][
                        "shard_count"
                    ]
                    for item in payloads
                },
                {8},
            )

            self.assertTrue(
                all(
                    item["payload"].get(
                        "config_revision"
                    )
                    for item in payloads
                )
            )

    def test_mismatched_batch_fails_closed(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)

            write_environment(
                root,
                shards=4,
            )

            spool = DistributedSpool(
                root / "spool"
            )

            with mock.patch.object(
                mining_pipeline,
                "ROOT",
                root,
            ):
                self.assertEqual(
                    mining_pipeline.enqueue_jobs(
                        spool
                    ),
                    4,
                )

                write_environment(
                    root,
                    shards=32,
                )

                self.assertEqual(
                    mining_pipeline.enqueue_jobs(
                        spool
                    ),
                    0,
                )

            self.assertEqual(
                spool.counts(
                    "mining"
                )["pending"],
                4,
            )

            guard = json.loads(
                (
                    spool.root
                    / "status"
                    / "mining_batch_guard.json"
                ).read_text(
                    encoding="utf-8"
                )
            )

            self.assertEqual(
                guard["state"],
                "configuration_mismatch",
            )

            self.assertEqual(
                guard["mismatches"][
                    "shard_count"
                ]["active"],
                [4],
            )

            self.assertEqual(
                guard["mismatches"][
                    "shard_count"
                ]["desired"],
                32,
            )

    def test_matching_batch_is_not_duplicated(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)

            write_environment(
                root,
                shards=6,
            )

            spool = DistributedSpool(
                root / "spool"
            )

            with mock.patch.object(
                mining_pipeline,
                "ROOT",
                root,
            ):
                self.assertEqual(
                    mining_pipeline.enqueue_jobs(
                        spool
                    ),
                    6,
                )

                self.assertEqual(
                    mining_pipeline.enqueue_jobs(
                        spool
                    ),
                    0,
                )

            self.assertEqual(
                spool.counts(
                    "mining"
                )["pending"],
                6,
            )

            guard = json.loads(
                (
                    spool.root
                    / "status"
                    / "mining_batch_guard.json"
                ).read_text(
                    encoding="utf-8"
                )
            )

            self.assertEqual(
                guard["state"],
                "active",
            )


if __name__ == "__main__":
    unittest.main(
        verbosity=2,
    )
