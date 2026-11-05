---
title: Archive
description: archive asks you to confirm, then archives every GitHub original in the inventory. It never deletes them.
---

`archive` archives the GitHub originals once the move is done. It's deliberately separate from the
other stages, asks before it changes anything, and archives the repositories rather than deleting
them.

```bash
joflux --config joflux.toml archive
```

## It asks first

Before touching anything it prompts:

```text
Archive <count> repositories in github.com/<org>? Type yes:
```

Anything other than `yes` (in any case) cancels it with `Archive cancelled`, and it exits 0 having
changed nothing. `--yes` skips the prompt, for scripted runs:

```bash
joflux --config joflux.toml archive --yes
```

:::caution[It archives the whole inventory]
`archive` works from `repos-inventory.json`, not from the verification report. It archives every
repository in the inventory, including any that `verify` found missing, so read
`verification-report.json` before you confirm.
:::

## What it does

For each repository it asks GitHub to mark it archived, waiting a second between requests. Each one
is logged in the shape `[<n>/<total>] Archiving <repo>`, and the summary at the end has the shape
`Archive complete: <archived> archived, <failed> failed`.

The GitHub token needs to be able to change repository settings for this; the earlier stages only
need it to read and clone.

## What it writes

Each repository appends an entry to `archive-log.json`, recorded as `success` with
`Repository archived`, or as `failed` with the error GitHub returned. `archive` exits 1 if any
failed. [Output files](/joflux/reference/output-files/) has the fields.

Keep `migration_output/` once you're done. Together the five files are the record of what moved,
what arrived and what was archived.
