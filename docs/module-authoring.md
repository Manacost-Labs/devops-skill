# Module authoring standard

## Create or change a module

1. Define concrete trigger examples, explicit non-goals, affected state, risk domains, handoffs, and acceptance evidence.
2. Initialize a new skill with the standard `skill-creator/scripts/init_skill.py`; do not hand-build its metadata skeleton.
3. Keep `SKILL.md` under 500 lines with only `name` and `description` frontmatter. Put detailed variants in one-level `references/` files and deterministic repeated checks in tested scripts.
4. Add `module.yaml` with a SemVer version, bounded unique capabilities, risk domains, and compatible `devops-core` and `devops-platform-contracts` requirements.
5. Inherit contract v2. A module may strengthen policy but may not weaken approvals, locks, recovery, evidence, tenant isolation, or untrusted-content boundaries.
6. Use opaque credential references only. Never include example values that resemble live credentials or customer identifiers.
7. Add capability routing, an install profile where justified, positive/negative/adversarial evaluations, and rollback/verification criteria.

## Provider and fast-moving technology packs

Declare `source_freshness` in the manifest, point only to registered official documentation hosts, and keep a concise source index with retrieval date and version scope. Refresh the exact official pages before a material change and discover the actual account/project/cluster read-only. Never infer flags, permissions, defaults, quotas, pricing, or preview behavior from memory.

## Acceptance

Run the standard skill validator, manifest/platform validation, unit and adversarial suites, deterministic release build/verification, and a fresh forward test that receives only the skill and realistic task artifacts. A successful command is not enough: the forward test must preserve boundaries, stop on missing authority, and produce evidence against user-visible acceptance criteria.

Version the changed module according to SemVer. Bump the platform minor version when adding a capability/module/profile or compatible contract extension; bump the contract/platform major for incompatible request, policy, manifest, or behavior changes.
