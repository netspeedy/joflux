---
title: Configuration
description: The config file's formats and sections, where tokens come from, GitHub Enterprise Server, and the older flat keys.
---

joflux reads `joflux.toml` in the current directory unless `--config` points somewhere else.
`--log-level` overrides the configured log level for one run:

```bash
joflux --config ./configs/acme.toml --log-level DEBUG export
```

## File formats

The file's extension decides how it's read:

| Extension | Format |
| --- | --- |
| `.json` | JSON |
| `.yaml` or `.yml` | YAML, which needs the optional `yaml` extra ([Installation](/joflux/installation/#yaml-configs)) |
| anything else | TOML |

TOML is the default and needs nothing beyond the standard library.

## The three sections

```toml title="joflux.toml"
[github]
org = "my-github-org"
# token = "ghp_your_github_token"

[forgejo]
url = "https://codeberg.org"
org = "my-forgejo-org"
# token = "your_forgejo_or_codeberg_token"

[migration]
poll_interval = 30
max_wait_time = 3600
log_level = "INFO"
output_dir = "migration_output"
metadata = true
```

`[github]` names the organization you're moving from, and `[forgejo]` the instance and organization
you're moving to. `[migration]` controls what `migrate` asks Forgejo to import, how long joflux
waits and how `monitor` polls, how much it logs and where it keeps its state. The organizations and
the Forgejo URL are required; everything in `[migration]` has a default.
[Config keys](/joflux/reference/configuration/) lists every key.

## Tokens

Keep the tokens out of the file and in the environment:

```bash
export JOFLUX_GITHUB_TOKEN="ghp_your_github_token"
export JOFLUX_FORGEJO_TOKEN="your_forgejo_token"
```

For Codeberg, `JOFLUX_CODEBERG_TOKEN` is accepted as well. joflux uses `JOFLUX_FORGEJO_TOKEN` when
both are set.

A token in the config file, such as `token` under `[github]` or `[forgejo]`, takes precedence when
it's set. An empty one doesn't count, so joflux falls back to the environment.
[Before you migrate](/joflux/guides/before-you-migrate/#get-the-tokens-right) covers what each token
needs to be able to do.

## GitHub Enterprise Server

joflux talks to `https://api.github.com` by default. For GitHub Enterprise Server, set `api_url`
under `[github]` to your server's API address, which is `https://<host>/api/v3`. `export` then
lists the organization from your server, `migrate` hands Forgejo the clone URLs your server put in
the inventory, and `archive`'s prompt names `<host>/<org>`.

## Metadata

`metadata` is `true` unless the config says otherwise, and `migrate` then asks Forgejo to import
each repository's wiki, issues, pull requests (with their comments and reviews), labels, milestones
and releases from GitHub along with the git data. Forgejo reads them through the GitHub API with
the GitHub token. Set `metadata = false` to import only the git data; `verify` then counts zero
issues, pull requests, labels and releases for every repository, because none were imported. It
has to be a real `true` or `false`, not a quoted string.

Git LFS objects aren't requested either way, so a repository that uses LFS arrives with its
pointer files but not the files they point to.

## Polling and logging

`max_wait_time` is how many seconds `migrate` waits for Forgejo to answer each migration request,
because Forgejo only answers once the import is done, and how long `monitor` keeps polling before
giving up on repositories that still haven't shown any git data. `poll_interval` is how many seconds
`monitor` waits between passes. Both must be positive whole numbers. `log_level` is one of `DEBUG`,
`INFO`, `WARNING`, `ERROR` or `CRITICAL`, in any case.

## The output directory

`output_dir` is where the five state files go, `migration_output` by default, relative to where you
run joflux. It's created if it doesn't exist. Keep it after the run: it's the audit trail, and it's
what `monitor`, `verify` and `archive` read when you run them again.

## Older flat keys

Flat keys from the older GitHub-to-Codeberg tool still work, so an earlier config can be moved
across gradually:

```toml
github_org = "my-github-org"
# github_token = "ghp_your_github_token"
codeberg_url = "https://codeberg.org"
codeberg_org = "my-codeberg-org"
# codeberg_token = "your_codeberg_token"
```

When a file has both, the flat key wins: `github_org` is used over `org` under `[github]`.
