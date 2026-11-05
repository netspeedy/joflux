---
title: Migrate
description: migrate resolves the target organization and asks Forgejo to migrate each repository in the inventory, one at a time.
---

`migrate` reads `repos-inventory.json`, resolves the target Forgejo organization, and asks Forgejo
to migrate each repository in the inventory, one at a time. It takes no flags.

```bash
joflux --config joflux.toml migrate
```

It fails straight away, with exit code 2, if there's no inventory to read, and with exit code 1 if
the target organization can't be resolved. Create the organization on Forgejo before running it.

## What each request asks for

For every repository, joflux asks Forgejo to import it from its GitHub clone URL into the target
organization, naming GitHub as the source so Forgejo can bring more than the git data. A few
details are worth knowing:

- Forgejo imports the wiki, issues, pull requests (with their comments and reviews), labels,
  milestones and releases along with the git data. Set `metadata = false` under `[migration]` to
  import only the git data; [Configuration](/joflux/guides/configuration/#metadata) has more.
- Git LFS objects aren't requested, so a repository that uses LFS arrives with its pointer files
  but not the files they point to.
- The copy is a normal repository, not a mirror, so it doesn't keep following GitHub afterwards.
- It's private on the target if it was private on GitHub.
- Forgejo clones it and reads its metadata with the GitHub token, so private repositories come
  across.
- A repository with no description on GitHub gets `Migrated from GitHub by joflux`.
- If the inventory has no clone URL for a repository, joflux uses
  `https://github.com/<org>/<name>.git`.

Forgejo doesn't answer a request until it has finished that import, which can take many minutes
for a repository with a long issue history. joflux waits up to `max_wait_time` seconds for each
answer, an hour by default. If Forgejo still hasn't answered by then, `migrate` stops with
`timed out` and exit code 1, and Forgejo carries on with that import.

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

Forgejo answers a migration request once it has finished importing that repository, so by the
time `migrate` logs a repository as `initiated`, its import is normally done. Run
[`monitor`](/joflux/stages/monitor/) next to confirm that each one is on the target.

Running `migrate` a second time sends a new request for every repository in the inventory,
including ones that already arrived, so only re-run it with an inventory that lists what's left.
