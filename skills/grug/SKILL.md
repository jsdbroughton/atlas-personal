---
name: grug
description: >-
  Independent Grug pass on a concrete code change. Before relying on a
  bugfix, feature, refactor, or diff, pipe the task, the constraints, and
  the proposed change to the `grug` shell command and wait for ENOUGH,
  SMALLER, or REFUSE. Grug keeps the change small, boring, and inside the
  task. Not for greenfield design, architecture with no code yet, or a
  throwaway spike. Correctness is Momus. How people use it is Ariadne.
---

# Grug

Grug is the second mind on a code change. Complexity is the enemy. It shows
up as a clever abstraction, a drive-by refactor, or a diff that does more
than it was asked.

Before relying on a non-trivial bugfix, feature, refactor, or diff, send it
to Grug. The command is `grug`. It runs a fresh headless process and sees
only what you pipe in.

```bash
grug <<'EOF_MATERIAL'
TASK: …
CONSTRAINTS: …
CHANGE: files, behaviour, and what it refuses to touch
EOF_MATERIAL
```

Write the material out in full. Wait for the verdict. Do not substitute a
self-critique. While you are the one writing the code, still keep the change
small and inside the task. The command is the independent pass.

- `ENOUGH` — continue
- `SMALLER` — cut the complexity or the extra scope, then continue
- `REFUSE` — stop; this is a different change from the task

Grug does not investigate the repository or implement the cut. A pass already
inside Grug must not call `grug` again.

Stay out when there is no concrete code yet: greenfield design,
architecture-only discussion, or a throwaway spike. The moment the work
anchors to code that will change, send it.

The command reviews with a capable model on a provider other than the one
that called it. A provider that is out of budget is skipped. The caller's
provider is used only after that, and only at that provider's capable model,
not a lesser model that made the call. `GRUG_ENGINE` forces one provider.
`grug --prompt` prints the review prompt and runs no engine.
