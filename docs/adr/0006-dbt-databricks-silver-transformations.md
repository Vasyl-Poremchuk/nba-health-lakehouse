# ADR-0006: dbt on Databricks for Silver Transformations

## Status

Accepted - 2026-10-22

## Context

The connection between Databricks and AWS is already set up (see ADR-0005), and the raw
  data is already loaded into the S3 bucket. This makes Databricks the natural engine
  for processing data in the silver layer. dbt can be added on top of it for modeling,
  testing, and documenting the transformations.
  This is also a chance to gain practical experience with dbt, which has not been
  integrated with Databricks in this project before.

## Decision

We will use dbt for modeling, testing, and documenting models in silver, and Databricks
  as the engine for processing data and storing it in Unity Catalog tables.

Alternatives considered:

- It was considered to use DuckDB as the engine. It was not pursued because Databricks
  is already integrated with S3 and there is no need to introduce a second engine.
- Using plain SQL or PySpark jobs without dbt was not pursued because dbt was chosen
  partly to gain hands-on experience with it.

## Consequences

Positive:

- dbt and Databricks are both well documented, which should help with the integration.
- All transformations can be written as SQL queries, which are in most cases more
  understandable than a Python-based approach. Python models are still available
  within dbt if they are ever needed.
- dbt provides a clear and easy way to define tests and document tables and columns.
  These descriptions can also be saved in Databricks Unity Catalog tables.

Negative:

- There is no prior experience integrating dbt with Databricks in this project, so it
  requires time to understand how things work and how to integrate them properly.
- Development and testing of dbt models require a running Databricks workspace; there
  is no cheap local run as there would be with DuckDB.
- Databricks compute adds cost and vendor coupling once the project moves beyond the
  Free Edition.
- dbt does not have many built-in tests, so you either have to write custom ones or
  install external packages (for example, `dbt_utils` or `dbt_expectations`), which
  creates one more dependency.
