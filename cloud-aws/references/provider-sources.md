# AWS provider sources

last_verified: 2026-08-17
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

## Freshness procedure

1. Record the installed AWS CLI version, partition, region, and service endpoint.
2. Open the exact official command or API operation reference immediately before planning a call. Record service API model or documentation version when exposed.
3. Confirm whether the operation is generally available, preview, region-limited, asynchronous, replacement-triggering, or eventually consistent.
4. Verify required IAM actions with the current service authorization reference and reduce the execution role to the approved resources.
5. Obtain cost, quota, recovery, and waiter behavior from current official service documentation or live read-only APIs; do not infer them from examples.
6. Record source URLs, `last_verified`, discovered target behavior, and discrepancies in the operation evidence.

Treat any stale source, undocumented parameter, unexpected service model, or target divergence as a stop condition.
