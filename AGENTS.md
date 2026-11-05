# Repository Guidelines

## Project Structure & Ownership

- Keep the package in `src/joflux/` and its tests in `tests/`. `cli.py` holds
  the parser and one handler per stage; the GitHub and Forgejo API clients,
  config loading and the JSON state files each have their own module.
- joflux runs on the Python 3.11+ standard library alone. PyYAML is the
  optional `yaml` extra. Don't add a runtime dependency: the Homebrew formula
  installs the wheel with `pip --no-deps`, so anything else would be missing
  there.
- Keep first-party automation, packaging and release assets at the root, under
  `.github/`, `scripts/` and `website/`.
- Treat `website/` as a first-party release surface, not a throwaway demo. It
  is the joflux documentation, built with Astro and Starlight; the pages are
  Markdown and MDX in `website/src/content/docs`.
- User-facing documentation lives in the site, not in `docs/`. The files in
  `docs/` other than `release.md` are pointers kept so old links still land
  somewhere; don't add guides there.
- When CLI behaviour, options, defaults, config keys, output files or exit codes
  change, update the matching site pages in the same change, and the README
  where it covers the same thing. `test_cli_reference_covers_every_flag` in
  `tests/test_docs.py` fails when an option is added or removed without
  updating `website/src/content/docs/reference/cli.mdx`.
- The mark, the README banner, the social cards and the site's icons all come
  from `scripts/readme/build_readme_hero.py` via `make readme-hero`. Change the
  generator, not the generated files. The tap, `netspeedy/homebrew-joflux`,
  carries a copy of the generator, so change both.
- Each sidebar group has its own colour and icon, and each header tab owns
  some of the groups and shows only those in its sidebar. Both are in
  `website/src/lib/sections.ts`, matched to the sidebar in
  `website/astro.config.mjs` by label, so adding or renaming a group means
  updating `sections` and `tabs` there.
- The site's components and styles are shared with the other netspeedy docs
  sites, so their classes, custom properties and elements use the neutral
  `ns-` prefix and they don't name joflux. s3ctl's site is the standard, so
  carry design changes over from there rather than diverging. What's
  particular to joflux (its name, description, links, footer columns and the
  home page's directory line) lives in `website/src/lib/site.ts`, and the
  pages written for joflux are `HomeTop.astro`, `InstallTabs.astro` and
  `src/pages/404.astro`, alongside the content, `astro.config.mjs`,
  `src/lib/sections.ts` and the mark's colour in `theme.css`. Keep it that
  way, so a change to a shared file can be copied between the sites as it is.
- The docs are versioned by release line. Only the latest line lives in
  `website/src/content/docs`; never copy pages into per-version folders. When a
  new minor ships, the release workflow rebuilds the outgoing line from git with
  `SITE_ARCHIVE=vX.Y`, which serves it under `/joflux/vX.Y/`, and the Pages
  workflow publishes it beside the latest. Keep page links root-relative
  (`/joflux/...`): archived builds rewrite them into their own line.
- Keep the website out of `.github/`. Dependabot stopped being able to open npm
  pull requests for manifests under `.github/` in June 2026 (its create-PR call
  is rejected as "invalid or unauthorized changes"), which is why it lives at
  the root.

## Build, Lint, and Test Commands

- Install the package with its development tools:
  ```bash
  make install-dev
  ```
- Format with black and isort, or check the formatting:
  ```bash
  make fmt
  make fmt-check
  ```
- Run pylint and the tests:
  ```bash
  make lint
  make test
  ```
- Build the wheel and source distribution, and smoke test the CLI:
  ```bash
  make build
  make smoke
  ```
- Lint the workflow YAML the way CI does:
  ```bash
  yamllint .github/workflows .github/dependabot.yml .github/release-drafter.yml .yamllint
  ```
- Build the docs site, then validate the built output (pages, search index,
  icons, share card and every internal link). The check reads `website/dist`,
  so it always runs after the build:
  ```bash
  make website-install
  make website-build
  make website-check
  ```
- Drive the site in headless Chrome: the theme controls, the header and its
  tabs, the version menu and an archived line. It builds its own latest and
  archived copies under `website/.test/`, so it needs no release metadata:
  ```bash
  make website-test
  ```
- Screenshot the built site in both themes at desktop and phone widths:
  ```bash
  make website-capture
  ```
- Serve the site with live reload while editing pages with `make website-dev`.
  When Astro detects an agent it starts the server in the background and returns,
  so stop it afterwards with `cd website && npx astro dev stop`.
  `website/README.md` summarises the folder, its targets and how it's published;
  keep it in step when any of those change.

## Python Style & Quality Rules

- black and isort at a line length of 100, and pylint clean with the project's
  settings in `pyproject.toml`.
- Keep the stages independent. Each one reads the previous stage's JSON from
  the output directory and writes its own, so a stage can be re-run on its own.
- Favour clear, operator-facing errors that name the repository, the stage and
  the API call that failed.
- Keep exit codes stable: 0 for success, 1 when a stage partly failed or an API
  call errored, 2 for a config problem or a missing state file.
- Tokens come from the environment (`JOFLUX_GITHUB_TOKEN`,
  `JOFLUX_FORGEJO_TOKEN`, `JOFLUX_CODEBERG_TOKEN`) or the config file. Never
  log them or write them into the output files.

## Workflow & Security Rules

- Treat workflow changes as security-sensitive. Keep GitHub Actions permissions
  least-privilege and scoped to the jobs that need them.
- Pull requests should validate code and packaging without gaining access to
  release or publish credentials.
- `archive` changes the GitHub originals. Keep its confirmation prompt, and
  never make it run as part of another stage.
- `feat:`, `fix:`, `perf:`, `revert:`, `deps:`, `build:`, `packaging:` and
  `release:` commits cut releases (`scripts/release/next-release.sh` decides);
  `docs:`, `ci:`, `chore:` and `test:` don't. Every release-bearing push
  to `main` cuts a release candidate. Updates from Dependabot, Renovate and
  this repository's workflows are then promoted to stable on their own; a
  release-bearing change a person merged waits at the candidate until someone
  runs `Promote Release Candidate`. While that's waiting, every validated push
  to `main` tags the next candidate, docs-only pushes included. That's
  expected. `docs/release.md` describes the release flow.

## Testing Expectations

- Minimum validation for Python changes:
  ```bash
  make fmt-check
  make lint
  make test
  make build
  make smoke
  ```
- If you change shell scripts, also run:
  ```bash
  bash -n scripts/release/*.sh
  shellcheck scripts/release/*.sh
  ```
- If you change the website, run `make website-build`, `make website-check` and
  `make website-test`, and look at `make website-capture` output for layout
  changes.
- If you change release tagging, release notes or publish workflows, also run:
  ```bash
  bash scripts/release/next-release.sh
  bash scripts/release/generate-release-notes.sh "$(git describe --tags --abbrev=0 2>/dev/null || true)" HEAD /tmp/joflux-release-notes.md
  ```

## Commit & PR Rules

- Do not create commits unless the user explicitly asks for a commit in the
  current turn.
- Use conventional commit subjects such as `feat:`, `fix:`, `docs:`, `ci:`,
  `deps:`, `chore:` or `test:`, and pick the type for its release effect: site
  changes are `docs:` and workflow changes are `ci:`.
- Keep changes focused by concern: runtime logic, automation, docs, packaging
  and website work shouldn't be bundled casually. A bug found while working on
  something else gets its own pull request.
- PR descriptions should explain the operational reason for the change, the
  validation performed, and any release or upgrade impact.
