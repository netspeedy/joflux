"""CLI tests."""

import argparse
import http.client as http_client
import json
import logging
from typing import Any

import pytest

from joflux import cli, http
from joflux.cli import _latest_entries, _latest_statuses, _pending_migration_repos, main
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
    assert calls[0]["owner"] == "target"
    assert "auth_username" not in calls[0]


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
    state.log_verification("slow", "verified", "size:1")
    state.log_verification("fine", "verified", "size:1")

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


def test_migrate_skips_repositories_that_already_completed(tmp_path, monkeypatch, caplog) -> None:
    """A re-run retries what didn't finish and leaves finished imports alone."""
    state = MigrationState(str(tmp_path))
    state.save_inventory([{"name": "done"}, {"name": "retry"}, {"name": "redone"}])
    state.log_migration("done", "completed", "Forgejo finished the import", 7)
    state.log_migration("retry", "failed", "Forgejo rejected or failed the import: HTTP 500")
    state.log_migration("redone", "completed", "Forgejo finished the import", 8)
    state.log_migration("redone", "failed", "Forgejo rejected or failed the import: HTTP 409")
    requested: list[str] = []

    class FakeForgejoClient:
        """Forgejo test double that finishes every import it's asked for."""

        def __init__(self, *_args) -> None:
            """Accept the production constructor shape."""

        def organization_id(self, _org_name: str) -> int:
            """Return a fixed organization id."""
            return 3

        def migrate_repository(self, **kwargs) -> MigrationResult:
            """Record the request and report a finished import."""
            requested.append(kwargs["repo_name"])
            return MigrationResult("completed", 9, "Forgejo finished the import")

    monkeypatch.setattr(cli, "ForgejoClient", FakeForgejoClient)
    monkeypatch.setattr(cli.time, "sleep", lambda _seconds: None)
    caplog.set_level(logging.INFO, logger="joflux")

    assert cli.cmd_migrate(argparse.Namespace(), _config(tmp_path)) == 0
    assert requested == ["retry", "redone"]
    new_events = state.load_json(state.migration_log)[4:]
    assert [(event["repo"], event["status"]) for event in new_events] == [
        ("retry", "completed"),
        ("redone", "completed"),
    ]
    assert "[1/3] Skipping done: its migration already completed" in caplog.text
    assert "Migrations finished: 2 completed, 0 unconfirmed, 0 failed, 1 skipped" in caplog.text


@pytest.mark.parametrize(
    ("answer", "expected_events", "expected_summary"),
    [
        (
            MigrationResult("failed", None, "Forgejo rejected or failed the import: HTTP 409", 409),
            [("pending", "initiated")],
            "Migrations finished: 0 completed, 1 unconfirmed, 0 failed, 0 skipped",
        ),
        (
            MigrationResult("completed", 9, "Forgejo finished the import"),
            [("pending", "initiated"), ("pending", "completed")],
            "Migrations finished: 1 completed, 0 unconfirmed, 0 failed, 0 skipped",
        ),
    ],
)
def test_migrate_leaves_an_unconfirmed_import_for_monitor(
    tmp_path, monkeypatch, caplog, answer, expected_events, expected_summary
) -> None:
    """A 409 for an unconfirmed import keeps it initiated; a fresh import replaces it."""
    state = MigrationState(str(tmp_path))
    state.save_inventory([{"name": "pending"}])
    state.log_migration("pending", "initiated", "no answer; Forgejo may still be importing it")

    class FakeForgejoClient:
        """Forgejo test double that gives one fixed answer."""

        def __init__(self, *_args) -> None:
            """Accept the production constructor shape."""

        def organization_id(self, _org_name: str) -> int:
            """Return a fixed organization id."""
            return 3

        def migrate_repository(self, **_kwargs) -> MigrationResult:
            """Return the parametrized answer."""
            return answer

    monkeypatch.setattr(cli, "ForgejoClient", FakeForgejoClient)
    monkeypatch.setattr(cli.time, "sleep", lambda _seconds: None)
    caplog.set_level(logging.INFO, logger="joflux")

    assert cli.cmd_migrate(argparse.Namespace(), _config(tmp_path)) == 0
    events = state.load_json(state.migration_log)
    assert [(event["repo"], event["status"]) for event in events] == expected_events
    assert expected_summary in caplog.text


