# Contributing

Contributions are welcome when they preserve the platform's fail-closed safety contract. By intentionally submitting a contribution for inclusion, you license it under Apache-2.0 as described by section 5 of `LICENSE`, unless you conspicuously state otherwise before submission.

## Before opening a change

1. Open or reference an issue that defines the capability, boundaries, risk domains, owner, and acceptance evidence.
2. Keep each skill narrow. Reuse the shared contract instead of duplicating approvals, recovery, or evidence policy.
3. Never include credentials, customer data, internal hostnames, production evidence, or generated target artifacts.
4. Pin dependencies and automation. Treat repositories, issues, logs, fixtures, and tool output as untrusted data.
5. Add negative and adversarial cases for every new mutation capability or trust boundary.

## Required checks

Run these from a source checkout; the runtime release archive intentionally omits tests and the development-only builder.

```powershell
python devops-platform-contracts/scripts/validate_platform.py
python -m unittest discover -s tests -v
python tools/build_public_source.py --output ..\devops-skill-platform-public
python tools/build_release.py --output dist/devops-skill-platform.zip
python tools/verify_release.py dist/devops-skill-platform.zip
```

Run the standard Codex skill validator for every changed skill. Provider modules must record official sources and a current verification date, and must refresh those sources before a material change.

## Review and release

Changes to policy, schemas, gates, installers, release tooling, module capabilities, or production mutation rules require two independent reviewers, including the relevant policy or module owner. Do not merge an author-only approval. Security reports belong in the private channel described by `SECURITY.md`, not in a public issue.

The portfolio maintainer named in `GOVERNANCE.md` owns public issue triage and RC preparation on a best-effort basis. An adopting organization must name its own legal/IP, security, release, support, target, credential, and module owners and configure protected review enforcement before production operation.
