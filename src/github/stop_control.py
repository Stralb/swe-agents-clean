from __future__ import annotations

import os
import sqlite3
import time


class CooperativeStopRequested(RuntimeError):
    """Raised when a controlled daemon is disabled during a wait."""


def controlled_daemon_stop_requested() -> bool:
    daemon_name = str(
        os.environ.get("DAEMON_NAME") or ""
    ).strip()

    generation_text = str(
        os.environ.get("DAEMON_GENERATION") or ""
    ).strip()

    db_path = str(
        os.environ.get("DB_PATH") or ""
    ).strip()

    if not daemon_name or not generation_text or not db_path:
        return False

    try:
        generation = int(generation_text)

        connection = sqlite3.connect(
            db_path,
            timeout=5,
        )

        try:
            row = connection.execute(
                """
                SELECT desired_enabled, generation
                FROM daemon_controls
                WHERE daemon_name=?
                """,
                (daemon_name,),
            ).fetchone()
        finally:
            connection.close()

        if row is None:
            return True

        desired_enabled = int(row[0] or 0)
        active_generation = int(row[1] or 0)

        return (
            desired_enabled != 1
            or active_generation != generation
        )

    except (sqlite3.Error, ValueError):
        # A temporary read failure must not terminate a healthy daemon.
        return False


def cooperative_sleep(
    seconds: float,
    poll_seconds: float = 5.0,
) -> None:
    deadline = time.monotonic() + max(
        float(seconds),
        0.0,
    )

    while True:
        if controlled_daemon_stop_requested():
            raise CooperativeStopRequested(
                "Controlled daemon disabled during wait."
            )

        remaining = deadline - time.monotonic()

        if remaining <= 0:
            return

        time.sleep(
            min(
                max(float(poll_seconds), 0.1),
                remaining,
            )
        )
