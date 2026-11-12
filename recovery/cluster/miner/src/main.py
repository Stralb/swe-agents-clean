from src.pipeline.collect_pipeline import collect
from src.pipeline.scan_pipeline import scan
from src.settings import load_settings
from src.utils.logging import setup_logging

if __name__ == "__main__":
    setup_logging()
    settings = load_settings()
    collect(settings)
    scan(settings)
