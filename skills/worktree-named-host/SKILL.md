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
   | **FE-only → running local server** | Same FE-only scope, but local data or a local feature flag is needed, and a local server of the **same era** is already up (usually `:3000`, or another worktree's alternative API port). Point at it rather than starting another. |
   | **Full local stack** | Ticket touches `packages/server` (or a shared API contract the FE must call); need migrations, local feature flags, queues, multi-region, importers; debugging auth / CORS / same-origin / nginx; offline or must not hit remote. |
   | **Full local stack on alternative ports** | Full local stack is needed, but another worktree (in this repo or `speckle-next`) already holds `:8081` or `:3000` behind the shared `:8080` ingress. Several features in flight at once is the normal case, so check before you pick plain full local stack. |

   Defaults: pure UI ticket → **FE-only**, against a remote or an
   already-running local server. Never start a server for a frontend-only
   ticket. Any server file in scope → **full local stack**, on alternative
   ports when the ingress backends are taken.

   **Server era is the only thing that must match.** A frontend can share any
   server of its own era, but never a server of the other era:
   - **App era:** `speckle-server-internal`, app.speckle.systems and its
     staging. Its frontend-3 talks to app-era servers only.
   - **Next era:** `speckle-next`, next.speckle.systems. Its frontend-3 talks
     to next-era servers only.

   The schemas differ (for example, next has no `insights` and app has no
   Workflows), so a cross-era pairing boots but breaks on the first query.
   To find a local listener's era, check which repo its process runs from:
   `lsof -a -p <pid> -d cwd` shows a path under `speckle-server-internal/`
   or `speckle-next/`. Do this before reusing `:3000`, because it often
   belongs to a next worktree.

4. **Port + `mise.local.toml` for that mode.**

   - **FE-only → remote:** set `HOST = "<short>.localhost"`. Set `PORT` to a
     free `8xxx` port (`8082+`) that no other worktree's
     `packages/frontend-3/mise.local.toml` sets, and confirm it with `lsof`.
     Set `NUXT_PUBLIC_BASE_URL` to `http://<short>.localhost:<PORT>` and
     `NUXT_PUBLIC_API_ORIGIN` to the remote of this repo's era. Do **not**
     start `mise run dev:server` unless asked. Do **not** take another
     worktree's `:8081` or the nginx ingress.
   - **FE-only → running local server:** set up the frontend as for remote,
     but point `NUXT_PUBLIC_API_ORIGIN` at the running server, for example
     `http://<short>.localhost:3000` or another worktree's API port, after
     checking it is the same era. Don't restart that server or change its
     config, because it belongs to another worktree. The server allows any
     origin for CORS, so API calls work from your host. The catch is sign-in.
     The server sends the post-login redirect to its own `FRONTEND_ORIGIN`,
     which is the owning worktree's frontend. Sign in there once, or use a
     token. If that gets in the way, switch to FE-only → remote.
   - **Full local stack:** same-origin via docker nginx ingress on `:8080`:
     set both `NUXT_PUBLIC_BASE_URL` and `NUXT_PUBLIC_API_ORIGIN` to
     `http://<short>.localhost:8080`. Leave Nuxt `PORT` at `8081` unless taken
     — then pick a free port and say so. Ingress has no `server_name` gate;
     Host header must reach Vite (next step). Start deps +
     `mise run dev:server` and `mise run dev:frontend-3` (or equivalent).

   - **Full local stack on alternative ports:** use this when the shared
     ingress is busy. Docker nginx on `:8080` (`lsof` shows it as colima's
     `ssh` mux) proxies to whatever is listening on the host's `:8081` (FE)
     and `:3000` (API). If another worktree owns either one, possibly in a
     different repo (`speckle-next` uses the same ports), then
     `<short>.localhost:8080` reaches *that* worktree's stack. Check the
     owner with `lsof -a -p <pid> -d cwd`. Skip the ingress, and pick:
     - an FE port in the `8xxx` range (`8082+`), free and not set as `PORT` in
       any other worktree's `packages/frontend-3/mise.local.toml`
     - a free API port (`3001+`)

     In `packages/frontend-3/mise.local.toml`, set `HOST = "<short>.localhost"`,
     `PORT` (FE port), `NUXT_PUBLIC_BASE_URL = "http://<short>.localhost:<fe>"`
     and `NUXT_PUBLIC_API_ORIGIN = "http://<short>.localhost:<api>"`.

     In `packages/server/mise.local.toml`, set `PORT` (API port),
     `CANONICAL_URL = "http://<short>.localhost:<api>"` and
     `FRONTEND_ORIGIN = "http://<short>.localhost:<fe>"`. These override the
     repo-root `127.0.0.1:8080` defaults for this worktree only.

     Postgres, Redis, object storage and maildev stay shared, so start only
     `dev:server` and `dev:frontend-3`. When the FE port changes, update
     `FRONTEND_ORIGIN` and restart both. Check with `serverInfo { canonicalUrl }`
     on the API port.

   Done when no other listener owns the chosen FE port and the keys match the
   mode. Hand-back URL uses `<short>.localhost`, never bare `127.0.0.1`.

5. **Vite `allowedHosts`.** In `packages/frontend-3/nuxt.config.ts`, ensure
   the `NUXT_PUBLIC_BASE_URL` hostname is allowed. Prefer the `baseUrlHost`
   helper that appends `new URL(process.env.NUXT_PUBLIC_BASE_URL).hostname` to
   `vite.server.allowedHosts` alongside `zog.local` / `zog.localhost`. If that
   pattern is missing, add it (do not hardcode one ticket's host). Done when
   a `mise run` / Nuxt boot with the new `BASE_URL` does not reject the Host.
   Vite accepts `localhost` and every `*.localhost` subdomain by default, so a
   `<short>.localhost` host needs no change. Boot first, and edit
   `nuxt.config.ts` only for a host outside `.localhost` or when the boot
   reports a blocked host.

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
  `../../node_modules/.bin` or `mise run dev` cannot find `nuxt`. If the
  committed file lacks it (the error is `nuxt: command not found`), add
  `_.path = ["../../node_modules/.bin"]` under `[env]` in that package's
  gitignored `mise.local.toml` instead of editing the tracked file.
- `post-checkout` can stop at its seed step. When the main checkout has no
  `packages/server/multiregion.json`, the seed script still runs `cp` on that
  path, because `nullglob` drops only globs that match nothing, not literal
  paths. The task then fails before `mise install` and `pnpm install`. The
  repo fix was closed unmerged, so this skill carries the patched copy:
  [`scripts/seed-worktree-local-config.sh`](scripts/seed-worktree-local-config.sh),
  which is the repo script plus `[[ -e "$src" ]] || continue`. In a
  speckle-server-internal worktree, run that copy in place of the repo's seed
  step, then the rest of `post-checkout` by hand:

  ```bash
  bash <this skill's dir>/scripts/seed-worktree-local-config.sh
  mise install && pnpm install && pnpm build:public:libs && pnpm --filter @speckle/graphql-explorer build
  ```

  Running `mise run post-checkout` first is fine. When it stops at the seed
  step, the files it copied before failing stay in place, and the patched copy
  skips them. If the repo script changes upstream, diff it against this copy
  before trusting the copy. A fresh worktree also has no husky
  hooks until `pnpm install` has run.
- `graphql-codegen --watch` rewrites `packages/frontend-3/lib/common/generated/gql/*`
  from the local schema on boot. That diff is not part of the ticket. Leave
  it out of commits unless the ticket changed the schema.
- Never point a new worktree at another live worktree’s named host (e.g. do not
  reuse `peq.localhost` for an `fea*` ticket).
