# Debian/Ubuntu baseline

Use this runbook only after confirming `/etc/os-release` reports Debian or Ubuntu.

## Read-only baseline

Confirm: release and support status, kernel, hostname, virtualization, time sync, package update status, enabled services, listening ports, firewall backend, disk/inode headroom, and a verified console/break-glass route.

## Safe bootstrap order

1. Confirm provider console or a second access path.
2. Create the named non-root operator and add its supplied public key.
3. Verify a second SSH session with the new account before touching the original session.
4. Apply minimum sudo scope; avoid passwordless full `sudo` unless explicitly required.
5. Validate `/etc/ssh/sshd_config` and included snippets with `sshd -t`; only then reload SSH.
6. Define required inbound ports from actual services and owner requirements; apply a narrow UFW/nftables policy without closing the active management path.
7. Verify NTP and schedule security updates according to the owner’s maintenance policy.

Do not blanket-install “hardening” packages. Each added service increases patch and operational load.