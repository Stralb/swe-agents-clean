from __future__ import annotations

import json
import os
import re
import socket
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any


_SAFE_COMPONENT = re.compile(r"[^A-Za-z0-9._-]+")


def _safe_component(value: str) -> str:
    cleaned = _SAFE_COMPONENT.sub(
        "_",
        str(value),
    ).strip("._")

    return cleaned or uuid.uuid4().hex


def _fsync_directory(path: Path) -> None:
    try:
        fd = os.open(path, os.O_RDONLY)

        try:
            os.fsync(fd)
        finally:
            os.close(fd)

    except OSError:
        pass


def _write_temporary_json(
    directory: Path,
    payload: dict[str, Any],
) -> Path:
    directory.mkdir(parents=True, exist_ok=True)

    temporary = directory / (
        f".tmp-{os.getpid()}-{uuid.uuid4().hex}.json"
    )

    encoded = json.dumps(
        payload,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")

    fd = os.open(
        temporary,
        os.O_CREAT | os.O_EXCL | os.O_WRONLY,
        0o600,
    )

    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())

    except BaseException:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass

        raise

    return temporary


def atomic_replace_json(
    destination: Path,
    payload: dict[str, Any],
) -> None:
    temporary = _write_temporary_json(
        destination.parent,
        payload,
    )

    try:
        os.replace(temporary, destination)
        _fsync_directory(destination.parent)

    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def atomic_create_json(
    destination: Path,
    payload: dict[str, Any],
) -> bool:
    """Create an immutable JSON file without replacing an existing result."""

    temporary = _write_temporary_json(
        destination.parent,
        payload,
    )

    try:
        try:
            os.link(temporary, destination)
            _fsync_directory(destination.parent)
            return True

        except FileExistsError:
            return False

    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(
        path.read_text(encoding="utf-8")
    )


@dataclass(frozen=True)
class ClaimedTask:
    pool: str
    task_id: str
    worker_id: str
    path: Path
    payload: dict[str, Any]


