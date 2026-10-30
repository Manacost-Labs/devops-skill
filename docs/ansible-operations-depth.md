# Ansible operations depth

Platform 0.11.0 expands the existing `iac-operations` module to 0.4.0. It adds inventory/identity review, repeatability validation, controlled fleet rollout and partial-failure recovery. Terraform/OpenTofu and cloud-init keep their separate workflows; no additional module or production auto-deployer is introduced.

## Operating behavior

- Resolve each play's hosts with the actual group expressions, limit and merged variables; bind aliases to real resource and access identities. Inspect controller configuration, plugins and inventory code before discovery, and enumerate delegated/API effects outside host limits.
- Validate candidates before activation; prove a repeated unchanged run causes no unintended changes or restarts. Treat check mode as advisory, and inspect tags, handlers, shell predicates, asynchronous work and secret output independently.
- Select an explicit canary and capacity/quorum-aware batches. Drain, change, activate, observe the real service path and return only accepted hosts. A per-run serial/throttle setting does not replace the fleet/shared-resource lock.
- Halt later batches on failed acceptance or unknown state, including successful rescue of a failed business operation. Reconstruct each host's disk/active/traffic/data state, preserve exclusions, and choose scoped resume, forward repair or compatible recovery. Old binaries/configuration do not undo new writes or external effects.

Admission reuses core's selected Safe/Balanced/Semi-Auto/Full Auto mode and scoped authority. Production mutation retains its R3 floor, and destructive/irreversible actions retain separate exact admission. Refreshed plans/gates do not cause repeated user prompts inside unchanged valid boundaries.

## Native CI acceptance

The required review evidence is the job **Ansible / repeatability and partial recovery** in `operations-smoke.yml`. It runs on a disposable GitHub-hosted Ubuntu runner with hash-pinned Ansible and all transitive wheel dependencies, without custom secrets, live inventory, privilege escalation or external targets. A missing executable, unsupported platform or test failure fails the job; it is not skipped or allowed to fail.

From a matching Linux x86_64 / CPython 3.13 development environment:

```sh
python -m pip install --isolated --disable-pip-version-check --no-input --only-binary=:all: --require-hashes -r tests/requirements-ansible.txt
python tests/smoke_ansible.py -v
```

Each test owns a newly created temporary directory with three local-connection inventory aliases and distinct host directories. Real `copy`, candidate validation, `slurp`, handlers, serial strategy, assertions, rescue and failure thresholds operate on synthetic files representing configuration, active release and traffic. Assertions inspect both callback statistics and actual file content/activation counters, so hiding a changed flag cannot establish repeatability.

Coverage includes:

- First convergence, two notifications coalescing to one activation, second convergence with zero changed tasks and unchanged file timestamps, targeted drift repair, check-mode non-mutation and invalid candidate rejection.
- Intersection/exclusion versus union group selection and preservation of unselected host state.
- Middle-node failure after config replacement, bounded baseline-file recovery, nonzero final outcome, preserved traffic exclusion, later batch untouched, targeted resume from actual mixed state, and no changes on a subsequent unchanged run.
- The negative control: successful rescue without re-raising permits later batches and exit zero despite an excluded failed host. The fixture exposes this hazard; it is not an accepted rollout.
- Recovery failing after configuration changed, injected connection loss both before execution and after a real file replacement inside the change block (without rescue/always completion), the strict 49-versus-50 percentage boundary for one failure in a two-host batch, and `run_once` executing once per serial batch rather than once globally.

This fixture validates Ansible orchestration and local file state. It does not test remote SSH/WinRM authentication, operating-system services/reboots, actual load-balancer drain, controller crash durability, database/schema recovery, network partitions, capacity/quorum or production downtime. Those require isolated target-specific rehearsals with the corresponding host/data/network/reliability module. The synthetic playbooks and callback/connection plugins are test artifacts, not production templates or runtime security controls.

Run the full platform suite, skill/manifest validation, public-source export, deterministic runtime build/verification and secret scanning as well. The runtime archive includes the expanded skill references, but excludes native CI dependencies, fixtures and test plugins. Two independent technical review passes include a fresh forward evaluation; AI review is not an identity-backed production-owner approval.
