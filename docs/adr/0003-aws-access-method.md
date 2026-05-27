# ADR-0003: AWS human/CLI access method

## Status

Accepted - 2026-05-27

## Context

We need to be able to access AWS services and defined resources there via console
  or CLI that follows best practices and is secure at the same time.

## Decision

We will use IAM Identity Center with `aws sso login` for human/CLI access rather
  than a long-lived IAM user access key, because we do not store the key forever and we can
  control its expiration time, and it is also the AWS-recommended approach to access
  AWS resources.

Alternatives considered:

- IAM user with static access key - simpler to set up but relies on long term credentials
  which AWS recommends against.


## Consequences

Positive:

- More secure approach as we can:
  - Control expiration time of our token.
  - MFA can be enforced at the Identity Center level, providing an additional security layer.
  - We will be provided with already predefined scope of permissions
    which we want to grant to new users.
- Access to AWS resources can be listed/provided for different developers
  from a single access portal for different environments and different users
  with different permissions.

Negative:

- It requires extra time to properly set up everything.
- Some developers might need some limited scope of permissions which can not
  be provided for predefined `permission sets` and we need to make extra effort
  to create new custom scope of permissions.
- Token has an expiration time and after it expires we need to re-authenticate.
