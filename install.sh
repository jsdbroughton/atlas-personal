#!/usr/bin/env bash
# Wire this clone into the local machine. Links are absolute and stay uncommitted.
set -euo pipefail

repo=$(cd "$(dirname "$0")" && pwd -P)
atlas_main="${1:-}"

if [[ -n "$atlas_main" && ! -f "$atlas_main/atlas/scripts/sync-agents.py" ]]; then
  echo "install: $atlas_main has no atlas/scripts/sync-agents.py" >&2
  exit 1
fi

mkdir -p "$HOME/.local/bin" "$HOME/.claude"
for name in momus ariadne grug; do
  chmod +x "$repo/skills/$name/$name"
  ln -sfn "$repo/skills/$name/$name" "$HOME/.local/bin/$name"
done
ln -sfn "$repo/skills/momus/momus" "$HOME/.local/bin/critic"
chmod +x "$repo/scripts/review-engine.sh"

claude_md="$HOME/.claude/CLAUDE.md"
if [[ -L "$claude_md" || ! -e "$claude_md" ]]; then
  ln -sfn "$repo/CLAUDE.md" "$claude_md"
elif [[ -f "$claude_md" ]]; then
  bak="$HOME/.claude/CLAUDE.md.bak.$(date +%Y%m%d%H%M%S)"
  mv "$claude_md" "$bak"
  ln -sfn "$repo/CLAUDE.md" "$claude_md"
  echo "install: moved previous CLAUDE.md to $bak"
else
  echo "install: $claude_md exists and is not a file or link" >&2
  exit 1
fi

python3 - "$HOME/.zshenv" "$repo" <<'PY'
import pathlib, shlex, sys

path, repo = sys.argv[1], sys.argv[2]
file = pathlib.Path(path)
text = file.read_text() if file.exists() else ""
begin, end = "# atlas-personal:begin", "# atlas-personal:end"
block = f"{begin}\nexport ATLAS_PERSONAL_DIR={shlex.quote(repo)}\n{end}\n"
if begin in text and end in text:
    pre, _, rest = text.partition(begin)
    _, _, post = rest.partition(end)
    if post.startswith("\n"):
        post = post[1:]
    file.write_text(pre + block + post)
elif "ATLAS_PERSONAL_DIR" in text:
    print("install: ~/.zshenv already sets ATLAS_PERSONAL_DIR; left it unchanged")
else:
    prefix = text
    if prefix and not prefix.endswith("\n"):
        prefix += "\n"
    if prefix.strip():
        prefix += "\n"
    file.write_text(prefix + block)
PY

if [[ -n "$atlas_main" ]]; then
  dest="$atlas_main/personal"
  if [[ -L "$dest" ]]; then
    ln -sfn "$repo" "$dest"
  elif [[ -e "$dest" ]]; then
    moved="${dest}.bak.$(date +%Y%m%d%H%M%S)"
    mv "$dest" "$moved"
    ln -sfn "$repo" "$dest"
    echo "install: moved $dest to $moved"
  else
    ln -sfn "$repo" "$dest"
  fi
fi

echo "install: commands on ~/.local/bin, CLAUDE.md linked, ATLAS_PERSONAL_DIR=$repo"
