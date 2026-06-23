"""CLI tests."""

import pytest

from joflux.cli import main


def test_help_exits_successfully(capsys) -> None:
    """The top-level help text exits cleanly."""
    with pytest.raises(SystemExit) as exc_info:
        main(["--help"])

    assert exc_info.value.code == 0
    assert "Move GitHub organization repositories" in capsys.readouterr().out
