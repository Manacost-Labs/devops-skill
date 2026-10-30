# AWS provider sources

last_verified: 2026-10-30
provider: Amazon Web Services
tooling_baseline: AWS CLI version 2 documentation; verify the installed CLI and live service model for every operation.

## Official sources

- [AWS CLI documentation](https://docs.aws.amazon.com/cli/)
- [AWS CLI command reference](https://docs.aws.amazon.com/cli/latest/reference/)
- [AWS identity discovery API](https://docs.aws.amazon.com/STS/latest/APIReference/API_GetCallerIdentity.html)
- [IAM security best practices](https://docs.aws.amazon.com/IAM/latest/UserGuide/best-practices.html)
- [Amazon VPC documentation](https://docs.aws.amazon.com/vpc/latest/userguide/)
- [Amazon EC2 documentation](https://docs.aws.amazon.com/ec2/)
- [Amazon ECS documentation](https://docs.aws.amazon.com/ecs/)
- [Amazon EKS documentation](https://docs.aws.amazon.com/eks/)
- [Amazon RDS documentation](https://docs.aws.amazon.com/rds/)
- [AWS pricing documentation](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/)

## Operation-specific evidence

The 2026-10-30 refresh opened the existing AWS/IAM/STS/EC2/ECS/EKS/RDS documentation entrypoints and the exact operation pages linked below. The VPC entrypoint returned no readable body; the concrete VPC rule/quota pages below supplied the network semantics. Documentation inspection and synthetic local tests do not verify a live account, installed CLI version, permissions, quotas or application behavior. No AWS account was queried or changed for this module update.

| Concern | Official references checked | Runbook |
|---|---|---|
| Policy staging, activation, attachment | [CreatePolicyVersion](https://docs.aws.amazon.com/IAM/latest/APIReference/API_CreatePolicyVersion.html), [SetDefaultPolicyVersion](https://docs.aws.amazon.com/IAM/latest/APIReference/API_SetDefaultPolicyVersion.html), [AttachRolePolicy](https://docs.aws.amazon.com/IAM/latest/APIReference/API_AttachRolePolicy.html) | [IAM changes](iam-changes.md) |
| Raw document decoding, complete version inventory | [GetPolicyVersion](https://docs.aws.amazon.com/IAM/latest/APIReference/API_GetPolicyVersion.html), [ListPolicyVersions](https://docs.aws.amazon.com/IAM/latest/APIReference/API_ListPolicyVersions.html) | [IAM changes](iam-changes.md) |
| IAM consistency and account limits | [propagation](https://docs.aws.amazon.com/IAM/latest/UserGuide/troubleshoot.html#troubleshoot_general_eventual-consistency), [quotas](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_iam-quotas.html) | [IAM changes](iam-changes.md) |
| Rule identity, default-VPC revoke, capacity | [ModifySecurityGroupRules](https://docs.aws.amazon.com/AWSEC2/latest/APIReference/API_ModifySecurityGroupRules.html), [RevokeSecurityGroupIngress](https://docs.aws.amazon.com/AWSEC2/latest/APIReference/API_RevokeSecurityGroupIngress.html), [rule behavior](https://docs.aws.amazon.com/vpc/latest/userguide/security-group-rules.html), [VPC quotas](https://docs.aws.amazon.com/vpc/latest/userguide/amazon-vpc-limits.html) | [network changes](network-changes.md) |
| Launch request and matching native evidence | [RunInstances](https://docs.aws.amazon.com/AWSEC2/latest/APIReference/API_RunInstances.html), [DescribeInstances](https://docs.aws.amazon.com/AWSEC2/latest/APIReference/API_DescribeInstances.html), [regional/zonal token scopes](https://docs.aws.amazon.com/ec2/latest/devguide/ec2-api-idempotency.html) | [EC2 launch](ec2-launch.md) |
| Observation limits and quota distinction | [running waiter](https://docs.aws.amazon.com/cli/latest/reference/ec2/wait/instance-running.html), [status waiter](https://docs.aws.amazon.com/cli/latest/reference/ec2/wait/instance-status-ok.html), [instance quotas](https://docs.aws.amazon.com/ec2/latest/instancetypes/ec2-instance-quotas.html) | [EC2 launch](ec2-launch.md) |
| Uncertain and asynchronous effects | [EC2 consistency](https://docs.aws.amazon.com/ec2/latest/devguide/eventual-consistency.html), [request errors](https://docs.aws.amazon.com/ec2/latest/devguide/query-api-troubleshooting.html) | [async recovery](async-recovery.md) |

The service-authorization URLs attempted during this refresh redirected to an unreadable index. Do not infer least-privilege resource support from that failed lookup: refresh the current exact action/resource/condition reference before issuing execution authority. New runbooks cover the named IAM/SG/EC2 operations; managed-container/database capabilities retain discovery/routing scope.

## Freshness procedure

1. Record the installed AWS CLI version, partition, region, and service endpoint.
2. Open the exact official command or API operation reference immediately before planning a call. Record service API model or documentation version when exposed.
3. Confirm whether the operation is generally available, preview, region-limited, asynchronous, replacement-triggering, or eventually consistent.
4. Verify required IAM actions with the current service authorization reference and reduce the execution role to the approved resources.
5. Obtain cost, quota, recovery, and waiter behavior from current official service documentation or live read-only APIs; do not infer them from examples.
6. Record source URLs, `last_verified`, discovered target behavior, and discrepancies in the operation evidence.

Treat any stale source, undocumented parameter, unexpected service model, or target divergence as a stop condition.
