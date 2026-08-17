# Evidence and exception records

## Control evidence record

Record the control objective and version, testable claim, scope/assets, accountable owner, implementation owner, evidence source and access-controlled reference, collection time, period covered, actor/tool identity, artifact digest, redaction status, test method, result, limitations, freshness/expiry, and next action. Distinguish design evidence from evidence that the control operated throughout the review period.

Evidence strength depends on the claim. Prefer authoritative configuration/state plus independently observable outcomes over policy prose or screenshots. Sample-based evidence must state population, selection method, sample size, and limitations.

## Finding or vulnerability record

Include source, affected asset and owner, first/last observed dates, technical condition, exposure and exploitability, business impact, data classification, existing controls, evidence confidence, severity rationale, remediation/risk owner, disposition, due date, verification method, and evidence references. Do not expose working exploits or sensitive target details in broad reports.

Closure states are explicit:

- false_positive: disproved with authoritative evidence.
- mitigated: compensating control reduces risk; condition remains.
- accepted: accountable owner approved bounded residual risk until expiry.
- remediated: change reported complete but not yet independently retested.
- verified_closed: retest proves the condition is absent or the objective is met.

## Exception record

Require exception owner, independent approver where policy requires, exact control/finding and scope, rationale, residual-risk statement, affected data/services, start and expiry, evidence/ticket reference, compensating controls, monitoring and alert owner, review cadence, revocation trigger, and remediation plan. On expiry, mark the exception invalid and escalate; do not auto-renew.

Framework mappings are indexes from testable claims to organizational requirements. Label mapping confidence and version, preserve gaps and conflicts, and route legal interpretation or certification decisions to qualified owners.
