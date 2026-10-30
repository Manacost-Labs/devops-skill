# Artifact identity, provenance and promotion

## Establish independently trusted expectations

Before download, identify repository ID/name, allowed workflow/signer/builder and immutable revision, source candidate/checkout semantics, run ID/attempt/event/ref, exact artifact ID, intended payload digest/type, scan/SBOM policy and target. Keep this policy outside the untrusted artifact. A manifest or attestation predicate can repeat attacker-selected expected values; self-consistency alone does not establish authority or authenticity.

Use immutable artifact IDs/digests, not latest successful run, a reused name/tag, cache key or a user-supplied URL. Verify producer metadata against the actual repository/workflow/run/source, current attempt and expected trust. Names can collide across reruns; reject expired, deleted/replaced or unexpected artifacts. Rerun/source identity and PR head versus tested merge SHA require explicit handling. A run being completed is not necessarily success or an admitted build.

GitHub artifact/archive digest, the hash of an extracted payload, an OCI index digest and platform image/config digests are different domains. Compare each against the correct independently bound expectation. Verify both download integrity and the bytes actually promoted. Do not compare a ZIP digest to a contained file hash or assume the download action's digest warning stops the job. Explicitly fail admission on mismatch/missing evidence; do not reconstruct a manifest to match corrupted bytes.

## Cryptographic provenance and policy

Use the actual supported verifier and trust roots, not JSON parsing or a `verified: true` field. Check signature/certificate chain, subject digest, predicate type, allowed issuer, source repository/workflow/ref/digest and authenticated builder identity, transparency/timestamp requirements and applicable validity/revocation policy. Pin/approve the verifier and its bootstrap provenance too. Public-key fingerprints or certificate expectations must come from an independent trusted policy, never the artifact they authenticate.

For GitHub attestations, use the current `gh attestation verify` flags for the exact repository and signer workflow/reusable builder, required source/identity constraints and runner policy. Inspect actual verified output before applying additional policy. Certificate/timestamp fields have a different trust origin from workflow-controlled predicate fields: a valid signature proves who made the statement, not that every caller-provided build input is true. A compromised builder can sign a bad release. SBOMs/scans must bind the subject digest and policy/version/exception expiry; they do not authorize deployment or certify a SLSA level by themselves.

Offline bundles require trusted root/freshness/revocation handling and bind historical identities; a renamed/reassigned repository can change the meaning of a name. Verify the expected current ownership/control plane where required. Failure to fetch or authenticate required provenance blocks promotion; do not switch to unsigned/checksum-only acceptance silently. Separate absence, invalid signature, wrong signer/source, unsupported policy and service-unavailable outcomes in the report.

## Safe consumption and same-byte deployment

Treat all artifact contents as code/data from their trust domain. Verify before extracting/executing. Reject path traversal, absolute/drive paths, links, duplicate or case-colliding members, archive bombs and unexpected files/permissions. Extract into a clean owned staging directory with bounds; never over workflow code, verifier policy, credentials or PATH. Review configuration/templates/scripts inside the payload independently of the transport envelope. Do not execute artifacts from an untrusted producer in a privileged verification job.

Build once; preserve the exact admitted payload through staging and production. Bind configuration/secret versions, migration artifacts and platform/architecture selection separately. Check target-reported digest/active version after activation; successful upload or a release tag does not prove running bytes. Keep previous accepted artifacts and recovery evidence under controlled retention without treating them as automatically compatible rollback candidates.
