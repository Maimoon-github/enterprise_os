# Governance

AgentSDR is an open-source project led by **Kandid** (the company that
started it and runs it in production). This document describes how
decisions are made and how people become maintainers.

## Roles

- **Users** run AgentSDR, report bugs, ask questions and share ideas.
- **Contributors** improve the code, docs or design through pull requests,
  issues and reviews. Anyone can contribute.
- **Maintainers** review and merge pull requests, triage issues, cut
  releases, and handle security reports. Maintainers are listed in
  [`.github/CODEOWNERS`](.github/CODEOWNERS) and are members of the
  maintainers team on GitHub.

## Decision making

- Day-to-day changes are decided in pull requests: one maintainer approval
  and a green `CI / required` check are enough to merge.
- Changes to architecture, the data model, licensing, security posture or
  public APIs are discussed in an issue or Discussion first and need the
  agreement of at least two maintainers. Design records live in
  [`docs/design/`](docs/design/).
- When maintainers disagree and a discussion does not converge, Kandid's
  project lead makes the final call and records the reasoning on the issue.

## Becoming a maintainer

Contributors who have made sustained, high-quality contributions —
code, reviews, docs, triage — and who show good judgement about the
project's direction can be invited by the existing maintainers. Maintainers
who are inactive for six months may move to emeritus status; they are
welcome back.

## Code of conduct and security

Everyone in the project follows the [Code of Conduct](CODE_OF_CONDUCT.md).
Security reports are handled privately by the maintainers as described in
[SECURITY.md](SECURITY.md).

## Changes to this document

Changes to governance follow the "architecture" path above.
