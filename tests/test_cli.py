"""CLI tests."""

import argparse
import json
from typing import Any

import pytest

from joflux import cli, http
from joflux.cli import _pending_migration_repos, main
from joflux.config import AppConfig
from joflux.forgejo import MigrationResult
from joflux.state import MigrationState


def test_help_exits_successfully(capsys) -> None:
    """The top-level help text exits cleanly."""
    with pytest.raises(SystemExit) as exc_info:
        main(["--help"])

    assert exc_info.value.code == 0
    assert "Move GitHub organization repositories" in capsys.readouterr().out


def test_pending_migrations_ignore_completed_statuses() -> None:
    """Monitor resumes from the latest terminal status events."""
    pending = _pending_migration_repos(
        [
            {"repo": "done", "status": "initiated", "timestamp": "2026-01-01T00:00:00+00:00"},
            {"repo": "waiting", "status": "initiated", "timestamp": "2026-01-01T00:00:00+00:00"},
        ],
        [{"repo": "done", "status": "completed", "checked_at": "2026-01-01T00:01:00+00:00"}],
    )

    assert pending == ["waiting"]


def test_monitor_fails_when_repositories_remain_pending(tmp_path, monkeypatch) -> None:
    """Pending migrations after max wait time produce a non-zero exit."""
    state = MigrationState(str(tmp_path))
    state.log_migration("example", "initiated", "started", 123)

    class FakeForgejoClient:
        """Forgejo test double that never observes completion."""

        def __init__(self, *_args) -> None:
            """Accept the production constructor shape."""

        def repository_status(self, _org_name: str, _repo_name: str) -> str:
            """Return a still-running migration status."""
            return "in_progress"

    monkeypatch.setattr(cli, "ForgejoClient", FakeForgejoClient)

    config = AppConfig(
        github_org="source",
        github_token="github-token",
        forgejo_url="https://forge.example",
        forgejo_org="target",
        forgejo_token="forgejo-token",
        max_wait_time=0,
        output_dir=str(tmp_path),
    )

    exit_code = cli.cmd_monitor(argparse.Namespace(interval=1), config)

    assert exit_code == 1


def test_migrate_passes_metadata_switch_and_wait_time(tmp_path, monkeypatch) -> None:
    """Migrate hands the metadata switch and max_wait_time to every Forgejo request."""
    state = MigrationState(str(tmp_path))
    state.save_inventory([{"name": "example", "private": False}])
    calls: list[dict] = []

    class FakeForgejoClient:
        """Forgejo test double that records migrate requests."""

        def __init__(self, *_args) -> None:
            """Accept the production constructor shape."""

        def organization_id(self, _org_name: str) -> int:
            """Return a fixed organization id."""
            return 3

        def migrate_repository(self, **kwargs) -> MigrationResult:
            """Record the request and report a finished import."""
            calls.append(kwargs)
            return MigrationResult("completed", 11)

    monkeypatch.setattr(cli, "ForgejoClient", FakeForgejoClient)
    monkeypatch.setattr(cli.time, "sleep", lambda _seconds: None)

    config = AppConfig(
        github_org="source",
        github_token="github-token",
        forgejo_url="https://forge.example",
        forgejo_org="target",
        forgejo_token="forgejo-token",
        max_wait_time=5400,
        output_dir=str(tmp_path),
        migrate_metadata=False,
    )

    assert cli.cmd_migrate(argparse.Namespace(), config) == 0
    assert calls[0]["metadata"] is False
    assert calls[0]["timeout"] == 5400


def _config(tmp_path, **overrides) -> AppConfig:
    values = {
        "github_org": "source",
        "github_token": "github-token",
        "forgejo_url": "https://forge.example",
        "forgejo_org": "target",
        "forgejo_token": "forgejo-token",
        "output_dir": str(tmp_path),
    }
    values.update(overrides)
    return AppConfig(**values)


def test_migrate_records_what_forgejo_answered(tmp_path, monkeypatch) -> None:
    """A 201 is recorded as completed, so monitor only rechecks unanswered imports."""
    state = MigrationState(str(tmp_path))
    state.save_inventory([{"name": "done"}, {"name": "slow"}, {"name": "taken"}])
    results = {
        "done": MigrationResult("completed", 7, "Forgejo finished the import"),
        "slow": MigrationResult("initiated", None, "Forgejo didn't answer"),
        "taken": MigrationResult("failed", None, "HTTP 409"),
    }
    timeouts: list[int] = []

    class FakeForgejoClient:
        """Forgejo test double that answers from a table."""

        def __init__(self, *_args) -> None:
            """Accept the production constructor shape."""

        def organization_id(self, _org_name: str) -> int:
            """Return a fixed organization id."""
            return 3

        def migrate_repository(self, **kwargs) -> MigrationResult:
            """Return the canned result for this repository."""
            timeouts.append(kwargs["timeout"])
            return results[kwargs["repo_name"]]

    monkeypatch.setattr(cli, "ForgejoClient", FakeForgejoClient)
    monkeypatch.setattr(cli.time, "sleep", lambda _seconds: None)

    exit_code = cli.cmd_migrate(argparse.Namespace(), _config(tmp_path, max_wait_time=5400))

    events = state.load_json(state.migration_log)
    assert exit_code == 1
    assert timeouts == [5400, 5400, 5400]
    assert [(event["repo"], event["status"], event["migration_id"]) for event in events] == [
        ("done", "completed", 7),
        ("slow", "initiated", None),
        ("taken", "failed", None),
    ]
    assert _pending_migration_repos(events, []) == ["slow"]


