# SSH access and hardening

## Before changing remote access

- Confirm hostname/IP and environment; production targets require R3 approval.
- Keep the current session open and establish a second verified session or provider console path.
- Record current effective settings with `sshd -T`; configuration may be split across `sshd_config.d`.
- Know the intended operator account, public key source, management port, source network, and rollback command.

## Safe sequence

1. Add the new public key with restrictive permissions.
2. Verify authentication in a new session.
3. Make the smallest configuration change in a dedicated snippet where the distribution supports it.
4. Run `sshd -t` before reload.
5. Reload, do not restart, SSH when possible.
6. Verify both the new policy and a current authorized access path.

Never disable password authentication or root login before the key-based path is proven. Do not turn off host-key checking. Do not copy private keys onto the host.