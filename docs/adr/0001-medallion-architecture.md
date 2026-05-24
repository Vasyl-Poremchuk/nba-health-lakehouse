# ADR-0001: Choose medallion architecture (bronze/silver/gold)

## Status

Accepted - 2026-05-24

## Context

The project uses NBA data from different sources with varying quality and structure.
  We need a layered architecture that progressively refines data from raw to
  analytics-ready, with clear separation between stages so data is easy to track,
  audit, and reprocess.

## Decision

We will use a three-layer (i.e., bronze/silver/gold) medallion architecture on S3:
- **Bronze**: raw, untransformed data exactly as ingested.
- **Silver**: cleaned, deduplicated, type-enforced, conformed data.
- **Gold**: dimensional models (facts and dimensions) for analytics.

Alternatives considered:
- **Inmon (normalized enterprise warehouse)**: too heavyweight for single-person project
  at this scale.
- **Data Vault**: strong for auditability and history but adds modeling complexity beyond
  what this project needs.
- **Single combined layer**: too little separation; raw and cleaned data would mix, making
  debugging and reprocessing hard.

## Consequences

Positive:

- Clear separation of concerns; each layer has one responsibility.
- Conventional and widely recognized; easy for others to follow.
- Raw data is preserved immutably, so silver/gold can be rebuilt anytime.

Negative:

- Data is duplicated across layers, increasing storage use.
- More pipeline stages to build and orchestrate.
- Some logical overlap between silver and gold transformations.
