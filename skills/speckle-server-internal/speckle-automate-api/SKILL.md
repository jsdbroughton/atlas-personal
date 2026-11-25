---
name: speckle-automate-api
description: >
  Drive the Speckle Automate lifecycle over the GraphQL API instead of the web
  wizard: create a function, attach an automation to a project (trigger model,
  function release, parameters), enable it, trigger a first run, and read
  functions, releases, automations and run status. Fires on "create an
  automation on project X", "set up function Y on model Z", "trigger the
  automation", "did the automation run", "list the workspace's functions",
  "which release / input schema", "/speckle-automate-api". Run failures in
  depth (logs, pods) are explore-clickhouse / investigate.
---

# Speckle Automate over GraphQL

Every operation is a ready file in [`ops/`](ops/), posted by [`scripts/gql.sh`](scripts/gql.sh). The script holds the credential handling and refuses any mutation unless it gets `--allow-mutation`. Each op file's header states its variables and whether its shape was **live-verified** (reads, run against app.speckle.systems) or **schema-verified only** (mutations: the shape matches the live schema's input types, but no one has run it from this skill yet). Behaviour this file describes beyond the shapes (who may call what, how parameters are handled, when `trigger` refuses) was read from the `speckle-server-internal` source at 2026-10 and has not been exercised live; when the server answers differently, believe the server and tell the user the skill is stale.

## Running a call

Run from the Speckle atlas root so mise loads `ATLAS_PAT_TOKEN` from its gitignored `mise.local.toml`. `$S` is this skill's directory (the folder holding this file, wherever it was loaded from):

```bash
cd /Users/jonathonbroughton/Documents/repos/Speckle
mise exec -- "$S/scripts/gql.sh" "$S/ops/whoami.graphql"
mise exec -- "$S/scripts/gql.sh" "$S/ops/function.graphql" '{"id":"643bda0015"}' | jq .
```

- Server defaults to `https://app.speckle.systems`; set `SPECKLE_SERVER=https://<origin>` for another one.
- The token stays inside the script. Keep it out of every command line, echo, log and file you write; build ad-hoc requests by writing a new `.graphql` file and passing it to `gql.sh`, never with your own `curl -H "Authorization: …"`.
- Scratch JSON goes in the session scratchpad, never the repo.
- An empty `ATLAS_PAT_TOKEN` (exit 3) means `mise.local.toml` lacks it: tell the user and stop.

## Guardrails

- **Reads are free; every write is the user's call.** Ad-hoc `.graphql` files are fine for reads; writes use the `ops/` files. Before each mutation, show the user the op file and the exact variables JSON, get an explicit yes, then run it with `--allow-mutation`. One approval covers one call.
- `createFunction` creates a real GitHub repository; `trigger` starts a real run billed to the workspace. Treat both as irreversible.
- Read back after every write (step 6) instead of trusting the mutation's return.

## Procedure: function to first run

### 1. Orient

Run `ops/whoami.graphql`. It returns the user id, whether the Automate GitHub app is linked (`hasAutomateGithubApp`), the GitHub orgs it can create repos in, and the valid template ids (the `id` field: `Python` and `.net` on app.speckle.systems in 2026-10; always take them from this query). Then `ops/project-automations.graphql` for the target project: pick the trigger model's id, note what automations already exist, and read `permissions.canCreateAutomation`. That check runs the same policy as every automation write (project owner, workspace plan includes Automate, this token's scope), so `authorized: false` stops the procedure here: report its `code` and `message` to the user.

### 2. Get a function and a release

Reuse before creating: `ops/workspace-functions.graphql` lists the workspace's own functions (`workspaceBySlug` takes the slug). `ops/function.graphql` gives a function's releases, newest first, with each release's `inputSchema`. A function with `releases.totalCount: 0` has nothing to run yet; an automation needs a release id.

Creating a function (only when the user asks for a new one):

