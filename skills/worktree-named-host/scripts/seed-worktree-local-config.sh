#!/usr/bin/env bash
# Personal stand-in for speckle-server-internal's utils/scripts/seed-worktree-local-config.sh.
# The repo copy hands the literal multiregion.json path to cp even when the main
# checkout lacks it (nullglob drops only unmatched globs), which aborts
# post-checkout before the installs. The repo fix was closed unmerged (PR #3837),
# so this copy carries the one-line guard. Run it from inside the worktree.
set -euo pipefail

main_worktree=$(git worktree list --porcelain | sed -n '1s/^worktree //p')
this_worktree=$(git rev-parse --show-toplevel)
[[ "$main_worktree" == "$this_worktree" ]] && exit 0

shopt -s nullglob
for src in "$main_worktree"/packages/*/mise.local.toml "$main_worktree"/packages/*/mise.test.local.toml "$main_worktree"/packages/server/multiregion.json; do
  [[ -e "$src" ]] || continue
  rel=${src#"$main_worktree/"}
  dest="$this_worktree/$rel"
  [[ -d "$(dirname "$dest")" && ! -e "$dest" ]] || continue
  cp "$src" "$dest"
  echo "seeded $rel from $main_worktree"
done
