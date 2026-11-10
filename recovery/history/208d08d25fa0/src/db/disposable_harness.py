"""Create a brand-new temporary miner DB through the unchanged Database class.

No caller-supplied path is accepted. The historical constructor and migration
statements run only under a new TemporaryDirectory created for this context.
Never pass a Wits database or research artifact to this harness.
"""
from __future__ import annotations

from contextlib import contextmanager
from importlib import resources
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Iterator

from src.db.database import Database


@contextmanager
def disposable_original_database() -> Iterator[Database]:
    """Yield an isolated, initialized SQLite miner DB; clean up on exit."""
    with TemporaryDirectory(prefix="arno_disposable_original_db_") as path:
        db_path = Path(path) / "miner.sqlite"
        db = Database(db_path, read_only=False, command_spool=None)
        schema_ref = resources.files("src.db").joinpath("schema.sql")
        with resources.as_file(schema_ref) as schema_path:
            db.init_schema(schema_path)
        yield db
