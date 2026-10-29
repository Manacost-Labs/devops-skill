# Access and security

Separate transport, host identity, authentication, account policy, discretionary access and SELinux/AppArmor denial. Preserve an operator session and independently proven recovery before access changes.

## SSH/sudo/local identity

Confirm version, service/socket identity and effective configuration. `sshd -t` validates syntax; `sshd -T` alone misses conditional Match behavior. Use reviewed `-C` context for actual user/source/host when supported. Neither replaces a new login test.

Check key/home ownership, account expiry, allowed groups, PAM/central identity and narrow auth logs. Do not publish private keys, authorized-key comments or identity databases. Verify public-key login and required sudo from a new session before tightening access. Confirm host fingerprints through a trusted channel, never disable host-key checking.

Separate local from SSSD/AD/LDAP ownership. Review exact sudo scope; writable scripts and shell escapes can grant root. Validate candidate setup with visudo. Compose privileged access/rotation/revocation with secrets-access. Revoking the final operator without recovery blocks the change.

## SELinux/AppArmor

Identify enforcement/profile and correlate the denial with the failed operation. For SELinux inspect scoped AVC evidence, contexts, labels, mount and expected service path. Rule out ordinary ownership/ACL first. Preview `restorecon -n` on the exact path; persistent mappings require a reviewed change. Do not use chcon as permanent configuration, disable enforcement or blindly generate audit2allow policy.

For AppArmor match denial, loaded profile, executable path and intended resource. Propose minimal permissions, then verify permitted and forbidden behavior. Do not globally switch profiles to complain mode. Redact sensitive denial content.

## Hardening

Identify owner requirements before removing services or applying benchmarks/sysctls. Test compatibility on a canary, stage access-sensitive controls separately and retain rollback. Scanner output is evidence to assess, not authority to mutate. Route control exceptions to security/compliance; an audit cannot certify a host secure.

Sources: [OpenSSH](https://www.openssh.org/manual.html), [SELinux](https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/9/html/using_selinux/index), [Ubuntu AppArmor](https://documentation.ubuntu.com/server/how-to/security/apparmor/), [sudoers](https://www.sudo.ws/docs/man/sudoers.man/).
