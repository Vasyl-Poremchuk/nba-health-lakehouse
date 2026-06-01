# Purpose

Creates the S3 bucket used as Terraform remote state backend for this project.

## Prerequisites

To be able to bootstrap all required resources you will need:

- The [Terraform CLI](https://developer.hashicorp.com/terraform/tutorials/aws-get-started/install-cli) (1.15+) installed.
- The [AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/install-cliv2.html) installed.
- An AWS account with IAM Identity Center access. Authenticate before running any commands:
  ```bash
  aws sso login --profile <profile>
  ```
  See `docs/aws-account-setup.md` for the full SSO setup guide.

## One-time Usage

The bootstrap setup should be run once (before creating other resources) using the following commands in exact order:

- `terraform -chdir=infra/terraform/bootstrap/<env> init` - download provider.
- `terraform -chdir=infra/terraform/bootstrap/<env> fmt` - fix code formatting.
- `terraform -chdir=infra/terraform/bootstrap/<env> validate` - check references.
- `terraform -chdir=infra/terraform/bootstrap/<env> plan` - review before applying.
- `terraform -chdir=infra/terraform/bootstrap/<env> apply` - create the resources.

## Resources Created

A short list of what gets provisioned:

- S3 bucket.
- S3 bucket versioning.
- S3 bucket encryption (i.e. `SSE-S3`).
- Public access block.

## Using the Bucket in Other Modules

Other Terraform modules should reference this bucket in their `backend` block. Backend values must be string literals - they can not reference Terraform outputs.

```hcl
terraform {
  backend "s3" {
    bucket       = "nbahl-terraform-state-<env>"
    key          = "path/to/terraform.tfstate"
    region       = "us-east-1"
    use_lockfile = true
  }
}
```

When adding this backend to a module for the first time, run `terraform init -migrate-state` to copy any existing local state into S3.

> NOTE: All logical parts are separated into different files to follow best practices
>   and to make things maintainable and reusable.

> NOTE: This module intentionally has no remote backend configured. The S3 bucket
>   must exist before any module can use it as a backend - configuring a remote
>   backend here would create a chicken-and-egg problem. Local state is expected.

> NOTE: The backend bucket is created with `prevent_destroy = true` to make sure
>   that it can not be removed by `terraform -chdir=infra/terraform/bootstrap/<env> destroy`.

> NOTE: The `<env>` should be replaced with either `dev` or `prod`.
