#!/usr/bin/env bash
# Wire this clone into the local machine. Links are absolute and stay uncommitted.
set -euo pipefail

repo=$(cd "$(dirname "$0")" && pwd -P)
atlas_main="${1:-}"

if [[ -n "$atlas_main" && ! -f "$atlas_main/atlas/scripts/sync-agents.py" ]]; then
  echo "install: $atlas_main has no atlas/scripts/sync-agents.py" >&2
  exit 1
fi

mkdir -p "$HOME/.local/bin"
for name in momus ariadne grug; do
  chmod +x "$repo/skills/$name/$name"
  ln -sfn "$repo/skills/$name/$name" "$HOME/.local/bin/$name"
done
ln -sfn "$repo/skills/momus/momus" "$HOME/.local/bin/critic"
chmod +x "$repo/skills/momus/scripts/review-engine.sh"

# Point a harness's required filename at AGENTS.md. The repo keeps one file.
link_file() {
  local target="$1" dest="$2"
  mkdir -p "$(dirname "$dest")"
  if [[ -L "$dest" || ! -e "$dest" ]]; then
    ln -sfn "$target" "$dest"
  elif [[ -f "$dest" ]]; then
    local bak="${dest}.bak.$(date +%Y%m%d%H%M%S)"
    mv "$dest" "$bak"
    ln -sfn "$target" "$dest"
    echo "install: moved previous $dest to $bak"
  else
    echo "install: $dest exists and is not a file or link" >&2
    exit 1
  fi
}

link_file "$repo/AGENTS.md" "$HOME/.claude/CLAUDE.md"
link_file "$repo/AGENTS.md" "$HOME/.codex/AGENTS.md"
link_file "$repo/AGENTS.md" "$HOME/.grok/AGENTS.md"

cursor_rule="$HOME/.cursor/rules/atlas-personal.mdc"
mkdir -p "$(dirname "$cursor_rule")"
cat >"$cursor_rule" <<EOF
---
description: Personal standing instructions live in AGENTS.md
alwaysApply: true
---

Follow the standing instructions in \`$repo/AGENTS.md\`. Read that file. It applies in every harness.
EOF

# Every-repo skills only. A skills/<repo>/<name> directory stays for atlas sync.
link_skill() {
  local src="$1" dest="$2"
  mkdir -p "$(dirname "$dest")"
  if [[ -L "$dest" || ! -e "$dest" ]]; then
    ln -sfn "$src" "$dest"
  else
    echo "install: left existing $dest in place"
  fi
}

for skill in "$repo"/skills/*; do
  [[ -f "$skill/SKILL.md" ]] || continue
  name=$(basename "$skill")
  for root in \
    "$HOME/.agents/skills" \
    "$HOME/.claude/skills" \
    "$HOME/.grok/skills" \
    "$HOME/.codex/skills" \
    "$HOME/.cursor/skills"
  do
    link_skill "$skill" "$root/$name"
  done
done

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

  # setup owns this file. Add one key to [env] and leave every other personal
  # value where it is, including keys written after setup.
  python3 - "$atlas_main/mise.local.toml" "$repo" <<'PY'
import pathlib, re, sys

path, repo = sys.argv[1], sys.argv[2]
file = pathlib.Path(path)
if not file.is_file():
    print(f"install: {path} is absent — run mise run setup in the atlas checkout, then re-run install")
    sys.exit(0)
text = file.read_text()
begin, end = "# atlas-personal:begin", "# atlas-personal:end"
quoted = '"' + repo.replace("\\", "\\\\").replace('"', '\\"') + '"'
block = f"{begin}\nATLAS_PERSONAL_DIR = {quoted}\n{end}\n"
if begin in text and end in text:
    pre, _, rest = text.partition(begin)
    _, _, post = rest.partition(end)
    if post.startswith("\n"):
        post = post[1:]
    new = pre + block + post
elif re.search(r"(?m)^ATLAS_PERSONAL_DIR\s*=", text):
    print("install: mise.local.toml already sets ATLAS_PERSONAL_DIR; left it unchanged")
    sys.exit(0)
elif re.search(r"(?m)^\[env\]\s*$", text):
    new = re.sub(r"(?m)^\[env\]\s*$", "[env]\n" + block.rstrip("\n"), text, count=1)
    if not new.endswith("\n"):
        new += "\n"
else:
    new = "[env]\n" + block + ("\n" if text and not text.startswith("\n") else "") + text
mode = file.stat().st_mode
file.write_text(new)
file.chmod(mode)
print(f"install: set ATLAS_PERSONAL_DIR in {path}")
PY
fi

echo "install: commands on ~/.local/bin, harnesses pointed at AGENTS.md, ATLAS_PERSONAL_DIR=$repo"
if [[ -n "$atlas_main" ]]; then
  echo "install: next, from the atlas checkout: mise run agents-sync"
fi
