"""Migration state files."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class MigrationState:
    """Manage migration inventory, logs, and reports."""

    def __init__(self, output_dir: str = "migration_output"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.inventory_file = self.output_dir / "repos-inventory.json"
        self.migration_log = self.output_dir / "migration-log.json"
        self.status_file = self.output_dir / "migration-status.json"
        self.verify_file = self.output_dir / "verification-report.json"
        self.archive_log = self.output_dir / "archive-log.json"

    def save_inventory(self, repositories: list[dict[str, Any]]) -> None:
        """Write the repository inventory."""
        self.save_json(self.inventory_file, repositories)

    def load_inventory(self) -> list[dict[str, Any]]:
        """Load the repository inventory."""
        if not self.inventory_file.exists():
            raise FileNotFoundError("inventory not found; run export first")
        data = self.load_json(self.inventory_file)
        if not isinstance(data, list):
            raise ValueError("inventory file must contain a JSON array")
        return data

    def log_migration(
        self, repo_name: str, status: str, message: str, migration_id: int | bool | None = None
    ) -> None:
        """Append a migration event."""
        self.append_json(
            self.migration_log,
            {
                "repo": repo_name,
                "status": status,
                "message": message,
                "migration_id": migration_id,
                "timestamp": utc_now(),
            },
        )

    def log_status(self, repo_name: str, status: str, details: str = "") -> None:
        """Append a monitor event."""
        self.append_json(
            self.status_file,
            {"repo": repo_name, "status": status, "details": details, "checked_at": utc_now()},
        )

    def log_verification(self, repo_name: str, status: str, details: str = "") -> None:
        """Append a verification event."""
        self.append_json(
            self.verify_file,
            {"repo": repo_name, "status": status, "details": details, "verified_at": utc_now()},
        )

    def log_archive(self, repo_name: str, status: str, message: str) -> None:
        """Append an archive event."""
        self.append_json(
            self.archive_log,
            {"repo": repo_name, "status": status, "message": message, "timestamp": utc_now()},
        )

    def append_json(self, path: Path, event: dict[str, Any]) -> None:
        """Append an event to a JSON list file."""
        events = self.load_json(path) if path.exists() else []
        if not isinstance(events, list):
            raise ValueError(f"{path} must contain a JSON array")
        events.append(event)
        self.save_json(path, events)

    @staticmethod
    def load_json(path: Path) -> Any:
        """Load JSON data from disk."""
        with path.open("r", encoding="utf-8") as file_handle:
            return json.load(file_handle)

    @staticmethod
    def save_json(path: Path, data: Any) -> None:
        """Write pretty JSON to disk."""
        with path.open("w", encoding="utf-8") as file_handle:
            json.dump(data, file_handle, indent=2, sort_keys=True)
            file_handle.write("\n")


def utc_now() -> str:
    """Return an ISO-8601 UTC timestamp."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
