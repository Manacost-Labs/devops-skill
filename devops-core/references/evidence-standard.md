# Evidence standard

Match evidence to the acceptance criterion. Record source, collection timestamp, target, actor/tool identity, relevant artifact digest, and redaction status. Redact secrets, identifiers not needed for review, request bodies, authorization headers, cookies, and personal data.

- Deployment: immutable release/image identifier, readiness/health check, external user-path check, and agreed post-deploy observation.
- DNS/TLS/edge: observed DNS answer, certificate validity, external HTTPS result, and origin-protection check where applicable.
- Infrastructure as code: validated configuration, reviewed plan, apply result, outputs/state consistency, and drift check.
- Data protection: backup age/location/encryption evidence, isolated restore-test result, integrity check, measured RPO/RTO.
- Incident: symptom timeline, confirmed cause or bounded hypothesis, stabilizing actions, current status, and next owner.
- Authorization: policy ID/version, target profile digest, plan digest, approval evidence references, approval timestamps/expiry, approver roles, separation-of-duties result, and exception reference if used.
- Agent/tool execution: invoked capability, bounded arguments after redaction, exit/result status, output artifact digest, and whether the result came from a trusted control plane or untrusted target content.

Do not copy large raw logs into the ledger. Store them in the approved evidence system and record an access-controlled reference plus digest. Treat screenshots and pasted terminal output as supporting evidence, not proof of identity or authorization.

A local Markdown or JSON record is not immutable audit storage. When policy requires tamper resistance, export chained records to an organization-controlled WORM/append-only system with independent access control and retention.

Use one result status: `verified`, `partially_verified`, `rolled_back`, or `blocked`.
