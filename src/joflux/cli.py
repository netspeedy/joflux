"""Command line interface for joflux."""

from __future__ import annotations

import argparse
import logging
import sys
import time
from collections.abc import Callable
from typing import Any

from . import package_version
from .config import AppConfig, ConfigError, load_config
from .forgejo import ForgejoClient
from .github import GitHubClient
from .http import APIError
from .logging import configure_logging
from .state import MigrationState

LOGGER = logging.getLogger("joflux")


def build_parser() -> argparse.ArgumentParser:
    """Create the CLI parser."""
    parser = argparse.ArgumentParser(
        prog="joflux",
        description="Move GitHub organization repositories to a Forgejo-compatible instance.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {package_version()}")
    parser.add_argument(
        "--config",
        default="joflux.toml",
        help="configuration file path (default: joflux.toml)",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="override the configured log level",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    export_parser = subparsers.add_parser("export", help="export repositories from GitHub")
    export_parser.add_argument(
        "--exclude-forks", action="store_true", help="skip forked repositories in the inventory"
    )
    export_parser.add_argument(
        "--exclude-archived", action="store_true", help="skip already archived GitHub repositories"
    )
    export_parser.set_defaults(handler=cmd_export)

    migrate_parser = subparsers.add_parser("migrate", help="start repository migrations")
    migrate_parser.set_defaults(handler=cmd_migrate)

    monitor_parser = subparsers.add_parser("monitor", help="monitor started migrations")
    monitor_parser.add_argument("--interval", type=int, help="poll interval in seconds")
    monitor_parser.set_defaults(handler=cmd_monitor)

    verify_parser = subparsers.add_parser("verify", help="verify migrated repositories")
    verify_parser.set_defaults(handler=cmd_verify)

    archive_parser = subparsers.add_parser("archive", help="archive original GitHub repositories")
    archive_parser.add_argument(
        "--yes", action="store_true", help="archive without an interactive prompt"
    )
    archive_parser.set_defaults(handler=cmd_archive)

    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        config = load_config(args.config)
        log_level = args.log_level or config.log_level
        configure_logging(log_level)
        handler: Callable[[argparse.Namespace, AppConfig], int] = args.handler
        return handler(args, config)
    except ConfigError as exc:
        print(f"config error: {exc}", file=sys.stderr)
        return 2
    except FileNotFoundError as exc:
        LOGGER.error("%s", exc)
        return 2
    except (APIError, OSError, ValueError) as exc:
        LOGGER.error("%s", exc)
        return 1
    except KeyboardInterrupt:
        LOGGER.warning("Interrupted by user")
        return 130


def cmd_export(args: argparse.Namespace, config: AppConfig) -> int:
    """Export repositories from GitHub."""
    state = MigrationState(config.output_dir)
    github = GitHubClient(config.github_org, config.github_token, config.github_api_url, LOGGER)
    repositories = github.list_repositories()

    if args.exclude_forks:
        repositories = [repo for repo in repositories if not repo.get("fork")]
    if args.exclude_archived:
        repositories = [repo for repo in repositories if not repo.get("archived")]

    state.save_inventory(repositories)

    private_count = sum(1 for repo in repositories if repo.get("private"))
    fork_count = sum(1 for repo in repositories if repo.get("fork"))
    archived_count = sum(1 for repo in repositories if repo.get("archived"))
    LOGGER.info("Inventory saved: %s", state.inventory_file)
    LOGGER.info(
        "Exported %d repositories (%d private, %d forks, %d archived)",
        len(repositories),
        private_count,
        fork_count,
        archived_count,
    )
    return 0


def cmd_migrate(_args: argparse.Namespace, config: AppConfig) -> int:
    """Start migrations into the target Forgejo instance."""
    state = MigrationState(config.output_dir)
    repositories = state.load_inventory()
    forgejo = ForgejoClient(config.forgejo_url, config.forgejo_token, LOGGER)

    org_id = forgejo.organization_id(config.forgejo_org)
    if org_id is None:
        return 1

    LOGGER.info("Target organization id: %s", org_id)
    successful = 0
    failed = 0

    for index, repo in enumerate(repositories, 1):
        repo_name = str(repo["name"])
        clone_url = str(
            repo.get("clone_url") or f"https://github.com/{config.github_org}/{repo_name}.git"
        )
        description = str(repo.get("description") or "Migrated from GitHub by joflux")

        LOGGER.info("[%d/%d] Migrating %s", index, len(repositories), repo_name)
        migration_id = forgejo.migrate_repository(
            clone_url=clone_url,
            repo_name=repo_name,
            org_id=org_id,
            private=bool(repo.get("private")),
            auth_token=config.github_token,
            auth_username=config.github_org,
            description=description,
        )

        if migration_id:
            state.log_migration(repo_name, "initiated", "Migration started", migration_id)
            successful += 1
        else:
            state.log_migration(repo_name, "failed", "Failed to start migration")
            failed += 1
        time.sleep(1)

    LOGGER.info("Migration requests complete: %d started, %d failed", successful, failed)
    return 0 if failed == 0 else 1


def cmd_monitor(args: argparse.Namespace, config: AppConfig) -> int:
    """Monitor repositories whose migration has been started."""
    state = MigrationState(config.output_dir)
    migration_events = state.load_json(state.migration_log)
    status_events = state.load_json(state.status_file) if state.status_file.exists() else []
    pending = _pending_migration_repos(migration_events, status_events)
    if not pending:
        LOGGER.warning("No initiated migrations found")
        return 0

    interval = args.interval or config.poll_interval
    forgejo = ForgejoClient(config.forgejo_url, config.forgejo_token, LOGGER)
    started_at = time.time()
    completed = 0
    failed = 0

    while pending:
        elapsed = int(time.time() - started_at)
        LOGGER.info("Checking %d pending migrations", len(pending))

        for repo_name in list(pending):
            status = forgejo.repository_status(config.forgejo_org, repo_name)
            if status == "completed":
                LOGGER.info("%s completed", repo_name)
                state.log_status(repo_name, "completed")
                pending.remove(repo_name)
                completed += 1
            elif status == "error":
                LOGGER.error("%s returned an error", repo_name)
                state.log_status(repo_name, "error")
                pending.remove(repo_name)
                failed += 1
            else:
                LOGGER.info("%s still in progress", repo_name)

        if pending and elapsed >= config.max_wait_time:
            LOGGER.warning("Max wait time reached with %d repositories still pending", len(pending))
            break
        if pending:
            time.sleep(interval)

    LOGGER.info(
        "Monitor complete: %d completed, %d failed, %d pending", completed, failed, len(pending)
    )
    return 0 if failed == 0 and not pending else 1


def cmd_verify(_args: argparse.Namespace, config: AppConfig) -> int:
    """Verify migrated repository metadata counts."""
    state = MigrationState(config.output_dir)
    repositories = state.load_inventory()
    forgejo = ForgejoClient(config.forgejo_url, config.forgejo_token, LOGGER)

    verified = 0
    missing: list[str] = []
    for index, repo in enumerate(repositories, 1):
        repo_name = str(repo["name"])
        LOGGER.info("[%d/%d] Verifying %s", index, len(repositories), repo_name)
        metadata = forgejo.repository_metadata(config.forgejo_org, repo_name)
        if metadata.get("status") == "verified":
            details = _verification_details(metadata)
            state.log_verification(repo_name, "verified", details)
            verified += 1
        else:
            state.log_verification(repo_name, "missing", str(metadata.get("error", "not found")))
            missing.append(repo_name)

    LOGGER.info("Verification complete: %d verified, %d missing", verified, len(missing))
    if missing:
        LOGGER.error("Missing repositories: %s", ", ".join(missing))
        return 1
    return 0


def cmd_archive(args: argparse.Namespace, config: AppConfig) -> int:
    """Archive original GitHub repositories after verification."""
    state = MigrationState(config.output_dir)
    repositories = state.load_inventory()

    if not args.yes:
        count = len(repositories)
        prompt = f"Archive {count} repositories in github.com/{config.github_org}? Type yes: "
        if input(prompt).strip().lower() != "yes":
            LOGGER.warning("Archive cancelled")
            return 0

    github = GitHubClient(config.github_org, config.github_token, config.github_api_url, LOGGER)
    successful = 0
    failed = 0
    for index, repo in enumerate(repositories, 1):
        repo_name = str(repo["name"])
        LOGGER.info("[%d/%d] Archiving %s", index, len(repositories), repo_name)
        try:
            github.archive_repository(repo_name)
        except APIError as exc:
            state.log_archive(repo_name, "failed", str(exc))
            failed += 1
        else:
            state.log_archive(repo_name, "success", "Repository archived")
            successful += 1
        time.sleep(1)

    LOGGER.info("Archive complete: %d archived, %d failed", successful, failed)
    return 0 if failed == 0 else 1


def _verification_details(metadata: dict[str, Any]) -> str:
    return (
        f"size:{metadata.get('size', 0)} "
        f"issues:{metadata.get('issues', 0)} "
        f"pulls:{metadata.get('pulls', 0)} "
        f"labels:{metadata.get('labels', 0)} "
        f"releases:{metadata.get('releases', 0)}"
    )


def _pending_migration_repos(
    migration_events: list[dict[str, Any]], status_events: list[dict[str, Any]]
) -> list[str]:
    latest_migrations: dict[str, tuple[str, str]] = {}
    for event in migration_events:
        repo_name = event.get("repo")
        status = event.get("status")
        if not isinstance(repo_name, str) or not isinstance(status, str):
            continue
        latest_migrations[repo_name] = (status, _event_timestamp(event))

    latest_statuses: dict[str, tuple[str, str]] = {}
    for event in status_events:
        repo_name = event.get("repo")
        status = event.get("status")
        if not isinstance(repo_name, str) or not isinstance(status, str):
            continue
        latest_statuses[repo_name] = (status, _event_timestamp(event))

    pending: list[str] = []
    for repo_name, (migration_status, migration_time) in latest_migrations.items():
        if migration_status != "initiated":
            continue

        status = latest_statuses.get(repo_name)
        if status is not None:
            status_name, status_time = status
            if status_name in {"completed", "error"} and (
                not migration_time or not status_time or status_time >= migration_time
            ):
                continue

        pending.append(repo_name)
    return pending


def _event_timestamp(event: dict[str, Any]) -> str:
    timestamp = event.get("timestamp") or event.get("checked_at")
    return timestamp if isinstance(timestamp, str) else ""
