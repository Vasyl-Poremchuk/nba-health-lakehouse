# ADR-0004: Terraform layout

## Status

Accepted - 2026-06-01

## Context

The project will eventually use two environments - `dev` and `prod`. Without
  clear separation between them, it will be hard to maintain state of all resources
  that need to be provisioned in each environment. Also, defining everything in a
  single file can become complicated when project grows. We need to commit to clear
  separation for provisioning necessary resources and best practices as early as
  possible to make resource definitions clear and maintainable.

## Decision

We will separate definitions of all necessary resources by their environments.
We also want to define each related AWS resource in a separate file,
in that case we can easily identify the purpose of the file and make sure
that it is responsible to provision resources for a specific service.
Also, we will separate each logical part (e.g., backend, locals, variables, etc.)
  in an appropriate file, to ensure that logically unrelated parts do not overlap.
  We will bootstrap the S3 backend via a one-time setup, to be able to create
  exactly the same if we needed.

Alternatives considered:

- It was considered to not separate to environment setup at this stage,
but eventually it is better to spend some time right now and do it in a better way
  and redefine what is needed in the future with minimal effort (if needed), rather than
  completely redo everything when the project becomes huge.
- It was considered to not creating a bootstrap setup for S3 backend, but
it was decided to put in the effort, for two main reasons:
  1. Properly understand how it can be done.
  2. Have a backup logic for it in case if it needs to be done quickly.

## Consequences

Positive:

- Clear separation by environment.
- Clear separation by logical part.
- Early commitment to best practices helps develop a habit of doing things the right way,
  especially on early stage of the project - "suffer now, not later".
- If you need to change something, it will be changed in direct files
  (i.e., for specific resources) and it will not touch unrelated stuff.
- Bootstrap setup is documented and can be used at any time.

Negative:

- Bootstrap setup is a one-time approach, you are unlikely to do it again and it requires
  time to do it properly.
- Separation by environments might be too much (especially on early stage) as it
  requires extra time and effort.
