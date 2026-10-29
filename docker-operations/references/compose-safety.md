# Compose safety

Preflight must establish the intended image, service owner, stateful mounts, ports, healthcheck, dependencies, and rollback revision.

Production defaults:

- Pin every service image by digest where possible; reject `latest`.
- Prefer named networks and internal-only service ports. Public ingress belongs to `network-edge-operations`.
- Require a healthcheck for services that can expose one.
- Treat `volumes`, bind mounts, and database directories as state. Verify recovery before destructive changes.
- Reject literal secrets, `privileged: true`, `network_mode: host`, Docker socket mounts, and broad capabilities unless explicitly justified and approved.
- Use `docker compose config` and this module's preflight before `up`. Review exact ordered files, project name/directory, profiles, interpolated environment, effective limits and resolved mount identities locally; rendering can expose secrets.

The preflight is a static advisory check, not a Compose schema validator, authorization gate or daemon/data compatibility test. Inspect the actual admitted/runtime state after change. A startup dependency order or healthy dependency does not prove ongoing application readiness.

Read `references/rollback.md` before selecting a rollout or reversal. Pin the old and new artifacts, verify all writers/migrations and the old/new data compatibility matrix. Narrow service selection and dependency options must be reviewed: changing one service can still recreate dependencies or invoke initialization work. Never select an empty new volume to make an incompatible release start.
