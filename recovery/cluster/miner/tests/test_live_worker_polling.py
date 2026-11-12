from pathlib import Path

from src.db.database import Database
from src.settings import RuntimeLimits, Settings
from src.workers import supervisor


class DummyThread:
    def join(self):
        return None


def make_settings(tmp_path):
    db_path = tmp_path / "miner.db"
    db = Database(db_path)
    db.init_schema(Path("src/db/schema.sql"))
    return Settings(
        config_path=Path("config.yml"),
        db_path=db_path,
        github_token=None,
        config={"workers": {"idle_seconds": 1}},
        limits=RuntimeLimits(max_repos=None, max_prs=None, max_cases=None, max_cases_per_repo=None, max_seconds=None),
    )


def test_live_mode_ignores_max_loops_so_workers_keep_polling(monkeypatch, tmp_path):
    settings = make_settings(tmp_path)
    calls = []

    def fake_start_thread(name, target):
        target()
        return DummyThread()

    def fake_mine_loop(settings_arg, *, max_loops=0, idle_seconds=30, worker_id=None):
        calls.append(("mine", worker_id, max_loops))

    def fake_evaluate_loop(settings_arg, *, job_group="all", worker_id=None, max_loops=None, idle_seconds=None, exit_when_idle=False, mode_label="evaluate"):
        calls.append(("eval", job_group, worker_id, max_loops, exit_when_idle, mode_label))
        return 0

    monkeypatch.setattr(supervisor, "_start_thread", fake_start_thread)
    monkeypatch.setattr(supervisor, "mine_loop", fake_mine_loop)
    monkeypatch.setattr(supervisor, "evaluate_loop", fake_evaluate_loop)

    supervisor.run_supervisor(
        settings,
        mode="live",
        github_workers=1,
        source_workers=1,
        dependency_workers=1,
        secret_workers=1,
        codeql_workers=1,
        max_loops=3,
        idle_seconds=1,
        exit_when_drained=False,
    )

    assert ("mine", "github-0", 0) in calls
    eval_calls = [c for c in calls if c[0] == "eval"]
    assert len(eval_calls) == 4
    assert all(c[3] == 0 for c in eval_calls)
    assert all(c[4] is False for c in eval_calls)
    assert all(c[5] == "live" for c in eval_calls)

    event = Database(settings.db_path).one("SELECT detail FROM pipeline_events WHERE event_type='live_max_loops_ignored'")
    assert "Ignored --max-loops=3" in event["detail"]


def test_evaluate_mode_still_drains_and_exits(monkeypatch, tmp_path):
    settings = make_settings(tmp_path)
    calls = []

    def fake_start_thread(name, target):
        target()
        return DummyThread()

    def fake_evaluate_loop(settings_arg, *, job_group="all", worker_id=None, max_loops=None, idle_seconds=None, exit_when_idle=False, mode_label="evaluate"):
        calls.append((job_group, max_loops, exit_when_idle, mode_label))
        return 0

    monkeypatch.setattr(supervisor, "_start_thread", fake_start_thread)
    monkeypatch.setattr(supervisor, "evaluate_loop", fake_evaluate_loop)

    supervisor.run_supervisor(
        settings,
        mode="evaluate",
        github_workers=0,
        source_workers=1,
        dependency_workers=0,
        secret_workers=0,
        codeql_workers=0,
        max_loops=3,
        idle_seconds=1,
        exit_when_drained=True,
    )

    assert calls == [("source", 3, True, "evaluate")]
