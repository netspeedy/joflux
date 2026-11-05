"""Docs site tests."""

# argparse has no public way to list a parser's options or its subcommands.
# pylint: disable=protected-access

import argparse
import re
from pathlib import Path

from joflux import cli

REFERENCE = (
    Path(__file__).resolve().parents[1] / "website" / "src" / "content" / "docs" / "reference"
) / "cli.mdx"


def _documented_flags() -> dict[str, set[str]]:
    """Return the options in each flag list on the CLI reference page, keyed by list name."""
    text = REFERENCE.read_text(encoding="utf-8")
    tables: dict[str, set[str]] = {}
    for name, body in re.findall(r"^export const (\w+) = \[(.*?)^\];", text, re.M | re.S):
        flags: set[str] = set()
        for short, flag in re.findall(r'(?:short: "(-\w)", )?flag: "(--[a-z0-9-]+)"', body):
            flags.add(flag)
            if short:
                flags.add(short)
        tables[name] = flags
    return tables


def _parser_flags(parser: argparse.ArgumentParser) -> set[str]:
    """Return every option string a parser accepts."""
    return {option for action in parser._actions for option in action.option_strings}


def test_cli_reference_covers_every_flag() -> None:
    """The CLI reference documents exactly the options each command accepts.

    The page is written by hand so options can be explained, which means nothing regenerates it
    when one changes. The top-level options are its globalOptions list, and each command's are
    its <command>Flags list. Every command takes -h too, which globalOptions covers.
    """
    tables = _documented_flags()
    parser = cli.build_parser()
    assert tables.pop("globalOptions") == _parser_flags(parser)

    subparsers = next(
        action for action in parser._actions if isinstance(action, argparse._SubParsersAction)
    )
    for command, subparser in subparsers.choices.items():
        documented = tables.pop(f"{command}Flags", set())
        assert documented == _parser_flags(subparser) - {"-h", "--help"}, command

    assert not tables, f"the page has flag lists for commands joflux doesn't have: {sorted(tables)}"
