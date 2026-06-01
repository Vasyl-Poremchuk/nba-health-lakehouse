# Purpose

Creates all necessary AWS resources needed to be able to execute the pipeline for this project.

## Prerequisites

To be able to provision necessary resources you will need to have completed the following:

- Create the remote backend (see [bootstrap/README](./bootstrap/README.md)).

## Usage

Use the following commands in exact order to provision resources:

- `terraform -chdir=infra/terraform/<env> init` - download provider.
- `terraform -chdir=infra/terraform/<env> fmt` - fix code formatting.
- `terraform -chdir=infra/terraform/<env> validate` - check references.
- `terraform -chdir=infra/terraform/<env> plan` - review before applying.
- `terraform -chdir=infra/terraform/<env> apply` - create the resources.

## Resources

The following AWS resources are provisioned by this configuration:

### IAM

- **Role** `nbahl-pipeline-runner-<env>` - assumed by the pipeline; grants access to the S3 buckets and CloudWatch Logs.

### S3

Three-tier medallion architecture; all buckets are encrypted (AES-256) with public access blocked:

| Bucket | Layer | Notes |
|---|---|---|
| `nbahl-bronze-<env>` | Raw ingestion | Versioning enabled; lifecycle -> STANDARD_IA after 30 d, old versions expire after 90 d |
| `nbahl-silver-<env>` | Processed | Encryption + public-access block |
| `nbahl-gold-<env>` | Aggregated | Encryption + public-access block |

> NOTE: All logical parts are separated into different files to follow best practices
>   and to make things maintainable and reusable.

> NOTE: The `<env>` should be replaced with either `dev` or `prod`.

> NOTE: The remote backend is configured in the `backend.tf` file as an S3 bucket
>   with a lock file for state locking. Also, make sure that defined
>   values in the file are not used as variables or locals - this is a Terraform
>   limitation - the `backend` block is evaluated before any variables or locals
>   are resolved, and Terraform does not know anything yet about them.
