---
title: Export
description: export lists every repository in the GitHub organization and saves the inventory the later stages work from.
---

`export` lists the repositories in the configured GitHub organization and saves them as
`repos-inventory.json`. It only reads from GitHub, so it changes nothing on either side and is
safe to run as often as you like.

```bash
joflux --config joflux.toml export
```

```text title="Output"
02:39:52 - INFO - Fetching repositories from GitHub org: my-github-org
02:39:52 - INFO - Found 14 repositories
02:39:52 - INFO - Inventory saved: migration_output/repos-inventory.json
02:39:52 - INFO - Exported 14 repositories (3 private, 1 forks, 1 archived)
```

It asks GitHub for every repository type in the organization, a hundred to a page, so private
repositories are included as long as the token can see them. The counts on the last line are for
what was saved, after any filter.

## Filters

Two flags drop repositories from the inventory before it's saved:

| Flag | Drops |
| --- | --- |
| `--exclude-forks` | Forked repositories |
| `--exclude-archived` | Repositories already archived on GitHub |

```bash
joflux --config joflux.toml export --exclude-forks --exclude-archived
```

## What it writes

`repos-inventory.json` is a JSON array of the repositories exactly as GitHub's API returned them.
The later stages use a handful of the fields: the name, the clone URL, the description, and
whether the repository is private, a fork or archived. Each export replaces the file rather than
adding to it.

## Before you migrate

Read the inventory. It's the list `migrate`, `verify` and `archive` all work from, so anything in
it will be moved, and archived on GitHub once `verify` has recorded it as verified. If it holds
forks or archived repositories that shouldn't move, export again with the filters above.
