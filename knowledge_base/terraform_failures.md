---
provider: terraform
title: Terraform Apply and State Lock Errors
product: terraform
source_url: https://developer.hashicorp.com/terraform/language/state/locking
version: 1.0
---

# Terraform Failure Guidance

Terraform errors during plan or apply usually indicate configuration, provider, or state backend problems.

## State lock

If Terraform reports that the state is locked, another operation may still be running or a previous run crashed without releasing the lock.

## Remediation

1. Inspect the first `Error:` block in the log.
2. Confirm no concurrent apply is running.
3. Fix invalid resource arguments or provider credentials.
4. Re-run `terraform plan` before apply.

## Prevention

Require reviewed plan artifacts and protect state backends with locking and access controls.
