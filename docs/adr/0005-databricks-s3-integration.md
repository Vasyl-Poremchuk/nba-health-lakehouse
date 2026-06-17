# ADR-0005: Databricks S3 Integration

## Status

Accepted - 2026-06-17

## Context

It would be beneficial to use Databricks functionality (even if limited) for free.
  This helps gain more practical experience and explore Databricks features
  without worrying that cost will become a barrier to running the pipeline,
  for example, several times - to properly understand how the flow works from
  different angles and whether there are any bottlenecks or potential improvements.
  Also, Databricks Free Edition can be a first step before switching to a paid
  Databricks plan with provider integrations.

## Decision

We will use Databricks Free Edition as a starting point. The connection to an AWS
  S3 bucket via Databricks will be set up manually (for now). After properly
  understanding Databricks, we can switch to the paid version with further exploration
  of other features which are not available in the Free Edition.

Alternatives considered:

- It was considered to use the paid version from the beginning and set up the
  connection to AWS S3 via Terraform. But for now it is not worth it - the Free
  Edition provides the bare minimum needed for pipeline development and Databricks
  exploration.

## Consequences

Positive:

- You can explore Databricks without burning your budget.
- Databricks Free Edition includes many of the base features available in the paid
  version, and it is enough to explore how it works and apply it to the current pipeline.
- Databricks Free Edition allows you to learn by doing - you can make mistakes,
  adjust, and try things in different ways to gain deeper knowledge and understanding
  without worrying about cost.

Negative:

- Databricks Free Edition has some limitations; for example, you cannot create a
  compute cluster. You are only allowed to use serverless compute.
- Using Databricks Free Edition might foster a false sense of safety - if you can run
  something several times without worrying about cost, it might cause you to develop
  poor principles or practices, causing you to neglect best practices, cost optimization,
  or processing efficiency. Eventually, you have to follow best practices because in
  production nobody has unlimited resources and budgets. You have to develop things
  wisely - just because it is free, it does not mean that your work should be "cheap".
