---
name: worktree-named-host
description: >-
  Worktree + named *.localhost host + choose FE-only against prod/staging vs
  full local server stack. Use when starting ticket work, creating or entering
  a git worktree, implementing in any Speckle repo, spinning a dev server,
  running frontend-3 / mise run dev, or ending that session. Close down
  leaves the worktree to resume later. Close down and clean up removes it
  because the work is done. Do the setup before coding; do not wait to be
  asked.
---

# Worktree named host

Standing prelude for ticket work. Shared `implement` / `ways-of-working`
already require a worktree; this skill adds the named FE host so concurrent
worktrees do not share the `authn` cookie (host-scoped, not port-scoped), and
picks **FE-only → remote API** vs **full local stack**.

## Steps

1. **Worktree.** If the session is not already inside `<repo>/.worktrees/<name>`,
   create one per `atlas/ways-of-working.md` § Worktrees
   (`mkdir -p .worktrees`, self-ignore, `git worktree add --no-track -b <user>/<name>
   .worktrees/<name> origin/<base>`, `mise trust`, `mise run post-checkout` when
   the repo defines it). Done when cwd is that worktree on branch `<user>/<name>`
   and `git status -sb` does not show `...origin/<base>`.

2. **Named host (only when `packages/frontend-3` exists).** Pick a short DNS
   label from the ticket slug (lowercase, no dots), unique among running
   worktrees — e.g. `fea799`, `peq`. Browse host is `<short>.localhost`.
   Never reuse another live worktree’s host. Write or merge
   `packages/frontend-3/mise.local.toml` (gitignored `*.local.toml`; seed may
   have copied secrets from the main checkout — keep those, only set the keys
   below).

3. **Choose backend mode (before ports).** Pick from the ticket scope; if
   unclear, ask once: “FE against staging/prod, or full local stack?”

   | Mode | When |
   | --- | --- |
   | **FE-only → remote** | Change is frontend-3 / viewer UI only; no server, GraphQL schema, migration, or worker work in the ticket; need real projects/models/auth that local seed won’t match cheaply. Prefer staging when prod risk or unreleased API; use prod (`https://app.speckle.systems`) when that is the house pattern for FE spikes. |
   | **Full local stack** | Ticket touches `packages/server` (or a shared API contract the FE must call); need migrations, local feature flags, queues, multi-region, importers; debugging auth / CORS / same-origin / nginx; offline or must not hit remote. |

   Defaults: pure UI ticket → **FE-only → remote**. Any server file in scope →
   **full local stack**.

4. **Port + `mise.local.toml` for that mode.**

   - **FE-only → remote:** set `HOST` / browse via `<short>.localhost`; set
     `PORT` to a free port (prefer `3030+`, confirm with `lsof`); set
     `NUXT_PUBLIC_BASE_URL` to `http://<short>.localhost:<PORT>`; set
     `NUXT_PUBLIC_API_ORIGIN` to the remote (`https://app.speckle.systems` or
     staging). Do **not** start `mise run dev:server` unless asked. Do **not**
     steal another worktree’s `:8081` / nginx ingress.
   - **Full local stack:** same-origin via docker nginx ingress on `:8080`:
     set both `NUXT_PUBLIC_BASE_URL` and `NUXT_PUBLIC_API_ORIGIN` to
     `http://<short>.localhost:8080`. Leave Nuxt `PORT` at `8081` unless taken
     — then pick a free port and say so. Ingress has no `server_name` gate;
     Host header must reach Vite (next step). Start deps +
     `mise run dev:server` and `mise run dev:frontend-3` (or equivalent).

   Done when no other listener owns the chosen FE port and the keys match the
   mode. Hand-back URL uses `<short>.localhost`, never bare `127.0.0.1`.

5. **Vite `allowedHosts`.** In `packages/frontend-3/nuxt.config.ts`, ensure
   the `NUXT_PUBLIC_BASE_URL` hostname is allowed. Prefer the `baseUrlHost`
   helper that appends `new URL(process.env.NUXT_PUBLIC_BASE_URL).hostname` to
   `vite.server.allowedHosts` alongside `zog.local` / `zog.localhost`. If that
   pattern is missing, add it (do not hardcode one ticket's host). Done when
   a `mise run` / Nuxt boot with the new `BASE_URL` does not reject the Host.

6. **Hand-back.** Tell the human the browse URL (`http://<short>.localhost:…`),
   the API target (remote host or local stack), not `127.0.0.1`. Re-login once
   on that host.

## Two ways to stop

Both modes stop this worktree’s processes and leave every other worktree
alone, including the shared `:8080` ingress, Postgres, and Redis. They
differ in what remains on disk.

**Close down** — another session will pick this up. Stop processes only.
Keep the worktree, the branch, uncommitted work, and `mise.local.toml`. The
short host stays reserved for this worktree.

**Close down and clean up** — the work is done. Stop processes, then remove
the worktree. Do not do this when the user only asked to close down.

### Stop processes

1. Stop the background `mise run` and any monitor or loop attached to this
   worktree. A stopped wrapper is not a stopped server.
2. Find processes whose cwd is inside this worktree, including `ppid` 1:
   `nuxt dev`, `nodemon` / `run.ts`, and `graphql-codegen --watch`. Match the
   FE by the `PORT` in this worktree’s `packages/frontend-3/mise.local.toml`,
   and the API by the server port that `mise run dev:server` bound. Stop
   those pids. Do not kill a listener whose cwd is a different worktree.
3. Confirm the FE port and the API port for this worktree are free. Shared
   `:8080` may still answer.

For **close down**, hand back the worktree path, branch, named host, and
whether the tree is dirty. Do not remove anything else.

### Clean up

After the stop, and only in **close down and clean up**:

1. From the main checkout, `git worktree remove` that path. If it refuses
   because of uncommitted work, stop and show the status. Do not force it.
2. Do not delete the branch if it has commits that are not on its upstream.
   Say that and leave the branch. The short host is free for another
   worktree once this one is gone.
3. Do not remove any other worktree. `mise.local.toml` goes away with the
   worktree directory.

## Notes

- frontend-3 is SPA (`ssr: false`); browser resolves `*.localhost` to loopback.
- Package-level `mise.local.toml` is per-worktree (not inherited from the parent
  path for package dirs); `post-checkout` seeds missing files only.
- Hoisted pnpm bins: `packages/frontend-3/mise.toml` `_.path` must include
  `../../node_modules/.bin` or `mise run dev` cannot find `nuxt`.
- Never point a new worktree at another live worktree’s named host (e.g. do not
  reuse `peq.localhost` for an `fea*` ticket).
