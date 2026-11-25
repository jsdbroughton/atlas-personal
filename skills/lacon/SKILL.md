---
name: lacon
description: >-
  Independent Lacon pass on a reply before it is sent. Before relying on a
  draft that explains more than the question asked, pipe the ask and the
  draft to the `lacon` shell command and wait for ENOUGH, CUT, or OPEN.
  Lacon cuts sentences. It does not judge whether the plan is sound, whether
  a person can finish, or whether the code is boring. Skip a one or two
  sentence answer, and skip when the user asked to be walked through it.
---

# Lacon

Lacon is the second mind on a reply. The failure is a sentence the reader
could have written, or one that answers a question they did not ask.

Before sending a draft that explains more than the question, send it to
Lacon. The command is `lacon`. It runs a fresh headless process and sees
only what you pipe in.

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

If the reader has said an answer was too long, stay at that length until
they ask for detail, and run Lacon on the next draft.

Lacon does not investigate, rewrite the draft, or drop a fact the reader
needs. A file, a diff, or a draft they asked for stays whole. Cut the chat
around it. Correctness is Momus. The outcome is Ariadne. The code is Grug.

The command reviews with a capable model on a provider other than the one
that called it. A provider that is out of budget is skipped. The caller's
provider is used only after that, and only at that provider's capable model.
`LACON_ENGINE` forces one provider. `lacon --prompt` prints the review
prompt and runs no engine.
