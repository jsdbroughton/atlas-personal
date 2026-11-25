---
name: clone-project-files
description: >-
  Cross-server clone/move of Speckle project files (CSV/XLSX/RVT) between any
  hosts — local, staging/next, or production — via public API reingest (not
  DB/S3). Whole project, one model source file, or one file; versions default
  latest (clone) / all (move). Same-server move refused (use
  packages/server/scripts/move/).
---

# Clone / move project files (API reingest)

**Job:** move or copy project **files** across Speckle server DBs — local ↔
staging/next ↔ production (any direction). Public API only: download source
bytes, re-upload into the target project (new document ids). Not the DB/S3
`packages/server/scripts/move/` path (that keeps ids on one deployment).
Geometry / object trees / workflows are out of scope.

## Modes

| Mode    | Same server (one host)            | Cross server (local / staging / production)      |
| ------- | --------------------------------- | ------------------------------------------------ |
| `clone` | OK (project→project on one host)  | Primary use — copy onto another host             |
| `move`  | **Refused** → use `scripts/move/` | Clone, verify, then soft-delete source **files** |

Cross-server **move** leaves source **models/versions** in place; only the
transferred source **documents** are soft-deleted. Models that pointed at those
files become file-orphaned on the source.

## Scope

- Default: all inventoriable csv/xlsx/xls (+ rvt with `--include-rvt`)
- `--source-model <id|exact-name>` — that model's `sourceDocument` / `document` file(s)
- `--source-file <id|exact-name>` — one data/binary file (exact one name match)

## Versions (`--versions`)

| Value    | Behaviour                                                                              |
| -------- | -------------------------------------------------------------------------------------- |
| `latest` | Highest `versionNumber` only; refuses if that ≠ `currentVersionId` (**clone default**) |
| `all`    | Every version, oldest → newest by `versionNumber` (**move default**)                   |
| `N`      | N most recent (≥1); clamps if N &gt; available                                         |

`--mode` defaults to `clone`. Omit `--versions` → `latest` on clone, `all` on
move. Explicit `--versions` always wins.

Upload always oldest→newest among the selected set. Target version numbers are
**renumbered** by that upload order (source numbers are not preserved).

`latest` refuses if highest `versionNumber` ≠ `currentVersionId`. `N` refuses if
`currentVersionId` falls outside the top-N by `versionNumber` (raise N or use
`all` — current is not force-included). If `N` ≥ available, selection clamps to
all versions and discard count is 0.

**Move + partial depth:** `--mode move` with `latest` or `N` soft-deletes the
whole source document (including unselected history). Requires
`--discard-older-versions` (dry-run prints how many versions would be discarded).
Same flag required for `--delete-source-only` when selected depth leaves history
behind.

**Pre-delete live check:** soft-delete only after id-map marks every selected
version `ok` and the live target `versionCount` equals the selected count. Blobs
also require live `currentVersionId` = last uploaded `targetVersionId`. Tabular
EDS check is **count + ready only** (no per-version identity on the wire) —
wrong-but-equal-count content is an accepted residual risk; id-map `ok` stamps
still gate the delete. Intermediate blob versions are covered by count + tip
id, not by enumerating every target version id.

Legacy id-maps missing `versions` / `selectedVersionIdsByDoc` are refused — use
a fresh artefacts dir.

## Script

Personal skill (gitignored, every repo): atlas
`personal/skills/clone-project-files/`. `$S` = this skill dir (folder holding
this file, wherever sync loaded it from).

```bash
python3 "$S/scripts/clone_project_files.py" --help
```

### Env (secrets — never CLI flags)

| Var                                         | Role                                                |
| ------------------------------------------- | --------------------------------------------------- |
| `SPECKLE_NEXT_TOKEN` / `--source-token-env` | Source bearer (or `SOURCE_EMAIL`/`SOURCE_PASSWORD`) |
| `TARGET_EMAIL` + `TARGET_PASSWORD`          | Target login                                        |
| `--target-token-env`                        | Target bearer env name                              |

### Examples

Same-server clone, latest tabular only, create project:

```bash
export TARGET_EMAIL='you@speckle.systems'
export TARGET_PASSWORD='…'

python3 "$S/scripts/clone_project_files.py" \
  --source-origin http://127.0.0.1:8080 \
  --source-project SOURCE_ID \
  --target-workspace WORKSPACE_ID \
  --create-project-name 'Snowdon copy' \
  --tabular-only \
  --artefacts-dir /tmp/clone-run
```

Cross-server move one model’s source file, last 2 versions:

```bash
python3 "$S/scripts/clone_project_files.py" \
  --mode move \
  --source-origin https://next.speckle.dev \
  --source-project ae38ee2acc \
  --source-model 'Snowdon Towers Sample Architectural' \
  --target-origin http://127.0.0.1:8080 \
  --blob-origin http://127.0.0.1:3000 \
  --target-project 72e1b70dde \
  --target-workspace 7ae7c55e5f \
  --versions 2 \
  --include-rvt \
  --force \
  --artefacts-dir /tmp/move-run
```

`--dry-run` lists planned docs/versions; no mutations. Move delete needs `--force`
when stdin is not a TTY. Resume delete after a successful clone:
`--mode move --delete-source-only`.

## Behaviour notes

1. Tabular → data-sources + `replaceOf` (DuckDB ready). Not bare `documents.create`.
2. Resume via `artefacts-dir/id-map.json` (per source version id).
3. Delete set = docs whose **selected** versions all `ok` in the id-map.
4. Origins normalised for same-server detection (scheme/host/port).

## Smoke

```bash
python3 "$S/scripts/clone_project_files.py" \
  --source-origin https://next.speckle.dev \
  --source-project ae38ee2acc \
  --target-origin http://127.0.0.1:8080 \
  --target-project 72e1b70dde \
  --target-workspace 7ae7c55e5f \
  --artefacts-dir /tmp/clone-inventory-smoke \
  --versions latest \
  --dry-run
```
