## Objective and scope

Describe the bounded capability, affected modules/contracts, and explicit non-goals.

- Linked issue/decision:
- Source revision to review:
- Portfolio/public-RC impact:

## Risk and trust boundaries

- Risk class/domain:
- State, destructive, tenant, credential, provider, or external-effect changes:
- New untrusted inputs or dependencies:
- Workflow permissions, runner class, and artifact path changes:

## Recovery and verification

- Rollback/recovery path:
- Acceptance evidence:
- Negative/adversarial scenarios:
- Remaining external or organization-owned gates:

## Checklist

- [ ] No secrets, customer data, target-specific artifacts, or mutable dependency references
- [ ] Examples and logs use synthetic identifiers; public text cannot identify a live target without documented permission
- [ ] Versions/catalog/profiles and official provider freshness updated where applicable
- [ ] Standard skill, manifest, platform, regression, and release checks pass
- [ ] GitHub Actions use minimal explicit permissions and immutable full-SHA action pins
- [ ] Policy, schema, gate, installer, release, or mutation-capability changes have the required independent review, or the missing reviewer is recorded as a release blocker
- [ ] Security-sensitive details were reported privately rather than copied into this pull request
