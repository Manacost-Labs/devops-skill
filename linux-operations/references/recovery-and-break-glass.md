# Recovery and break-glass

Recovery must preserve a management path and narrow the blast radius.

- Config failure: restore the saved known-good file, validate it, reload the smallest affected service, then verify.
- Service failure: collect status and recent logs; restart only after determining whether a restart risks data loss or hides evidence.
- Disk pressure: identify ownership, safely rotate approved logs or remove only explicitly approved disposable artifacts, then confirm disk and inode recovery.
- Network/SSH failure: use the provider console or existing second session; do not make further remote access changes from an unverified path.
- Reboot: require explicit approval, pre-check pending work and service restart behavior, confirm console path, then verify boot, SSH, critical units, and time sync.

Database recovery and persistent-volume recovery belong to `data-resilience-operations`; edge outages belong to `network-edge-operations`.