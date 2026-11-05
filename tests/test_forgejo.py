"""Forgejo client tests."""

import logging
from typing import Any

import pytest

from joflux import forgejo
from joflux.forgejo import ForgejoClient
from joflux.http import APIError, NoAnswerError


def test_repository_metadata_reports_count_failures(monkeypatch) -> None:
    """Verification does not silently convert API failures into zero counts."""

    def fake_request_json(
        _method: str,
        url: str,
        _headers: dict[str, str],
        payload: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        timeout: int = 30,
        allow_status: tuple[int, ...] = (),
    ) -> Any:
        del payload, params, timeout, allow_status
        if url.endswith("/api/v1/repos/target/example"):
            return {"size": 12, "has_wiki": True}
        if url.endswith("/api/v1/repos/target/example/issues"):
            raise APIError("HTTP 500 from issues", 500, "boom")
        return []

    monkeypatch.setattr(forgejo, "request_json", fake_request_json)

    client = ForgejoClient("https://forge.example", "token", logging.getLogger("test"))
    metadata = client.repository_metadata("target", "example")

    assert metadata["status"] == "error"
    assert "issues" in metadata["error"]


def test_repository_metadata_counts_paginated_collections(monkeypatch) -> None:
    """Verification counts full paginated Forgejo collections."""

    def fake_request_json(
        _method: str,
        url: str,
        _headers: dict[str, str],
        payload: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        timeout: int = 30,
        allow_status: tuple[int, ...] = (),
    ) -> Any:
        del payload, timeout, allow_status
        if url.endswith("/api/v1/repos/target/example"):
            return {"size": 12, "has_wiki": True}
        if params and params["page"] == 1:
            return [{} for _ in range(50)]
        return [{}, {}]

    monkeypatch.setattr(forgejo, "request_json", fake_request_json)

    client = ForgejoClient("https://forge.example", "token", logging.getLogger("test"))
    metadata = client.repository_metadata("target", "example")

    assert metadata["status"] == "verified"
    assert metadata["issues"] == 52
    assert metadata["pulls"] == 52
    assert metadata["labels"] == 52
    assert metadata["releases"] == 52


def test_repository_metadata_counts_issues_without_pull_requests(monkeypatch) -> None:
    """Forgejo lists pull requests among the issues unless asked for type=issues."""
    issues = [{"number": 1}, {"number": 2}]
    pulls = [{"number": 3}, {"number": 4}, {"number": 5}]

    def fake_request_json(
        _method: str,
        url: str,
        _headers: dict[str, str],
        payload: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        timeout: int = 30,
        allow_status: tuple[int, ...] = (),
    ) -> Any:
        del payload, timeout, allow_status
        params = params or {}
        if url.endswith("/api/v1/repos/target/example"):
            return {"size": 12}
        if url.endswith("/issues"):
            assert params.get("state") == "all"
            # ListIssues in routers/api/v1/repo/issue.go: no type means both kinds.
            return {"issues": issues, "pulls": pulls}.get(params.get("type"), issues + pulls)
        if url.endswith("/pulls"):
            return pulls
        return []

    monkeypatch.setattr(forgejo, "request_json", fake_request_json)

    client = ForgejoClient("https://forge.example", "token", logging.getLogger("test"))
    metadata = client.repository_metadata("target", "example")

    assert metadata["issues"] == 2
    assert metadata["pulls"] == 3


@pytest.mark.parametrize("contents", [True, False])
def test_repository_metadata_reports_whether_a_wiki_arrived(monkeypatch, contents: bool) -> None:
    """has_wiki is the wiki unit being on; has_wiki_contents is a wiki actually being there."""

    def fake_request_json(
        _method: str,
        url: str,
        _headers: dict[str, str],
        payload: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        timeout: int = 30,
        allow_status: tuple[int, ...] = (),
    ) -> Any:
        del payload, params, timeout, allow_status
        if url.endswith("/api/v1/repos/target/example"):
            return {"size": 12, "has_wiki": True, "has_wiki_contents": contents}
        return []

    monkeypatch.setattr(forgejo, "request_json", fake_request_json)

    client = ForgejoClient("https://forge.example", "token", logging.getLogger("test"))
    metadata = client.repository_metadata("target", "example")

    assert metadata["wiki"] is contents


METADATA_SWITCHES = ("wiki", "issues", "pull_requests", "labels", "milestones", "releases")


def _capture_migrate_request(monkeypatch) -> dict[str, Any]:
    captured: dict[str, Any] = {}

    def fake_request_json(
        method: str,
        url: str,
        _headers: dict[str, str],
        payload: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        timeout: int = 30,
        allow_status: tuple[int, ...] = (),
    ) -> Any:
        del params, allow_status
        captured.update(method=method, url=url, payload=payload, timeout=timeout)
        return {"id": 7}

    monkeypatch.setattr(forgejo, "request_json", fake_request_json)
    return captured


def _migrate(client: ForgejoClient, **kwargs: Any) -> forgejo.MigrationResult:
    return client.migrate_repository(
        clone_url="https://github.com/source/example.git",
        repo_name="example",
        owner="target",
        private=True,
        auth_token="ghp_token",
        description="Example",
        **kwargs,
    )


def test_migrate_repository_asks_forgejo_for_github_metadata(monkeypatch) -> None:
    """Without service=github and the item switches, Forgejo copies git data only."""
    captured = _capture_migrate_request(monkeypatch)
    client = ForgejoClient("https://forge.example", "token", logging.getLogger("test"))

    assert _migrate(client).repo_id == 7

    payload = captured["payload"]
    assert captured["url"] == "https://forge.example/api/v1/repos/migrate"
    assert payload["service"] == "github"
    assert payload["auth_token"] == "ghp_token"
    assert payload["mirror"] is False
    for switch in METADATA_SWITCHES:
        assert payload[switch] is True, switch


