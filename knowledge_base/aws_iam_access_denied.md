---
provider: aws
title: AWS IAM AccessDenied Guidance
product: iam
source_url: https://docs.aws.amazon.com/IAM/latest/UserGuide/troubleshoot_access-denied.html
version: 1.0
---

# AWS IAM AccessDenied

AccessDenied means the AWS principal authenticated successfully but is not authorized for the requested action.

## Common causes

- Missing IAM action on the role policy (for example `ecs:UpdateService` or `s3:PutObject`)
- Resource ARN does not match the policy resource statement
- Permission boundary or SCP denies the action
- Assumed role trust policy does not allow the caller

## Remediation

1. Identify the denied action from the error message.
2. Confirm the role used by CI or the deployment principal.
3. Grant least-privilege permission for that action and resource.
4. Re-run the workflow and verify success.

## Verification

Use IAM policy simulator or CloudTrail to confirm the call succeeds after the policy update.
