from pathlib import Path

from src.db.database import Database
from src.settings import load_settings

settings = load_settings()
schema = Path(__file__).resolve().parents[1] / "src" / "db" / "schema.sql"
Database(settings.db_path).init_schema(schema)
print(f"Initialized DB: {settings.db_path}")
