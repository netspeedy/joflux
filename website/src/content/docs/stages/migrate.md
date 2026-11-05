---
title: Migrate
description: migrate resolves the target organization and has Forgejo migrate each repository in the inventory, one at a time, waiting for each import to finish.
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
answer, an hour by default. If no answer has come back by then, it records the repository as
`initiated`, logs `<repo> may still be importing; run monitor to check it` and moves on to the
next one, while Forgejo carries on with that import. A reverse proxy in front of Forgejo that gives
up first, answering 504 (or 524 from Cloudflare), and a connection that drops before the answer
arrives are treated the same way.

joflux waits a second between requests. Each one is logged as it goes, in the shape
`[<n>/<total>] Migrating <repo>`, and a summary at the end has the shape
`Migrations finished: <completed> completed, <unconfirmed> unconfirmed, <failed> failed`.

## What it writes

Each request appends an entry to `migration-log.json` with its outcome:

- `completed`, with `Forgejo finished the import` and the target repository's ID, when Forgejo
  answered with the imported repository.
- `initiated`, when no answer came back, with a message saying why and that the import may still
  be running. These are the repositories `monitor` checks.
- `failed`, when Forgejo rejected or failed the import, with
  `Forgejo rejected or failed the import:` and the HTTP error. The error Forgejo sent back is
  logged too.

[Output files](/joflux/reference/output-files/) has every field.

`migrate` exits 1 if any import failed, even when the rest completed. An unanswered import doesn't
count as a failure, because it may still finish.

## Before you monitor

Forgejo answers a migration request only once it has finished importing that repository, and that
answer is the only sign of a finished import that its API gives. A repository logged as
`completed` is done, so `monitor` has nothing to do for it. Run
[`monitor`](/joflux/stages/monitor/) next anyway: it checks the repositories logged as
`initiated`, and exits 0 straight away when there are none.

A failed import isn't always cleaned up. Forgejo can leave the repository behind on the target,
and it refuses a new migration with the same name until that repository is deleted, so delete it
on the target before you migrate it again.

Running `migrate` a second time sends a new request for every repository in the inventory,
including ones that already arrived, so only re-run it with an inventory that lists what's left.