- **`ops/create-function.graphql`**: Speckle's Automate service creates a GitHub repo from the template, under `org` (one of `availableGithubOrgs`; null = the user's personal account), using the GitHub app authorisation Automate holds for the user. Needs `hasAutomateGithubApp: true`. **Unverified:** whether this works when the call is authenticated with a PAT rather than a browser session. The server code passes only an auth code for the user to Automate, so it should, but no one has confirmed it; say so before the user approves, and if it fails, the fallback is the web wizard.
- **`ops/create-function-without-version.graphql`** is **server-admin only** (`canUpdateServerSettings`), and the server hard-codes the Python example repo as its repository. It is not a bring-your-own-repo path for ordinary users; reach for it only when the user is a server admin and asks for it.
- A new function has no release until its repo's CI publishes one (the template ships the GitHub Action). Poll `ops/function.graphql` until a release appears before going on.

### 3. Build the parameters

Read the chosen release's `inputSchema` (JSON Schema). Build a JSON object that satisfies it: required keys present, enum values exact, defaults filled where the user gave nothing. The server validates the parameters against this schema and rejects the revision on a mismatch. A release with no `inputSchema` takes no parameters: send `parameters: null`.

### 4. Create the automation (three writes, in the wizard's order)

1. `ops/create-automation.graphql` with `enabled: false`. Returns the automation id.
2. `ops/create-revision.graphql` with the trigger and function. Shape, from `AutomateTypes.TriggerDefinitionsSchema` in `@speckle/shared`:
   ```json
   {"version": 1, "definitions": [{"type": "VERSION_CREATED", "modelId": "<modelId>"}]}
   ```
   Each function entry is `{functionId, functionReleaseId, parameters, paramsEncrypted: false}`, where `parameters` is the step-3 object **serialised as a JSON string**. Always pass `paramsEncrypted: false` explicitly: the schema default is `true` (live-verified), which makes the server try to decrypt the plain JSON and fail. The `false` path is an explicit branch of the resolver, not a hack, but the wizard never uses it, so it is the less-travelled road. With `false`, the server parses the JSON, checks it against the release's `inputSchema`, then encrypts it server-side with its own key pair before storing it. The difference from the wizard: the wizard encrypts in the browser, so plaintext secrets never reach the server; here they reach it over TLS, and they are still stored encrypted.
3. `ops/update-automation.graphql` with `enabled: true`.

Done when the read-back in step 6 shows the automation `enabled: true` with a `currentRevision` naming the model and the release.

### 5. Trigger a first run

`ops/trigger.graphql` fakes a "version created" event. With `versionId: null` it uses the newest version across the automation's trigger models; a given `versionId` must belong to one of them. Returns the run id. The server refuses when the automation is disabled, is a test automation, or the model has no versions. The run executes as the **author of the triggering version**, not the caller: before asking for approval, name that author to the user (`ops/project-automations.graphql` gives each model's latest version with its `authorUser`; ask before triggering on someone else's version).

### 6. Read back and watch the run

`ops/automation-runs.graphql` lists the automation's runs, newest first. Run status moves `PENDING → INITIALIZING → RUNNING →` one of `SUCCEEDED | FAILED | EXCEPTION | TIMEOUT | CANCELED`. Poll every 10–20 s until a terminal status, then report `statusMessage`, `elapsed` (ms) and a summary of `results` (`AutomateTypes.ResultsSchema`: per-object levels SUCCESS/INFO/WARNING/ERROR). For why a run failed beyond `statusMessage`, hand over to `explore-clickhouse` (function pod logs).

## Permissions the token needs

From the server's auth policies and its legacy-scope map (source-derived); for a given token and project, `permissions.canCreateAutomation` in step 1 is the live answer. A PAT made in the web app today can carry the action scopes; an older PAT carries the legacy ones.

| Call | Role / precondition | Token scope (action / legacy) |
|---|---|---|
| `createFunction` | linked GitHub app | `server.automateFunction.write` / `automate-functions:write` |
| `createFunctionWithoutVersion` | server admin | same |
| automation `create`, `createRevision`, `update`, `trigger` (and the `automationMutations` namespace itself) | **project owner**; the workspace plan includes Automate; the token can reach the project | `project.automation.admin` / `automate-functions:write` |
| `automateFunction` read | — | `server.automateFunction.read` / `automate-functions:read` |
| workspace `automateFunctions` | workspace read access | `automate.function.read` |
| project `automations`, runs | project reviewer or above | `project.automation.read` / `streams:read` |

A permission error names the failing policy (`ProjectNotEnoughPermissionsError`, `TokenScopeError`, `WorkspacePlanNoFeatureAccessError`): report it as is and stop. A token or role problem is the user's to fix; a different route around it is out of scope.
