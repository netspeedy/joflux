"""CLI tests."""

import argparse

import pytest

from joflux import cli
from joflux.cli import _pending_migration_repos, main
from joflux.config import AppConfig
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
