# Control crosswalk and evidence index

This is an engineering crosswalk, not certification or legal advice. An assessor must verify implementation and operating effectiveness in the adopting organization.

| Platform control | External reference | Repository evidence | Organization evidence still required |
|---|---|---|---|
| Governed roles, policy, exceptions | NIST CSF 2.0 GOVERN; NIST SP 800-53 AC-5/CM family | enterprise policy, change-control reference, operation gate | IAM roles, approved policy, SoD reports, exception review |
| Secure development and release | NIST SSDF 1.1; SLSA 1.2 | platform validator, deterministic manifest tooling, pinned runtime dependency | protected CI, SBOM, signed provenance, vulnerability SLA |
| Least privilege and credential isolation | NIST CSF PR.AA; OWASP Excessive Agency guidance | target-profile reference rules, access-request template | credential broker, JIT access, revocation evidence |
| Prompt/tool trust boundaries | NIST AI RMF; OWASP Prompt Injection and Excessive Agency | untrusted-content boundary, adversarial scenarios | model/system evaluation, gateway enforcement, red-team results |
| Change, rollback, and recovery | NIST CSF PR/RC; NIST SP 800-53 CM/CP | risk policy, plan-digest approvals, recovery gate | restore exercises, change tickets, business RPO/RTO |
| Detection and response | NIST CSF DETECT/RESPOND/RECOVER | reliability module, incident reference, chained ledger | SIEM ingestion, on-call ownership, exercises, retention |

Primary references:

- NIST SP 800-218 SSDF 1.1: https://csrc.nist.gov/pubs/sp/800/218/final
- NIST Cybersecurity Framework 2.0: https://www.nist.gov/cyberframework
- NIST AI Risk Management Framework: https://www.nist.gov/itl/ai-risk-management-framework
- SLSA specification 1.2: https://slsa.dev/spec/v1.2/
- OpenSSF Scorecard: https://scorecard.dev/
- OWASP Top 10 for LLM and GenAI: https://genai.owasp.org/llm-top-10/
