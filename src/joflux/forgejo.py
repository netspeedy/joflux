"""Forgejo and Codeberg API client."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from .http import APIError, NoAnswerError, request_json


@dataclass(frozen=True)
class MigrationResult:
    """What a migrate request established about one repository.

    status is "completed" when Forgejo answered with the imported repository,
    "initiated" when the request went out but no answer came back, so the import may
    still be running, and "failed" when Forgejo rejected or failed it. http_status is
    the HTTP status Forgejo answered a failed request with, when it answered at all.
    """

    status: str
    repo_id: int | None = None
    message: str = ""
    http_status: int | None = None


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
        owner: str,
        private: bool,
        auth_token: str,
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

        ``owner`` is the target organization's name, which MigrateRepoOptions takes as
        repo_owner. Forgejo clones and reads GitHub with ``auth_token`` alone, so no
        username is sent.
        """
        payload = {
            "clone_addr": clone_url,
            "repo_name": repo_name,
            "repo_owner": owner,
            "private": private,
            "service": "github",
            "auth_token": auth_token,
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
            )
        except NoAnswerError as exc:
            self.logger.warning("No answer from Forgejo for %s: %s", repo_name, exc)
            return MigrationResult(
                "initiated", message=f"{exc}; Forgejo may still be importing the repository"
            )
        except APIError as exc:
            self.logger.error("Migration failed for %s: %s", repo_name, exc.body or exc)
            return MigrationResult(
                "failed",
                message=f"Forgejo rejected or failed the import: {exc}",
                http_status=exc.status,
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
        except NoAnswerError:
            # A poll that timed out says nothing about the import, and an error would settle it.
            return "in_progress"
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

        base = f"/api/v1/repos/{org_name}/{repo_name}"
        counts: dict[str, int] = {}
        for label, path, filters in (
            # Forgejo's issue list includes pull requests unless it's asked for issues alone.
            ("issues", f"{base}/issues", {"state": "all", "type": "issues"}),
            ("pulls", f"{base}/pulls", {"state": "all"}),
            ("labels", f"{base}/labels", {}),
            ("releases", f"{base}/releases", {}),
        ):
            try:
                counts[label] = self._count_items(path, filters)
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
            # has_wiki only says the wiki unit is switched on. has_wiki_contents is whether the
            # wiki's git repository exists, which after an import means Forgejo brought one across.
            "wiki": (
                bool(repo_data.get("has_wiki_contents", False))
                if isinstance(repo_data, dict)
                else False
            ),
            "status": "verified",
        }

    def _count_items(self, path: str, filters: dict[str, str]) -> int:
        total = 0
        page = 1
        per_page = 50
        while True:
            data = request_json(
                "GET",
                f"{self.url}{path}",
                self.headers,
                params={**filters, "page": page, "limit": per_page},
            )
            if not isinstance(data, list) or not data:
                return total
            total += len(data)
            if len(data) < per_page:
                return total
            page += 1
