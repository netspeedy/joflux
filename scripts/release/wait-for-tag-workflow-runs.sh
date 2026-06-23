#!/usr/bin/env bash
set -euo pipefail

tag_name="${1:?tag name is required}"
head_sha="${2:?head sha is required}"
shift 2

if [ "$#" -eq 0 ]; then
  echo "at least one workflow file is required" >&2
  exit 1
fi

for workflow_file in "$@"; do
  echo "Waiting for ${workflow_file} on ${tag_name}..."
  run_id=""

  for _attempt in $(seq 1 30); do
    run_id="$(
      gh run list \
        --workflow "${workflow_file}" \
        --branch "${tag_name}" \
        --json databaseId,headSha \
        --jq ".[] | select(.headSha == \"${head_sha}\") | .databaseId" \
        --limit 10 \
        | head -n1
    )"

    if [ -n "${run_id}" ]; then
      break
    fi
    sleep 10
  done

  if [ -z "${run_id}" ]; then
    echo "No ${workflow_file} run found for ${tag_name}" >&2
    exit 1
  fi

  gh run watch "${run_id}" --exit-status --interval 15
done
