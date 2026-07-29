# E2E Regression Report

Scenarios: 34
Passed: 34
Failed: 0

Success-pipeline scenarios (must not classify as concrete failure categories):
- Count: 3
- Passed: 3

| ID | Technology | Expected | Actual | Pass | Failure state |
|----|------------|----------|--------|------|---------------|
| e2e-aws-01 | aws | aws_permission_failure | aws_permission_failure | True | True |
| e2e-aws-02 | aws | aws_permission_failure | aws_permission_failure | True | True |
| e2e-aws-03 | aws | aws_permission_failure | aws_permission_failure | True | True |
| e2e-tf-01 | terraform | terraform_failure | terraform_failure | True | True |
| e2e-tf-02 | terraform | terraform_failure | terraform_failure | True | True |
| e2e-tf-03 | terraform | terraform_failure | terraform_failure | True | True |
| e2e-tf-04 | terraform | unknown_failure | unknown_failure | True | False |
| e2e-docker-01 | docker | docker_failure | docker_failure | True | True |
| e2e-docker-02 | docker | docker_failure | docker_failure | True | True |
| e2e-docker-03 | docker | docker_failure | docker_failure | True | True |
| e2e-gha-01 | github_actions | ci_runner_failure | ci_runner_failure | True | True |
| e2e-gha-02 | github_actions | ci_runner_failure | ci_runner_failure | True | True |
| e2e-gha-03 | github_actions | build_failure | build_failure | True | True |
| e2e-gha-04 | github_actions | unknown_failure | unknown_failure | True | False |
| e2e-k8s-01 | kubernetes | deployment_failure | deployment_failure | True | True |
| e2e-k8s-02 | kubernetes | deployment_failure | deployment_failure | True | True |
| e2e-k8s-03 | kubernetes | deployment_failure | deployment_failure | True | True |
| e2e-k8s-04 | kubernetes | deployment_failure | deployment_failure | True | True |
| e2e-npm-01 | node | dependency_failure | dependency_failure | True | True |
| e2e-npm-02 | node | dependency_failure | dependency_failure | True | True |
| e2e-npm-03 | node | dependency_failure | dependency_failure | True | True |
| e2e-java-01 | java | build_failure | build_failure | True | True |
| e2e-java-02 | java | build_failure | build_failure | True | True |
| e2e-java-03 | java | build_failure | build_failure | True | True |
| e2e-py-01 | python | dependency_failure | dependency_failure | True | True |
| e2e-py-02 | python | dependency_failure | dependency_failure | True | True |
| e2e-py-03 | python | dependency_failure | dependency_failure | True | True |
| e2e-net-01 | network | network_failure | network_failure | True | True |
| e2e-sec-01 | tls | security_misconfiguration | security_misconfiguration | True | True |
| e2e-disk-01 | platform | unknown_failure | unknown_failure | True | True |
| e2e-mem-01 | platform | unknown_failure | unknown_failure | True | True |
| e2e-port-01 | platform | unknown_failure | unknown_failure | True | True |
| e2e-unk-01 | unknown | unknown_failure | unknown_failure | True | True |
| e2e-ok-01 | generic | unknown_failure | unknown_failure | True | False |

## Notes

- Automated suite asserts classification + failure-state expectations without paid OpenAI.
- Upload/persistence/ownership covered by API tests.
- Optional live-OpenAI smoke is separate and not required for CI.