def test_migrate_repository_names_the_owner_the_way_forgejo_reads_it(monkeypatch) -> None:
    """MigrateRepoOptions takes repo_owner by name; uid is deprecated, repo_owner_id unknown."""
    captured = _capture_migrate_request(monkeypatch)
    client = ForgejoClient("https://forge.example", "token", logging.getLogger("test"))

    _migrate(client)

    payload = captured["payload"]
    assert payload["repo_owner"] == "target"
    for unused in ("uid", "repo_owner_id", "auth_username"):
        assert unused not in payload, unused


def test_migrate_repository_can_copy_git_data_only(monkeypatch) -> None:
    """metadata=False turns every item switch off but still names the service."""
    captured = _capture_migrate_request(monkeypatch)
    client = ForgejoClient("https://forge.example", "token", logging.getLogger("test"))

    _migrate(client, metadata=False)

    payload = captured["payload"]
    assert payload["service"] == "github"
    for switch in METADATA_SWITCHES:
        assert payload[switch] is False, switch


def test_migrate_repository_waits_as_long_as_it_is_told(monkeypatch) -> None:
    """Forgejo answers the migrate request only once the import is done."""
    captured = _capture_migrate_request(monkeypatch)
    client = ForgejoClient("https://forge.example", "token", logging.getLogger("test"))

    _migrate(client, timeout=900)

    assert captured["timeout"] == 900


def _fake_get(monkeypatch, response: Any) -> None:
    def fake_request_json(
        _method: str,
        _url: str,
        _headers: dict[str, str],
        payload: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        timeout: int = 30,
        allow_status: tuple[int, ...] = (),
    ) -> Any:
        del payload, params, timeout, allow_status
        return response

    monkeypatch.setattr(forgejo, "request_json", fake_request_json)


@pytest.mark.parametrize(
    ("response", "expected"),
    [
        ({"_status": 404, "_body": ""}, "in_progress"),
        ({"name": "example", "empty": True}, "in_progress"),
        ({"name": "example", "empty": False}, "unconfirmed"),
    ],
)
def test_repository_status_never_reports_an_existing_repo_as_completed(
    monkeypatch, response: Any, expected: str
) -> None:
    """The repo exists from the moment the import starts, so a 200 proves nothing."""
    _fake_get(monkeypatch, response)
    client = ForgejoClient("https://forge.example", "token", logging.getLogger("test"))

    assert client.repository_status("target", "example") == expected


def _fake_migrate(monkeypatch, outcome: Any) -> dict[str, Any]:
    captured: dict[str, Any] = {}

    def fake_request_json(
        method: str,
        _url: str,
        _headers: dict[str, str],
        payload: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        timeout: int = 30,
        allow_status: tuple[int, ...] = (),
    ) -> Any:
        del payload, params, allow_status
        captured.update(method=method, timeout=timeout)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome

    monkeypatch.setattr(forgejo, "request_json", fake_request_json)
    return captured


def _start_migration(client: ForgejoClient, timeout: int = 30) -> forgejo.MigrationResult:
    return client.migrate_repository(
        clone_url="https://github.com/source/example.git",
        repo_name="example",
        owner="target",
        private=False,
        auth_token="ghp_token",
        description="Example",
        timeout=timeout,
    )


def test_migrate_repository_reports_a_finished_import(monkeypatch) -> None:
    """Forgejo answers 201 with the repository only once the import is done."""
    captured = _fake_migrate(monkeypatch, {"id": 7, "empty": False})
    client = ForgejoClient("https://forge.example", "token", logging.getLogger("test"))

    result = _start_migration(client, timeout=900)

    assert result.status == "completed"
    assert result.repo_id == 7
    assert captured["timeout"] == 900


@pytest.mark.parametrize(
    "outcome",
    [
        NoAnswerError("no answer from https://forge.example/api/v1/repos/migrate: timed out"),
        NoAnswerError("HTTP 504 from https://forge.example/api/v1/repos/migrate", 504, ""),
    ],
)
def test_migrate_repository_keeps_an_unanswered_import_open(monkeypatch, outcome: Any) -> None:
    """No answer means Forgejo may still be importing, not that the import failed."""
    _fake_migrate(monkeypatch, outcome)
    client = ForgejoClient("https://forge.example", "token", logging.getLogger("test"))

    result = _start_migration(client)

    assert result.status == "initiated"
    assert result.repo_id is None
    assert result.message == f"{outcome}; Forgejo may still be importing the repository"


@pytest.mark.parametrize("status", [409, 422, 500])
def test_migrate_repository_reports_rejected_imports_as_failed(monkeypatch, status: int) -> None:
    """Forgejo's own errors are final, so they don't wait on monitor."""
    _fake_migrate(monkeypatch, APIError(f"HTTP {status} from migrate", status, "{}"))
    client = ForgejoClient("https://forge.example", "token", logging.getLogger("test"))

    result = _start_migration(client)

    assert result.status == "failed"
    assert str(status) in result.message
    assert result.http_status == status


@pytest.mark.parametrize(
    ("outcome", "expected"),
    [
        (NoAnswerError("no answer from https://forge.example: timed out"), "in_progress"),
        (APIError("HTTP 500 from https://forge.example", 500, "{}"), "error"),
    ],
)
def test_repository_status_keeps_polling_after_a_timeout(
    monkeypatch, outcome: APIError, expected: str
) -> None:
    """A poll that times out leaves the repository pending; a real error settles it."""
    _fake_migrate(monkeypatch, outcome)
    client = ForgejoClient("https://forge.example", "token", logging.getLogger("test"))

    assert client.repository_status("target", "example") == expected
