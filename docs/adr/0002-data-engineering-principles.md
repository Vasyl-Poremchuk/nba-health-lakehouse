# ADR-0002: Data engineering principles for the NBAHL project

## Status

Accepted - 2026-05-24

## Context

Projects that do not follow best practices as early as possible become hard to
maintain. We need to establish foundational principles that we will follow to
keep the project well-structured, easy to understand, and easy to maintain.
These principles serve as the bar against which all work - and all code review,
human or AI - is judged.

## Decision

We commit to the following principles:

- **Linting and formatting**: code should follow established conventions
  (e.g., PEP 8) enforced by automated tools. We stick to a defined set of rules;
  if a rule is too strict, we redefine it deliberately - never drop or change a
  rule without a documented, reasonable justification.
- **Modularity**: each step (ingestion, cleansing, transformation, etc.) should
  be a self-contained module, so it can be reused and tested in isolation.
- **Idempotency**: every pipeline can be re-run any number of times, at any time,
  and will produce the same output from the same input (no duplicates, no partial
  reprocessing, no drift).
- **Schema-on-read in bronze**: bronze preserves source data exactly as ingested.
  No transformations and no business logic are applied at this layer;
  interpretation happens in silver.
- **Configuration via environment**: each environment has its own constants,
  credentials, and settings. All configuration comes from validated environment
  config - never hardcoded.
- **Security**: secrets and credentials are never committed to the repository or
  hardcoded; they come from environment variables or a secrets manager. Sensitive
  data is not logged. We prefer simple, reliable approaches to securing it.
- **Separation of concerns between layers**: bronze, silver, and gold each have a
  single responsibility; logic does not leak across layer boundaries.
- **Testability**: pipelines are structured so their logic can be tested in
  isolation (clients are mockable, pure functions are separable from I/O). We seek
  quality of tests, not quantity.
- **Observability via metadata**: every pipeline run is recorded in a metadata
  table, so we can always answer "did it run, when it ran, and how much it processed".
- **Data contracts between layers**: each layer publishes an explicit interface
  (e.g., grain, schema, freshness, etc.) that downstream consumers can rely on.
- **Fail loud, not silent**: misconfigurations and bad data cause immediate,
  visible failures, not quiet wrong results.
- **Simple-first, then evolve**: build the simplest version that works, then
  enhance working code, rather than starting complex.
- **Optimization and FinOps**: pipelines should use resources efficiently,
  especially on free tiers with usage limits. Compare a new approach against the
  current one before adopting it; optimize when there is a measured need, not
  speculatively, and avoid over-optimizing.
- **Decisions are documented**: every significant choice gets an ADR -
  "ADR-or-it-did-not-happen."

## Consequences

Positive:

- We commit to best practices from the start, rather than retrofitting them later.
- Every piece of work has a clear bar to meet; code review (human or AI) can
  reference these principles directly.
- The project stays consistent and understandable as it grows.

Negative:

- Each task takes more effort, since work must satisfy these principles, not just
  "function".
- Some principles (testing, metadata logging, ADRs) add upfront cost that a
  quick-and-dirty approach would skip.
- Principles occasionally conflict with each other (e.g., "simple-first" vs.
  "testability"), requiring judgment about which to prioritize.