def test_monitor_does_not_call_an_unanswered_import_complete(tmp_path, monkeypatch) -> None:
    """Git data on the target isn't proof the issues and releases arrived."""
    state = MigrationState(str(tmp_path))
    state.log_migration("slow", "initiated", "Forgejo didn't answer")

    class FakeForgejoClient:
        """Forgejo test double whose repository has its git data."""

        def __init__(self, *_args) -> None:
            """Accept the production constructor shape."""

        def repository_status(self, _org_name: str, _repo_name: str) -> str:
            """Report git data present but the import unconfirmed."""
            return "unconfirmed"

    monkeypatch.setattr(cli, "ForgejoClient", FakeForgejoClient)

    exit_code = cli.cmd_monitor(argparse.Namespace(interval=1), _config(tmp_path, max_wait_time=0))

    statuses = state.load_json(state.status_file)
    assert exit_code == 1
    assert [(event["repo"], event["status"]) for event in statuses] == [("slow", "unconfirmed")]
    assert _pending_migration_repos(state.load_json(state.migration_log), statuses) == ["slow"]


def test_verify_records_whether_each_wiki_arrived(tmp_path, monkeypatch) -> None:
    """The wiki check lands in the verification report next to the counts."""
    state = MigrationState(str(tmp_path))
    state.save_inventory([{"name": "with-wiki"}, {"name": "without-wiki"}])

    class FakeForgejoClient:
        """Forgejo test double with one repository that has a wiki."""

        def __init__(self, *_args) -> None:
            """Accept the production constructor shape."""

        def repository_metadata(self, _org_name: str, repo_name: str) -> dict:
            """Return verified counts, with a wiki only for with-wiki."""
            return {
                "name": repo_name,
                "size": 1,
                "issues": 2,
                "pulls": 3,
                "labels": 4,
                "releases": 5,
                "wiki": repo_name == "with-wiki",
                "status": "verified",
            }

    monkeypatch.setattr(cli, "ForgejoClient", FakeForgejoClient)

    assert cli.cmd_verify(argparse.Namespace(), _config(tmp_path)) == 0
    details = [event["details"] for event in state.load_json(state.verify_file)]
    assert details == [
        "size:1 issues:2 pulls:3 labels:4 releases:5 wiki:yes",
        "size:1 issues:2 pulls:3 labels:4 releases:5 wiki:no",
    ]


class _FakeResponse:
    """The parts of an HTTP response request_json reads."""

    def __init__(self, data: Any) -> None:
        self.body = json.dumps(data).encode("utf-8")

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *_args) -> None:
        return None

    def read(self) -> bytes:
        """Return the JSON body."""
        return self.body


def test_verify_carries_on_after_a_request_times_out(tmp_path, monkeypatch) -> None:
    """A timed-out GET is that repository's error, not the end of the stage."""
    state = MigrationState(str(tmp_path))
    state.save_inventory([{"name": "slow"}, {"name": "fine"}])

    def fake_urlopen(request: Any, timeout: int = 30) -> Any:
        del timeout
        if "/repos/target/slow" in request.full_url:
            raise TimeoutError("timed out")
        if request.full_url.endswith("/repos/target/fine"):
            return _FakeResponse({"size": 1, "has_wiki_contents": False})
        return _FakeResponse([])

    monkeypatch.setattr(http, "urlopen", fake_urlopen)

    assert cli.cmd_verify(argparse.Namespace(), _config(tmp_path)) == 1
    events = state.load_json(state.verify_file)
    assert [(event["repo"], event["status"]) for event in events] == [
        ("slow", "missing"),
        ("fine", "verified"),
    ]
    assert events[0]["details"].startswith("no answer from https://forge.example/")


def test_archive_carries_on_after_a_request_times_out(tmp_path, monkeypatch) -> None:
    """A timed-out archive request is logged as failed and the next repository still runs."""
    state = MigrationState(str(tmp_path))
    state.save_inventory([{"name": "slow"}, {"name": "fine"}])

    def fake_urlopen(request: Any, timeout: int = 30) -> Any:
        del timeout
        if request.full_url.endswith("/repos/source/slow"):
            raise TimeoutError("timed out")
        return _FakeResponse({"archived": True})

    monkeypatch.setattr(http, "urlopen", fake_urlopen)
    monkeypatch.setattr(cli.time, "sleep", lambda _seconds: None)

    assert cli.cmd_archive(argparse.Namespace(yes=True), _config(tmp_path)) == 1
    events = state.load_json(state.archive_log)
    assert [(event["repo"], event["status"]) for event in events] == [
        ("slow", "failed"),
        ("fine", "success"),
    ]
    assert events[0]["message"].startswith("no answer from https://api.github.com/")
