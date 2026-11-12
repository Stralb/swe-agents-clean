#Group members:
#Tazeem Tayob - 2659956
#Arno Strauss - 2613224
#Zeeshaan Ebrahim - 2543004.

from __future__ import annotations

import csv
import io
import os
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]

MALICIOUSNESS_LABELS = [
    "Unreviewed",
    "Clearly malicious",
    "Probably malicious",
    "Potentially suspicious",
    "Benign / legitimate change",
    "Scanner / attribution artifact",
    "Insufficient evidence",
]

INTENT_LABELS = [
    "Unassigned",
    "Introduce code vulnerability",
    "Introduce vulnerable dependency",
    "Dependency downgrade",
    "Expose secret",
    "CI/CD manipulation",
    "Disable or weaken security",
    "Other malicious intent",
    "None / benign",
    "Insufficient evidence",
]

DISGUISE_LABELS = [
    "Unassigned",
    "Bug fix",
    "Security improvement",
    "Feature request",
    "Performance improvement",
    "Refactor",
    "Dependency maintenance",
    "Testing / reliability",
    "Other",
    "None apparent",
    "Insufficient evidence",
]

CONFIDENCE_LABELS = [
    "Unassigned",
    "Low",
    "Medium",
    "High",
]

REVIEW_STATUSES = [
    "Unreviewed",
    "In review",
    "Reviewed",
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _db_path() -> Path:
    configured = os.getenv("MANUAL_REVIEW_DB", "").strip()
    if configured:
        path = Path(configured).expanduser()
        if not path.is_absolute():
            path = ROOT / path
        return path.resolve()
    return (ROOT / "data" / "manual_review.sqlite3").resolve()


class ReviewStore:
    """Durable local manual-labelling store for the immutable research snapshot."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._connection = sqlite3.connect(
            self.path,
            check_same_thread=False,
            timeout=30,
        )
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._connection.execute("PRAGMA synchronous=NORMAL")
        self._init_schema()

    def _init_schema(self) -> None:
        with self._lock:
            self._connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS manual_reviews (
                    case_id INTEGER PRIMARY KEY,
                    review_status TEXT NOT NULL DEFAULT 'Unreviewed',
                    maliciousness TEXT NOT NULL DEFAULT 'Unreviewed',
                    intent TEXT NOT NULL DEFAULT 'Unassigned',
                    disguise TEXT NOT NULL DEFAULT 'Unassigned',
                    confidence TEXT NOT NULL DEFAULT 'Unassigned',
                    rationale TEXT NOT NULL DEFAULT '',
                    technical_notes TEXT NOT NULL DEFAULT '',
                    reviewer TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_manual_reviews_status
                    ON manual_reviews(review_status);

                CREATE INDEX IF NOT EXISTS idx_manual_reviews_maliciousness
                    ON manual_reviews(maliciousness);
                """
            )
            self._connection.commit()

    def get(self, case_id: int) -> dict[str, Any]:
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM manual_reviews WHERE case_id = ?",
                (int(case_id),),
            ).fetchone()
        if row is None:
            return {
                "case_id": int(case_id),
                "review_status": "Unreviewed",
                "maliciousness": "Unreviewed",
                "intent": "Unassigned",
                "disguise": "Unassigned",
                "confidence": "Unassigned",
                "rationale": "",
                "technical_notes": "",
                "reviewer": "",
                "created_at": "",
                "updated_at": "",
            }
        return dict(row)

    def save(
        self,
        case_id: int,
        review_status: str,
        maliciousness: str,
        intent: str,
        disguise: str,
        confidence: str,
        rationale: str,
        technical_notes: str,
        reviewer: str,
    ) -> None:
        now = _now()
        current = self.get(case_id)
        created = current.get("created_at") or now

        if maliciousness != "Unreviewed" and review_status == "Unreviewed":
            review_status = "Reviewed"

        with self._lock:
            self._connection.execute(
                """
                INSERT INTO manual_reviews (
                    case_id,
                    review_status,
                    maliciousness,
                    intent,
                    disguise,
                    confidence,
                    rationale,
                    technical_notes,
                    reviewer,
                    created_at,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(case_id) DO UPDATE SET
                    review_status = excluded.review_status,
                    maliciousness = excluded.maliciousness,
                    intent = excluded.intent,
                    disguise = excluded.disguise,
                    confidence = excluded.confidence,
                    rationale = excluded.rationale,
                    technical_notes = excluded.technical_notes,
                    reviewer = excluded.reviewer,
                    updated_at = excluded.updated_at
                """,
                (
                    int(case_id),
                    review_status,
                    maliciousness,
                    intent,
                    disguise,
                    confidence,
                    rationale.strip(),
                    technical_notes.strip(),
                    reviewer.strip(),
                    created,
                    now,
                ),
            )
            self._connection.commit()

    def frame(self) -> pd.DataFrame:
        with self._lock:
            return pd.read_sql_query(
                "SELECT * FROM manual_reviews ORDER BY case_id",
                self._connection,
            )

    def progress(self, eligible_case_ids: list[int]) -> dict[str, int]:
        eligible = {int(value) for value in eligible_case_ids}
        frame = self.frame()
        if frame.empty:
            return {
                "total": len(eligible),
                "reviewed": 0,
                "in_review": 0,
                "unreviewed": len(eligible),
                "suspicious_or_malicious": 0,
                "benign": 0,
                "artifact": 0,
            }

        frame = frame[frame["case_id"].isin(eligible)]
        reviewed = int((frame["review_status"] == "Reviewed").sum())
        in_review = int((frame["review_status"] == "In review").sum())
        suspicious = int(
            frame["maliciousness"].isin(
                [
                    "Clearly malicious",
                    "Probably malicious",
                    "Potentially suspicious",
                ]
            ).sum()
        )
        benign = int((frame["maliciousness"] == "Benign / legitimate change").sum())
        artifact = int((frame["maliciousness"] == "Scanner / attribution artifact").sum())
        return {
            "total": len(eligible),
            "reviewed": reviewed,
            "in_review": in_review,
            "unreviewed": max(0, len(eligible) - reviewed - in_review),
            "suspicious_or_malicious": suspicious,
            "benign": benign,
            "artifact": artifact,
        }

    def export_csv_bytes(self) -> bytes:
        frame = self.frame()
        buffer = io.StringIO()
        frame.to_csv(buffer, index=False, quoting=csv.QUOTE_MINIMAL)
        return buffer.getvalue().encode("utf-8")

    def close(self) -> None:
        with self._lock:
            try:
                self._connection.close()
            except Exception:
                pass


@st.cache_resource(show_spinner=False)
def get_review_store() -> ReviewStore:
    return ReviewStore(_db_path())
