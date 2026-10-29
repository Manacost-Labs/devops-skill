# Boot, kernel and recovery

Confirm host via independent console, firmware mode, boot disks, root UUID, encryption/unlock reference and known-good kernel. Do not reboot to see whether an unexplained storage/access fault disappears.

| Stage | Evidence | Decision |
|---|---|---|
| Firmware/bootloader | Console error, boot entry, disk identity | Hardware/provider owner if path missing |
| Kernel/initramfs | Panic, root driver/unlock error | Verified known-good kernel or release-specific rescue |
| Mount/emergency | Exact UUID/mount and storage health | Correct identity/dependency after data assessment |
| Services/access | Bounded boot journal, unit and listener | Repair specific owner boundary |

Previous-boot logs need persistent evidence; missing logs do not prove a clean boot. Do not publish secret-bearing kernel command lines. Rescue mounts/namespaces differ and write mounts can alter evidence.

APT/RPM boot tooling differs: update-initramfs and dracut are examples, not interchangeable commands. Verify installed tool, kernel, root drivers, boot capacity, Secure Boot and vendor procedure. Preserve known-good entries. Do not rebuild all kernels, overwrite an assumed GRUB path, remove the running kernel or disable Secure Boot incidentally.

## Reboot procedure

1. Name service dependencies, drain/window, downtime bound and abort criteria. Stateful workloads need consistency and recoverability evidence.
2. Prove console, independent credential reference, known-good entry and recovery owner availability. A second SSH session cannot recover a failed boot.
3. Record boot ID, kernel, mounts, failed units, access/service baseline and package state.
4. Execute approved reboot. On missed startup deadline use console evidence and staged recovery, not a reboot loop.
5. Verify changed boot ID, expected kernel, mounts, time sync, fresh login and user path over an observation window.

Corruption/degraded arrays require storage recovery assessment before writes. Reconcile manual rescue changes with configuration management.

Source: [RHEL kernel management](https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/9/html/managing_monitoring_and_updating_the_kernel/index); verify release-specific Debian/Ubuntu/derivative recovery docs.
