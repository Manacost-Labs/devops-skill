# Tunnel configuration and route recovery

## Establish ownership and healthy capacity

Confirm account, tunnel UUID, tunnel type/configuration source, public hostname or private route, DNS record ID, ingress rules, origin endpoint and connector inventory. Distinguish remotely managed (`config_src=cloudflare`) from locally managed configuration. The remote configuration API cannot be treated as the source of truth for a local YAML file. Keep connector credentials/tokens outside snapshots and command arguments.

Record connector IDs, actual cloudflared versions, health, placement and failure domains. Multiple connections from one process are not independent connector redundancy. Establish remaining capacity and a tested administrator path before a change. Distinguish tunnel connectivity from connector-to-origin reachability, Access denial and application failure; a healthy tunnel does not prove its origin works.

For local files, validate the full ingress configuration with the installed cloudflared version and test rule matching for each approved URL before reload/restart by the host/container owner. Rules match in order and require a terminal catch-all, preferably a non-exposing `http_status:404`. A broad earlier hostname/path rule can shadow the intended narrow rule. Preserve origin TLS identity/trust and per-rule settings; never use `noTLSVerify` or a public origin as a repair shortcut.

## Stage independent effects

Remote configuration changes, connector updates, DNS routes and private routes are separate objects, with separate acceptance and recovery. Snapshot exact versions and full ingress order plus route/DNS state. A remote configuration version records control-plane configuration; confirm the running connectors received/serve it with their available logs/status and live requests. Do not invent a universal connector acknowledgement field or atomic version precondition.

Coordinate one writer across API/dashboard/IaC/host configuration. Re-read the exact remote version or local file digest immediately before the approved write. Upgrade a connector independently of changing routing unless the joint change is explicitly reviewed; pin the candidate binary/image version and retain the compatible former configuration/binary through its owner. Verify a canary connector first where the topology can isolate its traffic; a random shared tunnel request cannot prove which connector served it.

Prepare a healthy upstream before changing ingress; verify it privately. Validate/install ingress, observe the connector/origin path and only then activate the exact DNS/private route when required. Keep the old healthy route/origin through the measured propagation and connection-drain window. A local config validation is not a provider propagation test.

## Reconcile and restore

On a timeout or partial rollout, freeze further route and connector changes. Record each connector as old/new/unknown, each configuration version, DNS/proxy state and private route. Do not restart every connector to force convergence. If configuration changed but DNS did not, retain the functioning path while deciding a bounded resume or compensating change. If DNS changed but the connector/origin path is unhealthy, restore only the owned exact route after comparing the current post-change fingerprint.

Restoring the former remote ingress produces a new control-plane version; for local config, the host owner validates the exact compatible file and reloads it. Recheck healthy connectors, intended and unmatched host/path cases, origin health, Access allow/deny, authoritative and recursive DNS where relevant, plus direct-origin denial. Tunnel token rotation, host firewall changes and private-network routing require their respective owners and cannot be reversed by an ingress snapshot.

Official behavior: [Tunnel](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/), [local configuration](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/do-more-with-tunnels/local-management/configuration-file/), [remote configurations API](https://developers.cloudflare.com/api/resources/zero_trust/subresources/tunnels/subresources/cloudflared/subresources/configurations/).
