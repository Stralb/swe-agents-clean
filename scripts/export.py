from src.pipeline.export_pipeline import export_cases
from src.settings import load_settings

settings = load_settings()
out = export_cases(settings.db_path)
print(f"Exported: {out}")
