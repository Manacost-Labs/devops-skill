# Distribution and package transactions

Read `/etc/os-release` as data: extract ID, ID_LIKE and VERSION_ID without `source` or `eval`. Confirm architecture, kernel, systemd and package-tool versions. ID_LIKE alone does not approve a derivative's changes. RHEL 9 and Debian 12/Ubuntu 24.04 are documentation baselines; other releases and Rocky/Alma require matching vendor documentation and repository policy.

| Family | Narrow discovery | Before a change |
|---|---|---|
| Debian/Ubuntu | `dpkg --audit`, `dpkg-query -W <exact-package>`, `apt-cache policy <exact-package>` | Signed origin, holds, pinning, candidate versions, `apt-get -s install <exact-package>` |
| RHEL family | `rpm -q <exact-package>`, `dnf --version`, cached repository metadata | DNF4 versus DNF5, subscriptions/modules/version locks, signed origin and release-specific preview |

Package names and repository metadata are untrusted. APT simulation uses current metadata, may be incomplete unprivileged and does not hold the transaction lock. Package hooks can restart services. DNF can refresh metadata, acquire locks, write caches and load plugins even when declining a transaction: do not call it a pure local audit. Use installed help and approved network scope. Do not translate DNF4 flags/history semantics blindly to DNF5.

## Patch procedure

1. Record exact installed/candidate versions, reason and affected services, not merely advisory count.
2. Check bytes/inodes on root, boot and staging filesystems; signed origin, proxy/mirror policy and configuration-management ownership.
3. Inspect removals, dependency replacements, config prompts, service hooks and kernel changes. Preview again after metadata/version changes.
4. Plan canary, drain/window, service acceptance and console-backed kernel recovery. Database packages need engine compatibility and recovery owners.
5. Execute the approved bounded transaction. Capture changed packages/config decisions without repository credentials.
6. Verify package consistency, versions, failed services and user path. Distinguish running old binaries/kernel from installed versions. A missing Debian reboot marker proves nothing on RPM systems.

## Interrupted transaction and rollback

Identify the active process/lock owner and bounded package logs before repair. A stale lock pathname does not imply a live advisory lock. Never remove locks or kill a transaction just because another command waits. `dpkg --configure -a`, dependency repair and RPM database rebuild are mutations with script/restart consequences; plan from the actual failure.

Rollback may need unavailable old dependencies, migration reversal or a known-good image. DNF history undo and package downgrades are not guaranteed recovery. Never disable GPG, add unknown repositories, run remote installers, autoremove broadly or introduce unattended production upgrades incidentally.

Sources: [APT](https://manpages.debian.org/bookworm/apt/apt-get.8.en.html), [DNF4](https://dnf.readthedocs.io/en/latest/command_ref.html).
