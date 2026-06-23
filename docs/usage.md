# Usage

The normal migration flow is deliberately staged:

```bash
joflux --config joflux.toml export
joflux --config joflux.toml migrate
joflux --config joflux.toml monitor
joflux --config joflux.toml verify
joflux --config joflux.toml archive --yes
```

## export

`export` lists repositories in the configured GitHub organization and writes
`repos-inventory.json`.

Useful filters:

```bash
joflux export --exclude-forks
joflux export --exclude-archived
```

## migrate

`migrate` reads the inventory, resolves the target Forgejo organization ID, and
starts one migration per repository.

## monitor

`monitor` polls the target repository endpoints until repositories appear or the
configured max wait time is reached.

```bash
joflux monitor --interval 10
```

## verify

`verify` checks each target repository and records repository size plus issue,
pull request, label, and release counts.

## archive

`archive` archives the GitHub source repositories. It asks for confirmation
unless `--yes` is supplied.
