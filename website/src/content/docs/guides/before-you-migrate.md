---
title: Before you migrate
description: What to set up and check before moving a whole organization, from tokens and target limits to a trial export.
---

A move touches every repository in an organization, so a little checking first saves a lot of
cleaning up afterwards.

## Check the target's limits

Forgejo instances differ in what they allow. Some restrict private imports, metadata import, how
many repositories an organization can hold, or how many migrations run at once. Check the target's
limits before starting on a large organization.

Importing issues and pull requests takes far longer than copying git data, and it spends the GitHub
token's API quota; Forgejo pauses until the quota resets when it runs out. `migrate` waits up to
`max_wait_time` seconds for each repository, so raise it if your largest repositories need longer.
If the target won't take metadata imports, or you only need the code, set `metadata = false` under
`[migration]`.

## Create the target organization

`migrate` doesn't create the organization. It looks it up first and stops with exit code 1 if it
can't, before starting a single migration, so create it on the target and set `forgejo.org` to its
name.

## Get the tokens right

joflux needs two tokens, and it's best to keep both in the environment rather than in the config
file:

```bash
export JOFLUX_GITHUB_TOKEN="ghp_your_github_token"
export JOFLUX_FORGEJO_TOKEN="your_forgejo_token"
```

The GitHub token has to list the organization's repositories and clone any private ones you're
moving, because Forgejo clones each repository with it. Forgejo also reads each repository's
issues, pull requests, labels, milestones and releases through the GitHub API with it, so it needs
read access to those too. If you'll run `archive`, it also needs to update repository settings.

The Forgejo or Codeberg token has to create repositories in the target organization. For Codeberg,
`JOFLUX_CODEBERG_TOKEN` works in place of `JOFLUX_FORGEJO_TOKEN`.

A token set in the config file takes precedence over the environment, so remove any old one from
the file if you're switching to environment variables.

## Private repositories

A repository that's private on GitHub stays private on the target. Its clone needs the GitHub
token to reach it, and some Forgejo instances restrict private imports, so check both before a move
that includes them.

## Try an export first

`export` only reads from GitHub, so run it on its own and read
`migration_output/repos-inventory.json`. Everything in it will be migrated and, at the end,
archived. Drop forks or repositories that are already archived with `--exclude-forks` and
`--exclude-archived` if they shouldn't move.

## Keep the output directory

Keep `migration_output/` until the move is finished, and afterwards too. `monitor`, `verify` and
`archive` read it when you run them, including when you re-run a stage, and once the move is done
it's the audit trail of what moved, what arrived and what was archived.
