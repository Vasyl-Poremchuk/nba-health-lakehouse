# AWS Account Setup (NBAHL)

## Tag convention
All resources MUST carry:
- project=nbahl
- env=dev | prod
- owner=`XXXX`
- managed-by=console | terraform

The above tags were activated as cost-allocation tags on 2026-05-28.

## Identity
- Root user: MFA enabled 2026-05-27; not used except for billing preferences setup.
- IAM Identity Center: `XXXX` SSO session, `XXXX` permission set with `XXXXAccess`.
  - Daily access via `aws sso login --profile XXXX`.

## Billing safety net
- Billing alerts enabled (root account, one-time setup): 2026-05-28.
- SNS topic: `XXXX` (us-east-1), email subscription confirmed.
- CloudWatch alarm: `XXXX` (us-east-1), threshold $10.
- AWS Budget: $10/month with 50/80/100/forecast alerts.
- Cost Explorer enabled 2026-05-28.

## Security tooling
- IAM Access Analyzer: `XXXX` (Account type), active 2026-05-28.
- Trusted Advisor: free-tier checks reviewed, no Support plan.

## Future work
- All console-created resources above to be migrated to Terraform in NBAHL-13;
  `managed-by` tag flips to `terraform` at that point.

> NOTE: All resource names are filled with the placeholder `XXXX`.
