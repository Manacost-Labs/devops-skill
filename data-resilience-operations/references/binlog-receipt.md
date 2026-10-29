# Offline file/position receipt checker

Run `python data-resilience-operations/scripts/verify-binlog-chain.py <receipt.json> --root <artifact-directory>`. This performs bounded read-only file hashing, never SQL or shell execution. Authorize artifact I/O and protect the directory first; mounted storage may still incur load/cost. Default total artifact limit is 1 GiB; choose an explicit higher `--max-bytes` for an approved budget (maximum 1 TiB).

The receipt must contain exactly:

```json
{
  "schema_version": "1.0",
  "engine": "mysql",
  "source_ref": "inventory:db-a-epoch-2",
  "coordinate_evidence_ref": "evidence:consistent-base-2",
  "boundary_evidence_ref": "evidence:before-unwanted-transaction",
  "backup": {"file": "base.sql", "size": 1200, "sha256": "<64-lowercase-hex>"},
  "start": {"name": "recovery-bin.000021", "position": 450},
  "stop": {"name": "recovery-bin.000022", "position": 900},
  "logs": [
    {"name": "recovery-bin.000021", "file": "logs/recovery-bin.000021", "size": 1600, "sha256": "<64-lowercase-hex>"},
    {"name": "recovery-bin.000022", "file": "logs/recovery-bin.000022", "size": 1400, "sha256": "<64-lowercase-hex>"}
  ]
}
```

Use engine mysql or mariadb. Backup can be a logical artifact or the externally verified archive/manifest of a physical backup; hashing that file does not verify every extracted member. References are opaque bounded evidence identifiers, not secret values or proof that the evidence is valid.

Logs must be plain exported binary-log files with the standard binary-log magic, a single prefix and zero-padded contiguous sequence, in exact start-to-stop order. Logs are closed immutable copies; active/growing logs are rejected by the declared size/hash check. Start/stop offsets are byte positions >=4 and inside the relevant files; the stop may equal file length. An empty same-file interval is rejected. Byte bounds do not prove an event/transaction boundary.

Paths are relative portable components under the given root, with no traversal, symlinks/reparse points, duplicate file aliases or hard-linked artifacts. JSON duplicate/unknown fields, booleans as integers, malformed hashes, gaps and wrong bytes fail closed. The tool reads at most the declared artifact budget and does not print artifact content or raw error paths.

Exit 0 returns `integrity_verified_replay_unproven` plus file/byte counts. Exit 2 means invalid receipt/integrity or insufficient I/O budget. It does not validate a signature, log epoch/source claim, encryption, event checksums, GTID coverage, base completeness or transaction boundaries, and does not generate a replay command. Native engine-tool verification, exact core gates and isolated restoration are still mandatory. Revalidate immutable artifact identities immediately before real execution; mutable storage can change after any check.
