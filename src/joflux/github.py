"""GitHub API client."""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlsplit

from .http import request_json


def web_location(api_url: str, org: str) -> str:
    """Return where an organization lives on the web, such as github.com/acme, for messages.

    GitHub's API is at api.github.com, GitHub Enterprise Cloud with data residency at
    api.<subdomain>.ghe.com, and GitHub Enterprise Server at <host>/api/v3. Dropping the api.
    host prefix and the /api/v3 path gives the address people know the organization by.
    """
    parts = urlsplit(api_url.strip().rstrip("/"))
    host = parts.netloc or parts.path
    path = parts.path if parts.netloc else ""
    if host.startswith("api."):
        host = host[len("api.") :]
    if path.endswith("/api/v3"):
        path = path[: -len("/api/v3")]
    return f"{host}{path}/{org}"


class GitHubClient:
    """Small GitHub REST API client."""

    def __init__(self, org: str, token: str, api_url: str, logger: logging.Logger):
        self.org = org
        self.api_url = api_url.rstrip("/")
        self.logger = logger
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "joflux",
        }

    def list_repositories(self) -> list[dict[str, Any]]:
        """Return every repository in the configured GitHub organization."""
        repositories: list[dict[str, Any]] = []
        page = 1
        per_page = 100
        self.logger.info("Fetching repositories from GitHub org: %s", self.org)

        while True:
            batch = request_json(
                "GET",
                f"{self.api_url}/orgs/{self.org}/repos",
                self.headers,
                params={"per_page": per_page, "page": page, "type": "all"},
            )
            if not isinstance(batch, list) or not batch:
                break
            repositories.extend(batch)
            page += 1

        self.logger.info("Found %d repositories", len(repositories))
        return repositories

    def archive_repository(self, repo_name: str) -> bool:
        """Archive a GitHub repository."""
        request_json(
            "PATCH",
            f"{self.api_url}/repos/{self.org}/{repo_name}",
            self.headers,
            payload={"archived": True},
        )
        return True
