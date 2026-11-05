---
title: Monitor
description: monitor polls the target until each started migration has arrived, failed or run out of time, and can be stopped and re-run.
---

`monitor` waits for the migrations `migrate` started. It polls the target Forgejo instance until
each repository has arrived, returned an error, or the configured maximum wait has passed.

```bash
joflux --config joflux.toml monitor
```

## Which repositories it checks

`monitor` reads `migration-log.json` and, if it exists, `migration-status.json`. It checks a
repository when its latest migration entry is `initiated` and nothing since has recorded it as
completed or failed. So repositories whose request failed are skipped, and ones an earlier
`monitor` run already settled aren't checked again. If nothing is pending, it logs
`No initiated migrations found` and exits 0.

That's what makes it safe to stop with Ctrl-C and run again later: the next run picks up the
repositories that are still outstanding.

## How it polls

On each pass it asks the target for every pending repository:

- If the repository is there, it's recorded as `completed`.
- If the target answers that it doesn't exist yet, it's still in progress and stays pending.
- Any other error from the target records it as `error`.

Between passes it waits `poll_interval` seconds, 30 unless the config says otherwise. `--interval`
overrides that for one run:

```bash
joflux --config joflux.toml monitor --interval 10
```

It stops when nothing is left pending, or when `max_wait_time` has passed since it started with
repositories still outstanding. That defaults to 3600 seconds, an hour, and is checked once per
pass. A run that gives up logs `Max wait time reached with <n> repositories still pending`.

The summary at the end has the shape
`Monitor complete: <completed> completed, <failed> failed, <pending> pending`.

## What it writes

Every repository that completes or errors gets an entry in `migration-status.json`. Repositories
still in progress don't, which is how the next run knows to check them.

`monitor` exits 0 only when every pending repository completed. It exits 1 if any returned an
error or some were still pending when it gave up.

## Before you verify

If repositories were still pending, run `monitor` again; there's no need to start the migrations
over. Once everything has completed, run [`verify`](/joflux/stages/verify/).
