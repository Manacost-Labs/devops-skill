# Release process

This process separates a portfolio/public release candidate from production or enterprise adoption. A public RC is an evaluation artifact, not a production certification.

## Public RC prerequisites

1. Merge through a pull request against protected main; record the reviewed full commit SHA.
2. Enable and test GitHub private vulnerability reporting. SECURITY.md blocks public distribution until this succeeds.
3. Review the complete tracked-file list and diff. Exclude credentials, customer data, live target identifiers, evidence, private inventory, and target-specific administration scripts.
4. Confirm legal/IP ownership, Apache-2.0 distribution rights, and whether third-party notices are required.
5. Update the catalog, versions, changelog, release notes, support scope, and known limitations.
6. Require the validate and dependency review checks configured in docs/github-repository-settings.md after each check has completed successfully in the repository.
7. Keep any missing independent reviewer, SBOM, signing, provenance, or live-provider evidence visible as a limitation; never relabel it as complete.

## Build and verify locally

From a clean checkout of the reviewed revision:

~~~powershell
python -m pip install --isolated --disable-pip-version-check --no-input --require-hashes -r requirements.txt
python devops-platform-contracts/scripts/validate_platform.py
python -m unittest discover -s tests -v
python tools/build_release.py --output dist/devops-skill-platform-0.3.0.zip
python tools/verify_release.py dist/devops-skill-platform-0.3.0.zip
Get-FileHash -Algorithm SHA256 dist/devops-skill-platform-0.3.0.zip
~~~

The deterministic builder packages only catalog-declared skills, approved documentation, and allowlisted runtime tools. It rejects symlink/reparse/non-regular entries and known credential patterns and emits a per-file hash manifest. Target-specific administration scripts are not release members. Verification rejects undeclared, duplicate, case-colliding, traversing, encrypted, non-regular, wrongly permissioned, non-canonical-compression, oversized, catalog-inconsistent, or incomplete members.

## Build the public source tree

Do not publish the private working repository or rewrite its target-operation history in place. Build a fresh allowlisted tree outside it:

~~~powershell
python tools/build_public_source.py --output ..\devops-skill-platform-public
~~~

The builder validates the platform, refuses a non-empty destination, rejects symlink/reparse inputs and known credential patterns, and excludes Git history, private operations, lab artifacts, credentials, archives, and target-specific tools. Review `PUBLIC-SOURCE-MANIFEST.json`, initialize a new Git repository inside that clean tree, and perform the public-RC checks again before the first push.

## GitHub release-prep check

The manually triggered release prep workflow checks out the selected revision with persisted credentials disabled, uses CPython 3.13.5 and hash-locked dependencies, validates and tests the platform, builds the deterministic archive, verifies it, and prints its SHA-256 digest.

The workflow intentionally does not upload an artifact, create a GitHub release, write repository contents, request OIDC, use environments, read custom secrets, sign, or publish anything. A successful run is build evidence only. Record its run URL, actor, selected ref, full source SHA, and printed digest during review.

## Tag and publish a portfolio RC

After all public-RC prerequisites are evidenced, create an annotated prerelease tag such as v0.3.0-rc.1 from the reviewed commit. Publish the exact verified archive and checksum as prerelease assets using a controlled maintainer procedure. Do not substitute an unverified rebuild or GitHub-generated source archive for the tested artifact.

Until independent signing and provenance exist, label the asset as an **unsigned evaluation RC**. Preserve the source SHA, archive digest, validation run, dependency-review result, reviewer, release owner, limitations, and rollback artifact in the release notes.

## Production and enterprise gate

Before production promotion, additionally require:

- two independent identity-backed reviewers and protected tags/environments;
- SBOM generation and an approved vulnerability/license policy;
- signing and provenance bound to source, builder, inputs, workflow, and archive digest;
- independent verification through a separate trust path;
- short-lived least-privilege deployment identity and immutable audit export;
- target-owner-approved sandbox/pilot evidence, backup and restore, rollback, monitoring, and observation criteria.

Promote the same verified digest through environments; never rebuild per environment. If verification or acceptance fails, stop promotion, preserve evidence, restore the prior verified installation from the installer backup, revoke affected credentials or signatures where needed, and publish an attributable advisory when appropriate.
