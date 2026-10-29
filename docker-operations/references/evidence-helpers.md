# Offline container evidence

In a protected authorized session, collect one exact container with explicit Docker daemon context/endpoint and full ID. Record daemon/host identity, CLI/API version, collection time and command outcome separately. Inspect can contain environment secrets, paths, labels and health output; retain raw JSON only in approved storage.

`python scripts/inspect-container-state.py --id FULL_64_HEX_ID` reads UTF-8 JSON from stdin: exactly the one-element array produced by container inspect, at most 1 MiB. It does not connect to a daemon, execute content, acquire authority or verify freshness/authenticity. Bind the collector and artifact to the operation ledger; a matching ID inside supplied JSON is not independent proof.

Output includes selected lifecycle/OOM/exit/restart flags, configured limits, mount type/RW inventory and network count. Missing fields remain null/partial. Mount inventory is capped at 32 with truncation; environment, command, labels, health text, paths and network details are omitted. An image content ID is not registry provenance. Unknown enum text is suppressed.

Exit 0 means the selected snapshot was summarized, never healthy, safe-to-rollback or verified. Exit 2 returns generic unknown for malformed, oversized, duplicate-key, nonfinite or identity-mismatched input; it does not echo raw errors. Counts and JSON byte limits bound offline work; externally bound the collector/pipe lifetime because an unfinished stdin stream can wait. A producer failure or empty snapshot cannot become a green report.

Use local protected raw evidence when exact paths/addresses or error text are necessary; the summary deliberately cannot diagnose those layers alone. A false OOM flag does not rule out host kills or missed earlier events, and exit 137 does not determine cause. Null/zero memory or swap settings have specific Engine semantics and are not usage measurements.
