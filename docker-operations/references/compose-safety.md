# Compose safety

Preflight must establish the intended image, service owner, stateful mounts, ports, healthcheck, dependencies, and rollback revision.

Production defaults:

- Pin every service image by digest where possible; reject `latest`.
- Prefer named networks and internal-only service ports. Public ingress belongs to `network-edge-operations`.
- Require a healthcheck for services that can expose one.
- Treat `volumes`, bind mounts, and database directories as state. Verify recovery before destructive changes.
- Reject literal secrets, `privileged: true`, `network_mode: host`, Docker socket mounts, and broad capabilities unless explicitly justified and approved.
- Use `docker compose config` and this module's preflight before `up`.