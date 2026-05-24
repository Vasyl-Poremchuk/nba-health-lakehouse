# Contributing to NBAHL

This project (NBA Health Lakehouse) is built incrementally, one Jira card (`NBAHL-N`) at a time. This document describes how work gets done in the repo - branching, commits, pull requests, decisions, and quality checks - so the process stays consistent and reproducible.

## Getting started

```
make setup
```

This installs dependencies (via `uv`) and wires the git hooks (pre-commit and commit-msg). It is idempotent - safe to run any number of times.

## Workflow

Each unit of work corresponds to one Jira card. The cycle:

1. Pick a card from the board and move it to **In Progress** (keep WIP at 1).
2. Create a branch named `NBAHL-N`.
3. Do the work in small, focused commits.
4. Run `make lint` and `make test` before pushing.
5. Open a pull request. Have it reviewed against the card's acceptance criteria (AI review is fine; see below).
6. Address feedback by pushing more commits to the same branch.
7. **Squash and merge**. The card transitions to `Done` via the `Closes:` keyword in the PR description.

## Branches

- Name branches `NBAHL-N` so they trace back to the card.
- One card per branch. Do not bundle unrelated work.

## Commits

We follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <subject>

<optional body explaining the why>

<optional footer with issue references>
```

Types: `feat`, `fix`, `refactor`, `perf`, `docs`, `test`, `build`, `ci`, `chore`, `revert`.

**Rules of thumb**:

- Subject in imperative mood, lower case, no trailing period
  (e.g. "add game-logs pipeline", not "Added pipeline").
- Scope is optional; use it only when it names a meaningful area
  (`ingestion`, `silver`, `gold`, `orchestration`). Omit it for project-wide
  changes.
- The body explains *why*, not *what* - the diff already shows the what.
  Skip the body when the subject says everything.
- Reference the ticket in the footer:
  - `Refs: NBAHL-N` on commits that contribute to a card.
  - `Closes: NBAHL-N` once, in the **PR description**, on the work that
    finishes the card.
> Note: the commitizen prompt does not list `chore` by default. It is still a
> valid type — use `git commit -m "chore: ..." -m "Refs: NBAHL-N"` directly when you need it.

## Pull requests

- The **PR title** is the conventional commit subject (it becomes the squashed
  commit subject on `master`).
- The **PR description** is the commit body - keep it concise, and include
  `Closes: NBAHL-N`.
- Merge with **Squash and merge** so `master` stays linear (one commit per card).
- Review the pre-filled commit message at merge time and trim anything unwanted.

## Architecture Decision Records

**Every non-trivial decision gets an ADR**. A tool choice, a modeling approach,
a structural trade-off, a constraint-driven workaround - if a future reader
might ask "why was this done this way?", write an ADR.

ADRs live in [`docs/adr/`](docs/adr/). See that directory's README for the
process and template. Guiding principle: **ADR-or-it-did-not-happen**.

## Code quality

| Command | What it does |
|---------|--------------|
| `make lint` | Lint with ruff |
| `make format` | Auto-format with ruff |
| `make test` | Run the test suite (pytest) |

Pre-commit hooks enforce most of this automatically on every commit. All checks
must pass before a PR is merged.

Avoid bypassing hooks with `git commit --no-verify` - treat it as a fire alarm,
not a convenience.

## Principles

All work is held to the engineering principles recorded in
[ADR-0002](docs/adr/0002-data-engineering-principles.md) - idempotency,
schema-on-read in bronze, configuration via environment, testability,
fail-loud-not-silent, simple-first, and the rest. Code review (`coderabbitai[bot]`)
should reference those principles directly.
