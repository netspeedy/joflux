---
title: Archive
description: archive asks you to confirm, then archives the GitHub originals that verify recorded as verified. It never deletes them.
---

`archive` archives the GitHub originals once the move is done, but only the ones `verify` recorded
as verified. It's deliberately separate from the other stages, asks before it changes anything, and
archives the repositories rather than deleting them.

```bash
joflux --config joflux.toml archive
```

## It asks first

Before touching anything it prompts with the number it's about to archive:

```text
Archive <count> repositories in github.com/<org>? Type yes:
```

With `api_url` under `[github]` set for GitHub Enterprise Server, the prompt names your server
instead, taken from that address: `https://ghe.example.com/api/v3` gives `ghe.example.com/<org>`.

Anything other than `yes` (in any case) cancels it with `Archive cancelled`, and it exits 0 having
changed nothing. `--yes` skips the prompt, for scripted runs:

```bash
joflux --config joflux.toml archive --yes
```

## Only what verify confirmed

`archive` reads `verification-report.json` and archives a repository from the inventory only when
its latest entry there is `verified`. One that `verify` recorded as `missing`, or never checked, is
left as it is on GitHub. `archive` logs
`Not archiving <n> repositories that verify hasn't recorded as verified:` with their names, counts
them in the summary, and exits 1, so a script notices. Once they've arrived, run `verify` and then
`archive` again. If none are verified there's nothing to confirm, so it doesn't prompt.

Without a verification report it doesn't start: it stops with
`verification report not found; run verify first` and exit code 2. There's no flag to archive
anyway.

:::caution[Verified means it arrived, not that it's complete]
A `verified` entry says the repository was on the target with the counts in its details. Read
`verification-report.json` and compare those counts with GitHub before you confirm.
:::

## What it does

For each repository it asks GitHub to mark it archived, waiting a second between requests. Each one
is logged in the shape `[<n>/<total>] Archiving <repo>`, and the summary at the end has the shape
`Archive complete: <archived> archived, <failed> failed, <not verified> not verified`.

The GitHub token needs to be able to change repository settings for this; the earlier stages only
need it to read and clone.

## What it writes

Each repository appends an entry to `archive-log.json`, recorded as `success` with
`Repository archived`, or as `failed` with the error GitHub returned. A repository it doesn't try to
archive gets no entry. `archive` exits 1 if any failed, or if any were left because they weren't
verified. [Output files](/joflux/reference/output-files/) has the fields.

A request that times out or loses its connection is recorded as `failed` too, with that error, and
`archive` carries on with the next repository. GitHub may have archived the repository anyway, so
check it on GitHub before you run `archive` again for it.

Keep `migration_output/` once you're done. Together the five files are the record of what moved,
what arrived and what was archived.
