# Configuration

joflux reads TOML by default:

```toml
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
```

## GitHub token

The GitHub token must be able to list organization repositories and clone any
private repositories you want to migrate. To use `joflux archive`, it must also
be able to update repository settings.

Prefer setting it in the environment so it is not written to disk:

```bash
export JOFLUX_GITHUB_TOKEN="ghp_your_github_token"
```

`github.token` or `github_token` in the config file is still supported and takes
precedence when present.

## Forgejo token

The Forgejo or Codeberg token must be able to create repositories in the target
organization. Create the organization before running `migrate`.

Prefer setting it in the environment:

```bash
export JOFLUX_FORGEJO_TOKEN="your_forgejo_token"
```

For Codeberg migrations, `JOFLUX_CODEBERG_TOKEN` is accepted as an alias:

```bash
export JOFLUX_CODEBERG_TOKEN="your_codeberg_token"
```

`forgejo.token`, `forgejo_token`, `codeberg_token`, or `target_token` in the
config file is still supported and takes precedence when present.

## Output directory

`output_dir` controls where migration state is written. Keep this directory
after the run; it is the audit trail and retry surface for the migration.

## Legacy keys

Flat keys from the older tool are accepted:

```toml
github_org = "my-github-org"
# github_token = "ghp_your_github_token"
codeberg_url = "https://codeberg.org"
codeberg_org = "my-codeberg-org"
# codeberg_token = "your_codeberg_token"
```

YAML configs are supported only when the optional `joflux[yaml]` extra is
installed. TOML keeps the default install dependency-free.
