---
title: Migrate
description: migrate resolves the target organization and asks Forgejo to start one migration per repository in the inventory.
---

`migrate` reads `repos-inventory.json`, resolves the target Forgejo organization, and asks Forgejo
to start one migration for each repository in the inventory. It takes no flags.

```bash
joflux --config joflux.toml migrate
```

It fails straight away, with exit code 2, if there's no inventory to read, and with exit code 1 if
the target organization can't be resolved. Create the organization on Forgejo before running it.

## What each request asks for

For every repository, joflux asks Forgejo to import it from its GitHub clone URL into the target
organization. A few details are worth knowing:

- The copy is a normal repository, not a mirror, so it doesn't keep following GitHub afterwards.
- It's private on the target if it was private on GitHub.
- Forgejo clones it with the GitHub token, using the GitHub organization name as the username, so
  private repositories come across.
- A repository with no description on GitHub gets `Migrated from GitHub by joflux`.
- If the inventory has no clone URL for a repository, joflux uses
  `https://github.com/<org>/<name>.git`.

joflux waits a second between requests. Each one is logged as it goes, in the shape
`[<n>/<total>] Migrating <repo>`, and a summary at the end has the shape
`Migration requests complete: <started> started, <failed> failed`.

## What it writes

Each request appends an entry to `migration-log.json`. A started migration is recorded as
`initiated`, with the message `Migration started` and the migration ID Forgejo returned. A request
that fails is recorded as `failed`, with `Failed to start migration`, and the error Forgejo sent
back is logged. [Output files](/joflux/reference/output-files/) has every field.

`migrate` exits 1 if any request failed, even when the rest were started.

## Before you monitor

Starting a migration isn't the same as finishing one: Forgejo does the import in the background.
Run [`monitor`](/joflux/stages/monitor/) next to wait for the repositories to arrive.

Running `migrate` a second time sends a new request for every repository in the inventory,
including ones that already arrived, so only re-run it with an inventory that lists what's left.
