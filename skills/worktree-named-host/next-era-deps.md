# Next-era deps

Next era (`speckle-next`) has its own Postgres, Valkey, and Garage. App era
keeps `5432`, `6379`, and `9000`. Reach this file from `SKILL.md` when a next
checkout runs a local server, or when project `speckle-next` is still
published on `5432`.

Run compose from the **next main checkout**, so the project name stays
`speckle-next` and the volume stays `speckle-next_postgres-data`. A worktree
directory becomes a new project and an empty volume.

```bash
docker compose \
  -f docker-compose-deps.yml \
  -f <this skill's dir>/compose.next-era.yml \
  up -d postgres redis garage
docker compose \
  -f docker-compose-deps.yml \
  -f <this skill's dir>/compose.next-era.yml \
  run --rm garage-init
```

`up` those three services. Nginx, Authentik, Azurite, the region databases,
maildev, and telemetry stay down. Mail stays on the app era's `1025` / `1080`.
`garage-init` reaches Garage on the compose network and puts CORS on the bucket.

Done when `docker ps` shows project `speckle-next`, working directory the
next main checkout, host ports `5433`, `6380`, and `9001`, and the app era
still on `5432`, `6379`, and `9000`. Labels: `com.docker.compose.project` and
`com.docker.compose.project.working_dir`.

## URLs

Every next checkout that starts a server carries the next-era URLs. Write
them in the next main checkout's `packages/server/mise.local.toml` so
`post-checkout` seeds a worktree that does not have the file yet, and merge
them into a worktree that already has one. Frontend-only work sets none of
these. Leave the committed `mise.toml` on `5432`.

```toml
POSTGRES_URL = "postgres://speckle:speckle@127.0.0.1:5433/speckle"
REDIS_URL = "redis://127.0.0.1:6380"
S3_ENDPOINT = "http://127.0.0.1:9001"
```

`MULTI_REGION_CONFIG_PATH` unset: `POSTGRES_URL` is the database. Set: the
server ignores `POSTGRES_URL` and reads the JSON, so that file's URIs point
at this project.

A package whose own `mise.toml` sets a Postgres, Redis, or S3 URL needs the
same hosts in that package's `mise.local.toml` before the process starts.
`preview-service` sets `REDIS_URL`.

Server tests stay on the default test URL and `speckle2_test`. Leave
`mise.test.local.toml` alone unless this checkout is the one running tests.
That run shares `speckle2_test` on `5432` with the app era.

## Job cluster

Next's Garage file publishes `9000` twice. The second publish is the local
job cluster, via `MINIO_BIND_ADDRESS`. `compose.next-era.yml` replaces both
with `9001`. A checkout that uses the job cluster adds that second publish
back on `9001` in a further compose file passed after `compose.next-era.yml`.
Leave the shared file as it is.

## App era already up

When `speckle-next` is the project on `5432`, run the same `up` from the next
main checkout. Same project, same volume, next-era host ports. Then start the
app era with `pnpm dev:docker:up` from its main checkout. `down -v` drops the
volume. An ordinary `up` does not.
