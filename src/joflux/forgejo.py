"""Forgejo and Codeberg API client."""

from __future__ import annotations

import logging
from typing import Any

from .http import APIError, request_json


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
    ) -> int | bool | None:
        """Start a repository migration into the target Forgejo instance."""
        payload = {
            "clone_addr": clone_url,
            "repo_name": repo_name,
            "uid": org_id,
            "repo_owner_id": org_id,
            "private": private,
            "auth_token": auth_token,
            "auth_username": auth_username,
            "mirror": False,
            "description": description,
        }

        try:
            response = request_json(
                "POST",
                f"{self.url}/api/v1/repos/migrate",
                self.headers,
                payload=payload,
                allow_status=(201, 202),
            )
        except APIError as exc:
            self.logger.error("Migration failed for %s: %s", repo_name, exc.body or exc)
            return None

        if isinstance(response, dict) and isinstance(response.get("id"), int):
            return response["id"]
        return True

    def repository_status(self, org_name: str, repo_name: str) -> str:
        """Return completed, in_progress, or error for a migrated repository."""
        try:
            data = request_json(
                "GET",
                f"{self.url}/api/v1/repos/{org_name}/{repo_name}",
                self.headers,
                allow_status=(404,),
            )
        except APIError:
            return "error"

        if isinstance(data, dict) and data.get("_status") == 404:
            return "in_progress"
        if isinstance(data, dict):
            return "completed"
        return "error"

    def repository_metadata(self, org_name: str, repo_name: str) -> dict[str, Any]:
        """Return a compact verification summary for a repository."""
        try:
            repo_data = request_json(
                "GET", f"{self.url}/api/v1/repos/{org_name}/{repo_name}", self.headers
            )
        except APIError as exc:
            return {"name": repo_name, "status": "error", "error": str(exc)}

        return {
            "name": repo_name,
            "size": repo_data.get("size", 0) if isinstance(repo_data, dict) else 0,
            "issues": self._count_items(f"/api/v1/repos/{org_name}/{repo_name}/issues"),
            "pulls": self._count_items(f"/api/v1/repos/{org_name}/{repo_name}/pulls"),
            "labels": self._count_items(f"/api/v1/repos/{org_name}/{repo_name}/labels"),
            "releases": self._count_items(f"/api/v1/repos/{org_name}/{repo_name}/releases"),
            "has_wiki": repo_data.get("has_wiki", False) if isinstance(repo_data, dict) else False,
            "status": "verified",
        }

    def _count_items(self, path: str) -> int:
        total = 0
        page = 1
        per_page = 50
        while True:
            try:
                data = request_json(
                    "GET",
                    f"{self.url}{path}",
                    self.headers,
                    params={"page": page, "limit": per_page, "state": "all"},
                )
            except APIError:
                return total
            if not isinstance(data, list) or not data:
                return total
            total += len(data)
            if len(data) < per_page:
                return total
            page += 1
