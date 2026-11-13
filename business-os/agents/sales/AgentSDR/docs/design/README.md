# Design history

These documents are **decision records kept for history**. They explain why
parts of AgentSDR are the way they are: the Tables enrichment design, the
unified People and Companies lead database, and the one-time data migration
that introduced it.

They were written while the work was being planned or carried out, so they can
describe states the code has since moved past: statuses such as "pending",
file names that have changed, and steps that were run once and are finished.
Treat the code and the guides in [the docs index](../README.md) as the source of
truth. Read these for background and rationale, not as instructions.

| Document | Subject |
|---|---|
| [enrichment-plan.md](enrichment-plan.md) | Design of the enrichment layer (Tables): data model, execution, providers, UI. |
| [unified-lead-database.md](unified-lead-database.md) | The shared identity model for People and Companies across channels. |
| [pre-migration-remediation-plan.md](pre-migration-remediation-plan.md) | Remediation and cutover plan for migrating existing data into the unified model. |
| [people-migration-cutover-rollback-runbook.md](people-migration-cutover-rollback-runbook.md) | Operational runbook for that migration: cutover, rollback, reconciliation. |

The tenancy design lives in [../multi-tenancy/](../multi-tenancy/plan.md), and
the archived Prisma migrations of the LinkedIn tables in
[../prisma-history/](../prisma-history/README.md).
