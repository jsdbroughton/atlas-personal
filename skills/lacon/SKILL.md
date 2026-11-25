---
name: lacon
description: >-
  Independent pass on reply length. Use when the reader asks for the short
  form, invokes lacon, or asks to cut a draft. One ask covers that reply.
  Leave it on for later replies only when they say so. While it is on, pipe
  a draft of more than a sentence or two to the `lacon` command and wait for
  ENOUGH, CUT, or OPEN. Lacon cuts sentences. It does not judge the plan,
  the outcome, or the code.
---

# Lacon

Lacon is the second mind on a reply. The failure is a sentence the reader
could have written, or one that answers a question they did not ask.

When this pass was asked for, send the draft to Lacon before a reply of
more than a sentence or two. The command is `lacon`. It runs a fresh
headless process and sees only what you pipe in.

```bash
lacon <<'EOF_MATERIAL'
ASK: …
DRAFT: …
EOF_MATERIAL
```

Write the material out in full. Wait for the verdict. Do not substitute a
self-critique.

- `ENOUGH` — send it
- `CUT` — delete the named sentences, then send
- `OPEN` — the reader asked for the long form; send it

One ask covers that reply. Later replies stay on only when the reader says
to leave it on, and stop when they turn it off. A request for the detail,
or to be walked through it, skips this pass for that reply.

Lacon does not investigate, rewrite the draft, or drop a fact the reader
needs. A file, a diff, or a draft they asked for stays whole. Cut the chat
around it. Correctness is Momus. The outcome is Ariadne. The code is Grug.

The command reviews with a capable model on a provider other than the one
that called it. A provider that is out of budget is skipped. The caller's
provider is used only after that, and only at that provider's capable model.
`LACON_ENGINE` forces one provider. `lacon --prompt` prints the review
prompt and runs no engine.
