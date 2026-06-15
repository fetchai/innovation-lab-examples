#!/usr/bin/env bash
# .github/scripts/create-gssoc-labels.sh
#
# Bootstraps the GSSoC label set on a repository so the GSSoC dashboard can
# track contributions. Creates (or updates) every label defined in
# .github/labels/gssoc-labels.json:
#   - program  : gssoc26
#   - level    : level1, level2, level3 (points tiers read by the dashboard)
#   - difficulty / quality / type_bonus / validation : triage + bonus labels
#
# Usage:
#   bash .github/scripts/create-gssoc-labels.sh                       # current repo
#   bash .github/scripts/create-gssoc-labels.sh fetchai/innovation-lab-examples
#
# Requirements:
#   - GitHub CLI (gh), authenticated with repo write access
#   - jq

set -euo pipefail

REPO="${1:-}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LABELS_FILE="$SCRIPT_DIR/../labels/gssoc-labels.json"

if [[ ! -f "$LABELS_FILE" ]]; then
  echo "Labels file not found: $LABELS_FILE" >&2
  exit 1
fi

REPO_ARG=()
if [[ -n "$REPO" ]]; then
  REPO_ARG+=(--repo "$REPO")
fi

upsert_label() {
  local name="$1"
  local color="$2"
  local description="$3"

  if gh label list "${REPO_ARG[@]}" \
      --search "$name" \
      --json name \
      --jq '.[].name' \
      2>/dev/null | grep -Fxq "$name"; then
    printf '  updated  %s\n' "$name"
    gh label edit "$name" \
      --color "$color" \
      --description "$description" \
      "${REPO_ARG[@]}" \
      >/dev/null 2>&1
  else
    printf '  created  %s\n' "$name"
    gh label create "$name" \
      --color "$color" \
      --description "$description" \
      "${REPO_ARG[@]}" \
      >/dev/null
  fi
}

sync_group() {
  local group="$1"
  local count
  count="$(jq -r --arg g "$group" '.[$g] // [] | length' "$LABELS_FILE")"
  if [[ "$count" == "0" ]]; then
    return
  fi
  echo "-- ${group} labels --"
  # Tab-separated so names/descriptions with spaces survive the read.
  jq -r --arg g "$group" '.[$g][] | [.name, .color, .description] | @tsv' "$LABELS_FILE" \
    | while IFS=$'\t' read -r name color description; do
        upsert_label "$name" "$color" "$description"
      done
  echo ""
}

echo "=== GSSoC Label Bootstrap ==="
echo "Repo: ${REPO:-<current>}"
echo ""

sync_group "program"
sync_group "level"
sync_group "difficulty"
sync_group "quality"
sync_group "type_bonus"
sync_group "validation"

echo "GSSoC labels synchronized successfully."