class _FakeGitHubClient:
    """GitHub test double that records which repositories it was asked to archive."""

    archived: list[str] = []

    def __init__(self, *_args) -> None:
        """Accept the production constructor shape."""

    def archive_repository(self, repo_name: str) -> bool:
        """Record the request."""
        self.archived.append(repo_name)
        return True


def test_archive_only_archives_repositories_verify_recorded_as_verified(
    tmp_path, monkeypatch, caplog
) -> None:
    """Originals that never arrived, or were never checked, stay as they are on GitHub."""
    state = MigrationState(str(tmp_path))
    state.save_inventory(
        [{"name": "ok"}, {"name": "gone"}, {"name": "unchecked"}, {"name": "arrived-later"}]
    )
    state.log_verification("ok", "verified", "size:1")
    state.log_verification("gone", "missing", "HTTP 404")
    state.log_verification("arrived-later", "missing", "HTTP 404")
    state.log_verification("arrived-later", "verified", "size:1")
    prompts: list[str] = []

    def fake_input(prompt: str) -> str:
        prompts.append(prompt)
        return "yes"

    monkeypatch.setattr(cli, "GitHubClient", _FakeGitHubClient)
    monkeypatch.setattr(_FakeGitHubClient, "archived", [])
    monkeypatch.setattr("builtins.input", fake_input)
    monkeypatch.setattr(cli.time, "sleep", lambda _seconds: None)
    caplog.set_level(logging.INFO, logger="joflux")

    assert cli.cmd_archive(argparse.Namespace(yes=False), _config(tmp_path)) == 1
    assert prompts == ["Archive 2 repositories in github.com/source? Type yes: "]
    assert _FakeGitHubClient.archived == ["ok", "arrived-later"]
    assert [event["repo"] for event in state.load_json(state.archive_log)] == [
        "ok",
        "arrived-later",
    ]
    assert (
        "Not archiving 2 repositories that verify hasn't recorded as verified: gone, unchecked"
        in caplog.text
    )
    assert (
        "Archive complete: 2 archived, 0 failed, 0 already archived, 2 not verified" in caplog.text
    )


