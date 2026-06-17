# Architecture Decision Records

This directory contains Architecture Decision Records (ADRs) for the NBAHL
project. An ADR is a short document capturing a single significant decision:
the context that forced it, the decision made, and its consequences.

ADRs exist so the *reasoning* behind the project's structure is preserved, not
just the structure itself. They are written at decision time and are immutable
once accepted - if a decision is reversed, a new ADR supersedes the old one
rather than editing it.

## Format

Each ADR follows the template in [`0000-template.md`](0000-template.md), based
on Michael Nygard's format: **Title, Status, Context, Decision, Consequences**.

Files are named `NNNN-short-title.md` with a zero-padded sequential number.

## Status values

- **Proposed** - under consideration.
- **Accepted** - decided and in effect.
- **Deprecated** - no longer relevant.
- **Superseded by ADR-NNNN** - replaced by a later decision.

## How to add an ADR

1. Copy `0000-template.md` to `NNNN-your-title.md` (next number in sequence).
2. Fill in the five sections. Keep it short - a page or less.
3. Add it to the index below.
4. Commit with `docs: add ADR-NNNN on <topic>`.

> NOTE: You can use the command `make adr N=NNNN TITLE=your-title`.
> See [`makefile`](../../makefile) for more details.

## Index

| ADR | Title | Status |
|-----|-------|--------|
| [0001](0001-medallion-architecture.md) | Choose medallion architecture (bronze/silver/gold) | Accepted |
| [0002](0002-data-engineering-principles.md) | Data engineering principles for the NBAHL project | Accepted |
| [0003](0003-aws-access-method.md) | AWS human/CLI access method | Accepted |
| [0004](0004-terraform-layout.md) | Terraform layout | Accepted |
| [0005](0005-databricks-s3-integration.md) | Databricks S3 Integration | Accepted |
