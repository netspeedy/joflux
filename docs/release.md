# Release Notes

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

The first stable release should publish `v0.1.0` from a `feat:` commit.
