# IaC official sources

Last verified: 2026-10-30. Refresh the exact command, provider and backend documentation before a material change; record installed versions and target behavior. Ansible guidance follows the current official core documentation; native orchestration CI pins ansible-core 2.21.5 with CPython 3.13.5 on Ubuntu 24.04. Older cores, third-party collections, Windows transports and real service/data recovery need version- and target-specific validation.

- [Terraform plan](https://developer.hashicorp.com/terraform/cli/commands/plan), [backend](https://developer.hashicorp.com/terraform/language/backend), [state sensitivity](https://developer.hashicorp.com/terraform/language/state/sensitive-data), and [import](https://developer.hashicorp.com/terraform/cli/import)
- [OpenTofu plan](https://opentofu.org/docs/cli/commands/plan/)
- [Ansible check and diff mode](https://docs.ansible.com/ansible/latest/playbook_guide/playbooks_checkmode.html)
- [Inventory patterns](https://docs.ansible.com/projects/ansible/latest/inventory_guide/intro_patterns.html) and [configuration/variable precedence](https://docs.ansible.com/projects/ansible/latest/reference_appendices/general_precedence.html)
- [Strategies, serial, throttle and run_once](https://docs.ansible.com/projects/ansible/latest/playbook_guide/playbooks_strategies.html) and [delegation/context/concurrency](https://docs.ansible.com/projects/ansible/latest/playbook_guide/playbooks_delegation.html)
- [Failures, handlers and failure thresholds](https://docs.ansible.com/projects/ansible/latest/playbook_guide/playbooks_error_handling.html) and [blocks/rescue/always](https://docs.ansible.com/projects/ansible/latest/playbook_guide/playbooks_blocks.html)
- [cloud-init debugging and validation](https://cloudinit.readthedocs.io/en/latest/howto/debugging.html)

These sources define tool mechanics, not authorization. Provider-specific resources still require the named provider pack and read-only discovery of the live target.

The native fixture uses real Ansible modules and strategies with separate local directories for three synthetic inventory hosts. It proves orchestration and file-state behavior only; it does not certify SSH/WinRM, actual service readiness, load balancers, quorum, database rollback or production availability. Connection loss is injected through a test-only connection plugin. See the source-checkout test procedure in `docs/ansible-operations-depth.md`.
