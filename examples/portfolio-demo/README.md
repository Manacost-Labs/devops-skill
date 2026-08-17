# Safe change-control portfolio demo

This example demonstrates the platform workflow without contacting a server, cloud API, DNS provider, container runtime, or network endpoint:

`synthetic audit -> immutable plan digest -> exact approval gate -> gated wrapper execution -> verification -> rollback drill`

The approval identity and evidence reference are fixtures. They demonstrate contract binding only and cannot authorize a real operation. The R2 request models the controls required for an externally impactful rollout; the runner itself performs only local, reversible file operations in an automatically removed temporary directory.

## Run

From the repository root:

```powershell
python examples/portfolio-demo/run_demo.py
python -m unittest discover -s examples/portfolio-demo/tests -p "test_*.py"
```

To inspect the synthetic evidence record:

```powershell
python examples/portfolio-demo/run_demo.py --output lab-artifacts/portfolio-demo-evidence.json
```

`lab-artifacts/` is ignored by Git. The evidence contains digests and gate decisions, not credentials or live identifiers.
The runner refuses to overwrite an existing evidence file; choose a new path for each run.

## What the demo proves

- A target profile passes the shared secret-field contract validator.
- A synthetic approval with the wrong plan digest is rejected.
- An approval bound to the exact target, plan, policy, and execution window is accepted.
- The approved plan digest is the canonical digest of the exact command; `tools/devops_exec.py` re-runs the gate immediately before launch, blocks any command that drifts from that digest with a non-zero exit code, and records both outcomes in a secret-redacted execution ledger.
- Execution cannot start unless the fixture declares `simulation_only: true` and the full prohibited-capability boundary.
- Verification checks the desired immutable release and health state.
- A deliberately injected health failure triggers a rollback drill and restores the exact pre-change state.

It does not prove a production deployment, restore, availability level, security certification, or organization-specific approval process. Live validation belongs in a private environment overlay owned by the operator.
