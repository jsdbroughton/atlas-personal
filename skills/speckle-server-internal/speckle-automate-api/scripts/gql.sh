#!/usr/bin/env bash
# POST one GraphQL operation to a Speckle server and print the JSON response.
#
# Usage: gql.sh [--allow-mutation] <query-file|-> [variables-json]
#   SPECKLE_SERVER   server origin, default https://app.speckle.systems
#   ATLAS_PAT_TOKEN  personal access token (run via `mise exec --` from the
#                    Speckle atlas root so mise.local.toml is loaded)
#
# Mutations are refused unless --allow-mutation is given: the flag is the
# agent's explicit "the user approved this write" marker.
set -euo pipefail

allow_mutation=0
if [[ "${1:-}" == "--allow-mutation" ]]; then
  allow_mutation=1
  shift
fi

src="${1:?usage: gql.sh [--allow-mutation] <query-file|-> [variables-json]}"
vars="${2:-}"
[[ -n "$vars" ]] || vars='{}'
server="${SPECKLE_SERVER:-https://app.speckle.systems}"
server="${server%/}"

if [[ "$src" == "-" ]]; then
  query="$(cat)"
else
  query="$(cat "$src")"
fi

# A document may hold several operations and fragments, so look for a
# mutation/subscription keyword anywhere, not only at the start. Field names
# such as automateMutations never match: the keyword must stand alone.
if [[ "$allow_mutation" -ne 1 ]] &&
  printf '%s\n' "$query" | sed -e 's/#.*$//' |
  grep -Eq '(^|[^A-Za-z0-9_])(mutation|subscription)([^A-Za-z0-9_]|$)'; then
  echo "gql.sh: refusing a mutation/subscription without --allow-mutation" >&2
  exit 2
fi

token="${ATLAS_PAT_TOKEN:-}"
token="$(printf '%s' "$token" | tr -d '[:space:]"'"'")"
if [[ -z "$token" ]]; then
  echo "gql.sh: ATLAS_PAT_TOKEN is empty; run via 'mise exec --' from the Speckle atlas root" >&2
  exit 3
fi

body="$(jq -n --arg q "$query" --argjson v "$vars" '{query: $q, variables: $v}')"

curl -sS -m 60 "$server/graphql" \
  -H "Authorization: Bearer $token" \
  -H 'Content-Type: application/json' \
  --data-binary "$body"