class DistributedSpool:
    POOLS = (
        "mining",
        "cheap_analysis",
        "codeql_security",
        "ui_commands",
        "test",
    )

    QUEUES = (
        "pending",
        "claimed",
        "results",
        "failed",
        "heartbeats",
    )

    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def pool_path(self, pool: str) -> Path:
        pool = _safe_component(pool)
        path = self.root / pool

        for queue in self.QUEUES:
            (path / queue).mkdir(
                parents=True,
                exist_ok=True,
            )

        return path

    def queue_path(
        self,
        pool: str,
        queue: str,
    ) -> Path:
        if queue not in self.QUEUES:
            raise ValueError(
                f"Unsupported spool queue: {queue}"
            )

        return self.pool_path(pool) / queue

    def enqueue(
        self,
        pool: str,
        task_id: str,
        payload: dict[str, Any],
    ) -> bool:
        safe_task_id = _safe_component(task_id)

        pending = (
            self.queue_path(pool, "pending")
            / f"{safe_task_id}.json"
        )

        result = (
            self.queue_path(pool, "results")
            / f"{safe_task_id}.json"
        )

        if result.exists() or pending.exists():
            return False

        claimed = self.queue_path(pool, "claimed")

        if next(
            claimed.glob(
                f"{safe_task_id}__*.json"
            ),
            None,
        ):
            return False

        envelope = {
            "schema_version": 1,
            "pool": pool,
            "task_id": safe_task_id,
            "created_at": time.time(),
            "payload": payload,
        }

        return atomic_create_json(
            pending,
            envelope,
        )

    def claim(
        self,
        pool: str,
        worker_id: str,
    ) -> ClaimedTask | None:
        safe_worker = _safe_component(worker_id)

        pending_directory = self.queue_path(
            pool,
            "pending",
        )

        claimed_directory = self.queue_path(
            pool,
            "claimed",
        )

        result_directory = self.queue_path(
            pool,
            "results",
        )

        for pending in sorted(
            pending_directory.glob("*.json")
        ):
            task_id = pending.stem

            if (
                result_directory
                / f"{task_id}.json"
            ).exists():
                try:
                    pending.unlink()
                except FileNotFoundError:
                    pass

                continue

            claimed = claimed_directory / (
                f"{task_id}__{safe_worker}.json"
            )

            try:
                os.replace(
                    pending,
                    claimed,
                )

            except FileNotFoundError:
                continue

            except OSError:
                if not pending.exists():
                    continue

                raise

            payload = read_json(claimed)

            self.heartbeat(
                pool,
                worker_id,
                state="working",
                task_id=task_id,
                detail="Task claimed",
            )

            return ClaimedTask(
                pool=pool,
                task_id=task_id,
                worker_id=worker_id,
                path=claimed,
                payload=payload,
            )

        return None

    def heartbeat(
        self,
        pool: str,
        worker_id: str,
        *,
        state: str,
        task_id: str | None = None,
        detail: str = "",
    ) -> None:
        safe_worker = _safe_component(worker_id)

        destination = (
            self.queue_path(pool, "heartbeats")
            / f"{safe_worker}.json"
        )

        atomic_replace_json(
            destination,
            {
                "schema_version": 1,
                "pool": pool,
                "worker_id": worker_id,
                "hostname": socket.gethostname(),
                "pid": os.getpid(),
                "slurm_job_id": os.getenv(
                    "SLURM_JOB_ID"
                ),
                "partition": (
                    os.getenv("POOL_PARTITION")
                    or os.getenv("SLURM_JOB_PARTITION")
                ),
                "state": state,
                "task_id": task_id,
                "detail": detail,
                "updated_at": time.time(),
            },
        )

    def publish_result(
        self,
        claim: ClaimedTask,
        result: dict[str, Any],
    ) -> bool:
        destination = (
            self.queue_path(
                claim.pool,
                "results",
            )
            / f"{claim.task_id}.json"
        )

        created = atomic_create_json(
            destination,
            {
                "schema_version": 1,
                "pool": claim.pool,
                "task_id": claim.task_id,
                "worker_id": claim.worker_id,
                "hostname": socket.gethostname(),
                "slurm_job_id": os.getenv(
                    "SLURM_JOB_ID"
                ),
                "finished_at": time.time(),
                "task": claim.payload,
                "result": result,
            },
        )

        try:
            claim.path.unlink()
        except FileNotFoundError:
            pass

        self.heartbeat(
            claim.pool,
            claim.worker_id,
            state="idle",
            detail="Result published",
        )

        return created

    def publish_failure(
        self,
        claim: ClaimedTask,
        error: str,
    ) -> Path:
        failure_id = (
            f"{claim.task_id}__"
            f"{_safe_component(claim.worker_id)}__"
            f"{int(time.time())}"
        )

        destination = (
            self.queue_path(
                claim.pool,
                "failed",
            )
            / f"{failure_id}.json"
        )

        atomic_create_json(
            destination,
            {
                "schema_version": 1,
                "pool": claim.pool,
                "task_id": claim.task_id,
                "worker_id": claim.worker_id,
                "hostname": socket.gethostname(),
                "slurm_job_id": os.getenv(
                    "SLURM_JOB_ID"
                ),
                "failed_at": time.time(),
                "error": str(error)[:10000],
                "task": claim.payload,
            },
        )

        try:
            claim.path.unlink()
        except FileNotFoundError:
            pass

        self.heartbeat(
            claim.pool,
            claim.worker_id,
            state="error",
            task_id=claim.task_id,
            detail=str(error)[:500],
        )

        return destination

    def requeue_stale(
        self,
        pool: str,
        *,
        stale_seconds: int,
    ) -> int:
        now = time.time()
        changed = 0

        claimed_directory = self.queue_path(
            pool,
            "claimed",
        )

        heartbeat_directory = self.queue_path(
            pool,
            "heartbeats",
        )

        result_directory = self.queue_path(
            pool,
            "results",
        )

        pending_directory = self.queue_path(
            pool,
            "pending",
        )

        for claimed in claimed_directory.glob(
            "*.json"
        ):
            stem = claimed.stem

            if "__" not in stem:
                continue

            task_id, worker_id = stem.split(
                "__",
                1,
            )

            result = (
                result_directory
                / f"{task_id}.json"
            )

            if result.exists():
                try:
                    claimed.unlink()
                except FileNotFoundError:
                    pass

                continue

            heartbeat = (
                heartbeat_directory
                / f"{worker_id}.json"
            )

            timestamps = [
                claimed.stat().st_mtime
            ]

            if heartbeat.exists():
                timestamps.append(
                    heartbeat.stat().st_mtime
                )

            if now - max(timestamps) <= stale_seconds:
                continue

            pending = (
                pending_directory
                / f"{task_id}.json"
            )

            if pending.exists():
                try:
                    claimed.unlink()
                except FileNotFoundError:
                    pass

                changed += 1
                continue

            try:
                os.replace(
                    claimed,
                    pending,
                )
                changed += 1

            except FileNotFoundError:
                continue

        return changed

    def counts(
        self,
        pool: str,
    ) -> dict[str, int]:
        return {
            queue: sum(
                1
                for _ in self.queue_path(
                    pool,
                    queue,
                ).glob("*.json")
            )
            for queue in self.QUEUES
        }
