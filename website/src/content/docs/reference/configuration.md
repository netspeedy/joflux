---
title: Config keys
description: Every config key joflux reads, with its aliases, default and environment variables.
---

joflux looks each setting up under several names, so configs written for the older
GitHub-to-Codeberg tool keep working. A dotted name means a key inside a section: `github.org` is
`org` under `[github]`. When a file has more than one of a setting's names, the first one in the
list below wins, which puts the flat keys ahead of the sectioned ones.

## GitHub

| Setting | Names, first match wins | Default | Environment |
| --- | --- | --- | --- |
| Organization | `github_org`, `source_org`, `github.org` | Required | |
| Token | `github_token`, `source_token`, `github.token` | Required | `JOFLUX_GITHUB_TOKEN` |
| API URL | `github_api_url`, `github.api_url` | `https://api.github.com` | |

## Forgejo

| Setting | Names, first match wins | Default | Environment |
| --- | --- | --- | --- |
| Instance URL | `forgejo_url`, `codeberg_url`, `target_url`, `forgejo.url` | Required | |
| Organization | `forgejo_org`, `codeberg_org`, `target_org`, `forgejo.org` | Required | |
| Token | `forgejo_token`, `codeberg_token`, `target_token`, `forgejo.token` | Required | `JOFLUX_FORGEJO_TOKEN`, then `JOFLUX_CODEBERG_TOKEN` |

## Migration

| Setting | Names, first match wins | Default |
| --- | --- | --- |
| Poll interval, in seconds | `poll_interval`, `migration.poll_interval` | `30` |
| Maximum wait, in seconds | `max_wait_time`, `migration.max_wait_time` | `3600` |
| Log level | `log_level`, `migration.log_level` | `INFO` |
| Output directory | `output_dir`, `migration.output_dir` | `migration_output` |

## Tokens

A token from the config file is used when it's set and not blank. Otherwise joflux reads the
environment variables in the order shown, and the first one that's set and not blank wins. With
neither, the run stops with a config error naming the first key and the variables it tried, such as
`missing required config key: github_token or env var: JOFLUX_GITHUB_TOKEN`.

## Validation

A missing or blank required key stops the run with `missing required config key:` and the
setting's first name. `poll_interval` and `max_wait_time` must be positive whole numbers, and
anything else stops it with `config key must be a positive integer:`. `log_level` is case
insensitive and must be one of `DEBUG`, `INFO`, `WARNING`, `ERROR` or `CRITICAL`.

The file has to hold a mapping at the top level. Every config error exits with code 2.
