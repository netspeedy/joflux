---
title: Exit codes
description: What joflux's exit codes 0, 1, 2 and 130 mean, and what produces each.
---

Every command exits with one of four codes, so a script can run the stages in order and stop at
the first one that didn't go cleanly:

```bash
set -e
for stage in export migrate monitor verify; do
  joflux --config joflux.toml "$stage"
done
```

| Code | Meaning |
| --- | --- |
| `0` | The stage went cleanly |
| `1` | The stage partly failed, or an API call errored |
| `2` | A config problem or a missing state file |
| `130` | Interrupted with Ctrl-C |

## 0

The stage did everything it set out to. Two cases exit 0 without doing anything: `archive` when you
answer anything other than `yes` at its prompt, and `monitor` when there are no unconfirmed
migrations to check, which is the usual case because `migrate` waits for Forgejo to finish each
import.

## 1

A stage exits 1 when some of its work failed:

- `migrate` couldn't resolve the target organization, or Forgejo rejected or failed any import;
  an import that went unanswered doesn't count
- `monitor` recorded a repository as unconfirmed, saw one return an error, or gave up with
  repositories still pending
- `verify` found a repository missing on the target
- `archive` failed to archive any repository

A request that times out or loses its connection counts as a failed API call for the repository
it was about: the stage records it and carries on, like any other failed request. In `monitor` it
leaves the repository pending for the next pass instead, and in `migrate` it means the import went
unanswered, which doesn't count as a failure.

It also exits 1 when an error stops a stage part-way: an API call that fails outside those cases,
such as GitHub refusing the organization listing in `export`, a network error, a file that can't be
read or written, or a state file that isn't the JSON array it should be.

## 2

joflux exits 2 before doing any work when the config is wrong or a state file it needs is missing.
A config problem prints `config error:` and the reason to standard error: the file doesn't exist,
doesn't parse, or is missing a required key or has an invalid value. A missing state file is
logged instead, as when `migrate`, `verify` or `archive` runs before `export` and stops with
`inventory not found; run export first`.

An unknown command or flag also exits 2, with usage.

## 130

Ctrl-C stops the stage, logs `Interrupted by user` and exits 130. Whatever the stage already wrote
stays in the output directory, so an interrupted `monitor` can simply be run again.
