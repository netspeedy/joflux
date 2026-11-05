# Release and Website Notes

The repository follows the same release shape as other netspeedy CLI tools:

- `Build and Validate` checks formatting, linting, tests, packaging, and a CLI
  smoke test on pushes and pull requests.
- `Automated Release Candidate` creates an `-rc` tag after validation succeeds
  on `main` when `RELEASE_AUTOMATION_TOKEN` is configured.
- `Release Assets` builds a wheel and source distribution, publishes them to the
  GitHub release, and attaches `SHA256SUMS`.
- `Publish Homebrew Formula` updates `netspeedy/homebrew-joflux` on stable tags.

Release tags use `vMAJOR.MINOR.PATCH`. Conventional commit subjects decide the
next version:

- `feat:` creates a minor release.
- `fix:`, `deps:`, `build:`, `packaging:`, and `release:` create a patch release.
- `!` or `BREAKING CHANGE:` creates a major release.

Dependabot titles its pip updates `deps:`, since they change what ships, and the
website's npm updates `chore:`, so a docs-site dependency bump doesn't cut a
release.

The release workflow publishes an `-rc` tag first, waits for release assets to
build, and then promotes the same commit to a stable tag.

## Website

The site at https://netspeedy.github.io/joflux/ is the joflux documentation,
built with Astro and Starlight from `website/`. The pages are Markdown and MDX
in `website/src/content/docs`. Run it locally with live reload:

```bash
make website-install
make website-dev
```

Build it, validate the output, drive it in a browser, and take desktop and phone
screenshots in both themes:

```bash
make website-build
make website-check
make website-test
make website-capture
```

`website-test` runs `website/scripts/browser-test.mjs` in headless Chrome. It
builds the site twice into `website/.test/`, as an archived line and as the
latest with that line listed, unpacks the archive the way the Pages workflow
will, and checks the theme controls, the header, each tab's sidebar, the version
menu (including a long list of lines) and the archived notice. It reads the site
root, the tabs and the pages from the build, and exits non-zero if a check
fails.

`website-check` validates `website/dist`, so it runs after the build. Captures
are written to `website/.captures/`; the first one downloads the Chrome build
Puppeteer pins, since installing the site's dependencies never does. Search only
works in a build, because Pagefind indexes the finished pages.

The build always starts with a fresh content cache (`astro build --force`, which
logs "data store cleared"). Astro notices changes to its config, but not edits
to the Markdown plugins in `website/src/lib`, so without it a plugin change
could leave pages rendered by the old code.

The Pages workflow resolves the latest release before it builds, and passes it
to the site in `SITE_METADATA_FILE`, so the published pages name the real
release and link to its notes. Local and pull request builds fall back to the
newest local tag. The same JSON is still published as `website-metadata.json`.

### Versioned docs

The docs are versioned by release line. The latest line is built at the site
root, and each older line is served under its own path, such as
`https://netspeedy.github.io/joflux/v0.1/`. The version menu in the header lists
them, and an older line's pages open with a notice that links to the same page
in the latest docs.

Only the latest line is kept in the repository. When the first release of a new
line is published, such as `v0.2.0`, the Release Assets workflow finds the
commit just before the new line started
(`scripts/release/docs-archive-commit.sh`, which uses the same `feat:` and
breaking-change rules as `next-release.sh`), builds the site from it with
`SITE_ARCHIVE` set to the old line, and attaches the result to the old line's
last release as `joflux-docs-<line>.tar.gz`. The Pages workflow unpacks every
such archive into the site before `make website-check`, lists them in
`versions.json` at the root, and archived lines read that file when they load,
so their menus include lines released after them. A failed archive doesn't fail
the release: the job reports it in its summary and leaves the line unpublished.

v0.1 is the first line that gets an archive, when v0.2.0 ships. A line whose
last commit predates the Starlight site is skipped, because it can't build
under a line's own path.

To build an archived line by hand, for example to replace a lost archive, check
out the commit the script prints and build it with the line set. The
docs-archive job in `.github/workflows/release-assets.yml` shows how it writes
the `SITE_METADATA_FILE` the pages read their release from.

```bash
git checkout "$(bash scripts/release/docs-archive-commit.sh v0.1.4 v0.2.0)"
SITE_ARCHIVE=v0.1 make website-build
SITE_ARCHIVE=v0.1 make website-check
tar -C website/dist -czf joflux-docs-v0.1.tar.gz .
gh release upload v0.1.4 joflux-docs-v0.1.tar.gz --clobber
```

`test_cli_reference_covers_every_flag` in `tests/test_docs.py` fails when an
option is added to or removed from the CLI without updating
`website/src/content/docs/reference/cli.mdx`.

The favicon, Apple touch icon, `favicon.ico`, the mark and the share card in
`website/` come from `make readme-hero`, along with the README banner.
