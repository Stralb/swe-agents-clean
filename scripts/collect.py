from src.pipeline.collect_pipeline import collect
from src.settings import load_settings
from src.utils.logging import setup_logging

setup_logging()
collect(load_settings())
