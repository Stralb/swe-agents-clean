import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


import pytest


@pytest.fixture(scope="session")
def arc():
    import arc_agi
    from arc_agi import OperationMode
    return arc_agi.Arcade(operation_mode=OperationMode.NORMAL)