def test_archive_stops_without_a_verification_report(tmp_path, monkeypatch, caplog) -> None:
    """Archiving with nothing verified would archive blind, so it doesn't start."""
    MigrationState(str(tmp_path)).save_inventory([{"name": "example"}])
    config_path = tmp_path / "joflux.toml"
    config_path.write_text(
        f"""
[github]
org = "source"
token = "ghp_token"

[forgejo]
url = "https://forge.example"
org = "target"
token = "forgejo_token"

[migration]
output_dir = "{tmp_path}"
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setattr(cli, "GitHubClient", _FakeGitHubClient)
    monkeypatch.setattr(_FakeGitHubClient, "archived", [])
    # configure_logging would point the logger at stdout and stop it reaching caplog.
    monkeypatch.setattr(cli, "configure_logging", lambda _level: None)

    assert main(["--config", str(config_path), "archive", "--yes"]) == 2
    assert not _FakeGitHubClient.archived
    assert "verification report not found; run verify first" in caplog.text


def test_archive_prompt_names_the_enterprise_server(tmp_path, monkeypatch) -> None:
    """With github.api_url on a GitHub Enterprise Server, the prompt names that server."""
    state = MigrationState(str(tmp_path))
    state.save_inventory([{"name": "ok"}])
    state.log_verification("ok", "verified", "size:1")
    prompts: list[str] = []

    def fake_input(prompt: str) -> str:
        prompts.append(prompt)
        return "no"

    monkeypatch.setattr(cli, "GitHubClient", _FakeGitHubClient)
    monkeypatch.setattr(_FakeGitHubClient, "archived", [])
    monkeypatch.setattr("builtins.input", fake_input)

    config = _config(tmp_path, github_api_url="https://ghe.example.com/api/v3")
    assert cli.cmd_archive(argparse.Namespace(yes=False), config) == 0
    assert prompts == ["Archive 1 repositories in ghe.example.com/source? Type yes: "]
    assert not _FakeGitHubClient.archived


def test_archive_skips_repositories_that_are_already_archived(
    tmp_path, monkeypatch, caplog
) -> None:
    """A re-run doesn't touch what an earlier run archived, or what GitHub had archived already."""
    state = MigrationState(str(tmp_path))
    state.save_inventory(
        [
            {"name": "fresh", "archived": False},
            {"name": "was-archived", "archived": True},
            {"name": "done-before", "archived": False},
            {"name": "failed-before", "archived": False},
        ]
    )
    for name in ("fresh", "was-archived", "done-before", "failed-before"):
        state.log_verification(name, "verified", "size:1")
    state.log_archive("done-before", "success", "Repository archived")
    state.log_archive("failed-before", "failed", "HTTP 502 from https://api.github.com/")
    prompts: list[str] = []

    def fake_input(prompt: str) -> str:
        prompts.append(prompt)
        return "yes"

    monkeypatch.setattr(cli, "GitHubClient", _FakeGitHubClient)
    monkeypatch.setattr(_FakeGitHubClient, "archived", [])
    monkeypatch.setattr("builtins.input", fake_input)
    monkeypatch.setattr(cli.time, "sleep", lambda _seconds: None)
    caplog.set_level(logging.INFO, logger="joflux")

    assert cli.cmd_archive(argparse.Namespace(yes=False), _config(tmp_path)) == 0
    assert prompts == ["Archive 2 repositories in github.com/source? Type yes: "]
    assert _FakeGitHubClient.archived == ["fresh", "failed-before"]
    assert "Skipping was-archived: it was already archived on GitHub when it was exported" in (
        caplog.text
    )
    assert "Skipping done-before: an earlier archive run archived it" in caplog.text
    assert "Archive complete: 2 archived, 0 failed, 2 already archived, 0 not verified" in (
        caplog.text
    )


def test_verify_carries_on_after_an_answer_is_cut_off(tmp_path, monkeypatch) -> None:
    """A cut-off answer is that repository's error, not a traceback that ends the run."""
    state = MigrationState(str(tmp_path))
    state.save_inventory([{"name": "cut"}, {"name": "fine"}])

    class CutOffResponse(_FakeResponse):
        """A response whose body stops short."""

        def read(self) -> bytes:
            """Fail the way http.client does when the connection ends early."""
            raise http_client.IncompleteRead(b'{"size"', 40)

    def fake_urlopen(request: Any, timeout: int = 30) -> Any:
        del timeout
        if request.full_url.endswith("/repos/target/cut"):
            return CutOffResponse({})
        if request.full_url.endswith("/repos/target/fine"):
            return _FakeResponse({"size": 1, "has_wiki_contents": False})
        return _FakeResponse([])

    monkeypatch.setattr(http, "urlopen", fake_urlopen)

    assert cli.cmd_verify(argparse.Namespace(), _config(tmp_path)) == 1
    events = state.load_json(state.verify_file)
    assert [(event["repo"], event["status"]) for event in events] == [
        ("cut", "missing"),
        ("fine", "verified"),
    ]
    assert events[0]["details"].startswith("incomplete answer from https://forge.example/")


def test_verify_details_say_when_a_unit_is_off(tmp_path, monkeypatch) -> None:
    """A unit that's off shows in the details instead of a count."""
    state = MigrationState(str(tmp_path))
    state.save_inventory([{"name": "quiet"}])

    class FakeForgejoClient:
        """Forgejo test double for a repository with issues and pull requests off."""

        def __init__(self, *_args) -> None:
            """Accept the production constructor shape."""

        def repository_metadata(self, _org_name: str, repo_name: str) -> dict:
            """Return what repository_metadata gives for that repository."""
            return {
                "name": repo_name,
                "size": 1,
                "issues": "off",
                "pulls": "off",
                "labels": 4,
                "releases": 5,
                "wiki": False,
                "status": "verified",
            }

    monkeypatch.setattr(cli, "ForgejoClient", FakeForgejoClient)

    assert cli.cmd_verify(argparse.Namespace(), _config(tmp_path)) == 0
    assert state.load_json(state.verify_file)[0]["details"] == (
        "size:1 issues:off pulls:off labels:4 releases:5 wiki:no"
    )


def test_latest_means_the_last_entry_in_the_file_everywhere(tmp_path) -> None:
    """Every reader of a log takes a repository's last entry, whatever its timestamp says."""
    migration_events = [
        {"repo": "a", "status": "initiated", "timestamp": "2026-01-01T10:00:00+00:00"},
        {"repo": "b", "status": "completed", "timestamp": "2026-01-01T10:00:00+00:00"},
        {"repo": "c", "status": "initiated", "timestamp": "2026-01-01T10:00:00+00:00"},
        {"repo": "d", "status": "initiated", "timestamp": "2026-01-01T10:00:00+00:00"},
        # A clock that went backwards doesn't reorder the file.
        {"repo": "a", "status": "completed", "timestamp": "2026-01-01T09:00:00+00:00"},
        {"repo": "b", "status": "initiated", "timestamp": "2026-01-01T09:00:00+00:00"},
        {"repo": "broken"},
    ]
    status_events = [
        # Older than c's migration entry, so it doesn't settle c.
        {"repo": "c", "status": "error", "checked_at": "2026-01-01T09:59:00+00:00"},
        # Newer than d's, so it does.
        {"repo": "d", "status": "completed", "checked_at": "2026-01-01T10:01:00+00:00"},
    ]
    log = tmp_path / "migration-log.json"
    log.write_text(json.dumps(migration_events), encoding="utf-8")

    latest = _latest_entries(migration_events)
    assert {repo: event["status"] for repo, event in latest.items()} == {
        "a": "completed",
        "b": "initiated",
        "c": "initiated",
        "d": "initiated",
    }
    assert latest["a"]["timestamp"] == "2026-01-01T09:00:00+00:00"
    assert _latest_statuses(log) == {repo: event["status"] for repo, event in latest.items()}
    assert _pending_migration_repos(migration_events, status_events) == ["b", "c"]


@pytest.mark.parametrize(
    ("api_url", "clone_url"),
    [
        ("https://api.github.com", "https://github.com/source/bare.git"),
        ("https://ghe.example.com/api/v3", "https://ghe.example.com/source/bare.git"),
    ],
)
def test_migrate_falls_back_to_a_clone_url_on_the_configured_host(
    tmp_path, monkeypatch, api_url: str, clone_url: str
) -> None:
    """An inventory entry without a clone URL is cloned from the GitHub the config points at."""
    state = MigrationState(str(tmp_path))
    state.save_inventory([{"name": "bare"}])
    requested: list[str] = []

    class FakeForgejoClient:
        """Forgejo test double that records the clone URL it's asked for."""

        def __init__(self, *_args) -> None:
            """Accept the production constructor shape."""

        def organization_id(self, _org_name: str) -> int:
            """Return a fixed organization id."""
            return 3

        def migrate_repository(self, **kwargs) -> MigrationResult:
            """Record the clone URL and report a finished import."""
            requested.append(kwargs["clone_url"])
            return MigrationResult("completed", 9, "Forgejo finished the import")

    monkeypatch.setattr(cli, "ForgejoClient", FakeForgejoClient)
    monkeypatch.setattr(cli.time, "sleep", lambda _seconds: None)

    assert cli.cmd_migrate(argparse.Namespace(), _config(tmp_path, github_api_url=api_url)) == 0
    assert requested == [clone_url]
