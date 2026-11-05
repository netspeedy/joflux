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
size:<size> issues:<n|off|external> pulls:<n|off> labels:<n> releases:<n|off> wiki:<yes|no>
```

Forgejo won't list the issues of a repository whose issue tracker is turned off, or pointed at an
external tracker, the pull requests of one with pull requests turned off, or the releases of one
with releases turned off; it answers 404. So `verify` reads which are on from the repository itself
and doesn't ask for the others: the details say `issues:off`, `issues:external`, `pulls:off` or
`releases:off` in place of that count. Forgejo also won't list pull requests for an empty
repository, one with no commits, which can't have any, so `verify` records `pulls:0` for it without
asking.

`wiki` is `yes` when the target repository has a wiki, which for a freshly migrated repository
means Forgejo imported one; a wiki someone created on the target afterwards counts too. It's `no`
when there was nothing to import, as with a GitHub repository whose wiki tab is on but has no
pages, and always `no` with `metadata = false`.

The size is the one the target reports. The counts are of what Forgejo imported, so with
`metadata = false` in the config they're all zero. If the repository can't be read, or one of the
counts fails, it's recorded as `missing` along with the error.

Each check is logged in the shape `[<n>/<total>] Verifying <repo>`, and the summary at the end has
the shape `Verification complete: <verified> verified, <missing> missing`.

## What it writes

Each repository appends an entry to `verification-report.json`, so the file keeps every run's
results. [Output files](/joflux/reference/output-files/) has the fields.

If anything is missing, `verify` logs `Missing repositories:` with their names and exits 1.

## Before you archive

Read `verification-report.json` and compare the counts with what the repositories hold on GitHub.
`archive` works from this report: it archives only the repositories whose latest entry is
`verified`, and leaves the rest, so a repository that's `missing` stays unarchived until a later
`verify` records it as verified. A `verified` entry doesn't compare anything with GitHub, though, so
it's up to you to be sure the counts are right first. A repository that
[`monitor`](/joflux/stages/monitor/) recorded as `unconfirmed` is verified with whatever had arrived
when `verify` ran, so compare its counts with care, and run `verify` again once you've checked it in
the Forgejo web UI.
