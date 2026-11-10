"""Reproduce the frozen *base* miner SQLite schema exclusively in memory.

This module has no path parameter and cannot open the historical database.
The bundled schema file is SHA-256 verified before it is executed. This does
not run the historical Database migration routine, WAL setup or job queues.
"""
from __future__ import annotations

import hashlib
from importlib import resources
import sqlite3

SCHEMA_SHA256 = "1bd6e73515570b6e1248e8ecb9ded6cd3079b24e73d964de60b52a1a01aa4853"


class SchemaMismatchError(ValueError):
    """Bundled schema differs from the frozen recovered source."""


def verified_schema_sql() -> str:
    data = resources.files("src.db").joinpath("schema.sql").read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if digest != SCHEMA_SHA256:
        raise SchemaMismatchError(f"Bundled schema hash mismatch: {digest}")
    return data.decode("utf-8")


def open_ephemeral_database() -> sqlite3.Connection:
    """Create an isolated RAM-only schema; caller must close the connection."""
    sql = verified_schema_sql()
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    try:
        conn.executescript(sql)
        rows = conn.execute("PRAGMA database_list").fetchall()
        if len(rows) != 1 or rows[0][1] != "main" or rows[0][2] != "":
            raise RuntimeError("Expected one memory-only SQLite database")
        if conn.execute("PRAGMA foreign_keys").fetchone()[0] != 1:
            raise RuntimeError("Foreign key enforcement unexpectedly disabled")
    except Exception:
        conn.close()
        raise
    return conn
