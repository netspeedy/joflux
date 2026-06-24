"""Configuration tests."""

from pathlib import Path

import pytest

from joflux.config import ConfigError, load_config


def test_loads_toml_config(tmp_path: Path) -> None:
    """A sectioned TOML config maps onto runtime settings."""
    config_path = tmp_path / "joflux.toml"
    config_path.write_text(
        """
[github]
org = "source"
token = "ghp_token"

[forgejo]
url = "https://forge.example"
org = "target"
token = "forgejo_token"

[migration]
poll_interval = 5
max_wait_time = 60
output_dir = "state"
""".strip(),
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert config.github_org == "source"
    assert config.forgejo_url == "https://forge.example"
    assert config.forgejo_org == "target"
    assert config.poll_interval == 5
    assert config.max_wait_time == 60
    assert config.output_dir == "state"


def test_accepts_legacy_codeberg_keys(tmp_path: Path) -> None:
    """Older flat Codeberg keys still work."""
    config_path = tmp_path / "legacy.toml"
    config_path.write_text(
        """
github_org = "source"
github_token = "ghp_token"
codeberg_url = "https://codeberg.org"
codeberg_org = "target"
codeberg_token = "codeberg_token"
""".strip(),
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert config.forgejo_url == "https://codeberg.org"
    assert config.forgejo_org == "target"
    assert config.forgejo_token == "codeberg_token"


def test_token_fields_can_come_from_environment(tmp_path: Path, monkeypatch) -> None:
    """Sensitive tokens can stay out of the config file."""
    monkeypatch.setenv("JOFLUX_GITHUB_TOKEN", "github_from_env")
    monkeypatch.setenv("JOFLUX_FORGEJO_TOKEN", "forgejo_from_env")
    config_path = tmp_path / "env.toml"
    config_path.write_text(
        """
[github]
org = "source"

[forgejo]
url = "https://forge.example"
org = "target"
""".strip(),
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert config.github_token == "github_from_env"
    assert config.forgejo_token == "forgejo_from_env"


def test_codeberg_token_env_alias_is_supported(tmp_path: Path, monkeypatch) -> None:
    """Codeberg-oriented users can use a Codeberg-named env var."""
    monkeypatch.setenv("JOFLUX_GITHUB_TOKEN", "github_from_env")
    monkeypatch.setenv("JOFLUX_CODEBERG_TOKEN", "codeberg_from_env")
    config_path = tmp_path / "codeberg-env.toml"
    config_path.write_text(
        """
github_org = "source"
codeberg_url = "https://codeberg.org"
codeberg_org = "target"
""".strip(),
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert config.github_token == "github_from_env"
    assert config.forgejo_token == "codeberg_from_env"


def test_missing_required_key_raises(tmp_path: Path) -> None:
    """Invalid configs point at the missing key."""
    config_path = tmp_path / "bad.toml"
    config_path.write_text('github_org = "source"\n', encoding="utf-8")

    with pytest.raises(ConfigError, match="github_token"):
        load_config(config_path)


def test_poll_interval_must_be_positive(tmp_path: Path) -> None:
    """Runtime polling settings reject values that would break monitor loops."""
    config_path = tmp_path / "bad-poll.toml"
    config_path.write_text(
        """
[github]
org = "source"
token = "ghp_token"

[forgejo]
url = "https://forge.example"
org = "target"
token = "forgejo_token"

[migration]
poll_interval = 0
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="poll_interval"):
        load_config(config_path)


def test_log_level_must_be_known(tmp_path: Path) -> None:
    """Bad log levels fail during config loading."""
    config_path = tmp_path / "bad-log-level.toml"
    config_path.write_text(
        """
[github]
org = "source"
token = "ghp_token"

[forgejo]
url = "https://forge.example"
org = "target"
token = "forgejo_token"

[migration]
log_level = "VERBOSE"
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="log_level"):
        load_config(config_path)
