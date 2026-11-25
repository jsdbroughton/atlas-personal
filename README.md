# atlas-personal

Personal skills and standing instructions for a Speckle atlas checkout. Clone this repo, then run `./install.sh`.

Atlas loads skills from `<atlas-main>/personal/skills/` unless `ATLAS_PERSONAL_DIR` names another directory. An empty `ATLAS_PERSONAL_DIR` turns personal skills off. `install.sh` writes the variable into `~/.zshenv` and, given an atlas main checkout, points that checkout's `personal/` at this clone.

## Layout

- `skills/<name>/` — every repo (`momus`, `ariadne`, `grug`, `clone-project-files`, `worktree-named-host`)
- `skills/<repo>/<name>/` — that repo only (`speckle-server-internal/speckle-automate-api`)
- `skills/momus/scripts/review-engine.sh` — runner for `momus`, `ariadne`, and `grug`
- `CLAUDE.md` — standing instructions; install links `~/.claude/CLAUDE.md` here

## Commands

`install.sh` puts `momus`, `critic` (same command as `momus`), `ariadne`, and `grug` on `~/.local/bin`. Those links stay on the machine.

The runner lives inside the momus skill. Atlas sync copies one skill directory, so a script outside that directory would be missing from the synced tree. `ariadne` and `grug` load `../momus/scripts/review-engine.sh`. That path is the same in this repo and under a repo's `.agents/skills/`.

`ATLAS_PERSONAL_DIR` tells atlas where the skill tree is. A value that exists only in `mise.local.toml` does not reach the SessionStart hook. The review commands do not need that variable once the skills sit side by side.

## New machine

```bash
git clone https://github.com/jsdbroughton/atlas-personal.git
cd atlas-personal
./install.sh /path/to/the/atlas/main/checkout
```

The argument is the directory that contains `atlas/scripts/sync-agents.py`. Omit it to skip the `personal/` link and rely on `ATLAS_PERSONAL_DIR` alone. Open a new shell so later processes see the variable.

The atlas checkout gitignores `personal/` (`/*` at the atlas root). The link is local.
