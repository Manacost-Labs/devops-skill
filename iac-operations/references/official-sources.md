# IaC official sources

Last verified: 2026-08-17. Refresh the exact command, provider and backend documentation before a material change; record installed versions and target behavior.

- [Terraform plan](https://developer.hashicorp.com/terraform/cli/commands/plan), [backend](https://developer.hashicorp.com/terraform/language/backend), [state sensitivity](https://developer.hashicorp.com/terraform/language/state/sensitive-data), and [import](https://developer.hashicorp.com/terraform/cli/import)
- [OpenTofu plan](https://opentofu.org/docs/cli/commands/plan/)
- [Ansible check and diff mode](https://docs.ansible.com/ansible/latest/playbook_guide/playbooks_checkmode.html)
- [cloud-init debugging and validation](https://cloudinit.readthedocs.io/en/latest/howto/debugging.html)

These sources define tool mechanics, not authorization. Provider-specific resources still require the named provider pack and read-only discovery of the live target.
