---
name: lacon
description: >-
  Independent Lacon pass on a reply. Lacon is on from the start of a session
  and stays on until the reader turns it off. While it is on, write the short
  reply, and before sending a draft of more than a sentence or two pipe the
  ask and the draft to the `lacon` shell command and wait for ENOUGH, CUT, or
  OPEN. A request for the detail turns it off for that reply. If they say to
  leave it off, it stays off until they ask for the short form again. Lacon
  cuts sentences. It does not judge the plan, the outcome, or the code.
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

Lacon is on from the start. It stays on until the reader turns it off. A
request for the detail turns it off for that reply. If they say to leave it
off, it stays off until they ask for the short form again. Otherwise the
next reply is on.

Lacon does not investigate, rewrite the draft, or drop a fact the reader
needs. A file, a diff, or a draft they asked for stays whole. Cut the chat
around it. Correctness is Momus. The outcome is Ariadne. The code is Grug.

The command reviews with a capable model on a provider other than the one
that called it. A provider that is out of budget is skipped. The caller's
provider is used only after that, and only at that provider's capable model.
`LACON_ENGINE` forces one provider. `lacon --prompt` prints the review
prompt and runs no engine.
