---
name: worktree-named-host
description: >-
  Worktree + named *.localhost host + choose FE-only against prod/staging vs
  full local server stack. Use when starting ticket work, creating or entering
  a git worktree, implementing in any Speckle repo, spinning a dev server,
  running frontend-3 / mise run dev, or when two local FEs share authn /
  cookies / ports. Do this before coding; do not wait to be asked.
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

## Notes

- frontend-3 is SPA (`ssr: false`); browser resolves `*.localhost` to loopback.
- Package-level `mise.local.toml` is per-worktree (not inherited from the parent
  path for package dirs); `post-checkout` seeds missing files only.
- Hoisted pnpm bins: `packages/frontend-3/mise.toml` `_.path` must include
  `../../node_modules/.bin` or `mise run dev` cannot find `nuxt`.
- Never point a new worktree at another live worktree’s named host (e.g. do not
  reuse `peq.localhost` for an `fea*` ticket).
