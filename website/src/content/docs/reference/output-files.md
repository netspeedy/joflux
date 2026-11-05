---
title: Output files
description: The five JSON files joflux keeps in the output directory, which stage writes and reads each, and their fields.
---

Every stage keeps its state in the output directory, `migration_output/` unless `output_dir` says
otherwise. joflux creates the directory if it doesn't exist. The files are pretty-printed JSON with
sorted keys.

| File | Written by | Read by |
| --- | --- | --- |
| `repos-inventory.json` | `export` | `migrate`, `verify`, `archive` |
| `migration-log.json` | `migrate` | `monitor` |
| `migration-status.json` | `monitor` | `monitor` |
| `verification-report.json` | `verify` | `archive` |
| `archive-log.json` | `archive` | `archive` |

`export` replaces the inventory each time it runs. The other four files are lists of events: each
run appends to them and keeps what's already there.

Timestamps are ISO 8601 in UTC, to the second, such as `2026-11-05T02:39:52+00:00`.

## repos-inventory.json

A JSON array of the organization's repositories, exactly as GitHub's API returned them, after any
`--exclude-forks` or `--exclude-archived` filter. The later stages use these fields from each
entry:

| Field | Used for |
| --- | --- |
| `name` | The repository's name on the target, and in every log |
| `clone_url` | Where Forgejo clones it from |
| `description` | The target repository's description |
| `private` | Whether the target repository is private |
| `fork`, `archived` | The filters and the export summary, and `archive` skips a repository that was already archived |

## migration-log.json

One entry per migration request. A repository that `migrate` skips, because its latest entry is
already `completed`, gets no new one, and neither does an `initiated` one whose repository is still
on the target when `migrate` runs again.

| Field | Value |
| --- | --- |
| `repo` | Repository name |
| `status` | `completed` when Forgejo answered with the imported repository, `initiated` when no answer came back and the import may still be running, or `failed` when Forgejo rejected or failed it |
| `message` | For `completed`, `Forgejo finished the import`. For `initiated`, why no answer came, followed by `; Forgejo may still be importing the repository`, such as `no answer from <url>: timed out; Forgejo may still be importing the repository`, `HTTP 504 from <url>; Forgejo may still be importing the repository`, or `incomplete answer from <url>: ...` for an answer that was cut off partway. For `failed`, `Forgejo rejected or failed the import:` and the HTTP error. |
| `migration_id` | For `completed`, the target repository's ID from Forgejo's answer; otherwise `null` |
| `timestamp` | When the request finished |

## migration-status.json

One entry each time `monitor` records a repository as unconfirmed or as an error. Repositories
still in progress get no entry.

| Field | Value |
| --- | --- |
| `repo` | Repository name |
| `status` | `unconfirmed` when its git data is on the target but Forgejo's API can't say whether the rest of the import finished, or `error` when the target returned an error |
| `details` | For `unconfirmed`, `git data present; Forgejo's API doesn't report whether the import finished`. For `error`, empty. |
| `checked_at` | When it was checked |

## verification-report.json

One entry per repository per `verify` run.

| Field | Value |
| --- | --- |
| `repo` | Repository name |
| `status` | `verified` or `missing` |
| `details` | For `verified`, `size:<size> issues:<n> pulls:<n> labels:<n> releases:<n> wiki:<yes\|no>`, where `issues` is `off` or `external`, and `pulls` or `releases` is `off`, when that part of the target repository is turned off. An empty repository has `pulls:0`. For `missing`, the error, or `not found`. |
| `verified_at` | When it was checked |

## archive-log.json

One entry per repository that an `archive` run tries to archive. A repository it leaves alone,
because `verify` hasn't recorded it as verified or it's already archived, gets none.

| Field | Value |
| --- | --- |
| `repo` | Repository name |
| `status` | `success` or `failed` |
| `message` | `Repository archived`, or the error: the one GitHub returned, or for a request that got no answer, such as one that timed out, `no answer from <url>: timed out` |
| `timestamp` | When it was archived |
