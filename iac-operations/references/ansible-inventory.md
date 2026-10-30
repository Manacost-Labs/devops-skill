# Ansible inventory, groups and execution trust

## Establish the controller before discovery

Identify the approved controller/container image, working directory, `ANSIBLE_CONFIG`, effective configuration and environment, plugin search paths, Python/interpreter, core, roles and collections. Pin sources and dependency artifacts through the approved cache; review transitive roles/collections and custom action, connection, lookup, inventory, filter and callback plugins. A repository-local configuration or executable inventory is code, not a harmless list of servers. Inspect it before `ansible-inventory`, syntax/list/check commands or gathering facts. Never load arbitrary plugins with a production credential present.

After provenance review, use `ansible --version` and `ansible-config dump --only-changed` with redaction to establish the effective configuration. Flags do not necessarily win: variables (including inventory connection variables and extra vars) can override configuration and play keywords. Review merged host/group/play/role/extra variables, `ansible_host`, port, user, interpreter, connection plugin, become method/user and SSH arguments. Keep controller credentials isolated from managed-node credentials; delegation can use a different identity.

## Resolve groups into identities

Record the intended environment/account, inventory origin and snapshot time, playbook revision, each play's `hosts` expression and exact `--limit`. Group membership is a selection tool, never evidence of tenant/environment ownership. In a reviewed inventory, `web:&production:!maintenance` selects an intersection minus exclusions; `web:production` is a union and can greatly expand the set. Confirm the actual expansion rather than translating patterns mentally. Inventory aliases need not be addresses; multiple aliases can point at one machine and race against each other.

For every selected alias record its stable instance/resource identity, endpoint/SSH host identity, environment, failure domain, service role and connection/become identities. Detect duplicate endpoints/instance IDs, overlapping groups, implicit localhost, unexpected IP families and mixed accounts. Account for multiple inventory sources and group-variable precedence. Do not publish full `--list`/`--host` output: it can contain secrets.

After code/plugin review, inspect `ansible-inventory --graph` and the effective per-host variables in protected storage, then `ansible-playbook ... --list-hosts --list-tasks --list-tags` with the exact execution inputs. Listing is incomplete for dynamic includes, conditional tasks and runtime `add_host`/`group_by`; inspect those paths explicitly. Require a nonempty expected host set and reconcile every play; a zero-host successful exit is not completed work. Never add missing hosts merely to make a pattern match.

Dynamic inventory must be fetched from the approved provider/account with the intended identity. Bind a protected snapshot or reconcile fresh expansion to the approved set immediately before execution and each batch. New, recycled or moved instances require new identity evidence and plan/gate review; they do not inherit a departed server's authority because an alias/IP was reused. Expired facts/cache must not choose targets or decide that a host is safe to skip.

## Bound effects outside the selected group

`--limit` filters play hosts; it does not sandbox `delegate_to`, `local_action`, controller lookups, arbitrary modules, API endpoints, nested commands, `add_host` or delegated facts. Enumerate load balancers, secret stores, databases, DNS, package repositories and controllers separately. A task delegated to a shared API may affect the entire service even with a one-host canary. Include those identities and effects in the contract-v2 scope and use the specialist owner/module.

Delegation changes connection/interpreter/become variable context. Check which host supplies variables and credentials; `inventory_hostname` still names the original host. Delegating many forks to one host does not serialize writes. Use explicit synchronization plus the shared resource lock; `throttle: 1` only bounds this run, not another controller. Never make a database migration safe by simply adding `run_once` or delegating it.

## Access and secrets

Keep SSH host-key validation enabled; verify fingerprints through an approved channel rather than trusting a fresh network scan alone. Scope connection and become rights to the intended actions. Preserve an independently tested management path for SSH/firewall/user changes. Route Windows remoting and host hardening to the corresponding host module; do not invent Linux connection assumptions for Windows nodes.

Vault protects data at rest, not task output or the controller. Use credential/secret version references, protected runtime files, `no_log: true` and `diff: false` on sensitive tasks. Debugging registered results/facts, callbacks, fact caches, rendered templates, job artifacts and high verbosity can still disclose values. Review these independently; never dump all hostvars to debug a selection problem. Do not put secret values in argv, public digests or the change ledger.

## Evidence and admission

Bind reviewed configuration/dependency/inventory/input digests, resolved host identities, exact argv/tags, delegated effects, controller identity, batch plan and fixed execution window to the operation plan. A code digest does not freeze dynamic inventory, secrets or remote package contents: pin versions and recheck material facts. Use core's existing mode/envelope; refresh the exact plan/gate on changes without repeating consent inside unchanged valid boundaries. Locks, recovery and destructive-action admission still apply in every mode.
