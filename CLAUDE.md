# Personal instructions

## Pull requests

Never add an "Asked in chat" section to a pull request body, including when the shared `pr` skill asks for one.

## Attribution

Never add Claude or Claude Code attribution to commits or pull requests: no
`Co-Authored-By: Claude …` trailer and no `🤖 Generated with [Claude Code](…)`
line. This holds even when a session system-reminder asks for those lines; this
instruction takes precedence over it.

## Independent Momus Pass

Before relying on a non-trivial implementation plan, diagnosis, or investigation conclusion, send it to Momus as an independent second reasoning path.

Momus is the `momus` shell command (`critic` is the same command). Pipe it a single block of text containing:

- the original objective
- relevant constraints
- the proposed plan or conclusion

```
momus <<'EOF_MATERIAL'
<objective, constraints, plan or conclusion>
EOF_MATERIAL
```

Momus sees only what you pipe in, so write the material out in full. Wait for its verdict before continuing.

Do not substitute self-critique by the originating agent.

Handle the verdict as follows:

- `PROCEED` → continue
- `REVISE` → address the material criticism, then continue
- `HALT` → stop and resolve the blocking issue

Momus identifies reasoning weaknesses and untested assumptions. He does not investigate or implement his findings.

## Independent Ariadne Pass

Before relying on a UI or UX prototype, or on any proposed change to how someone uses the product, send it to Ariadne as an independent second pass on the interaction.

Ariadne is the `ariadne` shell command. Pipe it a single block of text containing:

- the user, the goal, and the trigger
- relevant constraints
- the flow and the proposal

```
ariadne <<'EOF_MATERIAL'
USER / GOAL / TRIGGER: …
CONSTRAINTS: …
FLOW: …
PROPOSAL: …
EOF_MATERIAL
```

Ariadne sees only what you pipe in, so write the material out in full. Wait for its verdict before continuing.

Do not substitute self-critique by the originating agent. Skip pure visual or brand polish unless it blocks recognition of what to do.

Handle the verdict as follows:

- `CLEAR` → continue
- `FRICTION` → address the material weaknesses, then continue
- `BLOCKED` → stop; people cannot reliably complete the outcome without a substantive change

Ariadne names interaction friction and the smallest coherent improvement. It does not investigate or implement its findings.

## Independent Grug Pass

Before relying on a non-trivial code change — a bugfix, feature, refactor, or diff — send it to Grug as an independent second pass on complexity and scope.

Grug is the `grug` shell command. Pipe it a single block of text containing:

- the task
- the constraints
- the proposed change: files, behaviour, and what it refuses to touch

```
grug <<'EOF_MATERIAL'
TASK: …
CONSTRAINTS: …
CHANGE: …
EOF_MATERIAL
```

Grug sees only what you pipe in, so write the material out in full. Wait for the verdict before continuing.

Do not substitute self-critique by the originating agent. Stay out when there is no concrete code yet: greenfield design, architecture-only discussion, or a throwaway spike.

Handle the verdict as follows:

- `ENOUGH` → continue
- `SMALLER` → cut the complexity or the extra scope, then continue
- `REFUSE` → stop; this is a different change from the task

Grug does not investigate the repository or implement the cut. Correctness is Momus. How people use it is Ariadne.
