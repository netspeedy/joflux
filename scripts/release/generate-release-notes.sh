#!/usr/bin/env bash
set -euo pipefail

previous_tag="${1:-}"
to_ref="${2:-HEAD}"
output_path="${3:-/dev/stdout}"

if ! git rev-parse --verify "${to_ref}" >/dev/null 2>&1; then
  {
    printf '## Release Overview\n\n'
    printf 'Initial joflux release preparation.\n\n'
    printf '## Included Changes\n\n'
    printf -- '- Initial package, CLI, docs, and automation.\n\n'
    printf '## Installation\n\n'
    printf '```bash\n'
    printf 'brew tap netspeedy/joflux\n'
    printf 'brew install joflux\n'
    printf '```\n\n'
    printf '## Published Artifacts\n\n'
    printf -- '- Python wheel and source distribution\n'
    printf -- '- SHA256 checksums\n'
    printf -- '- Homebrew formula update for stable releases\n'
  } > "${output_path}"
  exit 0
fi

if [ -n "${previous_tag}" ]; then
  log_range="${previous_tag}..${to_ref}"
else
  log_range="${to_ref}"
fi

tag_name="$(git describe --tags --exact-match "${to_ref}" 2>/dev/null || printf '%s' "${to_ref}")"
repo_url="${GITHUB_SERVER_URL:-https://github.com}/${GITHUB_REPOSITORY:-netspeedy/joflux}"

tmpfile="$(mktemp)"
trap 'rm -f "${tmpfile}"' EXIT

git log --reverse --format="- %s (\`%h\`)" "${log_range}" > "${tmpfile}" || true

if [ ! -s "${tmpfile}" ]; then
  printf -- '- Maintenance release.\n' > "${tmpfile}"
fi

{
  printf '## Release Overview\n\n'
  printf 'joflux %s packages the GitHub-to-Forgejo migration CLI for repeatable organization moves.\n\n' "${tag_name}"

  printf '## Included Changes\n\n'
  cat "${tmpfile}"
  printf '\n\n'

  printf '## Installation\n\n'
  printf '```bash\n'
  printf 'brew tap netspeedy/joflux\n'
  printf 'brew install joflux\n'
  printf '```\n\n'

  printf 'Python users can also install the wheel attached to this release.\n\n'

  printf '## Published Artifacts\n\n'
  printf -- '- Python wheel and source distribution\n'
  printf -- '- SHA256 checksums\n'
  printf -- '- Homebrew formula update for stable releases\n\n'

  if [ -n "${previous_tag}" ]; then
    printf 'Compare: %s/compare/%s...%s\n' "${repo_url}" "${previous_tag}" "${tag_name}"
  fi
} > "${output_path}"
