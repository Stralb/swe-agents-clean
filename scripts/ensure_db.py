from pathlib import Path
import sqlite3

from src.db.database import Database
from src.settings import load_settings

settings = load_settings()
db_path = Path(settings.db_path)
schema = Path(__file__).resolve().parents[1] / "src" / "db" / "schema.sql"

needs_init = not db_path.exists()
if not needs_init:
    try:
        with sqlite3.connect(db_path) as conn:
            row = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='repos'").fetchone()
            needs_init = row is None
    except sqlite3.DatabaseError:
        needs_init = True

# Always run init_schema: CREATE IF NOT EXISTS is safe and additive migrations
# keep older DBs compatible with newer UI/worker code.
Database(db_path).init_schema(schema)
print(("Initialized" if needs_init else "DB ready") + f": {db_path}")
