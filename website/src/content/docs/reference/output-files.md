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
| `verification-report.json` | `verify` | |
| `archive-log.json` | `archive` | |

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
| `fork`, `archived` | The filters and the export summary |

## migration-log.json

One entry per migration request.

| Field | Value |
| --- | --- |
| `repo` | Repository name |
| `status` | `initiated` or `failed` |
| `message` | `Migration started` or `Failed to start migration` |
| `migration_id` | The ID Forgejo returned, `true` if it accepted the request without one, or `null` when the request failed |
| `timestamp` | When the request was made |

## migration-status.json

One entry each time `monitor` settles a repository. Repositories still in progress get no entry.

| Field | Value |
| --- | --- |
| `repo` | Repository name |
| `status` | `completed` or `error` |
| `details` | Empty |
| `checked_at` | When it was checked |

## verification-report.json

One entry per repository per `verify` run.

| Field | Value |
| --- | --- |
| `repo` | Repository name |
| `status` | `verified` or `missing` |
| `details` | For `verified`, `size:<size> issues:<n> pulls:<n> labels:<n> releases:<n>`. For `missing`, the error, or `not found`. |
| `verified_at` | When it was checked |

## archive-log.json

One entry per repository per `archive` run.

| Field | Value |
| --- | --- |
| `repo` | Repository name |
| `status` | `success` or `failed` |
| `message` | `Repository archived`, or the error GitHub returned |
| `timestamp` | When it was archived |
