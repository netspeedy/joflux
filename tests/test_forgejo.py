"""Forgejo client tests."""

import logging
from typing import Any

from joflux import forgejo
from joflux.forgejo import ForgejoClient
from joflux.http import APIError


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
