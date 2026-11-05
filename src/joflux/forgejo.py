"""Forgejo and Codeberg API client."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from .http import APIError, request_json

# A gateway answering 504 or 524 (Cloudflare) has given up waiting on Forgejo,
# which keeps importing behind it.
GATEWAY_TIMEOUT_STATUSES = (504, 524)


@dataclass(frozen=True)
class MigrationResult:
    """What a migrate request established about one repository.

    status is "completed" when Forgejo answered with the imported repository,
    "initiated" when the request went out but no answer came back, so the import may
    still be running, and "failed" when Forgejo rejected or failed it.
    """

    status: str
    repo_id: int | None = None
    message: str = ""


class ForgejoClient:
    """Small Forgejo-compatible REST API client."""

    def __init__(self, url: str, token: str, logger: logging.Logger):
        self.url = url.rstrip("/")
        self.logger = logger
        self.headers = {
            "Authorization": f"token {token}",
            "Accept": "application/json",
            "User-Agent": "joflux",
        }

    def organization_id(self, org_name: str) -> int | None:
        """Resolve a target organization ID."""
        try:
            data = request_json("GET", f"{self.url}/api/v1/orgs/{org_name}", self.headers)
        except APIError as exc:
            self.logger.error("Failed to resolve target organization %s: %s", org_name, exc)
            return None
        if isinstance(data, dict) and isinstance(data.get("id"), int):
            return data["id"]
        self.logger.error("Target organization response did not include an integer id")
        return None

    def migrate_repository(
        self,
        clone_url: str,
        repo_name: str,
        org_id: int,
        private: bool,
        auth_token: str,
        auth_username: str,
        description: str,
        metadata: bool = True,
        timeout: int = 30,
    ) -> MigrationResult:
        """Migrate a GitHub repository into the target Forgejo instance.

        Forgejo only imports the wiki, issues, pull requests, labels, milestones and
        releases when the request names the source service and switches each of them
        on; otherwise it copies the git data alone. POST /repos/migrate is synchronous:
        Forgejo runs the whole import before it answers, and its 201 response is the
        only signal the API gives that an import has finished. ``timeout`` therefore
        has to cover the import itself.
        """
        payload = {
            "clone_addr": clone_url,
            "repo_name": repo_name,
            "uid": org_id,
            "repo_owner_id": org_id,
            "private": private,
            "service": "github",
            "auth_token": auth_token,
            "auth_username": auth_username,
            "mirror": False,
            "description": description,
            "wiki": metadata,
            "issues": metadata,
            "pull_requests": metadata,
            "labels": metadata,
            "milestones": metadata,
            "releases": metadata,
        }

        try:
            response = request_json(
                "POST",
                f"{self.url}/api/v1/repos/migrate",
                self.headers,
                payload=payload,
                timeout=timeout,
                allow_status=(201, 202),
            )
        except (TimeoutError, ConnectionError) as exc:
            self.logger.warning("No answer from Forgejo for %s: %s", repo_name, exc)
            return MigrationResult(
                "initiated",
                message=f"Forgejo didn't answer ({exc}); the import may still be running",
            )
        except APIError as exc:
            if exc.status in GATEWAY_TIMEOUT_STATUSES:
                self.logger.warning("Gateway gave up waiting on Forgejo for %s: %s", repo_name, exc)
                return MigrationResult(
                    "initiated", message=f"{exc}; Forgejo may still be importing the repository"
                )
            self.logger.error("Migration failed for %s: %s", repo_name, exc.body or exc)
            return MigrationResult(
                "failed", message=f"Forgejo rejected or failed the import: {exc}"
            )

        repo_id = response.get("id") if isinstance(response, dict) else None
        return MigrationResult(
            "completed",
            repo_id=repo_id if isinstance(repo_id, int) else None,
            message="Forgejo finished the import",
        )

    def repository_status(self, org_name: str, repo_name: str) -> str:
        """Return in_progress, unconfirmed or error for a repository being imported.

        Forgejo's repository JSON has no migration status. The repository exists from
        the moment the import starts, and a failed import is left behind rather than
        deleted, so a 200 never means the import finished. The ``empty`` flag only
        turns false once the git data is in, which is before issues, pull requests and
        releases are imported. So this reports in_progress until the git data shows
        up and unconfirmed after that, and never completed.
        """
        try:
            data = request_json(
                "GET",
                f"{self.url}/api/v1/repos/{org_name}/{repo_name}",
                self.headers,
                allow_status=(404,),
            )
        except APIError:
            return "error"

        if not isinstance(data, dict):
            return "error"
        if data.get("_status") == 404:
            return "in_progress"
        if data.get("empty") is False:
            return "unconfirmed"
        return "in_progress"

    def repository_metadata(self, org_name: str, repo_name: str) -> dict[str, Any]:
        """Return a compact verification summary for a repository."""
        try:
            repo_data = request_json(
                "GET", f"{self.url}/api/v1/repos/{org_name}/{repo_name}", self.headers
            )
        except APIError as exc:
            return {"name": repo_name, "status": "error", "error": str(exc)}

        counts: dict[str, int] = {}
        for label, path in {
            "issues": f"/api/v1/repos/{org_name}/{repo_name}/issues",
            "pulls": f"/api/v1/repos/{org_name}/{repo_name}/pulls",
            "labels": f"/api/v1/repos/{org_name}/{repo_name}/labels",
            "releases": f"/api/v1/repos/{org_name}/{repo_name}/releases",
        }.items():
            try:
                counts[label] = self._count_items(path)
            except APIError as exc:
                return {
                    "name": repo_name,
                    "status": "error",
                    "error": f"failed to count {label}: {exc}",
                }

        return {
            "name": repo_name,
            "size": repo_data.get("size", 0) if isinstance(repo_data, dict) else 0,
            "issues": counts["issues"],
            "pulls": counts["pulls"],
            "labels": counts["labels"],
            "releases": counts["releases"],
            "has_wiki": repo_data.get("has_wiki", False) if isinstance(repo_data, dict) else False,
            "status": "verified",
        }

    def _count_items(self, path: str) -> int:
        total = 0
        page = 1
        per_page = 50
        while True:
            data = request_json(
                "GET",
                f"{self.url}{path}",
                self.headers,
                params={"page": page, "limit": per_page, "state": "all"},
            )
            if not isinstance(data, list) or not data:
                return total
            total += len(data)
            if len(data) < per_page:
                return total
            page += 1
