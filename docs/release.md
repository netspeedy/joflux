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

`test_cli_reference_covers_every_flag` in `tests/test_docs.py` fails when an
option is added to or removed from the CLI without updating
`website/src/content/docs/reference/cli.mdx`.

The favicon, Apple touch icon, `favicon.ico`, the mark and the share card in
`website/` come from `make readme-hero`, along with the README banner.
