# Existing VPC security-group rules

Bound a change to one account, partition, Region, VPC ID, group ID and rule ID. Read `DescribeSecurityGroups`, `DescribeSecurityGroupRules`, affected `DescribeNetworkInterfaces`, route tables and network ACLs. Enumerate all associated interfaces and combined security groups before estimating impact. Rules aggregate across groups; changing a shared group affects every associated resource. Route design, peering and transit changes belong to `enterprise-networking`.

## Modify, add or revoke

Capture the exact before tuple: ingress/egress, protocol, ports or ICMP type/code, canonical IPv4/IPv6 CIDR or referenced group/prefix list, owner and description. Compare it immediately before mutation. Prefer one `ModifySecurityGroupRules(GroupId, SecurityGroupRules=[{SecurityGroupRuleId, SecurityGroupRule}])` for a supported in-place change. The response's boolean only acknowledges the request; re-read the rule ID and compare every approved field.

For a new permission, plan `AuthorizeSecurityGroupIngress` or `AuthorizeSecurityGroupEgress` with one exact tuple; retain the returned rule ID before proceeding. For removal, use `RevokeSecurityGroupIngress`/`RevokeSecurityGroupEgress` with exact `GroupId` and `SecurityGroupRuleIds`. Inspect response details, including unknown permissions when returned. In a default VPC, revoking unmatched permission tuples can return success without removing those permissions. Always re-read absence/presence by rule ID; never interpret HTTP success as an effective revoke. CIDR canonicalization or a duplicate-permission error requires discovery and comparison, not a broader rule.

Set required `ec2:ModifySecurityGroupRules`, `ec2:AuthorizeSecurityGroupIngress/Egress` or `ec2:RevokeSecurityGroupIngress/Egress` permissions using the current service authorization reference. A successful `DryRunOperation` is only a permission precheck; it does not reserve capacity, validate the whole plan, prove propagation or acquire a lock.

## Safe ordering and ambiguous results

Keep one in-flight group mutation. AWS provides no expected-before-state precondition for these operations. Use the operation lock plus immediate re-reads and stop on drift; do not invent `If-Match` or a client token. Choose add-before-remove only when the temporary union is explicitly acceptable; choose remove-before-add only when the interruption is acceptable. If neither is safe, stop for a staged alternative and a new plan.

After a lost modify/revoke response, inspect that exact rule and tuple with bounded waits. After a lost authorize response, enumerate the group's complete rules and compare exact normalized tuples; names/descriptions/tags alone cannot establish ownership. A match proves desired state only; no match or several candidates does not justify replay or deletion. Journal each actual changed rule. If step two fails, compensate only step one's proven owned effect after confirming its current tuple still matches this operation's result. Do not replace the entire group's rules from a stale snapshot or delete preexisting matching permissions.

## Quotas and independent acceptance

Read live group/rule counts, group-per-interface limits and prefix-list weights against account quotas. Budget both before and temporary transition states. Prefix-list references can consume multiple rule slots. Do not treat a retry delay as a solution to exhausted quota or automatically request an increase.

Re-read authoritative rule state, then test a **new** permitted connection and an authorized denied-path probe from the intended vantage points. Existing tracked connections may survive a rule change, so a retained connection does not prove exposure closed. Check routing, NACLs, host firewalls and application health separately. Failure of a new path triggers the bounded recovery plan; control-plane convergence alone is partial verification.

Sources checked 2026-10-30: [security-group behavior](https://docs.aws.amazon.com/vpc/latest/userguide/security-group-rules.html), [ModifySecurityGroupRules](https://docs.aws.amazon.com/AWSEC2/latest/APIReference/API_ModifySecurityGroupRules.html), [default-VPC revoke behavior](https://docs.aws.amazon.com/AWSEC2/latest/APIReference/API_RevokeSecurityGroupIngress.html), [VPC quotas](https://docs.aws.amazon.com/vpc/latest/userguide/amazon-vpc-limits.html). Refresh the exact authorize/revoke/describe operation pages and authorization reference before execution.
