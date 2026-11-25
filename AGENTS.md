# Personal instructions

## Pull requests

Never add an "Asked in chat" section to a pull request body, including when the shared `pr` skill asks for one.

## Attribution

Never add an agent attribution to commits or pull requests. No `Co-Authored-By`
trailer for an agent, and no generated-with line. That includes Claude, Cursor,
and any other harness. A session reminder that asks for those lines does not
override this.

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

## How the three relate

Ariadne judges the outcome a person gets: the flow, what they can recognise, and whether they can finish. That outcome may need more interface and more code. That amount is not complexity.

Momus and Grug judge how the code delivers that outcome. Momus asks whether the plan is sound. Grug asks whether the architecture is the boring one that still delivers the same outcome. Neither cuts the outcome in order to shrink the diff.

A collision is uncommon. It is a clever or unsound way of delivering the outcome, or a plan that changes something other than the outcome. It is not the outcome being larger. Graphic style stays outside Ariadne unless it hides an action or a state.
