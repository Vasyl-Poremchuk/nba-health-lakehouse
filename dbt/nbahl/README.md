# nbahl dbt project

dbt project for the silver layer of the NBA health lakehouse. It reads raw tables from the bronze schema in Databricks and builds cleaned, deduplicated, typed tables in the `silver` schema.

## Layout

| Path | Contents |
| --- | --- |
| `models/sources.yml` | Bronze source definition |
| `models/silver/` | Silver models and their tests/descriptions |
| `tests/generic/` | Custom generic test `length_equal_to` |
| `tests/` | Singular tests, e.g. each game has two zero-sum rows |
| `macros/generate_schema_name.sql` | Uses the configured schema name as-is (`silver`) instead of prefixing the target schema |

## Setup

1. Add a `nbahl` profile to your `profiles.yml` (Databricks host, HTTP path, `auth_type: oauth`, `catalog`, `schema`) with a `dev` target.
2. From `dbt/nbahl`, install packages: `dbt deps`

## Commands

Run from `dbt/nbahl`:

```bash
dbt build --select league_game_logs_00_t_regular_season   # run model + tests
dbt test --store-failures                                 # keep failing rows in Databricks
```

Use `--target <name>` to choose the environment. The catalog comes from the target, so `dev` and `prod` read and write different catalogs.

## Conventions

- Silver models are tables stored as Delta and are rebuilt on every run (no incremental models yet).
- Surrogate keys (`*_sk`) are `SHA2(<id>, 256)`; string IDs are trimmed.
- Duplicates are removed by keeping the latest row by `_ingested_at`, then `_bronze_path`.
- Every column has a description and a `data_type`; descriptions are written to Databricks as comments (`persist_docs`).
- Range tests warn; integrity tests (keys, nulls, totals) fail the build.
