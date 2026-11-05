---
title: Verify
description: verify checks every repository in the inventory on the target and records its size, its issue, pull request, label and release counts, and whether it has a wiki.
---

`verify` checks that every repository in the inventory is on the target, and records what each one
holds. It takes no flags.

```bash
joflux --config joflux.toml verify
```

It works from `repos-inventory.json`, not from the migration logs, so it checks every repository
you exported, whatever happened to its migration request.

## What it records

For each repository it reads the target repository and counts its issues, pull requests, labels
and releases, paging through all of them, open and closed, and checks whether it has a wiki. Issues
and pull requests are counted separately, so the issue count doesn't include pull requests. A
repository it can read is recorded as `verified`, with details in the shape:

```text
size:<size> issues:<n> pulls:<n> labels:<n> releases:<n> wiki:<yes|no>
```

`wiki` is `yes` when the target repository has a wiki, which for a freshly migrated repository
means Forgejo imported one; a wiki someone created on the target afterwards counts too. It's `no`
when there was nothing to import, as with a GitHub repository whose wiki tab is on but has no
pages, and always `no` with `metadata = false`.

The size is the one the target reports. The counts are of what Forgejo imported, so with
`metadata = false` in the config they're all zero. If the repository can't be read, or one of the
counts fails, it's recorded as `missing` along with the error. That includes a repository whose
issue tracker has been turned off on the target, or pointed at an external tracker: Forgejo won't
list its issues, and the count fails with HTTP 404.

Each check is logged in the shape `[<n>/<total>] Verifying <repo>`, and the summary at the end has
the shape `Verification complete: <verified> verified, <missing> missing`.

## What it writes

Each repository appends an entry to `verification-report.json`, so the file keeps every run's
results. [Output files](/joflux/reference/output-files/) has the fields.

If anything is missing, `verify` logs `Missing repositories:` with their names and exits 1.

## Before you archive

Read `verification-report.json` and compare the counts with what the repositories hold on GitHub.
`archive` doesn't look at this report: it archives every repository in the inventory, so it's up to
you to be sure the move worked first. A repository that [`monitor`](/joflux/stages/monitor/)
recorded as `unconfirmed` is verified with whatever had arrived when `verify` ran, so compare its
counts with care, and run `verify` again once you've checked it in the Forgejo web UI.
