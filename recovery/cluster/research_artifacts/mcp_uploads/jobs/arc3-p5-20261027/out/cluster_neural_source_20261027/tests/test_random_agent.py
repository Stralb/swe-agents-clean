import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "kaggle"))
sys.modules.setdefault("agents", type(sys)("agents"))          # framework not needed for pure sampler tests
sys.modules["agents.agent"] = type(sys)("agents.agent")
sys.modules["agents.agent"].Agent = object
from my_agent import sample_action  # noqa: E402


def test_never_illegal_or_reset():
    rng = random.Random(1)
    for avail in ([6], [1, 2, 3, 4], [3, 4, 6, 7], [5, 6, 7]):
        for mode in ("type_uniform", "flat_uniform"):
            for _ in range(2000):
                a, xy = sample_action(rng, avail, mode)
                assert a in avail and a != 0
                assert (xy is not None) == (a == 6)
                if xy:
                    assert 0 <= xy[0] < 64 and 0 <= xy[1] < 64


def test_click_share():
    rng = random.Random(2)
    avail = [1, 2, 3, 4, 5, 6]                                # 5 simple + click
    n = 20000
    flat = sum(sample_action(rng, avail, "flat_uniform")[0] == 6 for _ in range(n)) / n
    typ = sum(sample_action(rng, avail, "type_uniform")[0] == 6 for _ in range(n)) / n
    assert flat > 0.99                                        # 4096/4101 ~ 0.9988
    assert abs(typ - 1 / 6) < 0.02
