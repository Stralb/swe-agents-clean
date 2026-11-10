from src.pipeline.scan_pipeline import scan
from src.settings import load_settings
from src.utils.logging import setup_logging

setup_logging()
scan(load_settings())
