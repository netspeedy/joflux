---
title: Monitor
description: monitor rechecks the migrations Forgejo didn't answer for while migrate was waiting, and reports the ones it can't confirm.
---

`monitor` checks the migrations that `migrate` couldn't confirm. Forgejo answers a migration
request only once the import has finished, so by the time `migrate` ends most repositories are
already recorded as `completed` or `failed`. The ones left are those logged as `initiated`: Forgejo
didn't answer within `max_wait_time`, or a proxy in front of it gave up first, and the import may
still be running.

```bash
joflux --config joflux.toml monitor
```

## Which repositories it checks

`monitor` reads `migration-log.json` and, if it exists, `migration-status.json`. It checks a
repository when its latest migration entry is `initiated` and nothing since has recorded it as
`completed` or `error`, so repositories that `migrate` logged as `completed` or `failed` are
skipped. If nothing is pending, it logs `No unconfirmed migrations to check` and exits 0, which is
the usual outcome when Forgejo answered every request.

It's safe to stop with Ctrl-C and run again later: the next run picks up the repositories that are
still outstanding.

## What it can tell

Forgejo's API has no migration status. The target repository exists from the moment an import
starts, and a failed import can be left behind rather than deleted, so finding the repository
doesn't show that its import finished. All the API shows is whether the git data has arrived,
which happens before the issues, pull requests and releases are imported. So on each pass, for
every pending repository:

- If the target doesn't have it yet, or has it without any git data, it's still in progress and
  stays pending.
- Once its git data is there, it's recorded as `unconfirmed`, with a warning to check it in the
  Forgejo web UI, and `monitor` stops checking it for this run.
- If the request times out or the connection drops, it stays pending for the next pass, because
  that says nothing about the import.
- Any other error from the target records it as `error`.

`monitor` never records a repository as `completed`; only `migrate` can, from Forgejo's answer.

To check an unconfirmed repository, open it in the Forgejo web UI. A finished import shows the
repository as usual. One that hasn't finished shows Forgejo's migration page instead, and for an
import started through the API, as joflux's are, that page says the migration failed and offers to
delete the repository even while the import is still running. So don't delete anything straight
away: give it time and look again. If it stays that way, the import failed, and you need to delete
the repository on the target before you migrate it again, or Forgejo refuses the new migration
because the name is taken.

## How it polls

Between passes it waits `poll_interval` seconds, 30 unless the config says otherwise. `--interval`
overrides that for one run:

```bash
joflux --config joflux.toml monitor --interval 10
```

It stops when nothing is left pending, or when `max_wait_time` has passed since it started with
repositories still outstanding. That defaults to 3600 seconds, an hour, and is checked once per
pass. A run that gives up logs `Max wait time reached with <n> repositories still pending`. A
repository whose GitHub original has no commits never shows any git data, so if its import went
unanswered it stays pending until then.

The summary at the end has the shape
`Monitor complete: <unconfirmed> unconfirmed, <failed> failed, <pending> pending`.

## What it writes

Every repository it records as `unconfirmed` or `error` gets an entry in `migration-status.json`.
Repositories still in progress don't. An `error` entry settles a repository, but an `unconfirmed`
one doesn't, so the next run checks it again.

`monitor` exits 0 only when it had nothing to check. It exits 1 if it recorded any repository as
`unconfirmed` or `error`, or gave up with some still pending.

## Before you verify

Check every `unconfirmed` repository in the Forgejo web UI first. If repositories were still
pending, run `monitor` again; there's no need to start the migrations over. Then run
[`verify`](/joflux/stages/verify/), whose counts show what actually came across.
