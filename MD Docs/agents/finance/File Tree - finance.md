# File Tree: OpenBooks

**Root Path:** `/enterprise_os/business-os/agents/finance/OpenBooks`

```
├── 📁 OpenBooks
│   ├── 📁 .github
│   │   ├── 📁 ISSUE_TEMPLATE
│   │   │   ├── ⚙️ bug_report.yml
│   │   │   ├── ⚙️ config.yml
│   │   │   ├── ⚙️ feature_request.yml
│   │   │   └── ⚙️ initiative.yml
│   │   ├── 📁 actions
│   │   │   └── 📁 setup
│   │   │       └── ⚙️ action.yml
│   │   ├── 📁 scripts
│   │   │   └── 📄 check-token-lint.sh
│   │   ├── 📁 workflows
│   │   │   └── 📄 ci.yml.disabled
│   │   ├── ⚙️ FUNDING.yml
│   │   └── 📝 PULL_REQUEST_TEMPLATE.md
│   ├── 📁 .yarn
│   │   └── 📁 releases
│   │       └── 📄 yarn-4.17.1.cjs
│   ├── 📁 docker
│   │   └── 📁 mysql-init
│   │       ├── 📄 01-users.sql
│   │       └── 📄 02-grants.sql
│   ├── 📁 docs
│   │   ├── 📁 architecture
│   │   │   ├── 📝 api-and-transport.md
│   │   │   ├── 📝 data-and-tenancy.md
│   │   │   ├── 📝 ledger-kernel.md
│   │   │   ├── 📝 money-and-invariants.md
│   │   │   ├── 📝 overview.md
│   │   │   ├── 📝 providers-and-config.md
│   │   │   └── 📝 security.md
│   │   ├── 📁 decisions
│   │   │   ├── 📝 adr-template.md
│   │   │   └── 📝 index.md
│   │   ├── 📁 features
│   │   │   ├── 📝 banking-and-cash.md
│   │   │   ├── 📝 foundation.md
│   │   │   ├── 📝 frontend.md
│   │   │   ├── 📝 overview.md
│   │   │   ├── 📝 payments-processing.md
│   │   │   ├── 📝 platform-and-ai.md
│   │   │   ├── 📝 purchases-ap.md
│   │   │   ├── 📝 reporting-and-tax.md
│   │   │   └── 📝 sales-ar.md
│   │   ├── 📁 guides
│   │   │   ├── 📝 adding-a-feature.md
│   │   │   ├── 📝 database-and-migrations.md
│   │   │   ├── 📝 deployment.md
│   │   │   ├── 📝 development.md
│   │   │   ├── 📝 getting-started.md
│   │   │   ├── 📝 hosted-infra.md
│   │   │   └── 📝 testing.md
│   │   ├── 📝 README.md
│   │   ├── 📝 ci.md
│   │   └── 📝 glossary.md
│   ├── 📁 infra
│   │   ├── 📁 db-bootstrap
│   │   │   ├── 📄 01-users-rds.sql
│   │   │   └── 📄 02-grants.sql
│   │   ├── 📁 nginx
│   │   │   └── ⚙️ openbooks-web.conf
│   │   ├── 📁 scripts
│   │   │   ├── 📄 check-db-bootstrap-parity.sh
│   │   │   └── 📄 tf-validate.sh
│   │   ├── 📁 terraform
│   │   │   ├── 📁 modules
│   │   │   │   ├── 📁 compute
│   │   │   │   │   ├── 📄 cluster.tf
│   │   │   │   │   ├── 📄 ecr.tf
│   │   │   │   │   ├── 📄 iam.tf
│   │   │   │   │   ├── 📄 outputs.tf
│   │   │   │   │   ├── 📄 services.tf
│   │   │   │   │   ├── 📄 tasks.tf
│   │   │   │   │   ├── 📄 variables.tf
│   │   │   │   │   └── 📄 versions.tf
│   │   │   │   ├── 📁 data
│   │   │   │   │   ├── 📄 bootstrap.tf
│   │   │   │   │   ├── 📄 main.tf
│   │   │   │   │   ├── 📄 outputs.tf
│   │   │   │   │   ├── 📄 secrets.tf
│   │   │   │   │   ├── 📄 variables.tf
│   │   │   │   │   └── 📄 versions.tf
│   │   │   │   ├── 📁 edge
│   │   │   │   │   ├── 📄 acm.tf
│   │   │   │   │   ├── 📄 alb.tf
│   │   │   │   │   ├── 📄 cloudfront.tf
│   │   │   │   │   ├── 📄 outputs.tf
│   │   │   │   │   ├── 📄 variables.tf
│   │   │   │   │   └── 📄 versions.tf
│   │   │   │   ├── 📁 messaging
│   │   │   │   │   ├── 📄 outputs.tf
│   │   │   │   │   ├── 📄 s3.tf
│   │   │   │   │   ├── 📄 ses.tf
│   │   │   │   │   ├── 📄 sqs.tf
│   │   │   │   │   ├── 📄 variables.tf
│   │   │   │   │   └── 📄 versions.tf
│   │   │   │   └── 📁 network
│   │   │   │       ├── 📄 main.tf
│   │   │   │       ├── 📄 outputs.tf
│   │   │   │       ├── 📄 variables.tf
│   │   │   │       └── 📄 versions.tf
│   │   │   ├── 📁 state-backend
│   │   │   │   ├── ⚙️ .terraform.lock.hcl
│   │   │   │   ├── 📄 main.tf
│   │   │   │   ├── 📄 outputs.tf
│   │   │   │   └── 📄 variables.tf
│   │   │   ├── ⚙️ .terraform.lock.hcl
│   │   │   ├── 📝 README.md
│   │   │   ├── 📄 backend.tf
│   │   │   ├── 📄 kms.tf
│   │   │   ├── 📄 locals.tf
│   │   │   ├── 📄 main.tf
│   │   │   ├── 📄 outputs.tf
│   │   │   ├── 📄 providers.tf
│   │   │   ├── 📄 secrets.tf
│   │   │   ├── 📄 variables.tf
│   │   │   └── 📄 versions.tf
│   │   └── ⚙️ .gitignore
│   ├── 📁 packages
│   │   ├── 📁 e2e
│   │   │   ├── 📁 scripts
│   │   │   │   └── 📄 start-stack.mjs
│   │   │   ├── 📁 tests
│   │   │   │   ├── 📁 support
│   │   │   │   │   ├── 📄 banking.ts
│   │   │   │   │   ├── 📄 books.ts
│   │   │   │   │   ├── 📄 cash-application.ts
│   │   │   │   │   ├── 📄 pay-bills.ts
│   │   │   │   │   └── 📄 payments.ts
│   │   │   │   ├── 📄 accountant-and-close.spec.ts
│   │   │   │   ├── 📄 automations.spec.ts
│   │   │   │   ├── 📄 bank-feeds.spec.ts
│   │   │   │   ├── 📄 banking.spec.ts
│   │   │   │   ├── 📄 bill-capture.spec.ts
│   │   │   │   ├── 📄 budgets.spec.ts
│   │   │   │   ├── 📄 cash-application.spec.ts
│   │   │   │   ├── 📄 cash-basis.spec.ts
│   │   │   │   ├── 📄 fixed-assets-and-recurring-journals.spec.ts
│   │   │   │   ├── 📄 mobile-smoke.spec.ts
│   │   │   │   ├── 📄 month-of-books.spec.ts
│   │   │   │   ├── 📄 pay-bills.spec.ts
│   │   │   │   ├── 📄 payment-integration.spec.ts
│   │   │   │   ├── 📄 payout-sync.spec.ts
│   │   │   │   ├── 📄 platform-oauth-mcp.spec.ts
│   │   │   │   ├── 📄 procure-to-pay.spec.ts
│   │   │   │   ├── 📄 quickbooks-import.spec.ts
│   │   │   │   └── 📄 recurring-and-dunning.spec.ts
│   │   │   ├── ⚙️ package.json
│   │   │   ├── 📄 playwright.config.ts
│   │   │   └── ⚙️ tsconfig.json
│   │   ├── 📁 eslint-plugin
│   │   │   ├── 📁 src
│   │   │   │   ├── 📁 rules
│   │   │   │   │   ├── 📄 no-float-money.js
│   │   │   │   │   ├── 📄 no-journal-writes.js
│   │   │   │   │   ├── 📄 no-process-env.js
│   │   │   │   │   └── 📄 no-raw-color.js
│   │   │   │   └── 📄 index.js
│   │   │   ├── 📁 test
│   │   │   │   ├── 📁 fixtures
│   │   │   │   │   ├── 📄 file.ts
│   │   │   │   │   └── ⚙️ tsconfig.json
│   │   │   │   ├── 📄 no-float-money.test.ts
│   │   │   │   ├── 📄 no-journal-writes.test.ts
│   │   │   │   ├── 📄 no-process-env.test.ts
│   │   │   │   └── 📄 no-raw-color.test.ts
│   │   │   ├── ⚙️ package.json
│   │   │   └── ⚙️ tsconfig.json
│   │   ├── 📁 plugin-api
│   │   │   ├── 📁 src
│   │   │   │   ├── 📄 actor.ts
│   │   │   │   ├── 📄 context.ts
│   │   │   │   ├── 📄 events.ts
│   │   │   │   ├── 📄 index.ts
│   │   │   │   ├── 📄 mcp.ts
│   │   │   │   ├── 📄 migrations.ts
│   │   │   │   ├── 📄 module.ts
│   │   │   │   ├── 📄 permissions.ts
│   │   │   │   ├── 📄 posting.ts
│   │   │   │   ├── 📄 primitives.ts
│   │   │   │   ├── 📄 providers.ts
│   │   │   │   ├── 📄 registry.ts
│   │   │   │   └── 📄 routes.ts
│   │   │   ├── 📄 LICENSE
│   │   │   ├── 📝 README.md
│   │   │   ├── ⚙️ package.json
│   │   │   └── ⚙️ tsconfig.json
│   │   ├── 📁 server
│   │   │   ├── 📁 src
│   │   │   │   ├── 📁 config
│   │   │   │   │   ├── 📄 config.ts
│   │   │   │   │   ├── 📄 env.ts
│   │   │   │   │   ├── 📄 errors.ts
│   │   │   │   │   ├── 📄 index.ts
│   │   │   │   │   ├── 📄 providers.ts
│   │   │   │   │   ├── 📄 redact.ts
│   │   │   │   │   └── 📄 role.ts
│   │   │   │   ├── 📁 context
│   │   │   │   │   ├── 📄 authentication.ts
│   │   │   │   │   ├── 📄 context.ts
│   │   │   │   │   ├── 📄 errors.ts
│   │   │   │   │   ├── 📄 index.ts
│   │   │   │   │   └── 📄 store.ts
│   │   │   │   ├── 📁 crypto
│   │   │   │   │   └── 📄 field-encryption.ts
│   │   │   │   ├── 📁 db
│   │   │   │   │   ├── 📁 migrations
│   │   │   │   │   │   ├── 📄 0001_tenancy.ts
│   │   │   │   │   │   ├── 📄 0002_ledger.ts
│   │   │   │   │   │   ├── 📄 0003_idempotency.ts
│   │   │   │   │   │   ├── 📄 0005_subledger.ts
│   │   │   │   │   │   ├── 📄 0006_banking.ts
│   │   │   │   │   │   ├── 📄 0007_invoice_delivery.ts
│   │   │   │   │   │   ├── 📄 0008_recurring_dunning.ts
│   │   │   │   │   │   ├── 📄 0009_bill_capture.ts
│   │   │   │   │   │   ├── 📄 0010_platform.ts
│   │   │   │   │   │   ├── 📄 0011_payment_processing.ts
│   │   │   │   │   │   ├── 📄 0012_cash_application.ts
│   │   │   │   │   │   ├── 📄 0013_pay_bills.ts
│   │   │   │   │   │   ├── 📄 0014_fixed_assets.ts
│   │   │   │   │   │   ├── 📄 0015_procure_to_pay.ts
│   │   │   │   │   │   ├── 📄 0016_budgets.ts
│   │   │   │   │   │   ├── 📄 0017_accountant_close.ts
│   │   │   │   │   │   ├── 📄 0018_automations.ts
│   │   │   │   │   │   ├── 📄 0019_catalog.ts
│   │   │   │   │   │   ├── 📄 0020_contact_address.ts
│   │   │   │   │   │   ├── 📄 0021_bank_feeds.ts
│   │   │   │   │   │   ├── 📄 0022_account_statements.ts
│   │   │   │   │   │   ├── 📄 0023_ten99.ts
│   │   │   │   │   │   ├── 📄 0024_payout_sync.ts
│   │   │   │   │   │   ├── 📄 0025_inventory.ts
│   │   │   │   │   │   ├── 📄 0026_logs.ts
│   │   │   │   │   │   ├── 📄 0999_app_grants.ts
│   │   │   │   │   │   ├── 📝 README.md
│   │   │   │   │   │   ├── 📄 index.ts
│   │   │   │   │   │   └── 📄 types.ts
│   │   │   │   │   ├── 📄 api-key-lookup.ts
│   │   │   │   │   ├── 📄 client.ts
│   │   │   │   │   ├── 📄 connection.ts
│   │   │   │   │   ├── 📄 delivery-lookup.ts
│   │   │   │   │   ├── 📄 generated.ts
│   │   │   │   │   ├── 📄 index.ts
│   │   │   │   │   ├── 📄 keyset.ts
│   │   │   │   │   ├── 📄 migrator.ts
│   │   │   │   │   ├── 📄 mysql-errors.ts
│   │   │   │   │   ├── 📄 oauth-lookup.ts
│   │   │   │   │   ├── 📄 org-scope.ts
│   │   │   │   │   ├── 📄 processor-connection-lookup.ts
│   │   │   │   │   ├── 📄 secrets-store.ts
│   │   │   │   │   ├── 📄 statement-credential-lookup.ts
│   │   │   │   │   ├── 📄 tenant-tables.ts
│   │   │   │   │   ├── 📄 tenant.ts
│   │   │   │   │   ├── 📄 transaction-scope.ts
│   │   │   │   │   └── 📄 uuid.ts
│   │   │   │   ├── 📁 entrypoints
│   │   │   │   │   ├── 📄 api.ts
│   │   │   │   │   ├── 📄 main.ts
│   │   │   │   │   ├── 📄 migrate-cli.ts
│   │   │   │   │   ├── 📄 migrate.ts
│   │   │   │   │   ├── 📄 spec.ts
│   │   │   │   │   └── 📄 worker.ts
│   │   │   │   ├── 📁 errors
│   │   │   │   │   ├── 📄 assert.ts
│   │   │   │   │   ├── 📄 base.ts
│   │   │   │   │   ├── 📄 codes.ts
│   │   │   │   │   ├── 📄 errors.ts
│   │   │   │   │   ├── 📄 index.ts
│   │   │   │   │   ├── 📄 parse.ts
│   │   │   │   │   └── 📄 wire.ts
│   │   │   │   ├── 📁 logging
│   │   │   │   │   ├── 📄 index.ts
│   │   │   │   │   ├── 📄 log-sink-stream.ts
│   │   │   │   │   ├── 📄 logger.ts
│   │   │   │   │   ├── 📄 provenance.ts
│   │   │   │   │   ├── 📄 redact.ts
│   │   │   │   │   └── 📄 serialize.ts
│   │   │   │   ├── 📁 modules
│   │   │   │   │   ├── 📁 account-statements
│   │   │   │   │   │   ├── 📁 renderer
│   │   │   │   │   │   │   ├── 📄 document.ts
│   │   │   │   │   │   │   ├── 📄 index.ts
│   │   │   │   │   │   │   └── 📄 types.ts
│   │   │   │   │   │   ├── 📄 account-statement.repository.ts
│   │   │   │   │   │   ├── 📄 account-statement.service.test.ts
│   │   │   │   │   │   ├── 📄 account-statement.service.ts
│   │   │   │   │   │   ├── 📄 index.ts
│   │   │   │   │   │   ├── 📄 public-statement.service.ts
│   │   │   │   │   │   └── 📄 token.ts
│   │   │   │   │   ├── 📁 accounts
│   │   │   │   │   │   ├── 📄 accounts.repository.ts
│   │   │   │   │   │   ├── 📄 accounts.service.ts
│   │   │   │   │   │   ├── 📄 chart-templates.service.ts
│   │   │   │   │   │   ├── 📄 chart-templates.ts
│   │   │   │   │   │   ├── 📄 hierarchy.ts
│   │   │   │   │   │   └── 📄 index.ts
│   │   │   │   │   ├── 📁 agents
│   │   │   │   │   │   ├── 📄 index.ts
│   │   │   │   │   │   └── 📄 review.service.ts
│   │   │   │   │   ├── 📁 api-keys
│   │   │   │   │   │   ├── 📄 api-keys.repository.ts
│   │   │   │   │   │   ├── 📄 api-keys.service.ts
│   │   │   │   │   │   └── 📄 index.ts
│   │   │   │   │   ├── 📁 auth
│   │   │   │   │   │   ├── 📄 api-key-identity.ts
│   │   │   │   │   │   ├── 📄 auth.repository.ts
│   │   │   │   │   │   ├── 📄 auth.service.ts
│   │   │   │   │   │   ├── 📄 cookie.ts
│   │   │   │   │   │   ├── 📄 identity.ts
│   │   │   │   │   │   ├── 📄 index.ts
│   │   │   │   │   │   ├── 📄 oauth-identity.ts
│   │   │   │   │   │   ├── 📄 password.ts
│   │   │   │   │   │   └── 📄 tokens.ts
│   │   │   │   │   ├── 📁 automations
│   │   │   │   │   │   ├── 📄 automations.service.ts
│   │   │   │   │   │   ├── 📄 engine.ts
│   │   │   │   │   │   ├── 📄 index.ts
│   │   │   │   │   │   ├── 📄 job.ts
│   │   │   │   │   │   ├── 📄 queue.service.ts
│   │   │   │   │   │   └── 📄 repository.ts
│   │   │   │   │   ├── 📁 bank-feeds
│   │   │   │   │   │   ├── 📄 connections.repository.ts
│   │   │   │   │   │   ├── 📄 connections.service.ts
│   │   │   │   │   │   ├── 📄 feed-sync.job.ts
│   │   │   │   │   │   ├── 📄 feed-sync.service.ts
│   │   │   │   │   │   └── 📄 index.ts
│   │   │   │   │   ├── 📁 banking
│   │   │   │   │   │   ├── 📁 bank-accounts
│   │   │   │   │   │   │   ├── 📄 bank-accounts.repository.ts
│   │   │   │   │   │   │   ├── 📄 bank-accounts.service.test.ts
│   │   │   │   │   │   │   └── 📄 bank-accounts.service.ts
│   │   │   │   │   │   ├── 📁 clearing
│   │   │   │   │   │   │   ├── 📄 clearing.e4.test.ts
│   │   │   │   │   │   │   ├── 📄 clearing.multientry.property.test.ts
│   │   │   │   │   │   │   ├── 📄 clearing.race.test.ts
│   │   │   │   │   │   │   ├── 📄 clearing.repository.ts
│   │   │   │   │   │   │   ├── 📄 clearing.service.test.ts
│   │   │   │   │   │   │   ├── 📄 clearing.service.ts
│   │   │   │   │   │   │   └── 📄 index.ts
│   │   │   │   │   │   ├── 📁 csv
│   │   │   │   │   │   │   ├── 📄 index.ts
│   │   │   │   │   │   │   ├── 📄 mappings.repository.ts
│   │   │   │   │   │   │   ├── 📄 mappings.service.test.ts
│   │   │   │   │   │   │   ├── 📄 mappings.service.ts
│   │   │   │   │   │   │   ├── 📄 options.ts
│   │   │   │   │   │   │   ├── 📄 parse.test.ts
│   │   │   │   │   │   │   ├── 📄 parse.ts
│   │   │   │   │   │   │   └── 📄 tokenize.ts
│   │   │   │   │   │   ├── 📁 matching
│   │   │   │   │   │   │   ├── 📄 dates.ts
│   │   │   │   │   │   │   ├── 📄 index.ts
│   │   │   │   │   │   │   ├── 📄 proposals.service.test.ts
│   │   │   │   │   │   │   ├── 📄 repository.ts
│   │   │   │   │   │   │   ├── 📄 scoring.ts
│   │   │   │   │   │   │   └── 📄 service.ts
│   │   │   │   │   │   ├── 📁 ofx
│   │   │   │   │   │   │   ├── 📄 index.ts
│   │   │   │   │   │   │   ├── 📄 parser.test.ts
│   │   │   │   │   │   │   ├── 📄 parser.ts
│   │   │   │   │   │   │   └── 📄 tokenizer.ts
│   │   │   │   │   │   ├── 📁 reconciliation
│   │   │   │   │   │   │   ├── 📄 index.ts
│   │   │   │   │   │   │   ├── 📄 reconciliation.race.test.ts
│   │   │   │   │   │   │   ├── 📄 reconciliation.repository.ts
│   │   │   │   │   │   │   ├── 📄 reconciliation.service.test.ts
│   │   │   │   │   │   │   ├── 📄 reconciliation.service.ts
│   │   │   │   │   │   │   ├── 📄 report.property.test.ts
│   │   │   │   │   │   │   ├── 📄 report.service.test.ts
│   │   │   │   │   │   │   └── 📄 report.service.ts
│   │   │   │   │   │   ├── 📁 rules
│   │   │   │   │   │   │   ├── 📄 evaluator.ts
│   │   │   │   │   │   │   ├── 📄 index.ts
│   │   │   │   │   │   │   ├── 📄 rules.repository.ts
│   │   │   │   │   │   │   └── 📄 rules.service.ts
│   │   │   │   │   │   ├── 📁 statement-lines
│   │   │   │   │   │   │   ├── 📄 repository.ts
│   │   │   │   │   │   │   └── 📄 service.ts
│   │   │   │   │   │   ├── 📁 statements
│   │   │   │   │   │   │   ├── 📄 fingerprint.ts
│   │   │   │   │   │   │   ├── 📄 job.ts
│   │   │   │   │   │   │   ├── 📄 reads.ts
│   │   │   │   │   │   │   ├── 📄 repository.ts
│   │   │   │   │   │   │   └── 📄 service.ts
│   │   │   │   │   │   ├── 📄 index.ts
│   │   │   │   │   │   ├── 📄 parser.ts
│   │   │   │   │   │   └── 📄 rule-evaluator.ts
│   │   │   │   │   ├── 📁 bills
│   │   │   │   │   │   ├── 📁 capture
│   │   │   │   │   │   │   ├── 📄 capture.repository.ts
│   │   │   │   │   │   │   ├── 📄 capture.service.ts
│   │   │   │   │   │   │   └── 📄 extraction.job.ts
│   │   │   │   │   │   ├── 📄 ap-documents.repository.ts
│   │   │   │   │   │   ├── 📄 ap-documents.service.ts
│   │   │   │   │   │   ├── 📄 bills.service.ts
│   │   │   │   │   │   ├── 📄 index.ts
│   │   │   │   │   │   ├── 📄 summary.service.ts
│   │   │   │   │   │   └── 📄 vendor-credits.service.ts
│   │   │   │   │   ├── 📁 branding
│   │   │   │   │   │   ├── 📄 branding.repository.ts
│   │   │   │   │   │   ├── 📄 branding.service.ts
│   │   │   │   │   │   └── 📄 index.ts
│   │   │   │   │   ├── 📁 budgets
│   │   │   │   │   │   ├── 📄 budgets.repository.ts
│   │   │   │   │   │   ├── 📄 budgets.service.ts
│   │   │   │   │   │   └── 📄 index.ts
│   │   │   │   │   ├── 📁 catalog
│   │   │   │   │   │   ├── 📄 catalog.repository.ts
│   │   │   │   │   │   ├── 📄 catalog.service.ts
│   │   │   │   │   │   └── 📄 index.ts
│   │   │   │   │   ├── 📁 change-feed
│   │   │   │   │   │   ├── 📄 change-feed.repository.ts
│   │   │   │   │   │   ├── 📄 change-feed.service.ts
│   │   │   │   │   │   └── 📄 index.ts
│   │   │   │   │   ├── 📁 contacts
│   │   │   │   │   │   ├── 📄 contacts.repository.ts
│   │   │   │   │   │   ├── 📄 contacts.service.ts
│   │   │   │   │   │   └── 📄 index.ts
│   │   │   │   │   ├── 📁 delivery
│   │   │   │   │   │   ├── 📁 renderer
│   │   │   │   │   │   │   ├── 📄 document.ts
│   │   │   │   │   │   │   ├── 📄 fixtures.ts
│   │   │   │   │   │   │   ├── 📄 fonts.ts
│   │   │   │   │   │   │   ├── 📄 index.ts
│   │   │   │   │   │   │   ├── 📄 pdfmake-vfs.d.ts
│   │   │   │   │   │   │   └── 📄 types.ts
│   │   │   │   │   │   ├── 📄 delivery.repository.ts
│   │   │   │   │   │   ├── 📄 index.ts
│   │   │   │   │   │   ├── 📄 public-invoice.service.ts
│   │   │   │   │   │   ├── 📄 send-invoice.service.ts
│   │   │   │   │   │   └── 📄 token.ts
│   │   │   │   │   ├── 📁 dimensions
│   │   │   │   │   │   ├── 📄 dimensions.repository.ts
│   │   │   │   │   │   ├── 📄 dimensions.service.ts
│   │   │   │   │   │   ├── 📄 index.ts
│   │   │   │   │   │   ├── 📄 tagging.service.ts
│   │   │   │   │   │   └── 📄 tags.repository.ts
│   │   │   │   │   ├── 📁 drafts
│   │   │   │   │   │   ├── 📄 drafts.repository.ts
│   │   │   │   │   │   ├── 📄 drafts.service.ts
│   │   │   │   │   │   └── 📄 index.ts
│   │   │   │   │   ├── 📁 estimates
│   │   │   │   │   │   ├── 📄 estimates.repository.ts
│   │   │   │   │   │   ├── 📄 estimates.service.ts
│   │   │   │   │   │   ├── 📄 index.ts
│   │   │   │   │   │   └── 📄 summary.service.ts
│   │   │   │   │   ├── 📁 events
│   │   │   │   │   │   ├── 📄 bus.ts
│   │   │   │   │   │   ├── 📄 index.ts
│   │   │   │   │   │   └── 📄 outbox.ts
│   │   │   │   │   ├── 📁 expenses
│   │   │   │   │   │   ├── 📄 expenses.repository.ts
│   │   │   │   │   │   ├── 📄 expenses.service.ts
│   │   │   │   │   │   └── 📄 index.ts
│   │   │   │   │   ├── 📁 external-refs
│   │   │   │   │   │   ├── 📄 external-refs.repository.ts
│   │   │   │   │   │   ├── 📄 external-refs.service.ts
│   │   │   │   │   │   └── 📄 index.ts
│   │   │   │   │   ├── 📁 fixed-assets
│   │   │   │   │   │   ├── 📄 depreciation-sweep.ts
│   │   │   │   │   │   ├── 📄 depreciation.test.ts
│   │   │   │   │   │   ├── 📄 depreciation.ts
│   │   │   │   │   │   ├── 📄 fixed-assets.repository.ts
│   │   │   │   │   │   ├── 📄 fixed-assets.service.ts
│   │   │   │   │   │   ├── 📄 index.ts
│   │   │   │   │   │   └── 📄 job.ts
│   │   │   │   │   ├── 📁 idempotency
│   │   │   │   │   │   ├── 📄 claims.ts
│   │   │   │   │   │   ├── 📄 fingerprint.ts
│   │   │   │   │   │   ├── 📄 ids.ts
│   │   │   │   │   │   ├── 📄 index.ts
│   │   │   │   │   │   ├── 📄 response.ts
│   │   │   │   │   │   └── 📄 service.ts
│   │   │   │   │   ├── 📁 imports
│   │   │   │   │   │   ├── 📁 quickbooks
│   │   │   │   │   │   │   ├── 📄 mapping.ts
│   │   │   │   │   │   │   ├── 📄 parse.ts
│   │   │   │   │   │   │   └── 📄 service.ts
│   │   │   │   │   │   └── 📄 index.ts
│   │   │   │   │   ├── 📁 inventory
│   │   │   │   │   │   ├── 📄 costing.ts
│   │   │   │   │   │   ├── 📄 index.ts
│   │   │   │   │   │   ├── 📄 inventory.repository.ts
│   │   │   │   │   │   └── 📄 inventory.service.ts
│   │   │   │   │   ├── 📁 invoices
│   │   │   │   │   │   ├── 📄 ar-documents.repository.ts
│   │   │   │   │   │   ├── 📄 ar-documents.service.ts
│   │   │   │   │   │   ├── 📄 credit-notes.service.ts
│   │   │   │   │   │   ├── 📄 index.ts
│   │   │   │   │   │   ├── 📄 invoices.service.ts
│   │   │   │   │   │   ├── 📄 kinds.ts
│   │   │   │   │   │   ├── 📄 pricing.ts
│   │   │   │   │   │   ├── 📄 projection.ts
│   │   │   │   │   │   └── 📄 summary.service.ts
│   │   │   │   │   ├── 📁 invoicing
│   │   │   │   │   │   ├── 📁 dunning
│   │   │   │   │   │   │   ├── 📄 dunning.repository.ts
│   │   │   │   │   │   │   ├── 📄 dunning.service.ts
│   │   │   │   │   │   │   ├── 📄 engine.ts
│   │   │   │   │   │   │   ├── 📄 index.ts
│   │   │   │   │   │   │   ├── 📄 job.ts
│   │   │   │   │   │   │   └── 📄 worker.ts
│   │   │   │   │   │   ├── 📁 recurring
│   │   │   │   │   │   │   ├── 📄 engine.ts
│   │   │   │   │   │   │   ├── 📄 job.ts
│   │   │   │   │   │   │   ├── 📄 recurring.repository.ts
│   │   │   │   │   │   │   └── 📄 recurring.service.ts
│   │   │   │   │   │   └── 📄 index.ts
│   │   │   │   │   ├── 📁 ledger
│   │   │   │   │   │   ├── 📄 index.ts
│   │   │   │   │   │   ├── 📄 journal-list.service.ts
│   │   │   │   │   │   ├── 📄 journal-read.service.test.ts
│   │   │   │   │   │   ├── 📄 journal-read.service.ts
│   │   │   │   │   │   ├── 📄 posting.repository.ts
│   │   │   │   │   │   ├── 📄 posting.service.ts
│   │   │   │   │   │   └── 📄 trial-balance.service.ts
│   │   │   │   │   ├── 📁 log-retention
│   │   │   │   │   │   ├── 📄 index.ts
│   │   │   │   │   │   └── 📄 retention.ts
│   │   │   │   │   ├── 📁 mcp
│   │   │   │   │   │   ├── 📄 host.ts
│   │   │   │   │   │   └── 📄 tools.ts
│   │   │   │   │   ├── 📁 members
│   │   │   │   │   │   ├── 📄 index.ts
│   │   │   │   │   │   ├── 📄 input.ts
│   │   │   │   │   │   ├── 📄 invite-email.ts
│   │   │   │   │   │   ├── 📄 invites.service.ts
│   │   │   │   │   │   ├── 📄 members.repository.ts
│   │   │   │   │   │   ├── 📄 members.service.ts
│   │   │   │   │   │   └── 📄 tokens.ts
│   │   │   │   │   ├── 📁 oauth
│   │   │   │   │   │   ├── 📄 credentials.ts
│   │   │   │   │   │   ├── 📄 index.ts
│   │   │   │   │   │   ├── 📄 oauth.repository.ts
│   │   │   │   │   │   └── 📄 oauth.service.ts
│   │   │   │   │   ├── 📁 orgs
│   │   │   │   │   │   ├── 📄 inbound-email.ts
│   │   │   │   │   │   ├── 📄 index.ts
│   │   │   │   │   │   ├── 📄 orgs.repository.ts
│   │   │   │   │   │   └── 📄 orgs.service.ts
│   │   │   │   │   ├── 📁 pay-bills
│   │   │   │   │   │   ├── 📄 check-output.ts
│   │   │   │   │   │   ├── 📄 check-register.repository.ts
│   │   │   │   │   │   ├── 📄 index.ts
│   │   │   │   │   │   ├── 📄 issue.service.ts
│   │   │   │   │   │   ├── 📄 queue.repository.ts
│   │   │   │   │   │   ├── 📄 queue.service.ts
│   │   │   │   │   │   ├── 📄 rail-disbursements.service.ts
│   │   │   │   │   │   └── 📄 vendor-details.service.ts
│   │   │   │   │   ├── 📁 payment-terms
│   │   │   │   │   │   ├── 📄 compute-term.test.ts
│   │   │   │   │   │   ├── 📄 compute-term.ts
│   │   │   │   │   │   ├── 📄 index.ts
│   │   │   │   │   │   ├── 📄 suggestion.service.ts
│   │   │   │   │   │   ├── 📄 terms.repository.ts
│   │   │   │   │   │   └── 📄 terms.service.ts
│   │   │   │   │   ├── 📁 payments
│   │   │   │   │   │   ├── 📄 allocate.ts
│   │   │   │   │   │   ├── 📄 allocations.repository.ts
│   │   │   │   │   │   ├── 📄 allocations.service.ts
│   │   │   │   │   │   ├── 📄 index.ts
│   │   │   │   │   │   ├── 📄 input.ts
│   │   │   │   │   │   ├── 📄 payments.repository.ts
│   │   │   │   │   │   ├── 📄 payments.service.ts
│   │   │   │   │   │   └── 📄 settlement-discount.ts
│   │   │   │   │   ├── 📁 payments-processing
│   │   │   │   │   │   ├── 📄 connections.repository.ts
│   │   │   │   │   │   ├── 📄 connections.service.ts
│   │   │   │   │   │   ├── 📄 index.ts
│   │   │   │   │   │   ├── 📄 payout-account-map.repository.ts
│   │   │   │   │   │   ├── 📄 payout-config.service.ts
│   │   │   │   │   │   ├── 📄 payout-sync.repository.ts
│   │   │   │   │   │   ├── 📄 payout-sync.service.ts
│   │   │   │   │   │   ├── 📄 poll.job.ts
│   │   │   │   │   │   ├── 📄 posting.service.ts
│   │   │   │   │   │   ├── 📄 processor-events.repository.ts
│   │   │   │   │   │   ├── 📄 summary-journal.builder.ts
│   │   │   │   │   │   └── 📄 webhook.service.ts
│   │   │   │   │   ├── 📁 periods
│   │   │   │   │   │   ├── 📄 calendar.ts
│   │   │   │   │   │   ├── 📄 index.ts
│   │   │   │   │   │   ├── 📄 period-close.service.ts
│   │   │   │   │   │   ├── 📄 periods.repository.ts
│   │   │   │   │   │   ├── 📄 periods.schemas.ts
│   │   │   │   │   │   └── 📄 periods.service.ts
│   │   │   │   │   ├── 📁 permissions
│   │   │   │   │   │   ├── 📄 catalog.ts
│   │   │   │   │   │   ├── 📄 index.ts
│   │   │   │   │   │   ├── 📄 permissions.repository.ts
│   │   │   │   │   │   └── 📄 permissions.service.ts
│   │   │   │   │   ├── 📁 predocument-delivery
│   │   │   │   │   │   ├── 📄 index.ts
│   │   │   │   │   │   ├── 📄 predocument-delivery.repository.ts
│   │   │   │   │   │   └── 📄 send.service.ts
│   │   │   │   │   ├── 📁 purchase-orders
│   │   │   │   │   │   ├── 📄 index.ts
│   │   │   │   │   │   ├── 📄 purchase-orders.repository.ts
│   │   │   │   │   │   ├── 📄 purchase-orders.service.ts
│   │   │   │   │   │   └── 📄 summary.service.ts
│   │   │   │   │   ├── 📁 recurring-journals
│   │   │   │   │   │   ├── 📄 engine.ts
│   │   │   │   │   │   ├── 📄 index.ts
│   │   │   │   │   │   ├── 📄 job.ts
│   │   │   │   │   │   ├── 📄 recurring-journals.repository.ts
│   │   │   │   │   │   └── 📄 recurring-journals.service.ts
│   │   │   │   │   ├── 📁 reports
│   │   │   │   │   │   ├── 📁 cash-basis
│   │   │   │   │   │   │   ├── 📄 recognition.ts
│   │   │   │   │   │   │   ├── 📄 repository.ts
│   │   │   │   │   │   │   └── 📄 service.ts
│   │   │   │   │   │   ├── 📁 export
│   │   │   │   │   │   │   ├── 📄 adapters.test.ts
│   │   │   │   │   │   │   ├── 📄 adapters.ts
│   │   │   │   │   │   │   ├── 📄 csv.test.ts
│   │   │   │   │   │   │   ├── 📄 csv.ts
│   │   │   │   │   │   │   ├── 📄 export.service.ts
│   │   │   │   │   │   │   ├── 📄 index.ts
│   │   │   │   │   │   │   ├── 📄 tabular.ts
│   │   │   │   │   │   │   ├── 📄 xlsx.test.ts
│   │   │   │   │   │   │   └── 📄 xlsx.ts
│   │   │   │   │   │   ├── 📄 aging.repository.ts
│   │   │   │   │   │   ├── 📄 aging.service.ts
│   │   │   │   │   │   ├── 📄 amounts.ts
│   │   │   │   │   │   ├── 📄 audit.repository.ts
│   │   │   │   │   │   ├── 📄 audit.service.ts
│   │   │   │   │   │   ├── 📄 balance-sheet.service.ts
│   │   │   │   │   │   ├── 📄 balances.repository.ts
│   │   │   │   │   │   ├── 📄 balances.service.ts
│   │   │   │   │   │   ├── 📄 budget-vs-actual.service.ts
│   │   │   │   │   │   ├── 📄 cash-flow-projection.service.ts
│   │   │   │   │   │   ├── 📄 cash-flow.service.ts
│   │   │   │   │   │   ├── 📄 general-ledger.repository.ts
│   │   │   │   │   │   ├── 📄 general-ledger.service.ts
│   │   │   │   │   │   ├── 📄 index.ts
│   │   │   │   │   │   ├── 📄 profit-and-loss.service.ts
│   │   │   │   │   │   └── 📄 tree.ts
│   │   │   │   │   ├── 📁 roles
│   │   │   │   │   │   ├── 📄 index.ts
│   │   │   │   │   │   ├── 📄 roles.repository.ts
│   │   │   │   │   │   ├── 📄 roles.service.test.ts
│   │   │   │   │   │   └── 📄 roles.service.ts
│   │   │   │   │   ├── 📁 scheduling
│   │   │   │   │   │   ├── 📄 automation.ts
│   │   │   │   │   │   ├── 📄 index.ts
│   │   │   │   │   │   ├── 📄 tick.ts
│   │   │   │   │   │   └── 📄 trigger.ts
│   │   │   │   │   ├── 📁 settings
│   │   │   │   │   │   ├── 📄 control-accounts.ts
│   │   │   │   │   │   ├── 📄 depreciation-accounts.ts
│   │   │   │   │   │   ├── 📄 discount-accounts.ts
│   │   │   │   │   │   ├── 📄 index.ts
│   │   │   │   │   │   └── 📄 settings.repository.ts
│   │   │   │   │   ├── 📁 statements
│   │   │   │   │   │   ├── 📁 renderer
│   │   │   │   │   │   │   ├── 📄 document.ts
│   │   │   │   │   │   │   ├── 📄 index.ts
│   │   │   │   │   │   │   └── 📄 types.ts
│   │   │   │   │   │   ├── 📄 index.ts
│   │   │   │   │   │   ├── 📄 statement-package.repository.ts
│   │   │   │   │   │   ├── 📄 statement-package.service.test.ts
│   │   │   │   │   │   └── 📄 statement-package.service.ts
│   │   │   │   │   ├── 📁 tax
│   │   │   │   │   │   ├── 📄 index.ts
│   │   │   │   │   │   ├── 📄 tax-rates.repository.ts
│   │   │   │   │   │   └── 📄 tax-rates.service.ts
│   │   │   │   │   └── 📁 ten99
│   │   │   │   │       ├── 📁 renderer
│   │   │   │   │       │   ├── 📄 document.ts
│   │   │   │   │       │   ├── 📄 index.ts
│   │   │   │   │       │   └── 📄 types.ts
│   │   │   │   │       ├── 📄 index.ts
│   │   │   │   │       ├── 📄 ten99.repository.ts
│   │   │   │   │       └── 📄 ten99.service.ts
│   │   │   │   ├── 📁 providers
│   │   │   │   │   ├── 📁 bankfeed
│   │   │   │   │   │   ├── 📄 fake.ts
│   │   │   │   │   │   ├── 📄 index.ts
│   │   │   │   │   │   ├── 📄 stripe-financial-connections.ts
│   │   │   │   │   │   └── 📄 types.ts
│   │   │   │   │   ├── 📁 efile
│   │   │   │   │   │   ├── 📄 index.ts
│   │   │   │   │   │   ├── 📄 iris.ts
│   │   │   │   │   │   └── 📄 manual.ts
│   │   │   │   │   ├── 📁 email
│   │   │   │   │   │   ├── 📄 log.ts
│   │   │   │   │   │   └── 📄 ses.ts
│   │   │   │   │   ├── 📁 extraction
│   │   │   │   │   │   ├── 📄 anthropic.ts
│   │   │   │   │   │   ├── 📄 deterministic.ts
│   │   │   │   │   │   └── 📄 index.ts
│   │   │   │   │   ├── 📁 inbound-mail
│   │   │   │   │   │   ├── 📄 dev.ts
│   │   │   │   │   │   ├── 📄 index.ts
│   │   │   │   │   │   └── 📄 ses-inbound.ts
│   │   │   │   │   ├── 📁 logsink
│   │   │   │   │   │   ├── 📄 db.ts
│   │   │   │   │   │   └── 📄 index.ts
│   │   │   │   │   ├── 📁 payment
│   │   │   │   │   │   ├── 📄 fake.ts
│   │   │   │   │   │   ├── 📄 index.ts
│   │   │   │   │   │   ├── 📄 square.ts
│   │   │   │   │   │   ├── 📄 stripe.ts
│   │   │   │   │   │   └── 📄 types.ts
│   │   │   │   │   ├── 📁 queue
│   │   │   │   │   │   └── 📄 in-process.ts
│   │   │   │   │   ├── 📁 secrets
│   │   │   │   │   │   ├── 📄 aws-secrets-manager.ts
│   │   │   │   │   │   ├── 📄 index.ts
│   │   │   │   │   │   └── 📄 local.ts
│   │   │   │   │   ├── 📁 storage
│   │   │   │   │   │   ├── 📄 index.ts
│   │   │   │   │   │   ├── 📄 local.test.ts
│   │   │   │   │   │   ├── 📄 local.ts
│   │   │   │   │   │   └── 📄 s3.ts
│   │   │   │   │   └── 📄 index.ts
│   │   │   │   └── 📁 transport
│   │   │   │       ├── 📁 routes
│   │   │   │       │   ├── 📄 accounts.ts
│   │   │   │       │   ├── 📄 agent-proposals.ts
│   │   │   │       │   ├── 📄 api-keys.ts
│   │   │   │       │   ├── 📄 artifacts.ts
│   │   │   │       │   ├── 📄 auth.ts
│   │   │   │       │   ├── 📄 automations.ts
│   │   │   │       │   ├── 📄 bank-accounts.ts
│   │   │   │       │   ├── 📄 bank-feeds.ts
│   │   │   │       │   ├── 📄 bank-imports.ts
│   │   │   │       │   ├── 📄 bank-rules.ts
│   │   │   │       │   ├── 📄 bill-captures.ts
│   │   │   │       │   ├── 📄 bill-inbound.ts
│   │   │   │       │   ├── 📄 bills.ts
│   │   │   │       │   ├── 📄 branding.ts
│   │   │   │       │   ├── 📄 budgets.ts
│   │   │   │       │   ├── 📄 catalog.ts
│   │   │   │       │   ├── 📄 change-feed.ts
│   │   │   │       │   ├── 📄 chart-templates.ts
│   │   │   │       │   ├── 📄 contacts.ts
│   │   │   │       │   ├── 📄 customer-statements.ts
│   │   │   │       │   ├── 📄 dimensions.ts
│   │   │   │       │   ├── 📄 drafts.ts
│   │   │   │       │   ├── 📄 dunning.ts
│   │   │   │       │   ├── 📄 estimates.ts
│   │   │   │       │   ├── 📄 expenses.ts
│   │   │   │       │   ├── 📄 external-refs.ts
│   │   │   │       │   ├── 📄 fixed-assets.ts
│   │   │   │       │   ├── 📄 imports.ts
│   │   │   │       │   ├── 📄 index.ts
│   │   │   │       │   ├── 📄 inventory.ts
│   │   │   │       │   ├── 📄 invoices.ts
│   │   │   │       │   ├── 📄 journal-lines.ts
│   │   │   │       │   ├── 📄 journals.ts
│   │   │   │       │   ├── 📄 members.ts
│   │   │   │       │   ├── 📄 oauth-clients.ts
│   │   │   │       │   ├── 📄 oauth-flow.ts
│   │   │   │       │   ├── 📄 orgs.ts
│   │   │   │       │   ├── 📄 pay-bills.ts
│   │   │   │       │   ├── 📄 payment-terms.ts
│   │   │   │       │   ├── 📄 payments.ts
│   │   │   │       │   ├── 📄 periods.ts
│   │   │   │       │   ├── 📄 predocument-delivery.ts
│   │   │   │       │   ├── 📄 processing-webhook.ts
│   │   │   │       │   ├── 📄 processing.ts
│   │   │   │       │   ├── 📄 public-invoices.ts
│   │   │   │       │   ├── 📄 public-pay-link.ts
│   │   │   │       │   ├── 📄 public-statements.ts
│   │   │   │       │   ├── 📄 purchase-orders.ts
│   │   │   │       │   ├── 📄 reconciliation.ts
│   │   │   │       │   ├── 📄 recurring-invoices.ts
│   │   │   │       │   ├── 📄 recurring-journals.ts
│   │   │   │       │   ├── 📄 report-export.ts
│   │   │   │       │   ├── 📄 reports.ts
│   │   │   │       │   ├── 📄 roles.ts
│   │   │   │       │   ├── 📄 scheduling.ts
│   │   │   │       │   ├── 📄 settings.ts
│   │   │   │       │   ├── 📄 statement-lines.ts
│   │   │   │       │   ├── 📄 statement-packages.ts
│   │   │   │       │   ├── 📄 support.ts
│   │   │   │       │   ├── 📄 tax-rates.ts
│   │   │   │       │   └── 📄 ten99.ts
│   │   │   │       ├── 📄 app.ts
│   │   │   │       ├── 📄 context.ts
│   │   │   │       ├── 📄 cors.ts
│   │   │   │       ├── 📄 errors.ts
│   │   │   │       ├── 📄 health.ts
│   │   │   │       ├── 📄 idempotency.ts
│   │   │   │       ├── 📄 index.ts
│   │   │   │       ├── 📄 openapi.ts
│   │   │   │       ├── 📄 schemas.ts
│   │   │   │       └── 📄 types.ts
│   │   │   ├── 📁 test
│   │   │   │   ├── 📁 accounts
│   │   │   │   │   ├── 📄 accounts.service.test.ts
│   │   │   │   │   ├── 📄 chart-templates.test.ts
│   │   │   │   │   ├── 📄 hierarchy.test.ts
│   │   │   │   │   ├── 📄 pagination.test.ts
│   │   │   │   │   ├── 📄 schemas.test.ts
│   │   │   │   │   └── 📄 support.ts
│   │   │   │   ├── 📁 auth
│   │   │   │   │   ├── 📄 auth.service.test.ts
│   │   │   │   │   ├── 📄 caller-permissions.test.ts
│   │   │   │   │   ├── 📄 idempotency.test.ts
│   │   │   │   │   ├── 📄 identity.test.ts
│   │   │   │   │   ├── 📄 password.test.ts
│   │   │   │   │   ├── 📄 session.test.ts
│   │   │   │   │   ├── 📄 support.ts
│   │   │   │   │   └── 📄 switch.test.ts
│   │   │   │   ├── 📁 automations
│   │   │   │   │   ├── 📄 never-posts.test.ts
│   │   │   │   │   ├── 📄 queue.property.test.ts
│   │   │   │   │   └── 📄 support.ts
│   │   │   │   ├── 📁 bank-feeds
│   │   │   │   │   └── 📄 feed-sync.test.ts
│   │   │   │   ├── 📁 banking
│   │   │   │   │   ├── 📁 matching
│   │   │   │   │   │   └── 📄 support.ts
│   │   │   │   │   ├── 📁 rules
│   │   │   │   │   │   ├── 📄 evaluator.property.test.ts
│   │   │   │   │   │   ├── 📄 rules.service.test.ts
│   │   │   │   │   │   └── 📄 support.ts
│   │   │   │   │   ├── 📁 statements
│   │   │   │   │   │   ├── 📄 fingerprint.test.ts
│   │   │   │   │   │   ├── 📄 import.service.test.ts
│   │   │   │   │   │   └── 📄 manual-statement-line.test.ts
│   │   │   │   │   ├── 📄 clearing-support.ts
│   │   │   │   │   ├── 📄 credit-card-reconciliation.test.ts
│   │   │   │   │   ├── 📄 invariants.property.test.ts
│   │   │   │   │   ├── 📄 scale.e10.test.ts
│   │   │   │   │   └── 📄 support.ts
│   │   │   │   ├── 📁 bills
│   │   │   │   │   ├── 📁 capture
│   │   │   │   │   │   ├── 📄 capture.service.test.ts
│   │   │   │   │   │   ├── 📄 inbound.test.ts
│   │   │   │   │   │   └── 📄 support.ts
│   │   │   │   │   ├── 📄 approve-race.test.ts
│   │   │   │   │   ├── 📄 bills.service.test.ts
│   │   │   │   │   ├── 📄 committed.test.ts
│   │   │   │   │   ├── 📄 direction.test.ts
│   │   │   │   │   ├── 📄 duplicate-reference.test.ts
│   │   │   │   │   ├── 📄 permissions.test.ts
│   │   │   │   │   ├── 📄 summary.test.ts
│   │   │   │   │   ├── 📄 support.ts
│   │   │   │   │   └── 📄 vendor-credits.service.test.ts
│   │   │   │   ├── 📁 branding
│   │   │   │   │   ├── 📄 branding.test.ts
│   │   │   │   │   └── 📄 support.ts
│   │   │   │   ├── 📁 budgets
│   │   │   │   │   └── 📄 budget-vs-actual.property.test.ts
│   │   │   │   ├── 📁 catalog
│   │   │   │   │   ├── 📄 catalog.service.test.ts
│   │   │   │   │   ├── 📄 document-lines.test.ts
│   │   │   │   │   └── 📄 support.ts
│   │   │   │   ├── 📁 config
│   │   │   │   │   └── 📄 config.test.ts
│   │   │   │   ├── 📁 contacts
│   │   │   │   │   ├── 📄 contacts.service.test.ts
│   │   │   │   │   ├── 📄 pagination.test.ts
│   │   │   │   │   ├── 📄 schema.test.ts
│   │   │   │   │   ├── 📄 schemas.test.ts
│   │   │   │   │   └── 📄 support.ts
│   │   │   │   ├── 📁 context
│   │   │   │   │   └── 📄 store.test.ts
│   │   │   │   ├── 📁 db
│   │   │   │   │   ├── 📄 bootstrap.ts
│   │   │   │   │   ├── 📄 container.ts
│   │   │   │   │   ├── 📄 factories.ts
│   │   │   │   │   ├── 📄 harness.test.ts
│   │   │   │   │   ├── 📄 harness.ts
│   │   │   │   │   ├── 📄 index.ts
│   │   │   │   │   ├── 📄 tenant-scope.test.ts
│   │   │   │   │   ├── 📄 transaction-scope.test.ts
│   │   │   │   │   ├── 📄 uuid.test.ts
│   │   │   │   │   └── 📄 uuid.ts
│   │   │   │   ├── 📁 delivery
│   │   │   │   │   ├── 📄 public-invoice.test.ts
│   │   │   │   │   ├── 📄 renderer.test.ts
│   │   │   │   │   ├── 📄 support.ts
│   │   │   │   │   └── 📄 token.test.ts
│   │   │   │   ├── 📁 dimensions
│   │   │   │   │   ├── 📄 axis-bound.test.ts
│   │   │   │   │   ├── 📄 dimensions.service.test.ts
│   │   │   │   │   ├── 📄 support.ts
│   │   │   │   │   └── 📄 tagging.test.ts
│   │   │   │   ├── 📁 drafts
│   │   │   │   │   ├── 📄 drafts.service.test.ts
│   │   │   │   │   ├── 📄 post-race.test.ts
│   │   │   │   │   └── 📄 support.ts
│   │   │   │   ├── 📁 enforcement
│   │   │   │   │   ├── 📄 change-feed.property.test.ts
│   │   │   │   │   ├── 📄 cross-org-references.test.ts
│   │   │   │   │   ├── 📄 cross-org.test.ts
│   │   │   │   │   ├── 📄 event-outbox-support.ts
│   │   │   │   │   ├── 📄 event-outbox.property.test.ts
│   │   │   │   │   ├── 📄 external-refs.property.test.ts
│   │   │   │   │   ├── 📄 grants.test.ts
│   │   │   │   │   ├── 📄 idempotency-claims.test.ts
│   │   │   │   │   ├── 📄 period-lock-race.test.ts
│   │   │   │   │   ├── 📄 period-lock-scope.test.ts
│   │   │   │   │   ├── 📄 permission-matrix.test.ts
│   │   │   │   │   ├── 📄 platform-security.test.ts
│   │   │   │   │   ├── 📄 posting-race.test.ts
│   │   │   │   │   ├── 📄 refusal-vocabulary.test.ts
│   │   │   │   │   └── 📄 support.ts
│   │   │   │   ├── 📁 errors
│   │   │   │   │   └── 📄 errors.test.ts
│   │   │   │   ├── 📁 estimates
│   │   │   │   │   ├── 📄 estimates.property.test.ts
│   │   │   │   │   ├── 📄 estimates.service.test.ts
│   │   │   │   │   ├── 📄 summary.test.ts
│   │   │   │   │   └── 📄 support.ts
│   │   │   │   ├── 📁 expenses
│   │   │   │   │   ├── 📄 expenses.service.test.ts
│   │   │   │   │   └── 📄 support.ts
│   │   │   │   ├── 📁 fixed-assets
│   │   │   │   │   ├── 📄 depreciation-sweep.race.test.ts
│   │   │   │   │   ├── 📄 depreciation-sweep.test.ts
│   │   │   │   │   └── 📄 schedule-round-trip.property.test.ts
│   │   │   │   ├── 📁 idempotency
│   │   │   │   │   ├── 📄 concurrency.test.ts
│   │   │   │   │   ├── 📄 fingerprint.test.ts
│   │   │   │   │   ├── 📄 global-concurrency.test.ts
│   │   │   │   │   ├── 📄 ids.test.ts
│   │   │   │   │   ├── 📄 response.test.ts
│   │   │   │   │   ├── 📄 service.test.ts
│   │   │   │   │   └── 📄 support.ts
│   │   │   │   ├── 📁 imports
│   │   │   │   │   ├── 📄 quickbooks-parse.test.ts
│   │   │   │   │   └── 📄 quickbooks.test.ts
│   │   │   │   ├── 📁 inventory
│   │   │   │   │   ├── 📄 costing.test.ts
│   │   │   │   │   └── 📄 inventory.service.test.ts
│   │   │   │   ├── 📁 invoices
│   │   │   │   │   ├── 📄 approve-race.test.ts
│   │   │   │   │   ├── 📄 invoices.service.test.ts
│   │   │   │   │   ├── 📄 summary.test.ts
│   │   │   │   │   └── 📄 support.ts
│   │   │   │   ├── 📁 invoicing
│   │   │   │   │   ├── 📄 dunning-select.test.ts
│   │   │   │   │   ├── 📄 dunning.test.ts
│   │   │   │   │   ├── 📄 recurring-advance.test.ts
│   │   │   │   │   ├── 📄 recurring.test.ts
│   │   │   │   │   └── 📄 support.ts
│   │   │   │   ├── 📁 ledger
│   │   │   │   │   ├── 📄 journal-list.test.ts
│   │   │   │   │   ├── 📄 posting.test.ts
│   │   │   │   │   └── 📄 support.ts
│   │   │   │   ├── 📁 log-retention
│   │   │   │   │   └── 📄 retention.test.ts
│   │   │   │   ├── 📁 logging
│   │   │   │   │   ├── 📄 log-sink-stream.test.ts
│   │   │   │   │   ├── 📄 logger.test.ts
│   │   │   │   │   └── 📄 redact.test.ts
│   │   │   │   ├── 📁 members
│   │   │   │   │   ├── 📄 invite-email.test.ts
│   │   │   │   │   ├── 📄 invites.service.test.ts
│   │   │   │   │   ├── 📄 last-owner-race.test.ts
│   │   │   │   │   ├── 📄 members.service.test.ts
│   │   │   │   │   ├── 📄 race-support.ts
│   │   │   │   │   └── 📄 support.ts
│   │   │   │   ├── 📁 orgs
│   │   │   │   │   └── 📄 orgs.service.test.ts
│   │   │   │   ├── 📁 pay-bills
│   │   │   │   │   ├── 📄 issue.test.ts
│   │   │   │   │   ├── 📄 queue-contention.race.test.ts
│   │   │   │   │   ├── 📄 queue-invariants.test.ts
│   │   │   │   │   └── 📄 support.ts
│   │   │   │   ├── 📁 payment-terms
│   │   │   │   │   ├── 📄 discount-suggestion.property.test.ts
│   │   │   │   │   ├── 📄 suggestion.service.test.ts
│   │   │   │   │   ├── 📄 support.ts
│   │   │   │   │   └── 📄 terms.service.test.ts
│   │   │   │   ├── 📁 payments
│   │   │   │   │   ├── 📄 allocations.service.test.ts
│   │   │   │   │   ├── 📄 over-allocation-race.test.ts
│   │   │   │   │   ├── 📄 payments.service.test.ts
│   │   │   │   │   └── 📄 support.ts
│   │   │   │   ├── 📁 payments-processing
│   │   │   │   │   ├── 📄 enforcement.test.ts
│   │   │   │   │   ├── 📄 idempotency.property.test.ts
│   │   │   │   │   ├── 📄 manual-payout.property.test.ts
│   │   │   │   │   ├── 📄 summary-journal.builder.test.ts
│   │   │   │   │   └── 📄 support.ts
│   │   │   │   ├── 📁 periods
│   │   │   │   │   ├── 📄 calendar.test.ts
│   │   │   │   │   ├── 📄 period-close.service.test.ts
│   │   │   │   │   ├── 📄 periods.service.test.ts
│   │   │   │   │   ├── 📄 postable.test.ts
│   │   │   │   │   └── 📄 support.ts
│   │   │   │   ├── 📁 permissions
│   │   │   │   │   ├── 📄 catalog.test.ts
│   │   │   │   │   ├── 📄 memoization.test.ts
│   │   │   │   │   ├── 📄 resolution.test.ts
│   │   │   │   │   ├── 📄 support.ts
│   │   │   │   │   └── 📄 unauthenticated.test.ts
│   │   │   │   ├── 📁 predocument-delivery
│   │   │   │   │   └── 📄 send.service.test.ts
│   │   │   │   ├── 📁 properties
│   │   │   │   │   ├── 📄 accounting-equation.test.ts
│   │   │   │   │   ├── 📄 arbitraries.ts
│   │   │   │   │   ├── 📄 balance-sheet-arbitraries.ts
│   │   │   │   │   ├── 📄 balance-sheet.test.ts
│   │   │   │   │   ├── 📄 balance.test.ts
│   │   │   │   │   ├── 📄 credit-note-nets-to-zero.test.ts
│   │   │   │   │   ├── 📄 cross-report-arbitraries.ts
│   │   │   │   │   ├── 📄 cross-report.test.ts
│   │   │   │   │   ├── 📄 document-numbering.test.ts
│   │   │   │   │   ├── 📄 general-ledger-arbitraries.ts
│   │   │   │   │   ├── 📄 general-ledger.test.ts
│   │   │   │   │   ├── 📄 posting-order.test.ts
│   │   │   │   │   ├── 📄 report-account-filter.test.ts
│   │   │   │   │   ├── 📄 report-arbitraries.ts
│   │   │   │   │   ├── 📄 report-profit-and-loss.test.ts
│   │   │   │   │   ├── 📄 report-slices.test.ts
│   │   │   │   │   ├── 📄 report-subtotals.test.ts
│   │   │   │   │   ├── 📄 report-trial-balance.test.ts
│   │   │   │   │   ├── 📄 reversal.test.ts
│   │   │   │   │   ├── 📄 structural.test.ts
│   │   │   │   │   ├── 📄 subledger-agreement.test.ts
│   │   │   │   │   ├── 📄 subledger-allocation.test.ts
│   │   │   │   │   ├── 📄 subledger-arbitraries.ts
│   │   │   │   │   ├── 📄 subledger-support.ts
│   │   │   │   │   ├── 📄 support.ts
│   │   │   │   │   └── 📄 tax-mode.test.ts
│   │   │   │   ├── 📁 providers
│   │   │   │   │   ├── 📁 logsink
│   │   │   │   │   │   └── 📄 db.test.ts
│   │   │   │   │   ├── 📁 queue
│   │   │   │   │   │   └── 📄 in-process.test.ts
│   │   │   │   │   └── 📄 email.test.ts
│   │   │   │   ├── 📁 purchase-orders
│   │   │   │   │   ├── 📄 purchase-orders.property.test.ts
│   │   │   │   │   ├── 📄 purchase-orders.service.test.ts
│   │   │   │   │   └── 📄 support.ts
│   │   │   │   ├── 📁 recurring-journals
│   │   │   │   │   ├── 📄 materialize-cycle.race.test.ts
│   │   │   │   │   └── 📄 materialize-cycle.test.ts
│   │   │   │   ├── 📁 reports
│   │   │   │   │   ├── 📄 aging.test.ts
│   │   │   │   │   ├── 📄 audit.service.test.ts
│   │   │   │   │   ├── 📄 balance-sheet-support.ts
│   │   │   │   │   ├── 📄 balance-sheet.test.ts
│   │   │   │   │   ├── 📄 balances.test.ts
│   │   │   │   │   ├── 📄 cash-basis-recognition.test.ts
│   │   │   │   │   ├── 📄 cash-basis.test.ts
│   │   │   │   │   ├── 📄 cash-flow-projection.test.ts
│   │   │   │   │   ├── 📄 cash-flow.test.ts
│   │   │   │   │   ├── 📄 general-ledger.test.ts
│   │   │   │   │   ├── 📄 profit-and-loss.test.ts
│   │   │   │   │   └── 📄 support.ts
│   │   │   │   ├── 📁 schema
│   │   │   │   │   ├── 📄 banking.test.ts
│   │   │   │   │   ├── 📄 dimensions.test.ts
│   │   │   │   │   ├── 📄 journal-drafts.test.ts
│   │   │   │   │   ├── 📄 platform.test.ts
│   │   │   │   │   ├── 📄 q.test.ts
│   │   │   │   │   └── 📄 subledger.test.ts
│   │   │   │   ├── 📁 settings
│   │   │   │   │   ├── 📄 control-accounts.test.ts
│   │   │   │   │   ├── 📄 discount-accounts.test.ts
│   │   │   │   │   └── 📄 support.ts
│   │   │   │   ├── 📁 setup
│   │   │   │   │   └── 📄 global-setup.ts
│   │   │   │   ├── 📁 tax
│   │   │   │   │   ├── 📄 support.ts
│   │   │   │   │   └── 📄 tax-rates.service.test.ts
│   │   │   │   ├── 📁 ten99
│   │   │   │   │   └── 📄 rollup.test.ts
│   │   │   │   ├── 📁 transport
│   │   │   │   │   ├── 📄 app.test.ts
│   │   │   │   │   ├── 📄 bill-captures-support.ts
│   │   │   │   │   ├── 📄 bill-captures.http.test.ts
│   │   │   │   │   ├── 📄 cors.test.ts
│   │   │   │   │   ├── 📄 harness.ts
│   │   │   │   │   ├── 📄 openapi.test.ts
│   │   │   │   │   ├── 📄 routes.test.ts
│   │   │   │   │   ├── 📄 v1-inv.test.ts
│   │   │   │   │   ├── 📄 v1-m2.test.ts
│   │   │   │   │   ├── 📄 v1-m3.test.ts
│   │   │   │   │   ├── 📄 v1-m4.test.ts
│   │   │   │   │   ├── 📄 v1-q.test.ts
│   │   │   │   │   ├── 📄 v1-support.ts
│   │   │   │   │   └── 📄 v1.test.ts
│   │   │   │   └── 📝 README.md
│   │   │   ├── ⚙️ package.json
│   │   │   └── ⚙️ tsconfig.json
│   │   ├── 📁 shared-types
│   │   │   ├── 📁 src
│   │   │   │   ├── 📁 account-statements
│   │   │   │   │   ├── 📄 index.ts
│   │   │   │   │   └── 📄 statement.ts
│   │   │   │   ├── 📁 accountant
│   │   │   │   │   ├── 📄 audit.ts
│   │   │   │   │   ├── 📄 index.ts
│   │   │   │   │   ├── 📄 period-close.ts
│   │   │   │   │   └── 📄 statement-package.ts
│   │   │   │   ├── 📁 accounts
│   │   │   │   │   ├── 📄 accounts.ts
│   │   │   │   │   ├── 📄 chart-templates.ts
│   │   │   │   │   └── 📄 index.ts
│   │   │   │   ├── 📁 auth
│   │   │   │   │   ├── 📄 auth.ts
│   │   │   │   │   └── 📄 index.ts
│   │   │   │   ├── 📁 automations
│   │   │   │   │   ├── 📄 automations.ts
│   │   │   │   │   └── 📄 index.ts
│   │   │   │   ├── 📁 bank-feeds
│   │   │   │   │   ├── 📄 bank-feeds.ts
│   │   │   │   │   └── 📄 index.ts
│   │   │   │   ├── 📁 banking
│   │   │   │   │   ├── 📄 bank-accounts.ts
│   │   │   │   │   ├── 📄 banking.ts
│   │   │   │   │   ├── 📄 clearing.ts
│   │   │   │   │   ├── 📄 contracts.test.ts
│   │   │   │   │   ├── 📄 imports.ts
│   │   │   │   │   ├── 📄 index.ts
│   │   │   │   │   ├── 📄 matching.ts
│   │   │   │   │   ├── 📄 reconciliation-report.ts
│   │   │   │   │   ├── 📄 reconciliation.ts
│   │   │   │   │   ├── 📄 refusals.ts
│   │   │   │   │   ├── 📄 rules.ts
│   │   │   │   │   └── 📄 statement-lines.ts
│   │   │   │   ├── 📁 budgets
│   │   │   │   │   ├── 📄 budgets.ts
│   │   │   │   │   └── 📄 index.ts
│   │   │   │   ├── 📁 catalog
│   │   │   │   │   ├── 📄 catalog.ts
│   │   │   │   │   └── 📄 index.ts
│   │   │   │   ├── 📁 contacts
│   │   │   │   │   ├── 📄 contacts.ts
│   │   │   │   │   └── 📄 index.ts
│   │   │   │   ├── 📁 delivery
│   │   │   │   │   ├── 📄 branding.ts
│   │   │   │   │   ├── 📄 delivery.ts
│   │   │   │   │   └── 📄 index.ts
│   │   │   │   ├── 📁 dimensions
│   │   │   │   │   ├── 📄 dimensions.ts
│   │   │   │   │   └── 📄 index.ts
│   │   │   │   ├── 📁 drafts
│   │   │   │   │   ├── 📄 drafts.ts
│   │   │   │   │   └── 📄 index.ts
│   │   │   │   ├── 📁 fixed-assets
│   │   │   │   │   ├── 📄 fixed-assets.ts
│   │   │   │   │   └── 📄 index.ts
│   │   │   │   ├── 📁 imports
│   │   │   │   │   ├── 📄 index.ts
│   │   │   │   │   └── 📄 quickbooks.ts
│   │   │   │   ├── 📁 inventory
│   │   │   │   │   ├── 📄 index.ts
│   │   │   │   │   └── 📄 inventory.ts
│   │   │   │   ├── 📁 invoicing
│   │   │   │   │   ├── 📄 dunning.ts
│   │   │   │   │   ├── 📄 index.ts
│   │   │   │   │   └── 📄 recurring.ts
│   │   │   │   ├── 📁 journals
│   │   │   │   │   ├── 📄 index.ts
│   │   │   │   │   └── 📄 journals.ts
│   │   │   │   ├── 📁 members
│   │   │   │   │   ├── 📄 index.ts
│   │   │   │   │   └── 📄 members.ts
│   │   │   │   ├── 📁 money
│   │   │   │   │   ├── 📄 allocate.test.ts
│   │   │   │   │   ├── 📄 allocate.ts
│   │   │   │   │   ├── 📄 index.ts
│   │   │   │   │   ├── 📄 money.test.ts
│   │   │   │   │   ├── 📄 money.ts
│   │   │   │   │   ├── 📄 range.test.ts
│   │   │   │   │   ├── 📄 rounding.test.ts
│   │   │   │   │   └── 📄 rounding.ts
│   │   │   │   ├── 📁 orgs
│   │   │   │   │   ├── 📄 index.ts
│   │   │   │   │   ├── 📄 orgs.ts
│   │   │   │   │   └── 📄 settings.ts
│   │   │   │   ├── 📁 pay-bills
│   │   │   │   │   ├── 📄 index.ts
│   │   │   │   │   └── 📄 pay-bills.ts
│   │   │   │   ├── 📁 payment-terms
│   │   │   │   │   ├── 📄 index.ts
│   │   │   │   │   └── 📄 payment-terms.ts
│   │   │   │   ├── 📁 payments-processing
│   │   │   │   │   ├── 📄 connections.ts
│   │   │   │   │   ├── 📄 index.ts
│   │   │   │   │   ├── 📄 pay-link.ts
│   │   │   │   │   └── 📄 payout-sync.ts
│   │   │   │   ├── 📁 periods
│   │   │   │   │   ├── 📄 index.ts
│   │   │   │   │   └── 📄 periods.ts
│   │   │   │   ├── 📁 platform
│   │   │   │   │   ├── 📄 api-keys.ts
│   │   │   │   │   ├── 📄 change-feed.ts
│   │   │   │   │   ├── 📄 external-refs.ts
│   │   │   │   │   ├── 📄 index.ts
│   │   │   │   │   └── 📄 oauth.ts
│   │   │   │   ├── 📁 procurement
│   │   │   │   │   ├── 📄 deliveries.ts
│   │   │   │   │   ├── 📄 estimates.ts
│   │   │   │   │   ├── 📄 expenses.ts
│   │   │   │   │   ├── 📄 index.ts
│   │   │   │   │   └── 📄 purchase-orders.ts
│   │   │   │   ├── 📁 recurring-journals
│   │   │   │   │   ├── 📄 index.ts
│   │   │   │   │   └── 📄 recurring-journals.ts
│   │   │   │   ├── 📁 reports
│   │   │   │   │   ├── 📄 balance-sheet.ts
│   │   │   │   │   ├── 📄 balances.ts
│   │   │   │   │   ├── 📄 cash-flow-projection.ts
│   │   │   │   │   ├── 📄 cash-flow.ts
│   │   │   │   │   ├── 📄 export.ts
│   │   │   │   │   ├── 📄 general-ledger.ts
│   │   │   │   │   ├── 📄 groups.ts
│   │   │   │   │   ├── 📄 index.ts
│   │   │   │   │   ├── 📄 profit-and-loss.ts
│   │   │   │   │   └── 📄 reports.ts
│   │   │   │   ├── 📁 roles
│   │   │   │   │   ├── 📄 index.ts
│   │   │   │   │   └── 📄 roles.ts
│   │   │   │   ├── 📁 subledger
│   │   │   │   │   ├── 📄 aging.ts
│   │   │   │   │   ├── 📄 allocations.ts
│   │   │   │   │   ├── 📄 bills.ts
│   │   │   │   │   ├── 📄 captures.ts
│   │   │   │   │   ├── 📄 contracts.test.ts
│   │   │   │   │   ├── 📄 documents.ts
│   │   │   │   │   ├── 📄 index.ts
│   │   │   │   │   ├── 📄 invoices.ts
│   │   │   │   │   └── 📄 payments.ts
│   │   │   │   ├── 📁 tax
│   │   │   │   │   ├── 📄 compute.test.ts
│   │   │   │   │   ├── 📄 compute.ts
│   │   │   │   │   ├── 📄 index.ts
│   │   │   │   │   ├── 📄 rate.test.ts
│   │   │   │   │   ├── 📄 rate.ts
│   │   │   │   │   └── 📄 tax.ts
│   │   │   │   ├── 📁 ten99
│   │   │   │   │   ├── 📄 index.ts
│   │   │   │   │   └── 📄 ten99.ts
│   │   │   │   ├── 📁 wire
│   │   │   │   │   ├── 📄 index.ts
│   │   │   │   │   ├── 📄 pagination.ts
│   │   │   │   │   ├── 📄 patch.ts
│   │   │   │   │   └── 📄 wire.ts
│   │   │   │   └── 📄 index.ts
│   │   │   ├── ⚙️ package.json
│   │   │   └── ⚙️ tsconfig.json
│   │   └── 📁 web
│   │       ├── 📁 scripts
│   │       │   └── 📄 check-client-drift.mjs
│   │       ├── 📁 src
│   │       │   ├── 📁 api
│   │       │   │   ├── 📄 client.ts
│   │       │   │   ├── 📄 errors.ts
│   │       │   │   ├── 📄 idempotency.ts
│   │       │   │   ├── 📄 index.ts
│   │       │   │   ├── 📄 presentation.ts
│   │       │   │   └── 📄 schema.d.ts
│   │       │   ├── 📁 auth
│   │       │   │   ├── 📄 create-org.tsx
│   │       │   │   ├── 📄 identity.ts
│   │       │   │   ├── 📄 org-selection.tsx
│   │       │   │   ├── 📄 sign-out.tsx
│   │       │   │   └── 📄 switch-org.ts
│   │       │   ├── 📁 components
│   │       │   │   ├── 📄 button.tsx
│   │       │   │   ├── 📄 combobox.test.tsx
│   │       │   │   ├── 📄 combobox.tsx
│   │       │   │   ├── 📄 dialog.test.tsx
│   │       │   │   ├── 📄 dialog.tsx
│   │       │   │   ├── 📄 error-banner.tsx
│   │       │   │   ├── 📄 field.test.tsx
│   │       │   │   ├── 📄 field.tsx
│   │       │   │   ├── 📄 index.ts
│   │       │   │   ├── 📄 line-item-combobox.test.tsx
│   │       │   │   ├── 📄 line-item-combobox.tsx
│   │       │   │   ├── 📄 money-input.test.tsx
│   │       │   │   ├── 📄 money-input.tsx
│   │       │   │   ├── 📄 pill.tsx
│   │       │   │   ├── 📄 popover.test.tsx
│   │       │   │   ├── 📄 popover.tsx
│   │       │   │   ├── 📄 responsive-table.test.tsx
│   │       │   │   ├── 📄 responsive-table.tsx
│   │       │   │   ├── 📄 select.test.tsx
│   │       │   │   └── 📄 select.tsx
│   │       │   ├── 📁 dimensions
│   │       │   │   ├── 📄 axes.ts
│   │       │   │   ├── 📄 dimensions.test.tsx
│   │       │   │   ├── 📄 index.ts
│   │       │   │   └── 📄 line-dimensions.tsx
│   │       │   ├── 📁 lib
│   │       │   │   ├── 📄 cx.ts
│   │       │   │   ├── 📄 thin-client.ts
│   │       │   │   ├── 📄 use-viewport.test.ts
│   │       │   │   └── 📄 use-viewport.ts
│   │       │   ├── 📁 money
│   │       │   │   ├── 📄 format.test.ts
│   │       │   │   └── 📄 format.ts
│   │       │   ├── 📁 query
│   │       │   │   └── 📄 client.ts
│   │       │   ├── 📁 screens
│   │       │   │   ├── 📁 accounts
│   │       │   │   │   ├── 📄 account-dialogs.test.tsx
│   │       │   │   │   ├── 📄 account-dialogs.tsx
│   │       │   │   │   ├── 📄 account-table.test.tsx
│   │       │   │   │   ├── 📄 account-table.tsx
│   │       │   │   │   ├── 📄 accounts-api.ts
│   │       │   │   │   ├── 📄 apply-template-dialog.test.tsx
│   │       │   │   │   ├── 📄 apply-template-dialog.tsx
│   │       │   │   │   ├── 📄 classification-nudge.test.tsx
│   │       │   │   │   ├── 📄 classification-nudge.tsx
│   │       │   │   │   ├── 📄 fixtures.ts
│   │       │   │   │   ├── 📄 intent-key.ts
│   │       │   │   │   ├── 📄 refusal.tsx
│   │       │   │   │   ├── 📄 tree.test.tsx
│   │       │   │   │   ├── 📄 tree.ts
│   │       │   │   │   └── 📄 vocabulary.ts
│   │       │   │   ├── 📁 agent-proposals
│   │       │   │   │   ├── 📄 agent-proposals.test.tsx
│   │       │   │   │   ├── 📄 list.tsx
│   │       │   │   │   ├── 📄 queries.ts
│   │       │   │   │   ├── 📄 review-dialog.tsx
│   │       │   │   │   └── 📄 test-support.tsx
│   │       │   │   ├── 📁 api-keys
│   │       │   │   │   ├── 📄 api-keys.test.tsx
│   │       │   │   │   ├── 📄 create-dialog.tsx
│   │       │   │   │   ├── 📄 list.tsx
│   │       │   │   │   ├── 📄 queries.ts
│   │       │   │   │   └── 📄 test-support.tsx
│   │       │   │   ├── 📁 automations
│   │       │   │   │   ├── 📄 action-editor.tsx
│   │       │   │   │   ├── 📄 automation-state.ts
│   │       │   │   │   ├── 📄 automations.test.tsx
│   │       │   │   │   ├── 📄 form-dialog.tsx
│   │       │   │   │   ├── 📄 list.tsx
│   │       │   │   │   ├── 📄 queries.ts
│   │       │   │   │   └── 📄 test-support.tsx
│   │       │   │   ├── 📁 bank-accounts
│   │       │   │   │   ├── 📄 bank-accounts.test.tsx
│   │       │   │   │   ├── 📄 bank-accounts.tsx
│   │       │   │   │   ├── 📄 create-dialog.tsx
│   │       │   │   │   ├── 📄 index.ts
│   │       │   │   │   ├── 📄 queries.ts
│   │       │   │   │   └── 📄 refusal.tsx
│   │       │   │   ├── 📁 bank-feeds
│   │       │   │   │   ├── 📄 bank-feeds.test.tsx
│   │       │   │   │   ├── 📄 connect-dialog.tsx
│   │       │   │   │   ├── 📄 index.tsx
│   │       │   │   │   ├── 📄 list.tsx
│   │       │   │   │   ├── 📄 queries.ts
│   │       │   │   │   └── 📄 test-support.tsx
│   │       │   │   ├── 📁 bank-import
│   │       │   │   │   ├── 📄 bank-import.test.tsx
│   │       │   │   │   ├── 📄 bank-import.tsx
│   │       │   │   │   ├── 📄 controls.tsx
│   │       │   │   │   ├── 📄 import-progress.tsx
│   │       │   │   │   ├── 📄 index.ts
│   │       │   │   │   ├── 📄 mapping-editor.tsx
│   │       │   │   │   ├── 📄 preview.tsx
│   │       │   │   │   └── 📄 queries.ts
│   │       │   │   ├── 📁 banking
│   │       │   │   │   ├── 📄 banking.test.tsx
│   │       │   │   │   └── 📄 index.tsx
│   │       │   │   ├── 📁 banking-match
│   │       │   │   │   ├── 📄 banking-match.test.tsx
│   │       │   │   │   ├── 📄 correct-dialog.tsx
│   │       │   │   │   ├── 📄 entries.ts
│   │       │   │   │   ├── 📄 index.ts
│   │       │   │   │   ├── 📄 line-row.tsx
│   │       │   │   │   ├── 📄 matching-screen.tsx
│   │       │   │   │   ├── 📄 multi-entry-dialog.tsx
│   │       │   │   │   ├── 📄 new-transaction-dialog.tsx
│   │       │   │   │   ├── 📄 queries.ts
│   │       │   │   │   ├── 📄 reasons.tsx
│   │       │   │   │   ├── 📄 refusal.tsx
│   │       │   │   │   └── 📄 undo-dialog.tsx
│   │       │   │   ├── 📁 bill-captures
│   │       │   │   │   ├── 📄 bill-captures.test.tsx
│   │       │   │   │   ├── 📄 capture-list.tsx
│   │       │   │   │   ├── 📄 line-row.tsx
│   │       │   │   │   ├── 📄 queries.ts
│   │       │   │   │   ├── 📄 review-dialog.tsx
│   │       │   │   │   ├── 📄 review-state.ts
│   │       │   │   │   ├── 📄 test-support.tsx
│   │       │   │   │   └── 📄 upload.ts
│   │       │   │   ├── 📁 budgets
│   │       │   │   │   ├── 📄 budgets.test.tsx
│   │       │   │   │   ├── 📄 grid.tsx
│   │       │   │   │   ├── 📄 queries.ts
│   │       │   │   │   └── 📄 test-support.tsx
│   │       │   │   ├── 📁 connected-apps
│   │       │   │   │   ├── 📄 connected-apps.test.tsx
│   │       │   │   │   ├── 📄 list.tsx
│   │       │   │   │   ├── 📄 queries.ts
│   │       │   │   │   └── 📄 test-support.tsx
│   │       │   │   ├── 📁 contacts
│   │       │   │   │   ├── 📄 contact-form.test.tsx
│   │       │   │   │   ├── 📄 contact-form.tsx
│   │       │   │   │   ├── 📄 contacts.test.tsx
│   │       │   │   │   ├── 📄 delete-contact-dialog.tsx
│   │       │   │   │   └── 📄 queries.ts
│   │       │   │   ├── 📁 customer-statements
│   │       │   │   │   └── 📄 queries.ts
│   │       │   │   ├── 📁 dunning
│   │       │   │   │   ├── 📄 dunning.test.tsx
│   │       │   │   │   ├── 📄 overdue-panel.tsx
│   │       │   │   │   ├── 📄 policy-form-dialog.tsx
│   │       │   │   │   ├── 📄 policy-list.tsx
│   │       │   │   │   ├── 📄 queries.ts
│   │       │   │   │   ├── 📄 stage-editor.tsx
│   │       │   │   │   ├── 📄 stage-state.ts
│   │       │   │   │   └── 📄 test-support.tsx
│   │       │   │   ├── 📁 estimates
│   │       │   │   │   ├── 📄 approve-dialog.tsx
│   │       │   │   │   ├── 📄 convert-dialog.tsx
│   │       │   │   │   ├── 📄 detail-view.tsx
│   │       │   │   │   ├── 📄 discard-dialog.tsx
│   │       │   │   │   ├── 📄 estimate-editor.tsx
│   │       │   │   │   ├── 📄 estimate-form.tsx
│   │       │   │   │   ├── 📄 estimate-header.tsx
│   │       │   │   │   ├── 📄 estimate-presentation.ts
│   │       │   │   │   ├── 📄 estimate-state.ts
│   │       │   │   │   ├── 📄 estimates.test.tsx
│   │       │   │   │   ├── 📄 line-row.tsx
│   │       │   │   │   ├── 📄 list.tsx
│   │       │   │   │   ├── 📄 mobile-document-view.tsx
│   │       │   │   │   ├── 📄 queries.ts
│   │       │   │   │   ├── 📄 send-dialog.tsx
│   │       │   │   │   ├── 📄 summary-cards.tsx
│   │       │   │   │   ├── 📄 test-support.tsx
│   │       │   │   │   └── 📄 vocabulary.ts
│   │       │   │   ├── 📁 expenses
│   │       │   │   │   ├── 📄 expense-form.tsx
│   │       │   │   │   ├── 📄 expense-state.ts
│   │       │   │   │   ├── 📄 expenses.test.tsx
│   │       │   │   │   ├── 📄 list.tsx
│   │       │   │   │   ├── 📄 queries.ts
│   │       │   │   │   ├── 📄 test-support.tsx
│   │       │   │   │   └── 📄 vocabulary.ts
│   │       │   │   ├── 📁 fixed-assets
│   │       │   │   │   ├── 📄 asset-form.tsx
│   │       │   │   │   ├── 📄 asset-state.ts
│   │       │   │   │   ├── 📄 depreciation-accounts-panel.tsx
│   │       │   │   │   ├── 📄 dispose-dialog.tsx
│   │       │   │   │   ├── 📄 fixed-assets.test.tsx
│   │       │   │   │   ├── 📄 list.tsx
│   │       │   │   │   ├── 📄 queries.ts
│   │       │   │   │   ├── 📄 schedule-view.tsx
│   │       │   │   │   ├── 📄 test-support.tsx
│   │       │   │   │   └── 📄 vocabulary.ts
│   │       │   │   ├── 📁 inventory
│   │       │   │   │   ├── 📄 adjustment-form.tsx
│   │       │   │   │   ├── 📄 inventory.tsx
│   │       │   │   │   ├── 📄 item-detail.tsx
│   │       │   │   │   ├── 📄 item-form.tsx
│   │       │   │   │   ├── 📄 queries.ts
│   │       │   │   │   ├── 📄 reorder.tsx
│   │       │   │   │   ├── 📄 settings-panel.tsx
│   │       │   │   │   └── 📄 valuation.tsx
│   │       │   │   ├── 📁 journal-entry
│   │       │   │   │   ├── 📄 balance-indicator.tsx
│   │       │   │   │   ├── 📄 balance.test.tsx
│   │       │   │   │   ├── 📄 balance.ts
│   │       │   │   │   ├── 📄 draft-editor.tsx
│   │       │   │   │   ├── 📄 draft-state.ts
│   │       │   │   │   ├── 📄 idempotency-keys.ts
│   │       │   │   │   ├── 📄 journal-entry.test.tsx
│   │       │   │   │   ├── 📄 line-row.tsx
│   │       │   │   │   ├── 📄 posted-entry.tsx
│   │       │   │   │   └── 📄 queries.ts
│   │       │   │   ├── 📁 journals
│   │       │   │   │   ├── 📄 journals-list.test.tsx
│   │       │   │   │   ├── 📄 journals-list.tsx
│   │       │   │   │   ├── 📄 journals.test.tsx
│   │       │   │   │   └── 📄 queries.ts
│   │       │   │   ├── 📁 money-in
│   │       │   │   │   ├── 📄 aging.tsx
│   │       │   │   │   ├── 📄 allocation-editor.tsx
│   │       │   │   │   ├── 📄 amounts.tsx
│   │       │   │   │   ├── 📄 controls.tsx
│   │       │   │   │   ├── 📄 money-in.test.tsx
│   │       │   │   │   ├── 📄 payment-detail.tsx
│   │       │   │   │   ├── 📄 payments.tsx
│   │       │   │   │   ├── 📄 queries.ts
│   │       │   │   │   └── 📄 record-payment-dialog.tsx
│   │       │   │   ├── 📁 oauth-clients
│   │       │   │   │   ├── 📄 list.tsx
│   │       │   │   │   ├── 📄 oauth-clients.test.tsx
│   │       │   │   │   ├── 📄 queries.ts
│   │       │   │   │   ├── 📄 register-dialog.tsx
│   │       │   │   │   └── 📄 test-support.tsx
│   │       │   │   ├── 📁 oauth-consent
│   │       │   │   │   ├── 📄 oauth-consent.test.tsx
│   │       │   │   │   └── 📄 test-support.tsx
│   │       │   │   ├── 📁 pay-bills
│   │       │   │   │   ├── 📄 amounts.ts
│   │       │   │   │   ├── 📄 batch-issue-dialog.tsx
│   │       │   │   │   ├── 📄 cancel-dialog.tsx
│   │       │   │   │   ├── 📄 disbursement-details-dialog.tsx
│   │       │   │   │   ├── 📄 disbursements.test.tsx
│   │       │   │   │   ├── 📄 draft.ts
│   │       │   │   │   ├── 📄 issue-dialog.tsx
│   │       │   │   │   ├── 📄 pay-bills.test.tsx
│   │       │   │   │   ├── 📄 payable-bills-table.tsx
│   │       │   │   │   ├── 📄 pending-payments-table.tsx
│   │       │   │   │   ├── 📄 queries.ts
│   │       │   │   │   ├── 📄 test-support.tsx
│   │       │   │   │   └── 📄 vendor-payment-group.tsx
│   │       │   │   ├── 📁 processing
│   │       │   │   │   ├── 📄 connect-dialog.tsx
│   │       │   │   │   ├── 📄 list.tsx
│   │       │   │   │   ├── 📄 payout-sync-config.tsx
│   │       │   │   │   ├── 📄 payout-sync-queries.ts
│   │       │   │   │   ├── 📄 payout-sync.test.tsx
│   │       │   │   │   ├── 📄 payouts-review.tsx
│   │       │   │   │   ├── 📄 processing.test.tsx
│   │       │   │   │   ├── 📄 queries.ts
│   │       │   │   │   └── 📄 test-support.tsx
│   │       │   │   ├── 📁 purchase-orders
│   │       │   │   │   ├── 📄 approve-dialog.tsx
│   │       │   │   │   ├── 📄 convert-dialog.tsx
│   │       │   │   │   ├── 📄 detail-view.tsx
│   │       │   │   │   ├── 📄 discard-dialog.tsx
│   │       │   │   │   ├── 📄 line-row.tsx
│   │       │   │   │   ├── 📄 list.tsx
│   │       │   │   │   ├── 📄 mobile-document-view.tsx
│   │       │   │   │   ├── 📄 order-editor.tsx
│   │       │   │   │   ├── 📄 order-header.tsx
│   │       │   │   │   ├── 📄 order-presentation.ts
│   │       │   │   │   ├── 📄 order-state.ts
│   │       │   │   │   ├── 📄 purchase-orders.test.tsx
│   │       │   │   │   ├── 📄 queries.ts
│   │       │   │   │   ├── 📄 send-dialog.tsx
│   │       │   │   │   ├── 📄 summary-cards.tsx
│   │       │   │   │   ├── 📄 test-support.tsx
│   │       │   │   │   └── 📄 vocabulary.ts
│   │       │   │   ├── 📁 purchases
│   │       │   │   │   ├── 📄 allocate-dialog.tsx
│   │       │   │   │   ├── 📄 ap-document.test.ts
│   │       │   │   │   ├── 📄 ap-document.ts
│   │       │   │   │   ├── 📄 document-editor.tsx
│   │       │   │   │   ├── 📄 document-list.test.tsx
│   │       │   │   │   ├── 📄 document-list.tsx
│   │       │   │   │   ├── 📄 editor-state.ts
│   │       │   │   │   ├── 📄 intent-keys.ts
│   │       │   │   │   ├── 📄 line-row.tsx
│   │       │   │   │   ├── 📄 mobile-document-view.test.tsx
│   │       │   │   │   ├── 📄 mobile-document-view.tsx
│   │       │   │   │   ├── 📄 payment-history.test.tsx
│   │       │   │   │   ├── 📄 payment-history.tsx
│   │       │   │   │   ├── 📄 purchases.test.tsx
│   │       │   │   │   ├── 📄 queries.ts
│   │       │   │   │   ├── 📄 refusal.tsx
│   │       │   │   │   ├── 📄 summary-cards.test.tsx
│   │       │   │   │   └── 📄 summary-cards.tsx
│   │       │   │   ├── 📁 quickbooks-import
│   │       │   │   │   ├── 📄 index.ts
│   │       │   │   │   ├── 📄 preview.tsx
│   │       │   │   │   ├── 📄 queries.ts
│   │       │   │   │   └── 📄 quickbooks-import.tsx
│   │       │   │   ├── 📁 reconciliation
│   │       │   │   │   ├── 📄 balances.tsx
│   │       │   │   │   ├── 📄 index.ts
│   │       │   │   │   ├── 📄 open-session-dialog.tsx
│   │       │   │   │   ├── 📄 queries.ts
│   │       │   │   │   ├── 📄 reconciliation.test.tsx
│   │       │   │   │   ├── 📄 reconciliation.tsx
│   │       │   │   │   ├── 📄 refusal.tsx
│   │       │   │   │   ├── 📄 report.tsx
│   │       │   │   │   ├── 📄 session-detail.tsx
│   │       │   │   │   └── 📄 session-list.tsx
│   │       │   │   ├── 📁 recurring-invoices
│   │       │   │   │   ├── 📄 deactivate-dialog.tsx
│   │       │   │   │   ├── 📄 line-row.tsx
│   │       │   │   │   ├── 📄 list.tsx
│   │       │   │   │   ├── 📄 queries.ts
│   │       │   │   │   ├── 📄 recurring-invoices.test.tsx
│   │       │   │   │   ├── 📄 template-form.tsx
│   │       │   │   │   ├── 📄 template-state.ts
│   │       │   │   │   ├── 📄 test-support.tsx
│   │       │   │   │   └── 📄 vocabulary.ts
│   │       │   │   ├── 📁 recurring-journals
│   │       │   │   │   ├── 📄 balance-indicator.tsx
│   │       │   │   │   ├── 📄 balance.ts
│   │       │   │   │   ├── 📄 deactivate-dialog.tsx
│   │       │   │   │   ├── 📄 line-row.tsx
│   │       │   │   │   ├── 📄 list.tsx
│   │       │   │   │   ├── 📄 queries.ts
│   │       │   │   │   ├── 📄 recurring-journals.test.tsx
│   │       │   │   │   ├── 📄 template-form.tsx
│   │       │   │   │   ├── 📄 template-state.ts
│   │       │   │   │   ├── 📄 test-support.tsx
│   │       │   │   │   └── 📄 vocabulary.ts
│   │       │   │   ├── 📁 reports
│   │       │   │   │   ├── 📄 audit.test.tsx
│   │       │   │   │   ├── 📄 audit.tsx
│   │       │   │   │   ├── 📄 balance-sheet.test.tsx
│   │       │   │   │   ├── 📄 balance-sheet.tsx
│   │       │   │   │   ├── 📄 budget-vs-actual.test.tsx
│   │       │   │   │   ├── 📄 budget-vs-actual.tsx
│   │       │   │   │   ├── 📄 cash-flow-projection.test.tsx
│   │       │   │   │   ├── 📄 cash-flow-projection.tsx
│   │       │   │   │   ├── 📄 cash-flow.test.tsx
│   │       │   │   │   ├── 📄 cash-flow.tsx
│   │       │   │   │   ├── 📄 cells.tsx
│   │       │   │   │   ├── 📄 controls.tsx
│   │       │   │   │   ├── 📄 export-control.test.tsx
│   │       │   │   │   ├── 📄 export-control.tsx
│   │       │   │   │   ├── 📄 filters.test.ts
│   │       │   │   │   ├── 📄 filters.ts
│   │       │   │   │   ├── 📄 general-ledger.test.tsx
│   │       │   │   │   ├── 📄 general-ledger.tsx
│   │       │   │   │   ├── 📄 layout.tsx
│   │       │   │   │   ├── 📄 profit-and-loss.test.tsx
│   │       │   │   │   ├── 📄 profit-and-loss.tsx
│   │       │   │   │   ├── 📄 screen.test.tsx
│   │       │   │   │   ├── 📄 statement.test.tsx
│   │       │   │   │   ├── 📄 statement.tsx
│   │       │   │   │   ├── 📄 tree.ts
│   │       │   │   │   ├── 📄 trial-balance.tsx
│   │       │   │   │   └── 📄 views.ts
│   │       │   │   ├── 📁 roles
│   │       │   │   │   ├── 📄 list.tsx
│   │       │   │   │   ├── 📄 queries.ts
│   │       │   │   │   ├── 📄 role-editor.tsx
│   │       │   │   │   ├── 📄 roles.test.tsx
│   │       │   │   │   └── 📄 test-support.tsx
│   │       │   │   ├── 📁 sales
│   │       │   │   │   ├── 📄 allocate-dialog.tsx
│   │       │   │   │   ├── 📄 allocations-panel.tsx
│   │       │   │   │   ├── 📄 delivery-client.ts
│   │       │   │   │   ├── 📄 document-editor.tsx
│   │       │   │   │   ├── 📄 document-header.tsx
│   │       │   │   │   ├── 📄 document-list.test.tsx
│   │       │   │   │   ├── 📄 document-list.tsx
│   │       │   │   │   ├── 📄 document-state.ts
│   │       │   │   │   ├── 📄 document-view.tsx
│   │       │   │   │   ├── 📄 intent-keys.ts
│   │       │   │   │   ├── 📄 invoice-list.ts
│   │       │   │   │   ├── 📄 line-row.tsx
│   │       │   │   │   ├── 📄 mobile-document-view.tsx
│   │       │   │   │   ├── 📄 payment-history.tsx
│   │       │   │   │   ├── 📄 queries.ts
│   │       │   │   │   ├── 📄 refusal.tsx
│   │       │   │   │   ├── 📄 sales.test.tsx
│   │       │   │   │   ├── 📄 send-invoice.test.tsx
│   │       │   │   │   ├── 📄 summary-cards.test.tsx
│   │       │   │   │   ├── 📄 summary-cards.tsx
│   │       │   │   │   ├── 📄 totals.tsx
│   │       │   │   │   └── 📄 vocabulary.tsx
│   │       │   │   ├── 📁 settings
│   │       │   │   │   ├── 📄 branding-client.ts
│   │       │   │   │   ├── 📄 branding.test.tsx
│   │       │   │   │   ├── 📄 branding.tsx
│   │       │   │   │   ├── 📄 catalog-item-dialog.tsx
│   │       │   │   │   ├── 📄 catalog-queries.ts
│   │       │   │   │   ├── 📄 catalog.test.tsx
│   │       │   │   │   ├── 📄 catalog.tsx
│   │       │   │   │   ├── 📄 dimensions.test.tsx
│   │       │   │   │   ├── 📄 dimensions.tsx
│   │       │   │   │   ├── 📄 discount-accounts.test.tsx
│   │       │   │   │   ├── 📄 discount-accounts.tsx
│   │       │   │   │   ├── 📄 members.test.tsx
│   │       │   │   │   ├── 📄 members.tsx
│   │       │   │   │   ├── 📄 payment-terms.test.tsx
│   │       │   │   │   ├── 📄 payment-terms.tsx
│   │       │   │   │   ├── 📄 periods.test.tsx
│   │       │   │   │   ├── 📄 periods.tsx
│   │       │   │   │   ├── 📄 section.tsx
│   │       │   │   │   ├── 📄 support.ts
│   │       │   │   │   └── 📄 test-support.tsx
│   │       │   │   ├── 📁 statement-packages
│   │       │   │   │   ├── 📄 queries.ts
│   │       │   │   │   ├── 📄 statement-packages.test.tsx
│   │       │   │   │   └── 📄 test-support.tsx
│   │       │   │   ├── 📁 work-items
│   │       │   │   │   ├── 📄 list.tsx
│   │       │   │   │   ├── 📄 queries.ts
│   │       │   │   │   ├── 📄 test-support.tsx
│   │       │   │   │   └── 📄 work-items.test.tsx
│   │       │   │   ├── 📄 accounts.tsx
│   │       │   │   ├── 📄 agent-proposals.tsx
│   │       │   │   ├── 📄 api-keys.tsx
│   │       │   │   ├── 📄 auth.test.tsx
│   │       │   │   ├── 📄 auth.tsx
│   │       │   │   ├── 📄 automations.tsx
│   │       │   │   ├── 📄 bill-captures.tsx
│   │       │   │   ├── 📄 budgets.tsx
│   │       │   │   ├── 📄 connected-apps.tsx
│   │       │   │   ├── 📄 contacts.tsx
│   │       │   │   ├── 📄 customer-statements.test.tsx
│   │       │   │   ├── 📄 customer-statements.tsx
│   │       │   │   ├── 📄 disbursements.tsx
│   │       │   │   ├── 📄 dunning.tsx
│   │       │   │   ├── 📄 estimates.tsx
│   │       │   │   ├── 📄 expenses.tsx
│   │       │   │   ├── 📄 fixed-assets.tsx
│   │       │   │   ├── 📄 journal-entry.tsx
│   │       │   │   ├── 📄 journals.tsx
│   │       │   │   ├── 📄 money-in.tsx
│   │       │   │   ├── 📄 oauth-clients.tsx
│   │       │   │   ├── 📄 oauth-consent.tsx
│   │       │   │   ├── 📄 pay-bills.tsx
│   │       │   │   ├── 📄 processing.tsx
│   │       │   │   ├── 📄 public-invoice.test.tsx
│   │       │   │   ├── 📄 public-invoice.tsx
│   │       │   │   ├── 📄 purchase-orders.tsx
│   │       │   │   ├── 📄 purchases.tsx
│   │       │   │   ├── 📄 recurring-invoices.tsx
│   │       │   │   ├── 📄 recurring-journals.tsx
│   │       │   │   ├── 📄 reports.tsx
│   │       │   │   ├── 📄 roles.tsx
│   │       │   │   ├── 📄 sales.tsx
│   │       │   │   ├── 📄 settings.tsx
│   │       │   │   ├── 📄 statement-packages.tsx
│   │       │   │   └── 📄 work-items.tsx
│   │       │   ├── 📁 shell
│   │       │   │   ├── 📄 app-shell.test.tsx
│   │       │   │   ├── 📄 app-shell.tsx
│   │       │   │   ├── 📄 nav.ts
│   │       │   │   ├── 📄 org-switcher.test.tsx
│   │       │   │   ├── 📄 org-switcher.tsx
│   │       │   │   └── 📄 query-scope.tsx
│   │       │   ├── 📁 styles
│   │       │   │   ├── 🎨 index.css
│   │       │   │   └── 🎨 tokens.css
│   │       │   ├── 📁 ten99
│   │       │   │   ├── 📄 queries.ts
│   │       │   │   ├── 📄 run-detail.test.tsx
│   │       │   │   ├── 📄 run-detail.tsx
│   │       │   │   ├── 📄 runs-list.test.tsx
│   │       │   │   ├── 📄 runs-list.tsx
│   │       │   │   ├── 📄 ten99-center.test.tsx
│   │       │   │   ├── 📄 ten99-center.tsx
│   │       │   │   ├── 📄 vendor-tax-profile-dialog.test.tsx
│   │       │   │   ├── 📄 vendor-tax-profile-dialog.tsx
│   │       │   │   ├── 📄 worksheet.test.tsx
│   │       │   │   └── 📄 worksheet.tsx
│   │       │   ├── 📁 test
│   │       │   │   └── 📄 setup.ts
│   │       │   ├── 📁 theme
│   │       │   │   └── 📄 theme.tsx
│   │       │   ├── 📄 App.test.tsx
│   │       │   ├── 📄 App.tsx
│   │       │   ├── 📄 env.ts
│   │       │   ├── 📄 main.tsx
│   │       │   └── 📄 vite-env.d.ts
│   │       ├── ⚙️ .env.example
│   │       ├── 🌐 index.html
│   │       ├── ⚙️ package.json
│   │       ├── ⚙️ tsconfig.json
│   │       └── 📄 vite.config.ts
│   ├── 📁 scripts
│   │   ├── 📄 build-server.mjs
│   │   └── 📄 codegen.mjs
│   ├── ⚙️ .dependency-cruiser.cjs
│   ├── ⚙️ .dockerignore
│   ├── ⚙️ .editorconfig
│   ├── ⚙️ .env.example
│   ├── ⚙️ .gitignore
│   ├── ⚙️ .nvmrc
│   ├── ⚙️ .prettierignore
│   ├── ⚙️ .prettierrc.json
│   ├── ⚙️ .yarnrc.yml
│   ├── 📝 CLA.md
│   ├── 📝 CLAUDE.md
│   ├── 📝 CODE_OF_CONDUCT.md
│   ├── 📝 CONTRIBUTING.md
│   ├── 🐳 Dockerfile
│   ├── 📝 FUNDING.md
│   ├── 📄 LICENSE
│   ├── 📄 NOTICE
│   ├── 📝 README.md
│   ├── 📝 ROADMAP.md
│   ├── 📝 SECURITY.md
│   ├── ⚙️ docker-compose.yml
│   ├── 📄 eslint.config.js
│   ├── ⚙️ openapi.json
│   ├── ⚙️ package.json
│   ├── ⚙️ tsconfig.base.json
│   ├── 📄 vitest.config.ts
│   └── 📦 yarn.lock
├── ⚙️ .gitkeep
└── 📝 README.md
```

---