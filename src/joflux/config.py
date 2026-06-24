"""Configuration loading for joflux."""

from __future__ import annotations

import json
import os
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class ConfigError(ValueError):
    """Raised when the user configuration is missing or invalid."""


@dataclass(frozen=True)
class AppConfig:
    """Runtime configuration for a migration."""

    github_org: str
    github_token: str
    forgejo_url: str
    forgejo_org: str
    forgejo_token: str
    github_api_url: str = "https://api.github.com"
    poll_interval: int = 30
    max_wait_time: int = 3600
    log_level: str = "INFO"
    output_dir: str = "migration_output"

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "AppConfig":
        """Build a config from a mapping, accepting old Codeberg key aliases."""
        flattened = _flatten_sections(data)

        def required(*keys: str) -> str:
            value = _first_present(flattened, keys)
            if value is None or str(value).strip() == "":
                raise ConfigError(f"missing required config key: {keys[0]}")
            return str(value)

        def optional(default: Any, *keys: str) -> Any:
            value = _first_present(flattened, keys)
            return default if value is None else value

        def secret(*keys: str, env: tuple[str, ...]) -> str:
            value = _first_present(flattened, keys)
            if value is not None and str(value).strip() != "":
                return str(value)

            env_value = _first_env(env)
            if env_value is not None:
                return env_value

            env_names = ", ".join(env)
            raise ConfigError(f"missing required config key: {keys[0]} or env var: {env_names}")

        def positive_int(default: int, *keys: str) -> int:
            value = optional(default, *keys)
            try:
                parsed = int(value)
            except (TypeError, ValueError) as exc:
                raise ConfigError(f"config key must be a positive integer: {keys[0]}") from exc
            if parsed <= 0:
                raise ConfigError(f"config key must be a positive integer: {keys[0]}")
            return parsed

        def log_level() -> str:
            level = str(optional("INFO", "log_level", "migration.log_level")).upper()
            valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
            if level not in valid_levels:
                raise ConfigError(
                    "config key log_level must be one of: " + ", ".join(sorted(valid_levels))
                )
            return level

        return cls(
            github_org=required("github_org", "source_org", "github.org"),
            github_token=secret(
                "github_token",
                "source_token",
                "github.token",
                env=("JOFLUX_GITHUB_TOKEN",),
            ),
            forgejo_url=required("forgejo_url", "codeberg_url", "target_url", "forgejo.url"),
            forgejo_org=required("forgejo_org", "codeberg_org", "target_org", "forgejo.org"),
            forgejo_token=secret(
                "forgejo_token",
                "codeberg_token",
                "target_token",
                "forgejo.token",
                env=("JOFLUX_FORGEJO_TOKEN", "JOFLUX_CODEBERG_TOKEN"),
            ),
            github_api_url=str(
                optional("https://api.github.com", "github_api_url", "github.api_url")
            ),
            poll_interval=positive_int(30, "poll_interval", "migration.poll_interval"),
            max_wait_time=positive_int(3600, "max_wait_time", "migration.max_wait_time"),
            log_level=log_level(),
            output_dir=str(optional("migration_output", "output_dir", "migration.output_dir")),
        )


def load_config(path: str | os.PathLike[str]) -> AppConfig:
    """Load a TOML, JSON, or optional YAML configuration file."""
    config_path = Path(path)
    if not config_path.exists():
        raise ConfigError(f"config file not found: {config_path}")

    try:
        if config_path.suffix.lower() == ".json":
            with config_path.open("r", encoding="utf-8") as file_handle:
                data = json.load(file_handle)
        elif config_path.suffix.lower() in {".yaml", ".yml"}:
            data = _load_yaml(config_path)
        else:
            with config_path.open("rb") as file_handle:
                data = tomllib.load(file_handle)
    except OSError as exc:
        raise ConfigError(f"failed to read config: {exc}") from exc
    except (json.JSONDecodeError, tomllib.TOMLDecodeError) as exc:
        raise ConfigError(f"failed to parse config: {exc}") from exc

    if not isinstance(data, dict):
        raise ConfigError("config root must be a mapping")

    return AppConfig.from_mapping(data)


def _load_yaml(config_path: Path) -> dict[str, Any]:
    try:
        import yaml  # pylint: disable=import-outside-toplevel  # type: ignore[import-untyped]
    except ImportError as exc:
        raise ConfigError(
            "YAML config requires the optional PyYAML extra; use TOML or install joflux[yaml]"
        ) from exc

    try:
        with config_path.open("r", encoding="utf-8") as file_handle:
            data = yaml.safe_load(file_handle)
    except yaml.YAMLError as exc:
        raise ConfigError(f"failed to parse YAML config: {exc}") from exc

    return data or {}


def _flatten_sections(data: dict[str, Any]) -> dict[str, Any]:
    flattened: dict[str, Any] = dict(data)
    for section_name, section_data in data.items():
        if isinstance(section_data, dict):
            for key, value in section_data.items():
                flattened[f"{section_name}.{key}"] = value
    return flattened


def _first_present(data: dict[str, Any], keys: tuple[str, ...]) -> Any | None:
    for key in keys:
        if key in data:
            return data[key]
    return None


def _first_env(keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = os.environ.get(key)
        if value is not None and value.strip() != "":
            return value
    return None
