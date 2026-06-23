"""GitHub API client."""

from __future__ import annotations

import logging
from typing import Any

from .http import request_json


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
