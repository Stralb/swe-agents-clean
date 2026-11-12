"""Command line: python -m miner {init-db,collect,scan,export}."""
import argparse
from pathlib import Path
import sqlite3

from miner.db.database import Database
from miner.settings import load_settings
from miner.utils.logging import setup_logging


def init_db(settings):
    db_path = Path(settings.db_path)
    schema = Path(__file__).resolve().parent / "db" / "schema.sql"
    needs_init = not db_path.exists()
    if not needs_init:
        try:
            with sqlite3.connect(db_path) as conn:
                row = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='repos'"
                ).fetchone()
                needs_init = row is None
        except sqlite3.DatabaseError:
            needs_init = True
    # CREATE IF NOT EXISTS is safe; additive migrations keep older databases usable.
    Database(db_path).init_schema(schema)
    print(("Initialized" if needs_init else "DB ready") + f": {db_path}")


def main():
    parser = argparse.ArgumentParser(prog="miner", description=__doc__)
    parser.add_argument("command", choices=["init-db", "collect", "scan", "export"])
    command = parser.parse_args().command
    settings = load_settings()
    if command == "init-db":
        init_db(settings)
    elif command == "collect":
        from miner.pipeline.collect_pipeline import collect
        setup_logging()
        collect(settings)
    elif command == "scan":
        from miner.pipeline.scan_pipeline import scan
        setup_logging()
        scan(settings)
    else:
        from miner.pipeline.export_pipeline import export_cases
        print(f"Exported: {export_cases(settings.db_path)}")


if __name__ == "__main__":
    main()
