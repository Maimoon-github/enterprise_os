# File Tree: inbox

**Root Path:** `/enterprise_os/business-os/agents/inbox`

```
├── 📁 inbox-zero
│   ├── 📁 .agents
│   │   └── 📄 skills
│   ├── 📁 .claude
│   │   ├── 📁 agents
│   │   │   └── 📝 reviewer.md
│   │   └── 📁 skills
│   │       ├── 📁 agent-browser
│   │       │   ├── 📁 references
│   │       │   │   ├── 📝 authentication.md
│   │       │   │   ├── 📝 commands.md
│   │       │   │   ├── 📝 profiling.md
│   │       │   │   ├── 📝 proxy-support.md
│   │       │   │   ├── 📝 session-management.md
│   │       │   │   ├── 📝 snapshot-refs.md
│   │       │   │   └── 📝 video-recording.md
│   │       │   ├── 📁 templates
│   │       │   │   ├── 📄 authenticated-session.sh
│   │       │   │   ├── 📄 capture-workflow.sh
│   │       │   │   └── 📄 form-automation.sh
│   │       │   └── 📝 SKILL.md
│   │       ├── 📁 changelog
│   │       │   └── 📝 SKILL.md
│   │       ├── 📁 cloud-dev-environment
│   │       │   └── 📝 SKILL.md
│   │       ├── 📁 code-simplifier
│   │       │   ├── 📁 agents
│   │       │   │   └── ⚙️ openai.yaml
│   │       │   └── 📝 SKILL.md
│   │       ├── 📁 create-pr
│   │       │   └── 📝 SKILL.md
│   │       ├── 📁 e2e
│   │       │   └── 📝 SKILL.md
│   │       ├── 📁 environment-variables
│   │       │   └── 📝 SKILL.md
│   │       ├── 📁 explain-changes
│   │       │   └── 📝 SKILL.md
│   │       ├── 📁 fullstack-workflow
│   │       │   └── 📝 SKILL.md
│   │       ├── 📁 i18n
│   │       │   └── 📝 SKILL.md
│   │       ├── 📁 llm
│   │       │   └── 📝 SKILL.md
│   │       ├── 📁 llm-test
│   │       │   └── 📝 SKILL.md
│   │       ├── 📁 logging
│   │       │   └── 📝 SKILL.md
│   │       ├── 📁 pr-watch
│   │       │   ├── 📝 SKILL.md
│   │       │   ├── 📄 pr-digest
│   │       │   ├── 📄 pr-digest.test.mjs
│   │       │   ├── 📄 pr-screenshots
│   │       │   └── 📄 pr-screenshots.test.mjs
│   │       ├── 📁 prisma
│   │       │   └── 📝 SKILL.md
│   │       ├── 📁 project-structure
│   │       │   └── 📝 SKILL.md
│   │       ├── 📁 qa-label
│   │       │   └── 📝 SKILL.md
│   │       ├── 📁 review
│   │       │   └── 📝 SKILL.md
│   │       ├── 📁 review-ai-prompt-changes
│   │       │   ├── 📁 agents
│   │       │   │   └── ⚙️ openai.yaml
│   │       │   └── 📝 SKILL.md
│   │       ├── 📁 test-feature
│   │       │   └── 📝 SKILL.md
│   │       ├── 📁 testing
│   │       │   ├── 📝 SKILL.md
│   │       │   ├── 📝 e2e.md
│   │       │   ├── 📝 eval.md
│   │       │   ├── 📝 integration.md
│   │       │   ├── 📝 llm.md
│   │       │   ├── 📝 unit.md
│   │       │   └── 📝 write-tests.md
│   │       ├── 📁 ui-components
│   │       │   └── 📝 SKILL.md
│   │       ├── 📁 update-packages
│   │       │   └── 📝 SKILL.md
│   │       ├── 📁 wait
│   │       │   └── 📝 SKILL.md
│   │       └── 📁 write-tests
│   │           └── 📝 SKILL.md
│   ├── 📁 .codex
│   │   ├── 📁 agents
│   │   │   ├── ⚙️ code-simplifier.toml
│   │   │   └── ⚙️ reviewer.toml
│   │   └── ⚙️ config.toml
│   ├── 📁 .conductor
│   │   └── ⚙️ settings.toml
│   ├── 📁 .cursor-plugin
│   │   └── ⚙️ plugin.json
│   ├── 📁 .devcontainer
│   │   ├── 🐳 Dockerfile
│   │   ├── 📝 README.md
│   │   ├── ⚙️ devcontainer.json
│   │   ├── ⚙️ docker-compose.yml
│   │   └── 📄 setup.sh
│   ├── 📁 .github
│   │   ├── 📁 screenshots
│   │   │   ├── 🖼️ bulk-unsubscriber.png
│   │   │   ├── 🖼️ email-assistant.png
│   │   │   ├── 🖼️ email-client.png
│   │   │   └── 🖼️ reply-zero.png
│   │   └── 📁 workflows
│   │       ├── ⚙️ ai-evals.yml
│   │       ├── ⚙️ api-release.yml
│   │       ├── ⚙️ build-changelog.yml
│   │       ├── ⚙️ build-check.yml
│   │       ├── ⚙️ build_and_publish_docker.yml
│   │       ├── ⚙️ claude-code-review.yml
│   │       ├── ⚙️ claude.yml
│   │       ├── ⚙️ cli-release.yml
│   │       ├── ⚙️ deploy-image-proxy.yml
│   │       ├── ⚙️ desktop-release.yml
│   │       ├── ⚙️ e2e-flows.yml
│   │       ├── ⚙️ mail-packages-release.yml
│   │       ├── ⚙️ playwright.yml
│   │       ├── ⚙️ publish-playwright-report.yml
│   │       └── ⚙️ test.yml
│   ├── 📁 .husky
│   │   ├── ⚙️ .gitignore
│   │   ├── 📄 pre-commit
│   │   └── 📄 pre-push
│   ├── 📁 .superset
│   │   └── ⚙️ config.json
│   ├── 📁 Formula
│   │   └── 💎 inbox-zero.rb
│   ├── 📁 agents
│   │   └── 📝 inbox-zero-api-cli.md
│   ├── 📁 apps
│   │   ├── 📁 desktop
│   │   │   ├── 📁 __tests__
│   │   │   │   └── 📁 mail-engine
│   │   │   │       ├── 📄 electron-binary.ts
│   │   │   │       ├── 📄 electron-hosted-renderer-entry.ts
│   │   │   │       ├── 📄 electron-local-renderer-entry.ts
│   │   │   │       ├── 📄 electron-local-renderer.test.ts
│   │   │   │       ├── 📄 electron-packaged-renderer.test.ts
│   │   │   │       ├── 📄 electron-session-entry.ts
│   │   │   │       ├── 📄 electron-session.test.ts
│   │   │   │       ├── 📄 owner.test.ts
│   │   │   │       ├── 📄 recovery.test.ts
│   │   │   │       ├── 📄 run-hosted-electron-mail.mjs
│   │   │   │       ├── 📄 utility-child.test.ts
│   │   │   │       └── 📄 utility-host.test.ts
│   │   │   ├── 📁 scripts
│   │   │   │   └── 📄 mail-ui-css.mjs
│   │   │   ├── 📁 src
│   │   │   │   ├── 📁 mail-engine
│   │   │   │   │   ├── 📄 attachment.test.ts
│   │   │   │   │   ├── 📄 attachment.ts
│   │   │   │   │   ├── 📄 backend.ts
│   │   │   │   │   ├── 📄 host.ts
│   │   │   │   │   ├── 📄 ipc.test.ts
│   │   │   │   │   ├── 📄 ipc.ts
│   │   │   │   │   ├── 📄 mailbox-signals.test.ts
│   │   │   │   │   ├── 📄 mailbox-signals.ts
│   │   │   │   │   ├── 📄 owner.ts
│   │   │   │   │   ├── 📄 push-ipc.ts
│   │   │   │   │   ├── 📄 request.test.ts
│   │   │   │   │   ├── 📄 request.ts
│   │   │   │   │   ├── 📄 sqlite.ts
│   │   │   │   │   ├── 📄 storage-pressure.test.ts
│   │   │   │   │   ├── 📄 storage-pressure.ts
│   │   │   │   │   ├── 📄 utility-child-entry.ts
│   │   │   │   │   ├── 📄 utility-child.ts
│   │   │   │   │   ├── 📄 utility-host.test.ts
│   │   │   │   │   ├── 📄 utility-host.ts
│   │   │   │   │   ├── 📄 wipe.test.ts
│   │   │   │   │   └── 📄 wipe.ts
│   │   │   │   ├── 📁 renderer
│   │   │   │   │   ├── 📄 desktop-api.ts
│   │   │   │   │   ├── 🌐 index.html
│   │   │   │   │   └── 📄 main.tsx
│   │   │   │   ├── 📄 application-menu.test.ts
│   │   │   │   ├── 📄 application-menu.ts
│   │   │   │   ├── 📄 auto-update.test.ts
│   │   │   │   ├── 📄 auto-update.ts
│   │   │   │   ├── 📄 context-menu.test.ts
│   │   │   │   ├── 📄 context-menu.ts
│   │   │   │   ├── 📄 desktop.test.ts
│   │   │   │   ├── 📄 desktop.ts
│   │   │   │   ├── 📄 diagnostics.test.ts
│   │   │   │   ├── 📄 diagnostics.ts
│   │   │   │   ├── 📄 esm-bundle-require.test.ts
│   │   │   │   ├── 📄 health.ts
│   │   │   │   ├── 📄 load-recovery.test.ts
│   │   │   │   ├── 📄 load-recovery.ts
│   │   │   │   ├── 📄 mail-notifications.test.ts
│   │   │   │   ├── 📄 mail-notifications.ts
│   │   │   │   ├── 📄 main.ts
│   │   │   │   ├── 📄 network-errors.test.ts
│   │   │   │   ├── 📄 network-errors.ts
│   │   │   │   ├── 📄 preload.ts
│   │   │   │   ├── 📄 sentry.test.ts
│   │   │   │   ├── 📄 sentry.ts
│   │   │   │   ├── 📄 update-feed-cli.ts
│   │   │   │   ├── 📄 update-feed.test.ts
│   │   │   │   ├── 📄 update-feed.ts
│   │   │   │   ├── 📄 windows.test.ts
│   │   │   │   └── 📄 windows.ts
│   │   │   ├── 📝 README.md
│   │   │   ├── ⚙️ electron-builder.yml
│   │   │   ├── 📄 esbuild.config.mjs
│   │   │   ├── 📄 esm-main-banner.mjs
│   │   │   ├── ⚙️ package.json
│   │   │   ├── ⚙️ tsconfig.json
│   │   │   └── 📄 vitest.config.ts
│   │   ├── 📁 image-proxy
│   │   │   ├── 📁 src
│   │   │   │   └── 📄 index.ts
│   │   │   ├── ⚙️ package.json
│   │   │   ├── ⚙️ tsconfig.json
│   │   │   └── 📄 wrangler.jsonc
│   │   ├── 📁 image-proxy-aws
│   │   │   ├── 📁 src
│   │   │   │   ├── 📄 handler.test.ts
│   │   │   │   └── 📄 handler.ts
│   │   │   ├── 📝 README.md
│   │   │   ├── ⚙️ package.json
│   │   │   └── ⚙️ tsconfig.json
│   │   ├── 📁 unsubscribe-worker
│   │   │   ├── 📁 src
│   │   │   │   ├── 📁 adapters
│   │   │   │   │   ├── 📄 docker.test.ts
│   │   │   │   │   └── 📄 docker.ts
│   │   │   │   ├── 📁 eval
│   │   │   │   │   └── 📄 unsubscribe.eval.test.ts
│   │   │   │   ├── 📄 browser.test.ts
│   │   │   │   ├── 📄 browser.ts
│   │   │   │   ├── 📄 contracts.ts
│   │   │   │   ├── 📄 index.ts
│   │   │   │   ├── 📄 model.ts
│   │   │   │   ├── 📄 network.test.ts
│   │   │   │   ├── 📄 network.ts
│   │   │   │   ├── 📄 read-response.test.ts
│   │   │   │   ├── 📄 read-response.ts
│   │   │   │   ├── 📄 runner.ts
│   │   │   │   ├── 📄 server.test.ts
│   │   │   │   ├── 📄 server.ts
│   │   │   │   ├── 📄 service.test.ts
│   │   │   │   ├── 📄 service.ts
│   │   │   │   └── 📄 verify-egress.ts
│   │   │   ├── ⚙️ .env.example
│   │   │   ├── 🐳 Dockerfile
│   │   │   ├── 📄 Dockerfile.router
│   │   │   ├── 📝 README.md
│   │   │   ├── ⚙️ package.json
│   │   │   ├── 📄 router.sh
│   │   │   └── ⚙️ tsconfig.json
│   │   ├── 📁 web
│   │   │   ├── 📁 __tests__
│   │   │   │   ├── 📁 ai-regression
│   │   │   │   │   ├── 📁 reply
│   │   │   │   │   │   ├── 📄 draft-follow-up.test.ts
│   │   │   │   │   │   ├── 📄 draft-reply.test.ts
│   │   │   │   │   │   └── 📄 reply-context-collector.test.ts
│   │   │   │   │   ├── 📄 ai-assistant-chat-send-disabled-regression.test.ts
│   │   │   │   │   ├── 📄 ai-calendar-availability.test.ts
│   │   │   │   │   ├── 📄 ai-categorize-senders.test.ts
│   │   │   │   │   ├── 📄 ai-choose-args.test.ts
│   │   │   │   │   ├── 📄 ai-choose-rule.test.ts
│   │   │   │   │   ├── 📄 ai-detect-recurring-pattern.test.ts
│   │   │   │   │   ├── 📄 ai-extract-from-email-history.test.ts
│   │   │   │   │   ├── 📄 ai-extract-knowledge.test.ts
│   │   │   │   │   ├── 📄 ai-mcp-agent.test.ts
│   │   │   │   │   ├── 📄 ai-meeting-briefing.test.ts
│   │   │   │   │   ├── 📄 ai-persona.test.ts
│   │   │   │   │   ├── 📄 ai-prompt-to-rules.test.ts
│   │   │   │   │   ├── 📄 ai-prompt-to-split.test.ts
│   │   │   │   │   ├── 📄 ai-summarize-email-for-digest.test.ts
│   │   │   │   │   ├── 📄 ai-writing-style.test.ts
│   │   │   │   │   └── 📄 determine-thread-status.test.ts
│   │   │   │   ├── 📁 db
│   │   │   │   │   ├── 📝 README.md
│   │   │   │   │   ├── 📄 chat-action-totals.test.ts
│   │   │   │   │   ├── 📄 cold-email-exclude-replied-sender.test.ts
│   │   │   │   │   ├── 📄 cold-email-misfiled-patterns.test.ts
│   │   │   │   │   ├── 📄 custom-rule-label-removal.test.ts
│   │   │   │   │   ├── 📄 default-mail-splits.test.ts
│   │   │   │   │   ├── 📄 digest-claim.test.ts
│   │   │   │   │   ├── 📄 email-account-order.test.ts
│   │   │   │   │   ├── 📄 email-rename.test.ts
│   │   │   │   │   ├── 📄 fake-bot-provider.ts
│   │   │   │   │   ├── 📄 group-item-reconciliation.test.ts
│   │   │   │   │   ├── 📄 held-email-undo.test.ts
│   │   │   │   │   ├── 📄 mail-split-migration.test.ts
│   │   │   │   │   ├── 📄 mailbox-merge.test.ts
│   │   │   │   │   ├── 📄 meeting-recorder-reconcile.test.ts
│   │   │   │   │   ├── 📄 normalize-group-item-values-migration.test.ts
│   │   │   │   │   ├── 📄 pending-digest-migration.test.ts
│   │   │   │   │   ├── 📄 pending-digest.test.ts
│   │   │   │   │   ├── 📄 rule-name-unique-error.test.ts
│   │   │   │   │   ├── 📄 sender-category-overview.test.ts
│   │   │   │   │   ├── 📄 shared-conversations.test.ts
│   │   │   │   │   ├── 📄 snoozed-thread-scheduler.test.ts
│   │   │   │   │   ├── 📄 split-filter-migration.test.ts
│   │   │   │   │   └── 📄 stripe-trial-conversion.test.ts
│   │   │   │   ├── 📁 e2e
│   │   │   │   │   ├── 📁 calendar
│   │   │   │   │   │   ├── 📄 google-calendar.test.ts
│   │   │   │   │   │   └── 📄 microsoft-calendar.test.ts
│   │   │   │   │   ├── 📁 cold-email
│   │   │   │   │   │   ├── 📄 google-cold-email.test.ts
│   │   │   │   │   │   └── 📄 microsoft-cold-email.test.ts
│   │   │   │   │   ├── 📁 drafting
│   │   │   │   │   │   └── 📄 microsoft-drafting.test.ts
│   │   │   │   │   ├── 📁 flows
│   │   │   │   │   │   ├── 📁 helpers
│   │   │   │   │   │   │   ├── 📄 accounts.ts
│   │   │   │   │   │   │   ├── 📄 email.ts
│   │   │   │   │   │   │   ├── 📄 logging.ts
│   │   │   │   │   │   │   ├── 📄 polling.ts
│   │   │   │   │   │   │   └── 📄 webhook.ts
│   │   │   │   │   │   ├── 📝 README.md
│   │   │   │   │   │   ├── 📄 auto-labeling.test.ts
│   │   │   │   │   │   ├── 📄 config.ts
│   │   │   │   │   │   ├── 📄 draft-cleanup.test.ts
│   │   │   │   │   │   ├── 📄 follow-up-reminders.test.ts
│   │   │   │   │   │   ├── 📄 full-reply-cycle.test.ts
│   │   │   │   │   │   ├── 📄 message-preservation.test.ts
│   │   │   │   │   │   ├── 📄 outbound-tracking.test.ts
│   │   │   │   │   │   ├── 📄 sent-reply-preservation.test.ts
│   │   │   │   │   │   ├── 📄 setup.ts
│   │   │   │   │   │   └── 📄 teardown.ts
│   │   │   │   │   ├── 📁 labeling
│   │   │   │   │   │   ├── 📄 gmail-thread-label-removal.test.ts
│   │   │   │   │   │   ├── 📄 google-labeling.test.ts
│   │   │   │   │   │   ├── 📄 helpers.ts
│   │   │   │   │   │   ├── 📄 microsoft-labeling.test.ts
│   │   │   │   │   │   └── 📄 microsoft-thread-category-removal.test.ts
│   │   │   │   │   ├── 📝 README.md
│   │   │   │   │   ├── 📄 gmail-operations.test.ts
│   │   │   │   │   ├── 📄 helpers.ts
│   │   │   │   │   ├── 📄 outlook-draft-read-status.test.ts
│   │   │   │   │   ├── 📄 outlook-operations.test.ts
│   │   │   │   │   ├── 📄 outlook-query-parsing.test.ts
│   │   │   │   │   └── 📄 outlook-search.test.ts
│   │   │   │   ├── 📁 emulator
│   │   │   │   │   ├── 📄 google-mail-query.test.ts
│   │   │   │   │   └── 📄 microsoft-mail-query.test.ts
│   │   │   │   ├── 📁 emulators
│   │   │   │   │   ├── 📄 knowledge-base-mcp.ts
│   │   │   │   │   ├── 📄 llm.test.ts
│   │   │   │   │   ├── 📄 llm.ts
│   │   │   │   │   ├── 📄 recall.ts
│   │   │   │   │   ├── 📄 stripe.ts
│   │   │   │   │   └── 📄 todoist-mcp.ts
│   │   │   │   ├── 📁 eval
│   │   │   │   │   ├── 📁 decision-model
│   │   │   │   │   │   ├── 📄 categorize-sender.test.ts
│   │   │   │   │   │   ├── 📄 choose-rule.test.ts
│   │   │   │   │   │   ├── 📄 cold-email.test.ts
│   │   │   │   │   │   ├── 📄 helpers.ts
│   │   │   │   │   │   ├── 📄 recurring-pattern.test.ts
│   │   │   │   │   │   ├── 📄 reply-memory-selection.test.ts
│   │   │   │   │   │   ├── 📄 thread-status.test.ts
│   │   │   │   │   │   └── 📄 unsubscribe-page.test.ts
│   │   │   │   │   ├── 📁 harness
│   │   │   │   │   │   ├── 📄 assertions.test.ts
│   │   │   │   │   │   ├── 📄 assertions.ts
│   │   │   │   │   │   ├── 📄 case-schema.ts
│   │   │   │   │   │   ├── 📄 criteria-judge.ts
│   │   │   │   │   │   ├── 📄 draft-reply-adapter.test.ts
│   │   │   │   │   │   ├── 📄 draft-reply-adapter.ts
│   │   │   │   │   │   ├── 📄 draft-reply-run.ts
│   │   │   │   │   │   ├── 📄 draft-reply-schema.ts
│   │   │   │   │   │   ├── 📄 eval-run-compatibility.test.ts
│   │   │   │   │   │   ├── 📄 eval-run-compatibility.ts
│   │   │   │   │   │   ├── 📄 judge-model.ts
│   │   │   │   │   │   ├── 📄 load-cases.ts
│   │   │   │   │   │   ├── 📄 report.test.ts
│   │   │   │   │   │   ├── 📄 report.ts
│   │   │   │   │   │   ├── 📄 result-cache.test.ts
│   │   │   │   │   │   ├── 📄 result-cache.ts
│   │   │   │   │   │   ├── 📄 run-suite.test.ts
│   │   │   │   │   │   ├── 📄 run-suite.ts
│   │   │   │   │   │   ├── 📄 send-ready-judge-contract.ts
│   │   │   │   │   │   ├── 📄 send-ready-judge.test.ts
│   │   │   │   │   │   ├── 📄 send-ready-judge.ts
│   │   │   │   │   │   ├── 📄 split-lock.ts
│   │   │   │   │   │   ├── 📄 stats.test.ts
│   │   │   │   │   │   ├── 📄 stats.ts
│   │   │   │   │   │   └── 📄 taxonomy.ts
│   │   │   │   │   ├── 📁 suites
│   │   │   │   │   │   └── 📄 draft-reply-data.test.ts
│   │   │   │   │   ├── 📄 analyze-document.test.ts
│   │   │   │   │   ├── 📄 assistant-chat-action-totals.test.ts
│   │   │   │   │   ├── 📄 assistant-chat-attachments.test.ts
│   │   │   │   │   ├── 📄 assistant-chat-bulk-inbox-action.test.ts
│   │   │   │   │   ├── 📄 assistant-chat-calendar.test.ts
│   │   │   │   │   ├── 📄 assistant-chat-core-tools.test.ts
│   │   │   │   │   ├── 📄 assistant-chat-email-actions.test.ts
│   │   │   │   │   ├── 📄 assistant-chat-email-card-capability.test.ts
│   │   │   │   │   ├── 📄 assistant-chat-episode-utils.ts
│   │   │   │   │   ├── 📄 assistant-chat-eval-env.ts
│   │   │   │   │   ├── 📄 assistant-chat-eval-utils.ts
│   │   │   │   │   ├── 📄 assistant-chat-final-reply-step.test.ts
│   │   │   │   │   ├── 📄 assistant-chat-fix-rule-intent.scenarios.ts
│   │   │   │   │   ├── 📄 assistant-chat-fix-rule-intent.test.ts
│   │   │   │   │   ├── 📄 assistant-chat-fix-verification.test.ts
│   │   │   │   │   ├── 📄 assistant-chat-inbox-workflows-actions.test.ts
│   │   │   │   │   ├── 📄 assistant-chat-inbox-workflows-search.test.ts
│   │   │   │   │   ├── 📄 assistant-chat-inbox-workflows-test-utils.ts
│   │   │   │   │   ├── 📄 assistant-chat-inbox-workflows-triage.test.ts
│   │   │   │   │   ├── 📄 assistant-chat-label-management.test.ts
│   │   │   │   │   ├── 📄 assistant-chat-long-context-trimming.test.ts
│   │   │   │   │   ├── 📄 assistant-chat-memory-safety.scenarios.ts
│   │   │   │   │   ├── 📄 assistant-chat-memory-safety.test.ts
│   │   │   │   │   ├── 📄 assistant-chat-microsoft-search-feedback.test.ts
│   │   │   │   │   ├── 📄 assistant-chat-outlook-folders.test.ts
│   │   │   │   │   ├── 📄 assistant-chat-partial-action-failures.test.ts
│   │   │   │   │   ├── 📄 assistant-chat-phishing-hardening.test.ts
│   │   │   │   │   ├── 📄 assistant-chat-progressive-disclosure.test.ts
│   │   │   │   │   ├── 📄 assistant-chat-reply-language.test.ts
│   │   │   │   │   ├── 📄 assistant-chat-rule-diagnosis.test.ts
│   │   │   │   │   ├── 📄 assistant-chat-rule-editing-action-preservation.test.ts
│   │   │   │   │   ├── 📄 assistant-chat-rule-editing-action-updates.test.ts
│   │   │   │   │   ├── 📄 assistant-chat-rule-editing-condition-updates.test.ts
│   │   │   │   │   ├── 📄 assistant-chat-rule-editing-create-rule.test.ts
│   │   │   │   │   ├── 📄 assistant-chat-rule-editing-learned-patterns.test.ts
│   │   │   │   │   ├── 📄 assistant-chat-rule-editing-overlap-exceptions.test.ts
│   │   │   │   │   ├── 📄 assistant-chat-rule-editing-patch-semantics.test.ts
│   │   │   │   │   ├── 📄 assistant-chat-rule-eval-test-utils.ts
│   │   │   │   │   ├── 📄 assistant-chat-rule-suggestions.test.ts
│   │   │   │   │   ├── 📄 assistant-chat-sender-category-cleanup.test.ts
│   │   │   │   │   ├── 📄 assistant-chat-settings-memory.scenarios.ts
│   │   │   │   │   ├── 📄 assistant-chat-settings-memory.test.ts
│   │   │   │   │   ├── 📄 assistant-chat-static-sender-rules-learned-patterns.test.ts
│   │   │   │   │   ├── 📄 assistant-chat-static-sender-rules-semantic.test.ts
│   │   │   │   │   ├── 📄 assistant-chat-static-sender-rules-static-from.test.ts
│   │   │   │   │   ├── 📄 assistant-chat-teams-content-policy.test.ts
│   │   │   │   │   ├── 📄 assistant-chat-trash-delete.test.ts
│   │   │   │   │   ├── 📄 assistant-rule-suggestion-fixtures.ts
│   │   │   │   │   ├── 📄 assistant-rule-suggestion-state.ts
│   │   │   │   │   ├── 📄 bulk-inbox-action-filter.test.ts
│   │   │   │   │   ├── 📄 categorize-senders.test.ts
│   │   │   │   │   ├── 📄 choose-rule.test.ts
│   │   │   │   │   ├── 📄 classification-feedback-hint.test.ts
│   │   │   │   │   ├── 📄 cold-email-cases.ts
│   │   │   │   │   ├── 📄 cold-email-previous-prompt.ts
│   │   │   │   │   ├── 📄 cold-email.test.ts
│   │   │   │   │   ├── 📄 debug-artifacts.ts
│   │   │   │   │   ├── 📄 determine-thread-status.test.ts
│   │   │   │   │   ├── 📄 draft-attachments.test.ts
│   │   │   │   │   ├── 📄 draft-reply-voice.test.ts
│   │   │   │   │   ├── 📄 draft-reply.test.ts
│   │   │   │   │   ├── 📄 draft-sender-history.test.ts
│   │   │   │   │   ├── 📄 filing-reply.test.ts
│   │   │   │   │   ├── 📄 judge-provider.test.ts
│   │   │   │   │   ├── 📄 judge-provider.ts
│   │   │   │   │   ├── 📄 judge.ts
│   │   │   │   │   ├── 📄 llm-unavailable-model-fallback.test.ts
│   │   │   │   │   ├── 📄 meeting-briefing.test.ts
│   │   │   │   │   ├── 📄 meeting-follow-up-draft.test.ts
│   │   │   │   │   ├── 📄 meeting-summary.test.ts
│   │   │   │   │   ├── 📄 meeting-transcript-fixtures.ts
│   │   │   │   │   ├── 📄 message-cache-key.ts
│   │   │   │   │   ├── 📄 model-catalog.ts
│   │   │   │   │   ├── 📄 models.test.ts
│   │   │   │   │   ├── 📄 models.ts
│   │   │   │   │   ├── 📄 prompt-security-core-paths.test.ts
│   │   │   │   │   ├── 📄 reply-guidance-grounding.test.ts
│   │   │   │   │   ├── 📄 reply-memory.test.ts
│   │   │   │   │   ├── 📄 reporter.test.ts
│   │   │   │   │   ├── 📄 reporter.ts
│   │   │   │   │   ├── 📄 select-reply-memories.test.ts
│   │   │   │   │   ├── 📄 semantic-judge.ts
│   │   │   │   │   ├── 📄 translate-email.test.ts
│   │   │   │   │   └── 📄 unsubscribe-page-state.test.ts
│   │   │   │   ├── 📁 fixtures
│   │   │   │   │   └── 📁 inboxes
│   │   │   │   │       ├── 📄 adapters.test.ts
│   │   │   │   │       ├── 📄 adapters.ts
│   │   │   │   │       ├── 📄 demo-inboxes.ts
│   │   │   │   │       └── 📄 types.ts
│   │   │   │   ├── 📁 integration
│   │   │   │   │   ├── 📁 mail-engine
│   │   │   │   │   │   ├── 📄 archive-reconciliation.test.ts
│   │   │   │   │   │   ├── 📄 catch-up.test.ts
│   │   │   │   │   │   ├── 📄 http-archive.test.ts
│   │   │   │   │   │   └── 📄 search-body.test.ts
│   │   │   │   │   ├── 📄 custom-mcp-server.test.ts
│   │   │   │   │   ├── 📄 demo-inbox-fixture.test.ts
│   │   │   │   │   ├── 📄 draft-attachments.test.ts
│   │   │   │   │   ├── 📄 draft-creation.test.ts
│   │   │   │   │   ├── 📄 gmail-mailbox-history.test.ts
│   │   │   │   │   ├── 📄 google-calendar-events.test.ts
│   │   │   │   │   ├── 📄 google-emulator-oauth.test.ts
│   │   │   │   │   ├── 📄 helpers.ts
│   │   │   │   │   ├── 📄 labeling-archiving.test.ts
│   │   │   │   │   ├── 📄 mailbox-change-push.test.ts
│   │   │   │   │   ├── 📄 message-source.test.ts
│   │   │   │   │   ├── 📄 outlook-assistant-search-paging.test.ts
│   │   │   │   │   ├── 📄 outlook-attachment-stream.test.ts
│   │   │   │   │   ├── 📄 outlook-category-update.test.ts
│   │   │   │   │   ├── 📄 outlook-folders.test.ts
│   │   │   │   │   ├── 📄 outlook-inbox-classification.test.ts
│   │   │   │   │   ├── 📄 outlook-mail-view-parity.test.ts
│   │   │   │   │   ├── 📄 outlook-mailbox-delta.test.ts
│   │   │   │   │   ├── 📄 outlook-mailbox-flag.test.ts
│   │   │   │   │   ├── 📄 provider-operations.test.ts
│   │   │   │   │   ├── 📄 public-booking-google.test.ts
│   │   │   │   │   ├── 📄 recall-bot-provider.test.ts
│   │   │   │   │   ├── 📄 recall-meeting-lifecycle.test.ts
│   │   │   │   │   ├── 📄 reply-context-search-thread-precedent.test.ts
│   │   │   │   │   ├── 📄 rule-action-retry.test.ts
│   │   │   │   │   ├── 📄 rule-execution.test.ts
│   │   │   │   │   ├── 📄 run-rules-learned-exclusions.test.ts
│   │   │   │   │   ├── 📄 scim-better-auth.test.ts
│   │   │   │   │   ├── 📄 security-pipeline.test.ts
│   │   │   │   │   ├── 📄 shared-conversations.test.ts
│   │   │   │   │   ├── 📄 slack-chat.test.ts
│   │   │   │   │   ├── 📄 slack-notifications.test.ts
│   │   │   │   │   ├── 📄 sso-login.test.ts
│   │   │   │   │   ├── 📄 sso-okta.test.ts
│   │   │   │   │   ├── 📄 stats-reuse-messages.test.ts
│   │   │   │   │   ├── 📄 thread-fetching.test.ts
│   │   │   │   │   ├── 📄 todoist-integration-action.test.ts
│   │   │   │   │   ├── 📄 webhook-action.test.ts
│   │   │   │   │   ├── 📄 webhook-flow.test.ts
│   │   │   │   │   └── 📄 worker-queue.test.ts
│   │   │   │   ├── 📁 mocks
│   │   │   │   │   ├── 📄 email-provider.mock.ts
│   │   │   │   │   └── 📄 sentry-nextjs.mock.ts
│   │   │   │   ├── 📁 playwright
│   │   │   │   │   ├── 📁 emulated
│   │   │   │   │   │   ├── 📁 attachments
│   │   │   │   │   │   │   ├── 📄 attachment-onboarding.spec.ts
│   │   │   │   │   │   │   └── 📄 attachment-test-helpers.ts
│   │   │   │   │   │   ├── 📁 automation
│   │   │   │   │   │   │   ├── 📄 automation-tabs-test-helpers.ts
│   │   │   │   │   │   │   ├── 📄 automation-test-helpers.ts
│   │   │   │   │   │   │   ├── 📄 bulk-processing.spec.ts
│   │   │   │   │   │   │   ├── 📄 history-tab.spec.ts
│   │   │   │   │   │   │   ├── 📄 integration-action.spec.ts
│   │   │   │   │   │   │   ├── 📄 learned-exclusions.spec.ts
│   │   │   │   │   │   │   ├── 📄 manual-rule-management.spec.ts
│   │   │   │   │   │   │   ├── 📄 mobile-layout.spec.ts
│   │   │   │   │   │   │   ├── 📄 rule-label-change.spec.ts
│   │   │   │   │   │   │   ├── 📄 settings-controls.spec.ts
│   │   │   │   │   │   │   ├── 📄 settings-drafting-knowledge.spec.ts
│   │   │   │   │   │   │   └── 📄 test-tab.spec.ts
│   │   │   │   │   │   ├── 📁 billing
│   │   │   │   │   │   │   ├── 📄 billing-test-helpers.ts
│   │   │   │   │   │   │   └── 📄 upgrade-to-paid.spec.ts
│   │   │   │   │   │   ├── 📁 calendars
│   │   │   │   │   │   │   ├── 📄 calendar-core-flows.spec.ts
│   │   │   │   │   │   │   └── 📄 calendar-test-helpers.ts
│   │   │   │   │   │   ├── 📁 channels
│   │   │   │   │   │   │   ├── 📄 channel-routing.spec.ts
│   │   │   │   │   │   │   └── 📄 channels-test-helpers.ts
│   │   │   │   │   │   ├── 📁 chat
│   │   │   │   │   │   │   ├── 📄 bulk-inbox-action.spec.ts
│   │   │   │   │   │   │   ├── 📄 chat-test-helpers.ts
│   │   │   │   │   │   │   ├── 📄 email-context.spec.ts
│   │   │   │   │   │   │   ├── 📄 first-visit.spec.ts
│   │   │   │   │   │   │   ├── 📄 history-management.spec.ts
│   │   │   │   │   │   │   ├── 📄 inline-email-cards.spec.ts
│   │   │   │   │   │   │   └── 📄 mail-screen.spec.ts
│   │   │   │   │   │   ├── 📁 cleanup
│   │   │   │   │   │   │   ├── 📄 analytics.spec.ts
│   │   │   │   │   │   │   ├── 📄 bulk-archive.spec.ts
│   │   │   │   │   │   │   ├── 📄 bulk-unsubscribe.spec.ts
│   │   │   │   │   │   │   ├── 📄 clean-onboarding.spec.ts
│   │   │   │   │   │   │   └── 📄 cleanup-test-helpers.ts
│   │   │   │   │   │   ├── 📁 integrations
│   │   │   │   │   │   │   ├── 📄 custom-mcp-server.spec.ts
│   │   │   │   │   │   │   ├── 📄 integration-configuration.spec.ts
│   │   │   │   │   │   │   └── 📄 integration-test-helpers.ts
│   │   │   │   │   │   ├── 📁 mail
│   │   │   │   │   │   │   ├── 📄 account-selection.spec.ts
│   │   │   │   │   │   │   ├── 📄 account-test-helpers.ts
│   │   │   │   │   │   │   ├── 📄 archive-feedback.spec.ts
│   │   │   │   │   │   │   ├── 📄 archive-reconciliation.spec.ts
│   │   │   │   │   │   │   ├── 📄 assistant-catch-up.spec.ts
│   │   │   │   │   │   │   ├── 📄 attachment-previews.spec.ts
│   │   │   │   │   │   │   ├── 📄 cached-settings.spec.ts
│   │   │   │   │   │   │   ├── 📄 calendar-invitation.spec.ts
│   │   │   │   │   │   │   ├── 📄 command-palette.spec.ts
│   │   │   │   │   │   │   ├── 📄 compose-and-reply.spec.ts
│   │   │   │   │   │   │   ├── 📄 compose-attachment-send.spec.ts
│   │   │   │   │   │   │   ├── 📄 compose-drafts.spec.ts
│   │   │   │   │   │   │   ├── 📄 compose-send-warnings.spec.ts
│   │   │   │   │   │   │   ├── 📄 composer-editing.spec.ts
│   │   │   │   │   │   │   ├── 📄 contact-autocomplete.spec.ts
│   │   │   │   │   │   │   ├── ⚙️ coverage.json
│   │   │   │   │   │   │   ├── 📄 desktop-update-toast.spec.ts
│   │   │   │   │   │   │   ├── 📄 draft-deletion.spec.ts
│   │   │   │   │   │   │   ├── 📄 draft-send-recovery.spec.ts
│   │   │   │   │   │   │   ├── 📄 hosted-electron-archive.spec.ts
│   │   │   │   │   │   │   ├── 📄 hosted-electron-send.spec.ts
│   │   │   │   │   │   │   ├── 📄 hosted-electron-test-helpers.ts
│   │   │   │   │   │   │   ├── 📄 inline-image-send.spec.ts
│   │   │   │   │   │   │   ├── 📄 interaction-latency.spec.ts
│   │   │   │   │   │   │   ├── 📄 latency-compose.spec.ts
│   │   │   │   │   │   │   ├── 📄 latency-reading.spec.ts
│   │   │   │   │   │   │   ├── 📄 latency-test-helpers.ts
│   │   │   │   │   │   │   ├── 📄 latency-triage.spec.ts
│   │   │   │   │   │   │   ├── 📄 layout.spec.ts
│   │   │   │   │   │   │   ├── 📄 local-draft-badge.spec.ts
│   │   │   │   │   │   │   ├── 📄 mail-engine-inspect.spec.ts
│   │   │   │   │   │   │   ├── 📄 mail-engine-startup.spec.ts
│   │   │   │   │   │   │   ├── 📄 mail-queue.spec.ts
│   │   │   │   │   │   │   ├── 📄 mail-setup.spec.ts
│   │   │   │   │   │   │   ├── 📄 mail-test-helpers.ts
│   │   │   │   │   │   │   ├── 📄 manual-label.spec.ts
│   │   │   │   │   │   │   ├── 📄 message-actions.spec.ts
│   │   │   │   │   │   │   ├── 📄 message-overflow.spec.ts
│   │   │   │   │   │   │   ├── 📄 message-tools.spec.ts
│   │   │   │   │   │   │   ├── 📄 navigation-and-views.spec.ts
│   │   │   │   │   │   │   ├── 📄 offline-loading.spec.ts
│   │   │   │   │   │   │   ├── 📄 plain-text-links.spec.ts
│   │   │   │   │   │   │   ├── 📄 reader-transition.spec.ts
│   │   │   │   │   │   │   ├── 📄 reader-unsubscribe.spec.ts
│   │   │   │   │   │   │   ├── 📄 reader-visuals.spec.ts
│   │   │   │   │   │   │   ├── 📄 reply-typing-stability.spec.ts
│   │   │   │   │   │   │   ├── 📄 scheduled-replies.spec.ts
│   │   │   │   │   │   │   ├── 📄 search.spec.ts
│   │   │   │   │   │   │   ├── 📄 send-as.spec.ts
│   │   │   │   │   │   │   ├── 📄 server-drafts.spec.ts
│   │   │   │   │   │   │   ├── 📄 split-tabs.spec.ts
│   │   │   │   │   │   │   ├── 📄 starring.spec.ts
│   │   │   │   │   │   │   ├── 📄 team-comments-access.spec.ts
│   │   │   │   │   │   │   ├── 📄 team-comments-test-helpers.ts
│   │   │   │   │   │   │   ├── 📄 team-comments.spec.ts
│   │   │   │   │   │   │   ├── 📄 theme.spec.ts
│   │   │   │   │   │   │   ├── 📄 thread-navigation.spec.ts
│   │   │   │   │   │   │   ├── 📄 thread-select-all.spec.ts
│   │   │   │   │   │   │   ├── 📄 thread-states.spec.ts
│   │   │   │   │   │   │   └── 📄 triage-actions.spec.ts
│   │   │   │   │   │   ├── 📁 meetings
│   │   │   │   │   │   │   ├── 📄 meeting-bot-core-flow.spec.ts
│   │   │   │   │   │   │   └── 📄 meeting-bot-test-helpers.ts
│   │   │   │   │   │   ├── 📁 onboarding
│   │   │   │   │   │   │   ├── 📄 background-scans.spec.ts
│   │   │   │   │   │   │   ├── 📄 control-onboarding.spec.ts
│   │   │   │   │   │   │   ├── 📄 missing-permissions-onboarding.spec.ts
│   │   │   │   │   │   │   ├── 📄 onboarding-test-helpers.ts
│   │   │   │   │   │   │   └── 📄 signup-intent-onboarding.spec.ts
│   │   │   │   │   │   ├── 📁 settings
│   │   │   │   │   │   │   ├── 📄 api-keys.spec.ts
│   │   │   │   │   │   │   ├── 📄 appearance.spec.ts
│   │   │   │   │   │   │   ├── 📄 email-account-settings.spec.ts
│   │   │   │   │   │   │   ├── 📄 email-otp.spec.ts
│   │   │   │   │   │   │   ├── 📄 language.spec.ts
│   │   │   │   │   │   │   ├── 📄 mcp-access.spec.ts
│   │   │   │   │   │   │   ├── 📄 reset-label-colors.spec.ts
│   │   │   │   │   │   │   ├── 📄 scim-credentials.spec.ts
│   │   │   │   │   │   │   ├── 📄 settings-dialog.spec.ts
│   │   │   │   │   │   │   └── 📄 settings-test-helpers.ts
│   │   │   │   │   │   ├── 📁 setup
│   │   │   │   │   │   │   └── 📄 auth.setup.ts
│   │   │   │   │   │   ├── 📄 account-test-helpers.ts
│   │   │   │   │   │   ├── 📄 mail-provider.ts
│   │   │   │   │   │   ├── 📄 playwright-evidence.ts
│   │   │   │   │   │   └── 📄 playwright-test.ts
│   │   │   │   │   ├── 📁 mail-simulation
│   │   │   │   │   │   ├── 📝 README.md
│   │   │   │   │   │   ├── 📄 bulk-run.spec.ts
│   │   │   │   │   │   ├── 📄 loading.spec.ts
│   │   │   │   │   │   ├── 📄 playwright.config.mjs
│   │   │   │   │   │   ├── 📄 quota-proxy.mjs
│   │   │   │   │   │   ├── 📄 quota-proxy.test.mjs
│   │   │   │   │   │   ├── 📄 run.mjs
│   │   │   │   │   │   └── 📄 server.mjs
│   │   │   │   │   ├── 📝 README.md
│   │   │   │   │   ├── 📄 email-server.mjs
│   │   │   │   │   ├── 📄 run-emulated-suite.mjs
│   │   │   │   │   ├── 📝 selection-comparison.md
│   │   │   │   │   ├── 📄 todoist-preload.mjs
│   │   │   │   │   └── 📄 todoist-transport.ts
│   │   │   │   ├── 📁 redis
│   │   │   │   │   ├── 📝 README.md
│   │   │   │   │   └── 📄 local-mail-sync-budget.test.ts
│   │   │   │   ├── 📄 ai-assistant-chat.test.ts
│   │   │   │   ├── 📄 helpers.ts
│   │   │   │   ├── 📄 setup.ts
│   │   │   │   └── 📄 test-env.ts
│   │   │   ├── 📁 app
│   │   │   │   ├── 📁 (app)
│   │   │   │   │   ├── 📁 [emailAccountId]
│   │   │   │   │   │   ├── 📁 assistant
│   │   │   │   │   │   │   ├── 📁 group
│   │   │   │   │   │   │   │   ├── 📄 LearnedPatterns.tsx
│   │   │   │   │   │   │   │   └── 📄 ViewLearnedPatterns.tsx
│   │   │   │   │   │   │   ├── 📁 knowledge
│   │   │   │   │   │   │   │   ├── 📄 DraftDocsSites.tsx
│   │   │   │   │   │   │   │   ├── 📄 KnowledgeBase.tsx
│   │   │   │   │   │   │   │   └── 📄 KnowledgeForm.tsx
│   │   │   │   │   │   │   ├── 📁 rule
│   │   │   │   │   │   │   │   ├── 📁 [ruleId]
│   │   │   │   │   │   │   │   │   ├── 📄 error.tsx
│   │   │   │   │   │   │   │   │   └── 📄 page.tsx
│   │   │   │   │   │   │   │   └── 📁 create
│   │   │   │   │   │   │   │       └── 📄 page.tsx
│   │   │   │   │   │   │   ├── 📁 settings
│   │   │   │   │   │   │   │   ├── 📄 AboutSetting.tsx
│   │   │   │   │   │   │   │   ├── 📄 DigestSetting.tsx
│   │   │   │   │   │   │   │   ├── 📄 DraftConfidenceSetting.tsx
│   │   │   │   │   │   │   │   ├── 📄 DraftKnowledgeSetting.tsx
│   │   │   │   │   │   │   │   ├── 📄 DraftReplies.tsx
│   │   │   │   │   │   │   │   ├── 📄 FollowUpRemindersSetting.tsx
│   │   │   │   │   │   │   │   ├── 📄 HiddenAiDraftLinksSetting.tsx
│   │   │   │   │   │   │   │   ├── 📄 LearnedPatternsSetting.tsx
│   │   │   │   │   │   │   │   ├── 📄 MultiRuleSetting.tsx
│   │   │   │   │   │   │   │   ├── 📄 PersonalSignatureSetting.tsx
│   │   │   │   │   │   │   │   ├── 📄 ProactiveUpdatesSetting.tsx
│   │   │   │   │   │   │   │   ├── 📄 ReferralSignatureSetting.tsx
│   │   │   │   │   │   │   │   ├── 📄 RuleImportExportSetting.tsx
│   │   │   │   │   │   │   │   ├── 📄 SensitiveDataPolicySetting.tsx
│   │   │   │   │   │   │   │   ├── 📄 SentWithSignatureSetting.tsx
│   │   │   │   │   │   │   │   ├── 📄 SettingsTab.tsx
│   │   │   │   │   │   │   │   ├── 📄 SignaturesSetting.tsx
│   │   │   │   │   │   │   │   ├── 📄 SnippetsSetting.tsx
│   │   │   │   │   │   │   │   ├── 📄 SyncToExtensionSetting.tsx
│   │   │   │   │   │   │   │   ├── 📄 WritingStyleSetting.tsx
│   │   │   │   │   │   │   │   └── 📄 cron-schedule-messages.ts
│   │   │   │   │   │   │   ├── 📄 AIChatButton.tsx
│   │   │   │   │   │   │   ├── 📄 ActionAttachmentsField.test.tsx
│   │   │   │   │   │   │   ├── 📄 ActionAttachmentsField.tsx
│   │   │   │   │   │   │   ├── 📄 ActionSteps.tsx
│   │   │   │   │   │   │   ├── 📄 AddRuleDialog.tsx
│   │   │   │   │   │   │   ├── 📄 AllRulesDisabledBanner.tsx
│   │   │   │   │   │   │   ├── 📄 AvailableActionsPanel.tsx
│   │   │   │   │   │   │   ├── 📄 BulkProcessActivityLog.tsx
│   │   │   │   │   │   │   ├── 📄 BulkRunRules.test.ts
│   │   │   │   │   │   │   ├── 📄 BulkRunRules.tsx
│   │   │   │   │   │   │   ├── 📄 ConditionSteps.tsx
│   │   │   │   │   │   │   ├── 📄 DateCell.tsx
│   │   │   │   │   │   │   ├── 📄 ExamplesList.tsx
│   │   │   │   │   │   │   ├── 📄 FixWithChat.tsx
│   │   │   │   │   │   │   ├── 📄 History.tsx
│   │   │   │   │   │   │   ├── 📄 LearnedPatternExclusionHint.tsx
│   │   │   │   │   │   │   ├── 📄 PersonaDialog.tsx
│   │   │   │   │   │   │   ├── 📄 Process.tsx
│   │   │   │   │   │   │   ├── 📄 ProcessRules.tsx
│   │   │   │   │   │   │   ├── 📄 ResultDisplay.test.tsx
│   │   │   │   │   │   │   ├── 📄 ResultDisplay.tsx
│   │   │   │   │   │   │   ├── 📄 RuleDialog.tsx
│   │   │   │   │   │   │   ├── 📄 RuleForm.render.test.tsx
│   │   │   │   │   │   │   ├── 📄 RuleForm.test.ts
│   │   │   │   │   │   │   ├── 📄 RuleForm.tsx
│   │   │   │   │   │   │   ├── 📄 RuleLoader.test.tsx
│   │   │   │   │   │   │   ├── 📄 RuleLoader.tsx
│   │   │   │   │   │   │   ├── 📄 RuleNotFoundState.tsx
│   │   │   │   │   │   │   ├── 📄 RuleSectionCard.tsx
│   │   │   │   │   │   │   ├── 📄 RuleStep.tsx
│   │   │   │   │   │   │   ├── 📄 RuleSteps.tsx
│   │   │   │   │   │   │   ├── 📄 Rules.test.tsx
│   │   │   │   │   │   │   ├── 📄 Rules.tsx
│   │   │   │   │   │   │   ├── 📄 RulesPromptNew.tsx
│   │   │   │   │   │   │   ├── 📄 RulesSelect.tsx
│   │   │   │   │   │   │   ├── 📄 RulesTabNew.tsx
│   │   │   │   │   │   │   ├── 📄 SetDateDropdown.tsx
│   │   │   │   │   │   │   ├── 📄 TestCustomEmailForm.tsx
│   │   │   │   │   │   │   ├── 📄 ThreadSkipHint.tsx
│   │   │   │   │   │   │   ├── 📄 attachment-source-selection.test.ts
│   │   │   │   │   │   │   ├── 📄 attachment-source-selection.ts
│   │   │   │   │   │   │   ├── 📄 bulk-run-retry.test.ts
│   │   │   │   │   │   │   ├── 📄 bulk-run-retry.ts
│   │   │   │   │   │   │   ├── 📄 bulk-run-rules-reducer.test.ts
│   │   │   │   │   │   │   ├── 📄 bulk-run-rules-reducer.ts
│   │   │   │   │   │   │   ├── 📄 bulk-run.test.ts
│   │   │   │   │   │   │   ├── 📄 bulk-run.ts
│   │   │   │   │   │   │   ├── 📄 condition-messages.ts
│   │   │   │   │   │   │   ├── 📄 constants.ts
│   │   │   │   │   │   │   ├── 📄 consts.ts
│   │   │   │   │   │   │   ├── 📄 draftReplyActions.test.ts
│   │   │   │   │   │   │   ├── 📄 draftReplyActions.ts
│   │   │   │   │   │   │   ├── 📄 examples.ts
│   │   │   │   │   │   │   ├── 📄 page.test.ts
│   │   │   │   │   │   │   ├── 📄 page.tsx
│   │   │   │   │   │   │   ├── 📄 rule-fetch-error.test.ts
│   │   │   │   │   │   │   ├── 📄 rule-fetch-error.ts
│   │   │   │   │   │   │   ├── 📄 ruleFormActions.test.ts
│   │   │   │   │   │   │   └── 📄 ruleFormActions.ts
│   │   │   │   │   │   ├── 📁 automation
│   │   │   │   │   │   │   ├── 📄 AutomationTabs.tsx
│   │   │   │   │   │   │   └── 📄 page.tsx
│   │   │   │   │   │   ├── 📁 briefs
│   │   │   │   │   │   │   ├── 📄 DeliveryChannelsSetting.tsx
│   │   │   │   │   │   │   ├── 📄 IntegrationsSetting.tsx
│   │   │   │   │   │   │   ├── 📄 Onboarding.tsx
│   │   │   │   │   │   │   ├── 📄 TimeDurationSetting.tsx
│   │   │   │   │   │   │   ├── 📄 UpcomingMeetings.tsx
│   │   │   │   │   │   │   └── 📄 page.tsx
│   │   │   │   │   │   ├── 📁 bulk-archive
│   │   │   │   │   │   │   ├── 📄 AutoCategorizationSetup.test.tsx
│   │   │   │   │   │   │   ├── 📄 AutoCategorizationSetup.tsx
│   │   │   │   │   │   │   ├── 📄 BulkArchive.tsx
│   │   │   │   │   │   │   ├── 📄 BulkArchiveProgress.test.tsx
│   │   │   │   │   │   │   ├── 📄 BulkArchiveProgress.tsx
│   │   │   │   │   │   │   ├── 📄 BulkArchiveSettingsModal.tsx
│   │   │   │   │   │   │   └── 📄 page.tsx
│   │   │   │   │   │   ├── 📁 bulk-unsubscribe
│   │   │   │   │   │   │   ├── 📄 ArchiveProgress.test.tsx
│   │   │   │   │   │   │   ├── 📄 ArchiveProgress.tsx
│   │   │   │   │   │   │   ├── 📄 BulkActions.tsx
│   │   │   │   │   │   │   ├── 📄 BulkUnsubscribeDesktop.tsx
│   │   │   │   │   │   │   ├── 📄 BulkUnsubscribeSection.tsx
│   │   │   │   │   │   │   ├── 📄 BulkUnsubscribeSkeleton.tsx
│   │   │   │   │   │   │   ├── 📄 ResubscribeDialog.tsx
│   │   │   │   │   │   │   ├── 📄 SearchBar.tsx
│   │   │   │   │   │   │   ├── 📄 SenderPanel.tsx
│   │   │   │   │   │   │   ├── 📄 UnsubscribeCelebrationDialog.tsx
│   │   │   │   │   │   │   ├── 📄 UnsubscribeShareCard.tsx
│   │   │   │   │   │   │   ├── 📄 common.tsx
│   │   │   │   │   │   │   ├── 📄 hooks.test.ts
│   │   │   │   │   │   │   ├── 📄 hooks.ts
│   │   │   │   │   │   │   ├── 📄 page.tsx
│   │   │   │   │   │   │   ├── 📄 share.test.ts
│   │   │   │   │   │   │   ├── 📄 share.ts
│   │   │   │   │   │   │   ├── 📄 suggestions.test.ts
│   │   │   │   │   │   │   ├── 📄 suggestions.ts
│   │   │   │   │   │   │   └── 📄 types.ts
│   │   │   │   │   │   ├── 📁 calendars
│   │   │   │   │   │   │   ├── 📄 AvailabilitySection.tsx
│   │   │   │   │   │   │   ├── 📄 BookingLinkDialog.tsx
│   │   │   │   │   │   │   ├── 📄 BookingLinksSection.tsx
│   │   │   │   │   │   │   ├── 📄 CalendarConnectionCard.tsx
│   │   │   │   │   │   │   ├── 📄 CalendarConnections.tsx
│   │   │   │   │   │   │   ├── 📄 CalendarList.tsx
│   │   │   │   │   │   │   ├── 📄 CalendarSettings.tsx
│   │   │   │   │   │   │   ├── 📄 ConfigureBookingLinkDialog.test.tsx
│   │   │   │   │   │   │   ├── 📄 ConfigureBookingLinkDialog.tsx
│   │   │   │   │   │   │   ├── 📄 ConnectCalendar.tsx
│   │   │   │   │   │   │   ├── 📄 CreateBookingLinkDialog.test.tsx
│   │   │   │   │   │   │   ├── 📄 CreateBookingLinkDialog.tsx
│   │   │   │   │   │   │   ├── 📄 VideoConferencingItem.tsx
│   │   │   │   │   │   │   ├── 📄 WeeklyHoursEditor.tsx
│   │   │   │   │   │   │   ├── 📄 availability-schedule.test.ts
│   │   │   │   │   │   │   ├── 📄 availability-schedule.ts
│   │   │   │   │   │   │   ├── 📄 booking-calendar-helpers.test.ts
│   │   │   │   │   │   │   ├── 📄 booking-calendar-helpers.ts
│   │   │   │   │   │   │   └── 📄 page.tsx
│   │   │   │   │   │   ├── 📁 channels
│   │   │   │   │   │   │   ├── 📄 Channels.tsx
│   │   │   │   │   │   │   └── 📄 page.tsx
│   │   │   │   │   │   ├── 📁 clean
│   │   │   │   │   │   │   ├── 📁 history
│   │   │   │   │   │   │   │   └── 📄 page.tsx
│   │   │   │   │   │   │   ├── 📁 onboarding
│   │   │   │   │   │   │   │   ├── 📄 page.test.ts
│   │   │   │   │   │   │   │   └── 📄 page.tsx
│   │   │   │   │   │   │   ├── 📁 run
│   │   │   │   │   │   │   │   └── 📄 page.tsx
│   │   │   │   │   │   │   ├── 📄 ActionSelectionStep.tsx
│   │   │   │   │   │   │   ├── 📄 CleanHistory.tsx
│   │   │   │   │   │   │   ├── 📄 CleanInstructionsStep.tsx
│   │   │   │   │   │   │   ├── 📄 CleanRun.tsx
│   │   │   │   │   │   │   ├── 📄 ConfirmationStep.tsx
│   │   │   │   │   │   │   ├── 📄 EmailFirehose.tsx
│   │   │   │   │   │   │   ├── 📄 EmailFirehoseItem.tsx
│   │   │   │   │   │   │   ├── 📄 IntroStep.tsx
│   │   │   │   │   │   │   ├── 📄 PreviewBatch.tsx
│   │   │   │   │   │   │   ├── 📄 TimeRangeStep.tsx
│   │   │   │   │   │   │   ├── 📄 consts.ts
│   │   │   │   │   │   │   ├── 📄 helpers.ts
│   │   │   │   │   │   │   ├── 📄 loading.tsx
│   │   │   │   │   │   │   ├── 📄 page.tsx
│   │   │   │   │   │   │   ├── 📄 types.ts
│   │   │   │   │   │   │   ├── 📄 useEmailStream.test.ts
│   │   │   │   │   │   │   ├── 📄 useEmailStream.ts
│   │   │   │   │   │   │   ├── 📄 useSkipSettings.ts
│   │   │   │   │   │   │   └── 📄 useStep.tsx
│   │   │   │   │   │   ├── 📁 cold-email-blocker
│   │   │   │   │   │   │   ├── 📄 ColdEmailContent.tsx
│   │   │   │   │   │   │   ├── 📄 ColdEmailList.tsx
│   │   │   │   │   │   │   ├── 📄 ColdEmailRejected.tsx
│   │   │   │   │   │   │   ├── 📄 ColdEmailTest.tsx
│   │   │   │   │   │   │   ├── 📄 TestRules.tsx
│   │   │   │   │   │   │   └── 📄 page.tsx
│   │   │   │   │   │   ├── 📁 compose
│   │   │   │   │   │   │   ├── 📄 ComposeAttachmentList.tsx
│   │   │   │   │   │   │   ├── 📄 ComposeContactRecipientField.test.tsx
│   │   │   │   │   │   │   ├── 📄 ComposeContactRecipientField.tsx
│   │   │   │   │   │   │   ├── 📄 ComposeEmailForm.tsx
│   │   │   │   │   │   │   ├── 📄 ComposeEmailFormLazy.test.tsx
│   │   │   │   │   │   │   ├── 📄 ComposeEmailFormLazy.tsx
│   │   │   │   │   │   │   ├── 📄 ComposeHeaderFields.tsx
│   │   │   │   │   │   │   ├── 📄 ComposeSignaturePicker.tsx
│   │   │   │   │   │   │   ├── 📄 DeliveryOptions.tsx
│   │   │   │   │   │   │   ├── 📄 SendWarningsDialog.tsx
│   │   │   │   │   │   │   ├── 📄 compose-attachments.test.ts
│   │   │   │   │   │   │   ├── 📄 compose-attachments.ts
│   │   │   │   │   │   │   ├── 📄 compose-error-messages.ts
│   │   │   │   │   │   │   ├── 📄 compose-message-html.ts
│   │   │   │   │   │   │   ├── 📄 compose-recipients.test.ts
│   │   │   │   │   │   │   ├── 📄 compose-recipients.ts
│   │   │   │   │   │   │   ├── 📄 contact-suggestions.test.ts
│   │   │   │   │   │   │   ├── 📄 contact-suggestions.ts
│   │   │   │   │   │   │   ├── 📄 delivery-times.test.ts
│   │   │   │   │   │   │   ├── 📄 delivery-times.ts
│   │   │   │   │   │   │   ├── 📄 draft-operation-queue.ts
│   │   │   │   │   │   │   ├── 📄 find-signature-id.test.ts
│   │   │   │   │   │   │   ├── 📄 find-signature-id.ts
│   │   │   │   │   │   │   ├── 📄 follow-provider-draft-message.test.ts
│   │   │   │   │   │   │   ├── 📄 follow-provider-draft-message.ts
│   │   │   │   │   │   │   ├── 📄 initial-compose-content.test.ts
│   │   │   │   │   │   │   ├── 📄 initial-compose-content.ts
│   │   │   │   │   │   │   ├── 📄 queued-reply.test.ts
│   │   │   │   │   │   │   ├── 📄 queued-reply.ts
│   │   │   │   │   │   │   ├── 📄 reply-to-email-payload.test.ts
│   │   │   │   │   │   │   ├── 📄 reply-to-email-payload.ts
│   │   │   │   │   │   │   ├── 📄 resolve-remote-images.test.ts
│   │   │   │   │   │   │   ├── 📄 resolve-remote-images.ts
│   │   │   │   │   │   │   ├── 📄 send-draft-reference.test.ts
│   │   │   │   │   │   │   ├── 📄 send-draft-reference.ts
│   │   │   │   │   │   │   ├── 📄 send-warnings.dom.test.ts
│   │   │   │   │   │   │   ├── 📄 send-warnings.test.ts
│   │   │   │   │   │   │   ├── 📄 send-warnings.ts
│   │   │   │   │   │   │   ├── 📄 undo-send.test.ts
│   │   │   │   │   │   │   ├── 📄 undo-send.ts
│   │   │   │   │   │   │   ├── 📄 upload-draft-attachment.test.ts
│   │   │   │   │   │   │   ├── 📄 upload-draft-attachment.ts
│   │   │   │   │   │   │   ├── 📄 useComposeAttachments.ts
│   │   │   │   │   │   │   ├── 📄 useComposeDraft.ts
│   │   │   │   │   │   │   ├── 📄 useComposeDraftAttachments.test.ts
│   │   │   │   │   │   │   ├── 📄 useComposeDraftAttachments.ts
│   │   │   │   │   │   │   ├── 📄 useComposeSend.ts
│   │   │   │   │   │   │   └── 📄 useComposeSnippets.tsx
│   │   │   │   │   │   ├── 📁 debug
│   │   │   │   │   │   │   ├── 📁 drafts
│   │   │   │   │   │   │   │   └── 📄 page.tsx
│   │   │   │   │   │   │   ├── 📁 follow-up
│   │   │   │   │   │   │   │   └── 📄 page.tsx
│   │   │   │   │   │   │   ├── 📁 mail-queue
│   │   │   │   │   │   │   │   └── 📄 page.tsx
│   │   │   │   │   │   │   ├── 📁 memories
│   │   │   │   │   │   │   │   └── 📄 page.tsx
│   │   │   │   │   │   │   ├── 📁 report
│   │   │   │   │   │   │   │   └── 📄 page.tsx
│   │   │   │   │   │   │   ├── 📁 rule-history
│   │   │   │   │   │   │   │   ├── 📁 [ruleId]
│   │   │   │   │   │   │   │   │   └── 📄 page.tsx
│   │   │   │   │   │   │   │   └── 📄 page.tsx
│   │   │   │   │   │   │   ├── 📁 rules
│   │   │   │   │   │   │   │   └── 📄 page.tsx
│   │   │   │   │   │   │   └── 📄 page.tsx
│   │   │   │   │   │   ├── 📁 drive
│   │   │   │   │   │   │   ├── 📄 AllowedFolders.tsx
│   │   │   │   │   │   │   ├── 📄 ConnectDrive.tsx
│   │   │   │   │   │   │   ├── 📄 DriveConnectionCard.tsx
│   │   │   │   │   │   │   ├── 📄 DriveConnections.tsx
│   │   │   │   │   │   │   ├── 📄 DriveOnboarding.tsx
│   │   │   │   │   │   │   ├── 📄 DriveSetup.tsx
│   │   │   │   │   │   │   ├── 📄 FilingActivity.tsx
│   │   │   │   │   │   │   ├── 📄 FilingPreferences.tsx
│   │   │   │   │   │   │   ├── 📄 FilingRulesForm.tsx
│   │   │   │   │   │   │   ├── 📄 allowed-folder-selection.test.ts
│   │   │   │   │   │   │   ├── 📄 allowed-folder-selection.ts
│   │   │   │   │   │   │   ├── 📄 page.tsx
│   │   │   │   │   │   │   ├── 📄 use-folder-selection.test.ts
│   │   │   │   │   │   │   └── 📄 use-folder-selection.ts
│   │   │   │   │   │   ├── 📁 integrations
│   │   │   │   │   │   │   ├── 📄 AddCustomMcpServerDialog.tsx
│   │   │   │   │   │   │   ├── 📄 IntegrationRow.tsx
│   │   │   │   │   │   │   ├── 📄 Integrations.tsx
│   │   │   │   │   │   │   ├── 📄 IntegrationsPremiumAlert.tsx
│   │   │   │   │   │   │   ├── 📄 RequestAccessDialog.tsx
│   │   │   │   │   │   │   ├── 📄 integration-messages.ts
│   │   │   │   │   │   │   ├── 📄 page.tsx
│   │   │   │   │   │   │   └── 📄 startMcpOAuth.ts
│   │   │   │   │   │   ├── 📁 mail
│   │   │   │   │   │   │   ├── 📄 AllAccountsSelectionDialog.tsx
│   │   │   │   │   │   │   ├── 📄 BufferedThreadReader.test.tsx
│   │   │   │   │   │   │   ├── 📄 BufferedThreadReader.tsx
│   │   │   │   │   │   │   ├── 📄 DeploymentUpdateNotice.test.tsx
│   │   │   │   │   │   │   ├── 📄 DeploymentUpdateNotice.tsx
│   │   │   │   │   │   │   ├── 📄 InboxBundleRow.tsx
│   │   │   │   │   │   │   ├── 📄 InboxZeroCelebration.tsx
│   │   │   │   │   │   │   ├── 📄 LabelPickerDialog.test.tsx
│   │   │   │   │   │   │   ├── 📄 LabelPickerDialog.tsx
│   │   │   │   │   │   │   ├── 📄 ListSenderCommands.tsx
│   │   │   │   │   │   │   ├── 📄 ListToolbar.tsx
│   │   │   │   │   │   │   ├── 📄 MailAccountSwitcher.test.tsx
│   │   │   │   │   │   │   ├── 📄 MailAccountSwitcher.tsx
│   │   │   │   │   │   │   ├── 📄 MailLabelChip.test.ts
│   │   │   │   │   │   │   ├── 📄 MailLabelChip.tsx
│   │   │   │   │   │   │   ├── 📄 MailListPanel.tsx
│   │   │   │   │   │   │   ├── 📄 MailPanelErrorBoundary.test.tsx
│   │   │   │   │   │   │   ├── 📄 MailPanelErrorBoundary.tsx
│   │   │   │   │   │   │   ├── 📄 MailPreviewOverlay.tsx
│   │   │   │   │   │   │   ├── 📄 MailReaderPane.tsx
│   │   │   │   │   │   │   ├── 📄 MailSearchFilters.tsx
│   │   │   │   │   │   │   ├── 📄 MailSearchSuggestions.tsx
│   │   │   │   │   │   │   ├── 📄 MailSetupPanel.tsx
│   │   │   │   │   │   │   ├── 📄 MailShell.tsx
│   │   │   │   │   │   │   ├── 📄 MailShellSidebar.tsx
│   │   │   │   │   │   │   ├── 📄 MailSidebar.test.tsx
│   │   │   │   │   │   │   ├── 📄 MailSidebar.tsx
│   │   │   │   │   │   │   ├── 📄 MailSplitTabs.tsx
│   │   │   │   │   │   │   ├── 📄 MailThemeScope.tsx
│   │   │   │   │   │   │   ├── 📄 MailboxItemContextMenu.tsx
│   │   │   │   │   │   │   ├── 📄 MessageActionsMenu.tsx
│   │   │   │   │   │   │   ├── 📄 MessageSourceDialog.tsx
│   │   │   │   │   │   │   ├── 📄 NewSplitDialog.tsx
│   │   │   │   │   │   │   ├── 📄 OutlookSearchFilters.tsx
│   │   │   │   │   │   │   ├── 📄 ReaderToolbar.tsx
│   │   │   │   │   │   │   ├── 📄 ScheduledEmailList.tsx
│   │   │   │   │   │   │   ├── 📄 SelectAllCheckbox.tsx
│   │   │   │   │   │   │   ├── 📄 SenderContextPanel.test.tsx
│   │   │   │   │   │   │   ├── 📄 SenderContextPanel.tsx
│   │   │   │   │   │   │   ├── 📄 ShortcutsDialog.tsx
│   │   │   │   │   │   │   ├── 📄 SplitPickerDialog.tsx
│   │   │   │   │   │   │   ├── 📄 SplitTabs.tsx
│   │   │   │   │   │   │   ├── 📄 ThreadActionsMenu.tsx
│   │   │   │   │   │   │   ├── 📄 ThreadList.tsx
│   │   │   │   │   │   │   ├── 📄 ThreadReader.test.tsx
│   │   │   │   │   │   │   ├── 📄 ThreadReader.tsx
│   │   │   │   │   │   │   ├── 📄 ThreadRow.test.tsx
│   │   │   │   │   │   │   ├── 📄 ThreadRow.tsx
│   │   │   │   │   │   │   ├── 📄 chat-mail-view.test.ts
│   │   │   │   │   │   │   ├── 📄 chat-mail-view.ts
│   │   │   │   │   │   │   ├── 📄 inbox-bundles.test.ts
│   │   │   │   │   │   │   ├── 📄 inbox-bundles.ts
│   │   │   │   │   │   │   ├── 📄 label-tree.test.ts
│   │   │   │   │   │   │   ├── 📄 label-tree.ts
│   │   │   │   │   │   │   ├── 📄 label-visibility.test.ts
│   │   │   │   │   │   │   ├── 📄 label-visibility.ts
│   │   │   │   │   │   │   ├── 📄 latest-shown-message.test.ts
│   │   │   │   │   │   │   ├── 📄 latest-shown-message.ts
│   │   │   │   │   │   │   ├── 📄 layout.tsx
│   │   │   │   │   │   │   ├── 📄 mail-account-url.test.ts
│   │   │   │   │   │   │   ├── 📄 mail-account-url.ts
│   │   │   │   │   │   │   ├── 📄 mail-command-palette.test.ts
│   │   │   │   │   │   │   ├── 📄 mail-command-palette.ts
│   │   │   │   │   │   │   ├── 📄 mail-search-query.test.ts
│   │   │   │   │   │   │   ├── 📄 mail-search-query.ts
│   │   │   │   │   │   │   ├── 📄 message-source.ts
│   │   │   │   │   │   │   ├── 📄 otp-code.test.ts
│   │   │   │   │   │   │   ├── 📄 otp-code.ts
│   │   │   │   │   │   │   ├── 📄 outlook-folder-list.test.ts
│   │   │   │   │   │   │   ├── 📄 outlook-folder-list.ts
│   │   │   │   │   │   │   ├── 📄 outlook-search-query.test.ts
│   │   │   │   │   │   │   ├── 📄 outlook-search-query.ts
│   │   │   │   │   │   │   ├── 📄 page.tsx
│   │   │   │   │   │   │   ├── 📄 panel-widths.ts
│   │   │   │   │   │   │   ├── 📄 print-messages.test.ts
│   │   │   │   │   │   │   ├── 📄 print-messages.ts
│   │   │   │   │   │   │   ├── 📄 read-state.test.ts
│   │   │   │   │   │   │   ├── 📄 read-state.ts
│   │   │   │   │   │   │   ├── 📄 snooze-command-palette.test.ts
│   │   │   │   │   │   │   ├── 📄 snooze-command-palette.ts
│   │   │   │   │   │   │   ├── 📄 star-state.ts
│   │   │   │   │   │   │   ├── 📄 subscribe-to-visible-revalidation.test.ts
│   │   │   │   │   │   │   ├── 📄 subscribe-to-visible-revalidation.ts
│   │   │   │   │   │   │   ├── 📄 thread-list-behavior.test.ts
│   │   │   │   │   │   │   ├── 📄 thread-list-behavior.ts
│   │   │   │   │   │   │   ├── 📄 thread-participants.test.ts
│   │   │   │   │   │   │   ├── 📄 thread-participants.ts
│   │   │   │   │   │   │   ├── 📄 thread-select-all.ts
│   │   │   │   │   │   │   ├── 📄 types.test.ts
│   │   │   │   │   │   │   ├── 📄 types.ts
│   │   │   │   │   │   │   ├── 📄 use-combined-mail-threads.test.ts
│   │   │   │   │   │   │   ├── 📄 use-combined-mail-threads.ts
│   │   │   │   │   │   │   ├── 📄 use-drag-reorder.ts
│   │   │   │   │   │   │   ├── 📄 use-engine-mail-threads.test.tsx
│   │   │   │   │   │   │   ├── 📄 use-engine-mail-threads.ts
│   │   │   │   │   │   │   ├── 📄 use-mail-performance-telemetry.ts
│   │   │   │   │   │   │   ├── 📄 use-mail-threads.ts
│   │   │   │   │   │   │   ├── 📄 use-optimistic-archive.test.ts
│   │   │   │   │   │   │   ├── 📄 use-optimistic-archive.ts
│   │   │   │   │   │   │   ├── 📄 use-public-contact-context.test.tsx
│   │   │   │   │   │   │   ├── 📄 use-public-contact-context.ts
│   │   │   │   │   │   │   ├── 📄 use-sender-commands.ts
│   │   │   │   │   │   │   ├── 📄 use-split-counts.ts
│   │   │   │   │   │   │   ├── 📄 use-stable-callback.ts
│   │   │   │   │   │   │   ├── 📄 use-thread-actions.test.ts
│   │   │   │   │   │   │   ├── 📄 use-thread-actions.ts
│   │   │   │   │   │   │   ├── 📄 use-thread-selection.test.ts
│   │   │   │   │   │   │   ├── 📄 use-thread-selection.ts
│   │   │   │   │   │   │   ├── 📄 use-thread-translation.test.tsx
│   │   │   │   │   │   │   ├── 📄 use-thread-translation.ts
│   │   │   │   │   │   │   ├── 📄 use-unsubscribe-sender.ts
│   │   │   │   │   │   │   ├── 📄 use-warm-neighbour-threads.test.tsx
│   │   │   │   │   │   │   └── 📄 use-warm-neighbour-threads.ts
│   │   │   │   │   │   ├── 📁 meetings
│   │   │   │   │   │   │   ├── 📄 MeetingDetail.tsx
│   │   │   │   │   │   │   ├── 📄 MeetingListItem.tsx
│   │   │   │   │   │   │   ├── 📄 MeetingRecorderOnboarding.tsx
│   │   │   │   │   │   │   ├── 📄 MeetingRecorderSettingsDialog.tsx
│   │   │   │   │   │   │   ├── 📄 MeetingsList.tsx
│   │   │   │   │   │   │   ├── 📄 UpcomingMeetingsToggleList.tsx
│   │   │   │   │   │   │   ├── 📄 calendar-connection-state.ts
│   │   │   │   │   │   │   ├── 📄 join-rule-options.ts
│   │   │   │   │   │   │   ├── 📄 meeting-detail-state.test.ts
│   │   │   │   │   │   │   ├── 📄 meeting-detail-state.ts
│   │   │   │   │   │   │   ├── 📄 page.tsx
│   │   │   │   │   │   │   ├── 📄 recording-status.test.ts
│   │   │   │   │   │   │   └── 📄 recording-status.ts
│   │   │   │   │   │   ├── 📁 onboarding
│   │   │   │   │   │   │   ├── 📁 illustrations
│   │   │   │   │   │   │   │   ├── 📄 BulkUnsubscribeIllustration.tsx
│   │   │   │   │   │   │   │   ├── 📄 ChatIllustration.tsx
│   │   │   │   │   │   │   │   ├── 📄 CustomRulesIllustration.tsx
│   │   │   │   │   │   │   │   ├── 📄 DraftRepliesIllustration.tsx
│   │   │   │   │   │   │   │   ├── 📄 EmailsSortedIllustration.tsx
│   │   │   │   │   │   │   │   ├── 📄 IllustrationWindow.tsx
│   │   │   │   │   │   │   │   └── 📄 SplitInboxIllustration.tsx
│   │   │   │   │   │   │   ├── 📄 ContinueButton.tsx
│   │   │   │   │   │   │   ├── 📄 IconCircle.tsx
│   │   │   │   │   │   │   ├── 📄 Onboarding.tsx
│   │   │   │   │   │   │   ├── 📄 OnboardingButton.tsx
│   │   │   │   │   │   │   ├── 📄 OnboardingCategories.tsx
│   │   │   │   │   │   │   ├── 📄 OnboardingContent.test.tsx
│   │   │   │   │   │   │   ├── 📄 OnboardingContent.tsx
│   │   │   │   │   │   │   ├── 📄 OnboardingFeatureStep.tsx
│   │   │   │   │   │   │   ├── 📄 OnboardingPermissionsGate.tsx
│   │   │   │   │   │   │   ├── 📄 OnboardingWrapper.tsx
│   │   │   │   │   │   │   ├── 📄 StepBulkUnsubscribe.tsx
│   │   │   │   │   │   │   ├── 📄 StepChat.tsx
│   │   │   │   │   │   │   ├── 📄 StepCompanySize.tsx
│   │   │   │   │   │   │   ├── 📄 StepCustomRules.tsx
│   │   │   │   │   │   │   ├── 📄 StepDraft.tsx
│   │   │   │   │   │   │   ├── 📄 StepDraftReplies.tsx
│   │   │   │   │   │   │   ├── 📄 StepEmailsSorted.tsx
│   │   │   │   │   │   │   ├── 📄 StepHowYouHeard.tsx
│   │   │   │   │   │   │   ├── 📄 StepInboxProcessed.tsx
│   │   │   │   │   │   │   ├── 📄 StepIntent.tsx
│   │   │   │   │   │   │   ├── 📄 StepInviteTeam.tsx
│   │   │   │   │   │   │   ├── 📄 StepLabels.tsx
│   │   │   │   │   │   │   ├── 📄 StepMailApp.tsx
│   │   │   │   │   │   │   ├── 📄 StepWho.tsx
│   │   │   │   │   │   │   ├── 📄 UnsubscribeSuggestionRow.tsx
│   │   │   │   │   │   │   ├── 📄 category-messages.ts
│   │   │   │   │   │   │   ├── 📄 config.ts
│   │   │   │   │   │   │   ├── 📄 onboardingFlow.test.ts
│   │   │   │   │   │   │   ├── 📄 onboardingFlow.ts
│   │   │   │   │   │   │   ├── 📄 page.tsx
│   │   │   │   │   │   │   └── 📄 useCompleteOnboarding.ts
│   │   │   │   │   │   ├── 📁 onboarding-brief
│   │   │   │   │   │   │   ├── 📄 MeetingBriefsOnboardingContent.tsx
│   │   │   │   │   │   │   ├── 📄 StepConnectCalendar.tsx
│   │   │   │   │   │   │   ├── 📄 StepReady.tsx
│   │   │   │   │   │   │   ├── 📄 StepSendTestBrief.tsx
│   │   │   │   │   │   │   └── 📄 page.tsx
│   │   │   │   │   │   ├── 📁 organization
│   │   │   │   │   │   │   ├── 📁 create
│   │   │   │   │   │   │   │   └── 📄 page.tsx
│   │   │   │   │   │   │   └── 📄 page.tsx
│   │   │   │   │   │   ├── 📁 permissions
│   │   │   │   │   │   │   └── 📁 consent
│   │   │   │   │   │   │       └── 📄 page.tsx
│   │   │   │   │   │   ├── 📁 quick-bulk-archive
│   │   │   │   │   │   │   ├── 📄 BulkArchiveTab.tsx
│   │   │   │   │   │   │   └── 📄 page.tsx
│   │   │   │   │   │   ├── 📁 settings
│   │   │   │   │   │   │   ├── 📄 AboutSectionForm.tsx
│   │   │   │   │   │   │   ├── 📄 ApiKeysCreateForm.tsx
│   │   │   │   │   │   │   ├── 📄 ApiKeysSection.tsx
│   │   │   │   │   │   │   ├── 📄 BillingSection.tsx
│   │   │   │   │   │   │   ├── 📄 CleanupDraftsSection.tsx
│   │   │   │   │   │   │   ├── 📄 ConnectedAppsSection.tsx
│   │   │   │   │   │   │   ├── 📄 CopyRulesDialog.tsx
│   │   │   │   │   │   │   ├── 📄 CopyRulesSection.tsx
│   │   │   │   │   │   │   ├── 📄 DecisionModelSection.tsx
│   │   │   │   │   │   │   ├── 📄 DeleteSection.tsx
│   │   │   │   │   │   │   ├── 📄 DigestSettingsForm.tsx
│   │   │   │   │   │   │   ├── 📄 McpSection.tsx
│   │   │   │   │   │   │   ├── 📄 ModelSection.tsx
│   │   │   │   │   │   │   ├── 📄 OrgAnalyticsConsentSection.tsx
│   │   │   │   │   │   │   ├── 📄 ResetAnalyticsSection.tsx
│   │   │   │   │   │   │   ├── 📄 ResetLabelColorsSection.tsx
│   │   │   │   │   │   │   ├── 📄 SentMessageOpenTrackingSetting.tsx
│   │   │   │   │   │   │   ├── 📄 SentWithSignatureSection.tsx
│   │   │   │   │   │   │   ├── 📄 ToggleAllRulesSection.tsx
│   │   │   │   │   │   │   ├── 📄 WebhookGenerate.tsx
│   │   │   │   │   │   │   ├── 📄 WebhookSection.tsx
│   │   │   │   │   │   │   ├── 📄 api-key-messages.ts
│   │   │   │   │   │   │   ├── 📄 digest-selection.test.ts
│   │   │   │   │   │   │   ├── 📄 digest-selection.ts
│   │   │   │   │   │   │   └── 📄 page.tsx
│   │   │   │   │   │   ├── 📁 setup
│   │   │   │   │   │   │   ├── 📄 SetupContent.tsx
│   │   │   │   │   │   │   ├── 📄 page.tsx
│   │   │   │   │   │   │   ├── 📄 setup-action-timeout.test.ts
│   │   │   │   │   │   │   └── 📄 setup-action-timeout.ts
│   │   │   │   │   │   ├── 📁 smart-categories
│   │   │   │   │   │   │   ├── 📁 setup
│   │   │   │   │   │   │   │   ├── 📄 SetUpCategories.tsx
│   │   │   │   │   │   │   │   ├── 📄 SmartCategoriesOnboarding.tsx
│   │   │   │   │   │   │   │   └── 📄 page.tsx
│   │   │   │   │   │   │   ├── 📄 CategorizeProgress.test.tsx
│   │   │   │   │   │   │   ├── 📄 CategorizeProgress.tsx
│   │   │   │   │   │   │   ├── 📄 CategorizeWithAiButton.test.tsx
│   │   │   │   │   │   │   ├── 📄 CategorizeWithAiButton.tsx
│   │   │   │   │   │   │   ├── 📄 CreateCategoryButton.tsx
│   │   │   │   │   │   │   ├── 📄 Uncategorized.tsx
│   │   │   │   │   │   │   └── 📄 page.tsx
│   │   │   │   │   │   ├── 📁 stats
│   │   │   │   │   │   │   ├── 📄 ActionBar.tsx
│   │   │   │   │   │   │   ├── 📄 BarChart.tsx
│   │   │   │   │   │   │   ├── 📄 BarListCard.tsx
│   │   │   │   │   │   │   ├── 📄 DetailedStatsFilter.tsx
│   │   │   │   │   │   │   ├── 📄 EmailActionsAnalytics.tsx
│   │   │   │   │   │   │   ├── 📄 EmailAnalytics.tsx
│   │   │   │   │   │   │   ├── 📄 EmailsToIncludeFilter.tsx
│   │   │   │   │   │   │   ├── 📄 LoadStatsButton.tsx
│   │   │   │   │   │   │   ├── 📄 MainStatChart.tsx
│   │   │   │   │   │   │   ├── 📄 ResponseTimeAnalytics.tsx
│   │   │   │   │   │   │   ├── 📄 RuleStatsChart.tsx
│   │   │   │   │   │   │   ├── 📄 Stats.tsx
│   │   │   │   │   │   │   ├── 📄 StatsOnboarding.tsx
│   │   │   │   │   │   │   ├── 📄 StatsSummary.tsx
│   │   │   │   │   │   │   ├── 📄 page.tsx
│   │   │   │   │   │   │   └── 📄 params.ts
│   │   │   │   │   │   ├── 📁 usage
│   │   │   │   │   │   │   ├── 📄 page.tsx
│   │   │   │   │   │   │   └── 📄 usage.tsx
│   │   │   │   │   │   ├── 📄 PermissionsCheck.tsx
│   │   │   │   │   │   ├── 📄 assess.tsx
│   │   │   │   │   │   └── 📄 error.tsx
│   │   │   │   │   ├── 📁 accounts
│   │   │   │   │   │   ├── 📄 AddAccount.tsx
│   │   │   │   │   │   └── 📄 page.tsx
│   │   │   │   │   ├── 📁 admin
│   │   │   │   │   │   ├── 📄 AdminHashEmail.tsx
│   │   │   │   │   │   ├── 📄 AdminScimCredentials.tsx
│   │   │   │   │   │   ├── 📄 AdminSyncStripe.tsx
│   │   │   │   │   │   ├── 📄 AdminTopSpenders.tsx
│   │   │   │   │   │   ├── 📄 AdminUpgradeUserForm.tsx
│   │   │   │   │   │   ├── 📄 AdminUserControls.tsx
│   │   │   │   │   │   ├── 📄 AdminUserInfo.tsx
│   │   │   │   │   │   ├── 📄 DebugLabels.tsx
│   │   │   │   │   │   ├── 📄 GmailUrlConverter.tsx
│   │   │   │   │   │   ├── 📄 RegisterSSOModal.tsx
│   │   │   │   │   │   ├── 📄 page.tsx
│   │   │   │   │   │   └── 📄 validation.tsx
│   │   │   │   │   ├── 📁 config
│   │   │   │   │   │   └── 📄 page.tsx
│   │   │   │   │   ├── 📁 early-access
│   │   │   │   │   │   ├── 📄 EarlyAccessFeatures.tsx
│   │   │   │   │   │   └── 📄 page.tsx
│   │   │   │   │   ├── 📁 license
│   │   │   │   │   │   └── 📄 page.tsx
│   │   │   │   │   ├── 📁 no-access
│   │   │   │   │   │   └── 📄 page.tsx
│   │   │   │   │   ├── 📁 organization
│   │   │   │   │   │   └── 📁 [organizationId]
│   │   │   │   │   │       ├── 📁 rules
│   │   │   │   │   │       │   ├── 📄 OrgActionSteps.tsx
│   │   │   │   │   │       │   ├── 📄 OrgRuleDialog.tsx
│   │   │   │   │   │       │   ├── 📄 OrgRules.tsx
│   │   │   │   │   │       │   ├── 📄 orgRuleForm.ts
│   │   │   │   │   │       │   └── 📄 page.tsx
│   │   │   │   │   │       ├── 📁 stats
│   │   │   │   │   │       │   ├── 📄 OrgStats.tsx
│   │   │   │   │   │       │   └── 📄 page.tsx
│   │   │   │   │   │       ├── 📄 Members.tsx
│   │   │   │   │   │       ├── 📄 OrgAnalyticsConsentBanner.tsx
│   │   │   │   │   │       ├── 📄 OrganizationTabs.tsx
│   │   │   │   │   │       ├── 📄 member-activity.test.ts
│   │   │   │   │   │       ├── 📄 member-activity.ts
│   │   │   │   │   │       └── 📄 page.tsx
│   │   │   │   │   ├── 📁 premium
│   │   │   │   │   │   ├── 📄 AppPricingLazy.tsx
│   │   │   │   │   │   ├── 📄 ManageSubscription.tsx
│   │   │   │   │   │   ├── 📄 PremiumModal.tsx
│   │   │   │   │   │   ├── 📄 Pricing.tsx
│   │   │   │   │   │   ├── 📄 PricingFrequencyToggle.tsx
│   │   │   │   │   │   ├── 📄 config-messages.test.ts
│   │   │   │   │   │   ├── 📄 config-messages.ts
│   │   │   │   │   │   ├── 📄 config.test.ts
│   │   │   │   │   │   ├── 📄 config.ts
│   │   │   │   │   │   └── 📄 page.tsx
│   │   │   │   │   ├── 📁 refer
│   │   │   │   │   │   └── 📄 page.tsx
│   │   │   │   │   ├── 📁 settings
│   │   │   │   │   │   ├── 📄 AppearanceSection.tsx
│   │   │   │   │   │   ├── 📄 EmailOtpSection.tsx
│   │   │   │   │   │   ├── 📄 LanguageSection.tsx
│   │   │   │   │   │   ├── 📄 SettingsContent.tsx
│   │   │   │   │   │   ├── 📄 SettingsDialog.tsx
│   │   │   │   │   │   ├── 📄 SettingsPageContent.tsx
│   │   │   │   │   │   ├── 📄 TeamSection.tsx
│   │   │   │   │   │   └── 📄 page.tsx
│   │   │   │   │   ├── 📁 shared
│   │   │   │   │   │   ├── 📁 [conversationId]
│   │   │   │   │   │   │   ├── 📄 SharedConversationReader.tsx
│   │   │   │   │   │   │   └── 📄 page.tsx
│   │   │   │   │   │   ├── 📁 activity
│   │   │   │   │   │   │   ├── 📄 ConversationActivity.tsx
│   │   │   │   │   │   │   └── 📄 page.tsx
│   │   │   │   │   │   ├── 📄 SharedConversationList.tsx
│   │   │   │   │   │   ├── 📄 SharedEmptyState.tsx
│   │   │   │   │   │   ├── 📄 SharedTabs.tsx
│   │   │   │   │   │   └── 📄 page.tsx
│   │   │   │   │   ├── 📄 AiAutomationStatusBanner.tsx
│   │   │   │   │   ├── 📄 AppAlertBanner.tsx
│   │   │   │   │   ├── 📄 DesktopMailIndicators.test.ts
│   │   │   │   │   ├── 📄 DesktopMailIndicators.tsx
│   │   │   │   │   ├── 📄 DesktopMailboxOpeningToast.test.tsx
│   │   │   │   │   ├── 📄 DesktopMailboxOpeningToast.tsx
│   │   │   │   │   ├── 📄 DesktopUpdateToast.tsx
│   │   │   │   │   ├── 📄 ErrorMessages.tsx
│   │   │   │   │   ├── 📄 ProviderRateLimitBanner.tsx
│   │   │   │   │   ├── 📄 error.tsx
│   │   │   │   │   ├── 📄 layout.tsx
│   │   │   │   │   └── 📄 sentry-identify.tsx
│   │   │   │   ├── 📁 (landing)
│   │   │   │   │   ├── 📁 app
│   │   │   │   │   │   ├── 📄 StoreBadges.tsx
│   │   │   │   │   │   └── 📄 page.tsx
│   │   │   │   │   ├── 📁 app-review
│   │   │   │   │   │   └── 📁 sign-in
│   │   │   │   │   │       ├── 📄 ReviewSignInForm.tsx
│   │   │   │   │   │       └── 📄 page.tsx
│   │   │   │   │   ├── 📁 brand
│   │   │   │   │   │   ├── 📄 CopyButton.tsx
│   │   │   │   │   │   └── 📄 page.tsx
│   │   │   │   │   ├── 📁 components
│   │   │   │   │   │   ├── 📁 chat
│   │   │   │   │   │   │   └── 📄 page.tsx
│   │   │   │   │   │   ├── 📁 onboarding
│   │   │   │   │   │   │   └── 📄 page.tsx
│   │   │   │   │   │   ├── 📁 slack
│   │   │   │   │   │   │   └── 📄 page.tsx
│   │   │   │   │   │   ├── 📁 tools
│   │   │   │   │   │   │   └── 📄 page.tsx
│   │   │   │   │   │   ├── 📄 TestAction.tsx
│   │   │   │   │   │   ├── 📄 TestError.tsx
│   │   │   │   │   │   ├── 📄 layout.tsx
│   │   │   │   │   │   ├── 📄 page.tsx
│   │   │   │   │   │   └── 📄 test-action.ts
│   │   │   │   │   ├── 📁 connect-mailbox
│   │   │   │   │   │   ├── 📄 layout.tsx
│   │   │   │   │   │   └── 📄 page.tsx
│   │   │   │   │   ├── 📁 home
│   │   │   │   │   │   ├── 📄 FAQs.tsx
│   │   │   │   │   │   ├── 📄 FinalCTA.tsx
│   │   │   │   │   │   ├── 📄 Footer.tsx
│   │   │   │   │   │   ├── 📄 Hero.tsx
│   │   │   │   │   │   ├── 📄 HeroVideoDialog.tsx
│   │   │   │   │   │   ├── 📄 HomePage.tsx
│   │   │   │   │   │   ├── 📄 SquaresPattern.tsx
│   │   │   │   │   │   ├── 📄 home-metadata.ts
│   │   │   │   │   │   └── 📄 page.tsx
│   │   │   │   │   ├── 📁 l
│   │   │   │   │   │   └── 📁 [locale]
│   │   │   │   │   │       ├── 📁 pricing
│   │   │   │   │   │       │   └── 📄 page.tsx
│   │   │   │   │   │       ├── 📄 layout.tsx
│   │   │   │   │   │       └── 📄 page.tsx
│   │   │   │   │   ├── 📁 login
│   │   │   │   │   │   ├── 📁 app-sign-in-error
│   │   │   │   │   │   │   └── 📄 page.tsx
│   │   │   │   │   │   ├── 📁 desktop-update-required
│   │   │   │   │   │   │   └── 📄 page.tsx
│   │   │   │   │   │   ├── 📁 email
│   │   │   │   │   │   │   ├── 📄 EmailOtpForm.tsx
│   │   │   │   │   │   │   └── 📄 page.tsx
│   │   │   │   │   │   ├── 📁 error
│   │   │   │   │   │   │   └── 📄 page.tsx
│   │   │   │   │   │   ├── 📁 microsoft-admin-consent
│   │   │   │   │   │   │   └── 📄 page.tsx
│   │   │   │   │   │   ├── 📁 options
│   │   │   │   │   │   │   └── 📄 page.tsx
│   │   │   │   │   │   ├── 📁 sso
│   │   │   │   │   │   │   └── 📄 page.tsx
│   │   │   │   │   │   ├── 📄 LoginForm.test.tsx
│   │   │   │   │   │   ├── 📄 LoginForm.tsx
│   │   │   │   │   │   ├── 📄 messages.ts
│   │   │   │   │   │   └── 📄 page.tsx
│   │   │   │   │   ├── 📁 logout
│   │   │   │   │   │   └── 📄 page.tsx
│   │   │   │   │   ├── 📁 mcp
│   │   │   │   │   │   ├── 📁 consent
│   │   │   │   │   │   │   ├── 📄 McpConsent.tsx
│   │   │   │   │   │   │   ├── 📄 page.test.tsx
│   │   │   │   │   │   │   └── 📄 page.tsx
│   │   │   │   │   │   └── 📁 login
│   │   │   │   │   │       └── 📄 page.tsx
│   │   │   │   │   ├── 📁 oss-friends
│   │   │   │   │   │   └── 📄 page.tsx
│   │   │   │   │   ├── 📁 pricing
│   │   │   │   │   │   ├── 📄 PricingComparisonTable.tsx
│   │   │   │   │   │   ├── 📄 PricingFAQs.tsx
│   │   │   │   │   │   ├── 📄 PricingPage.tsx
│   │   │   │   │   │   ├── 📄 page.tsx
│   │   │   │   │   │   └── 📄 pricing-metadata.ts
│   │   │   │   │   ├── 📁 thank-you
│   │   │   │   │   │   └── 📄 page.tsx
│   │   │   │   │   ├── 📁 welcome
│   │   │   │   │   │   ├── 📄 form.tsx
│   │   │   │   │   │   ├── 📄 page.tsx
│   │   │   │   │   │   ├── 📄 survey.ts
│   │   │   │   │   │   └── 📄 utms.tsx
│   │   │   │   │   ├── 📁 welcome-redirect
│   │   │   │   │   │   ├── 📄 page.test.ts
│   │   │   │   │   │   └── 📄 page.tsx
│   │   │   │   │   ├── 📁 welcome-upgrade
│   │   │   │   │   │   ├── 📄 ContinueWithEmailClient.tsx
│   │   │   │   │   │   ├── 📄 Testimonial.tsx
│   │   │   │   │   │   ├── 📄 WelcomeUpgradeHeader.tsx
│   │   │   │   │   │   ├── 📄 WelcomeUpgradeNav.tsx
│   │   │   │   │   │   ├── 📄 WelcomeUpgradePricing.tsx
│   │   │   │   │   │   ├── 📄 layout.tsx
│   │   │   │   │   │   ├── 📄 page.test.tsx
│   │   │   │   │   │   └── 📄 page.tsx
│   │   │   │   │   ├── 📄 error.tsx
│   │   │   │   │   ├── 📄 layout.tsx
│   │   │   │   │   └── 📄 page.tsx
│   │   │   │   ├── 📁 (marketing)
│   │   │   │   ├── 📁 (redirects)
│   │   │   │   │   ├── 📁 assistant
│   │   │   │   │   │   └── 📄 page.tsx
│   │   │   │   │   ├── 📁 automation
│   │   │   │   │   │   └── 📄 page.tsx
│   │   │   │   │   ├── 📁 briefs
│   │   │   │   │   │   └── 📄 page.tsx
│   │   │   │   │   ├── 📁 bulk-archive
│   │   │   │   │   │   └── 📄 page.tsx
│   │   │   │   │   ├── 📁 bulk-unsubscribe
│   │   │   │   │   │   └── 📄 page.tsx
│   │   │   │   │   ├── 📁 calendars
│   │   │   │   │   │   └── 📄 page.tsx
│   │   │   │   │   ├── 📁 channels
│   │   │   │   │   │   └── 📄 page.tsx
│   │   │   │   │   ├── 📁 clean
│   │   │   │   │   │   └── 📄 page.tsx
│   │   │   │   │   ├── 📁 cold-email-blocker
│   │   │   │   │   │   └── 📄 page.tsx
│   │   │   │   │   ├── 📁 debug
│   │   │   │   │   │   └── 📄 page.tsx
│   │   │   │   │   ├── 📁 drive
│   │   │   │   │   │   └── 📄 page.tsx
│   │   │   │   │   ├── 📁 integrations
│   │   │   │   │   │   └── 📄 page.tsx
│   │   │   │   │   ├── 📁 mail
│   │   │   │   │   │   └── 📄 page.tsx
│   │   │   │   │   ├── 📁 meetings
│   │   │   │   │   │   └── 📄 page.tsx
│   │   │   │   │   ├── 📁 onboarding
│   │   │   │   │   │   └── 📄 page.tsx
│   │   │   │   │   ├── 📁 onboarding-brief
│   │   │   │   │   │   └── 📄 page.tsx
│   │   │   │   │   ├── 📁 quick-bulk-archive
│   │   │   │   │   │   └── 📄 page.tsx
│   │   │   │   │   ├── 📁 setup
│   │   │   │   │   │   └── 📄 page.tsx
│   │   │   │   │   ├── 📁 smart-categories
│   │   │   │   │   │   └── 📄 page.tsx
│   │   │   │   │   └── 📁 stats
│   │   │   │   │       └── 📄 page.tsx
│   │   │   │   ├── 📁 .well-known
│   │   │   │   │   ├── 📁 apple-app-site-association
│   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   ├── 📁 assetlinks.json
│   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   ├── 📁 oauth-authorization-server
│   │   │   │   │   │   ├── 📁 api
│   │   │   │   │   │   │   └── 📁 auth
│   │   │   │   │   │   │       └── 📄 route.ts
│   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   ├── 📁 oauth-protected-resource
│   │   │   │   │   │   ├── 📁 mcp
│   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   └── 📁 openapi.json
│   │   │   │   │       └── 📄 route.ts
│   │   │   │   ├── 📁 api
│   │   │   │   │   ├── 📁 admin
│   │   │   │   │   │   └── 📁 top-spenders
│   │   │   │   │   │       ├── 📄 route.test.ts
│   │   │   │   │   │       └── 📄 route.ts
│   │   │   │   │   ├── 📁 ai
│   │   │   │   │   │   ├── 📁 analyze-sender-pattern
│   │   │   │   │   │   │   ├── 📄 route.test.ts
│   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   ├── 📁 compose-autocomplete
│   │   │   │   │   │   │   ├── 📄 route.ts
│   │   │   │   │   │   │   └── 📄 validation.ts
│   │   │   │   │   │   ├── 📁 digest
│   │   │   │   │   │   │   ├── 📁 queue
│   │   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   │   ├── 📄 route.test.ts
│   │   │   │   │   │   │   ├── 📄 route.ts
│   │   │   │   │   │   │   ├── 📄 upsert-digest.test.ts
│   │   │   │   │   │   │   ├── 📄 upsert-digest.ts
│   │   │   │   │   │   │   └── 📄 validation.ts
│   │   │   │   │   │   ├── 📁 models
│   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   ├── 📁 summarise
│   │   │   │   │   │   │   ├── 📄 controller.ts
│   │   │   │   │   │   │   ├── 📄 route.ts
│   │   │   │   │   │   │   └── 📄 validation.ts
│   │   │   │   │   │   └── 📁 translate
│   │   │   │   │   │       ├── 📄 route.ts
│   │   │   │   │   │       ├── 📄 validation.test.ts
│   │   │   │   │   │       └── 📄 validation.ts
│   │   │   │   │   ├── 📁 apple
│   │   │   │   │   │   ├── 📁 subscription
│   │   │   │   │   │   │   └── 📁 sync
│   │   │   │   │   │   │       └── 📄 route.ts
│   │   │   │   │   │   └── 📁 webhook
│   │   │   │   │   │       ├── 📄 route.test.ts
│   │   │   │   │   │       └── 📄 route.ts
│   │   │   │   │   ├── 📁 auth
│   │   │   │   │   │   └── 📁 [...all]
│   │   │   │   │   │       └── 📄 route.ts
│   │   │   │   │   ├── 📁 automation-jobs
│   │   │   │   │   │   └── 📁 execute
│   │   │   │   │   │       ├── 📁 queue
│   │   │   │   │   │       │   ├── 📄 route.test.ts
│   │   │   │   │   │       │   └── 📄 route.ts
│   │   │   │   │   │       └── 📄 route.ts
│   │   │   │   │   ├── 📁 bulk-inbox-action
│   │   │   │   │   │   └── 📁 process
│   │   │   │   │   │       ├── 📁 queue
│   │   │   │   │   │       │   └── 📄 route.ts
│   │   │   │   │   │       ├── 📄 route.ts
│   │   │   │   │   │       └── 📄 validation.ts
│   │   │   │   │   ├── 📁 chat
│   │   │   │   │   │   ├── 📁 [id]
│   │   │   │   │   │   │   ├── 📁 stop
│   │   │   │   │   │   │   │   ├── 📄 route.test.ts
│   │   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   │   └── 📁 stream
│   │   │   │   │   │   │       ├── 📄 route.test.ts
│   │   │   │   │   │   │       └── 📄 route.ts
│   │   │   │   │   │   ├── 📁 confirm-email-action
│   │   │   │   │   │   │   ├── 📄 route.test.ts
│   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   ├── 📄 chat-message-persistence.test.ts
│   │   │   │   │   │   ├── 📄 chat-message-persistence.ts
│   │   │   │   │   │   ├── 📄 route.test.ts
│   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   ├── 📁 chats
│   │   │   │   │   │   ├── 📁 [chatId]
│   │   │   │   │   │   │   ├── 📄 route.test.ts
│   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   ├── 📁 clean
│   │   │   │   │   │   ├── 📁 gmail
│   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   ├── 📁 history
│   │   │   │   │   │   │   ├── 📄 route.test.ts
│   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   ├── 📄 controller.ts
│   │   │   │   │   │   ├── 📄 route.test.ts
│   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   ├── 📁 cron
│   │   │   │   │   │   ├── 📁 automation-jobs
│   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   ├── 📁 draft-cleanup
│   │   │   │   │   │   │   ├── 📁 account
│   │   │   │   │   │   │   │   ├── 📁 queue
│   │   │   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   │   │   ├── 📄 route.ts
│   │   │   │   │   │   │   │   └── 📄 validation.ts
│   │   │   │   │   │   │   ├── 📄 route.test.ts
│   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   ├── 📁 email-send-operation-retention
│   │   │   │   │   │   │   ├── 📄 route.test.ts
│   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   ├── 📁 mobile-push-retention
│   │   │   │   │   │   │   ├── 📄 route.test.ts
│   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   ├── 📁 reasoning-retention
│   │   │   │   │   │   │   ├── 📄 route.test.ts
│   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   └── 📁 scheduled-actions
│   │   │   │   │   │       └── 📄 route.ts
│   │   │   │   │   ├── 📁 deployment
│   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   ├── 📁 digest-preview
│   │   │   │   │   │   ├── 📄 route.ts
│   │   │   │   │   │   └── 📄 validation.ts
│   │   │   │   │   ├── 📁 email
│   │   │   │   │   │   └── 📁 render-html
│   │   │   │   │   │       └── 📄 route.ts
│   │   │   │   │   ├── 📁 email-send-operations
│   │   │   │   │   │   └── 📁 [mutationId]
│   │   │   │   │   │       ├── 📄 route.test.ts
│   │   │   │   │   │       └── 📄 route.ts
│   │   │   │   │   ├── 📁 email-stream
│   │   │   │   │   │   ├── 📄 route.test.ts
│   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   ├── 📁 follow-up-reminders
│   │   │   │   │   │   ├── 📁 account
│   │   │   │   │   │   │   ├── 📁 queue
│   │   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   ├── 📁 google
│   │   │   │   │   │   ├── 📁 calendar
│   │   │   │   │   │   │   ├── 📁 auth-url
│   │   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   │   └── 📁 callback
│   │   │   │   │   │   │       └── 📄 route.ts
│   │   │   │   │   │   ├── 📁 drive
│   │   │   │   │   │   │   ├── 📁 auth-url
│   │   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   │   └── 📁 callback
│   │   │   │   │   │   │       └── 📄 route.ts
│   │   │   │   │   │   ├── 📁 linking
│   │   │   │   │   │   │   ├── 📁 auth-url
│   │   │   │   │   │   │   │   ├── 📄 route.test.ts
│   │   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   │   └── 📁 callback
│   │   │   │   │   │   │       ├── 📄 route.test.ts
│   │   │   │   │   │   │       └── 📄 route.ts
│   │   │   │   │   │   └── 📁 webhook
│   │   │   │   │   │       ├── 📄 route.test.ts
│   │   │   │   │   │       └── 📄 route.ts
│   │   │   │   │   ├── 📁 health
│   │   │   │   │   │   ├── 📄 route.test.ts
│   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   ├── 📁 image-proxy
│   │   │   │   │   │   ├── 📄 route.test.ts
│   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   ├── 📁 knowledge
│   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   ├── 📁 labels
│   │   │   │   │   │   ├── 📁 counts
│   │   │   │   │   │   │   ├── 📄 route.test.ts
│   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   ├── 📁 create
│   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   ├── 📁 lemon-squeezy
│   │   │   │   │   │   └── 📁 webhook
│   │   │   │   │   │       ├── 📄 route.ts
│   │   │   │   │   │       └── 📄 types.ts
│   │   │   │   │   ├── 📁 loops
│   │   │   │   │   │   └── 📁 webhook
│   │   │   │   │   │       ├── 📄 email-source.test.ts
│   │   │   │   │   │       ├── 📄 email-source.ts
│   │   │   │   │   │       ├── 📄 route.test.ts
│   │   │   │   │   │       └── 📄 route.ts
│   │   │   │   │   ├── 📁 mail
│   │   │   │   │   │   ├── 📁 settings
│   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   └── 📁 v1
│   │   │   │   │   │       ├── 📁 accounts
│   │   │   │   │   │       │   └── 📁 [accountId]
│   │   │   │   │   │       │       ├── 📁 assistant-state
│   │   │   │   │   │       │       │   └── 📄 route.ts
│   │   │   │   │   │       │       ├── 📁 attachment-content
│   │   │   │   │   │       │       │   ├── 📄 route.test.ts
│   │   │   │   │   │       │       │   └── 📄 route.ts
│   │   │   │   │   │       │       ├── 📁 bootstrap
│   │   │   │   │   │       │       │   └── 📄 route.ts
│   │   │   │   │   │       │       ├── 📁 capabilities
│   │   │   │   │   │       │       │   └── 📄 route.ts
│   │   │   │   │   │       │       ├── 📁 changes
│   │   │   │   │   │       │       │   ├── 📁 batch
│   │   │   │   │   │       │       │   │   ├── 📄 route.test.ts
│   │   │   │   │   │       │       │   │   └── 📄 route.ts
│   │   │   │   │   │       │       │   └── 📄 route.ts
│   │   │   │   │   │       │       ├── 📁 conversation-membership
│   │   │   │   │   │       │       │   └── 📄 route.ts
│   │   │   │   │   │       │       ├── 📁 enumeration
│   │   │   │   │   │       │       │   ├── 📄 route.test.ts
│   │   │   │   │   │       │       │   └── 📄 route.ts
│   │   │   │   │   │       │       ├── 📁 hydration
│   │   │   │   │   │       │       │   └── 📄 route.ts
│   │   │   │   │   │       │       ├── 📁 operations
│   │   │   │   │   │       │       │   └── 📁 [commandId]
│   │   │   │   │   │       │       │       └── 📄 route.ts
│   │   │   │   │   │       │       ├── 📁 scopes
│   │   │   │   │   │       │       │   └── 📄 route.ts
│   │   │   │   │   │       │       ├── 📁 search
│   │   │   │   │   │       │       │   └── 📄 route.ts
│   │   │   │   │   │       │       └── 📁 splits
│   │   │   │   │   │       │           ├── 📁 [splitId]
│   │   │   │   │   │       │           │   └── 📄 route.ts
│   │   │   │   │   │       │           ├── 📁 presets
│   │   │   │   │   │       │           │   └── 📄 route.ts
│   │   │   │   │   │       │           ├── 📁 reorder
│   │   │   │   │   │       │           │   └── 📄 route.ts
│   │   │   │   │   │       │           ├── 📄 route.test.ts
│   │   │   │   │   │       │           └── 📄 route.ts
│   │   │   │   │   │       └── 📁 devices
│   │   │   │   │   │           ├── 📄 route.test.ts
│   │   │   │   │   │           └── 📄 route.ts
│   │   │   │   │   ├── 📁 mail-stream
│   │   │   │   │   │   ├── 📄 route.test.ts
│   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   ├── 📁 mcp
│   │   │   │   │   │   ├── 📁 [integration]
│   │   │   │   │   │   │   ├── 📁 arg-options
│   │   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   │   ├── 📁 auth-url
│   │   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   │   ├── 📁 callback
│   │   │   │   │   │   │   │   ├── 📄 route.test.ts
│   │   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   │   └── 📁 provider-callback
│   │   │   │   │   │   │       ├── 📄 route.test.ts
│   │   │   │   │   │   │       └── 📄 route.ts
│   │   │   │   │   │   └── 📁 integrations
│   │   │   │   │   │       └── 📄 route.ts
│   │   │   │   │   ├── 📁 mcp-server
│   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   ├── 📁 meeting-briefs
│   │   │   │   │   │   ├── 📄 route.test.ts
│   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   ├── 📁 meeting-recorder
│   │   │   │   │   │   ├── 📁 process
│   │   │   │   │   │   │   ├── 📁 queue
│   │   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   │   ├── 📄 route.ts
│   │   │   │   │   │   │   └── 📄 validation.ts
│   │   │   │   │   │   ├── 📁 schedule
│   │   │   │   │   │   │   ├── 📄 route.test.ts
│   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   └── 📁 transcript
│   │   │   │   │   │       ├── 📁 queue
│   │   │   │   │   │       │   └── 📄 route.ts
│   │   │   │   │   │       ├── 📄 route.test.ts
│   │   │   │   │   │       ├── 📄 route.ts
│   │   │   │   │   │       └── 📄 validation.ts
│   │   │   │   │   ├── 📁 messages
│   │   │   │   │   │   ├── 📁 attachment
│   │   │   │   │   │   │   ├── 📄 route.test.ts
│   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   ├── 📁 batch
│   │   │   │   │   │   │   ├── 📄 route.test.ts
│   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   ├── 📁 calendar-invitation
│   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   ├── 📁 forward
│   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   ├── 📁 send
│   │   │   │   │   │   │   ├── 📄 route.test.ts
│   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   ├── 📁 source
│   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   ├── 📄 route.ts
│   │   │   │   │   │   └── 📄 validation.ts
│   │   │   │   │   ├── 📁 mobile
│   │   │   │   │   │   ├── 📁 all-inboxes
│   │   │   │   │   │   │   ├── 📁 archive
│   │   │   │   │   │   │   │   ├── 📄 route.test.ts
│   │   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   │   ├── 📄 route.test.ts
│   │   │   │   │   │   │   ├── 📄 route.ts
│   │   │   │   │   │   │   ├── 📄 summary.test.ts
│   │   │   │   │   │   │   └── 📄 summary.ts
│   │   │   │   │   │   ├── 📁 mailbox-sync
│   │   │   │   │   │   │   ├── 📄 route.test.ts
│   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   ├── 📁 otps
│   │   │   │   │   │   │   ├── 📄 route.ts
│   │   │   │   │   │   │   ├── 📄 summary.test.ts
│   │   │   │   │   │   │   └── 📄 summary.ts
│   │   │   │   │   │   ├── 📁 push
│   │   │   │   │   │   │   └── 📁 test
│   │   │   │   │   │   │       ├── 📁 trigger
│   │   │   │   │   │   │       │   ├── 📄 route.test.ts
│   │   │   │   │   │   │       │   └── 📄 route.ts
│   │   │   │   │   │   │       └── 📄 route.ts
│   │   │   │   │   │   ├── 📁 push-token
│   │   │   │   │   │   │   ├── 📄 route.test.ts
│   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   ├── 📁 rules
│   │   │   │   │   │   │   ├── 📁 [id]
│   │   │   │   │   │   │   │   ├── 📁 toggle
│   │   │   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   └── 📁 threads
│   │   │   │   │   │       └── 📁 batch
│   │   │   │   │   │           ├── 📄 route.test.ts
│   │   │   │   │   │           └── 📄 route.ts
│   │   │   │   │   ├── 📁 mobile-auth
│   │   │   │   │   │   ├── 📁 browser-start
│   │   │   │   │   │   │   ├── 📄 route.test.ts
│   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   ├── 📁 callback
│   │   │   │   │   │   │   ├── 📄 route.test.ts
│   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   ├── 📁 exchange-code
│   │   │   │   │   │   │   ├── 📄 route.test.ts
│   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   └── 📁 start
│   │   │   │   │   │       ├── 📄 route.test.ts
│   │   │   │   │   │       └── 📄 route.ts
│   │   │   │   │   ├── 📁 mobile-review
│   │   │   │   │   │   ├── 📁 sign-in
│   │   │   │   │   │   │   ├── 📄 route.test.ts
│   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   ├── 📁 status
│   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   └── 📝 README.md
│   │   │   │   │   ├── 📁 organizations
│   │   │   │   │   │   └── 📁 [organizationId]
│   │   │   │   │   │       ├── 📁 executed-rules-count
│   │   │   │   │   │       │   └── 📄 route.ts
│   │   │   │   │   │       ├── 📁 members
│   │   │   │   │   │       │   └── 📄 route.ts
│   │   │   │   │   │       ├── 📁 rules
│   │   │   │   │   │       │   └── 📄 route.ts
│   │   │   │   │   │       ├── 📁 stats
│   │   │   │   │   │       │   ├── 📁 email-buckets
│   │   │   │   │   │       │   │   └── 📄 route.ts
│   │   │   │   │   │       │   ├── 📁 rules-buckets
│   │   │   │   │   │       │   │   └── 📄 route.ts
│   │   │   │   │   │       │   ├── 📁 totals
│   │   │   │   │   │       │   │   └── 📄 route.ts
│   │   │   │   │   │       │   ├── 📄 types.ts
│   │   │   │   │   │       │   └── 📄 utils.ts
│   │   │   │   │   │       └── 📄 route.ts
│   │   │   │   │   ├── 📁 outlook
│   │   │   │   │   │   ├── 📁 admin-consent
│   │   │   │   │   │   │   ├── 📁 callback
│   │   │   │   │   │   │   │   ├── 📄 route.test.ts
│   │   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   ├── 📁 calendar
│   │   │   │   │   │   │   ├── 📁 auth-url
│   │   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   │   └── 📁 callback
│   │   │   │   │   │   │       └── 📄 route.ts
│   │   │   │   │   │   ├── 📁 drive
│   │   │   │   │   │   │   ├── 📁 auth-url
│   │   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   │   └── 📁 callback
│   │   │   │   │   │   │       └── 📄 route.ts
│   │   │   │   │   │   ├── 📁 linking
│   │   │   │   │   │   │   ├── 📁 auth-url
│   │   │   │   │   │   │   │   ├── 📄 route.test.ts
│   │   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   │   └── 📁 callback
│   │   │   │   │   │   │       ├── 📄 route.test.ts
│   │   │   │   │   │   │       └── 📄 route.ts
│   │   │   │   │   │   ├── 📁 watch
│   │   │   │   │   │   │   ├── 📁 all
│   │   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   └── 📁 webhook
│   │   │   │   │   │       ├── 📄 process-lifecycle.test.ts
│   │   │   │   │   │       ├── 📄 process-lifecycle.ts
│   │   │   │   │   │       ├── 📄 route.test.ts
│   │   │   │   │   │       └── 📄 route.ts
│   │   │   │   │   ├── 📁 public
│   │   │   │   │   │   ├── 📁 booking-links
│   │   │   │   │   │   │   └── 📁 [slug]
│   │   │   │   │   │   │       ├── 📁 availability
│   │   │   │   │   │   │       │   ├── 📄 route.test.ts
│   │   │   │   │   │   │       │   └── 📄 route.ts
│   │   │   │   │   │   │       └── 📄 route.ts
│   │   │   │   │   │   └── 📁 bookings
│   │   │   │   │   │       ├── 📁 [id]
│   │   │   │   │   │       │   ├── 📁 cancel
│   │   │   │   │   │       │   │   └── 📄 route.ts
│   │   │   │   │   │       │   └── 📁 reschedule
│   │   │   │   │   │       │       ├── 📄 route.test.ts
│   │   │   │   │   │       │       └── 📄 route.ts
│   │   │   │   │   │       └── 📄 route.ts
│   │   │   │   │   ├── 📁 recall
│   │   │   │   │   │   └── 📁 webhook
│   │   │   │   │   │       ├── 📄 route.test.ts
│   │   │   │   │   │       └── 📄 route.ts
│   │   │   │   │   ├── 📁 referrals
│   │   │   │   │   │   ├── 📁 code
│   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   └── 📁 stats
│   │   │   │   │   │       └── 📄 route.ts
│   │   │   │   │   ├── 📁 reply-tracker
│   │   │   │   │   │   └── 📁 disable-unused-auto-draft
│   │   │   │   │   │       ├── 📄 disable-unused-auto-drafts.test.ts
│   │   │   │   │   │       ├── 📄 disable-unused-auto-drafts.ts
│   │   │   │   │   │       └── 📄 route.ts
│   │   │   │   │   ├── 📁 resend
│   │   │   │   │   │   ├── 📁 digest
│   │   │   │   │   │   │   ├── 📁 all
│   │   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   │   ├── 📁 queue
│   │   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   │   ├── 📄 route.ts
│   │   │   │   │   │   │   └── 📄 validation.ts
│   │   │   │   │   │   ├── 📁 inbox-health
│   │   │   │   │   │   │   ├── 📁 all
│   │   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   │   ├── 📁 queue
│   │   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   │   ├── 📄 helpers.test.ts
│   │   │   │   │   │   │   ├── 📄 helpers.ts
│   │   │   │   │   │   │   ├── 📄 route.test.ts
│   │   │   │   │   │   │   ├── 📄 route.ts
│   │   │   │   │   │   │   └── 📄 validation.ts
│   │   │   │   │   │   └── 📁 summary
│   │   │   │   │   │       ├── 📁 all
│   │   │   │   │   │       │   └── 📄 route.ts
│   │   │   │   │   │       ├── 📁 queue
│   │   │   │   │   │       │   └── 📄 route.ts
│   │   │   │   │   │       ├── 📄 archived-emails.test.ts
│   │   │   │   │   │       ├── 📄 archived-emails.ts
│   │   │   │   │   │       ├── 📄 route.test.ts
│   │   │   │   │   │       ├── 📄 route.ts
│   │   │   │   │   │       └── 📄 validation.ts
│   │   │   │   │   ├── 📁 scheduled-actions
│   │   │   │   │   │   └── 📁 execute
│   │   │   │   │   │       └── 📄 route.ts
│   │   │   │   │   ├── 📁 scheduled-emails
│   │   │   │   │   │   └── 📁 execute
│   │   │   │   │   │       └── 📄 route.ts
│   │   │   │   │   ├── 📁 slack
│   │   │   │   │   │   ├── 📁 auth-url
│   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   ├── 📁 callback
│   │   │   │   │   │   │   ├── 📄 route.test.ts
│   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   ├── 📁 commands
│   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   └── 📁 events
│   │   │   │   │   │       ├── 📄 route.test.ts
│   │   │   │   │   │       └── 📄 route.ts
│   │   │   │   │   ├── 📁 snoozed-threads
│   │   │   │   │   │   └── 📁 execute
│   │   │   │   │   │       └── 📄 route.ts
│   │   │   │   │   ├── 📁 sso
│   │   │   │   │   │   └── 📁 signin
│   │   │   │   │   │       ├── 📄 route.test.ts
│   │   │   │   │   │       └── 📄 route.ts
│   │   │   │   │   ├── 📁 stripe
│   │   │   │   │   │   ├── 📁 invoice-email
│   │   │   │   │   │   │   ├── 📁 queue
│   │   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   ├── 📁 success
│   │   │   │   │   │   │   ├── 📄 route.test.ts
│   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   └── 📁 webhook
│   │   │   │   │   │       ├── 📄 cancellation-initiated.ts
│   │   │   │   │   │       ├── 📄 controller.ts
│   │   │   │   │   │       ├── 📄 route-handler.test.ts
│   │   │   │   │   │       ├── 📄 route.test.ts
│   │   │   │   │   │       ├── 📄 route.ts
│   │   │   │   │   │       ├── 📄 trial-conversion.test.ts
│   │   │   │   │   │       └── 📄 trial-conversion.ts
│   │   │   │   │   ├── 📁 team-comments
│   │   │   │   │   │   ├── 📁 activity
│   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   ├── 📁 conversations
│   │   │   │   │   │   │   ├── 📁 [conversationId]
│   │   │   │   │   │   │   │   ├── 📁 attachments
│   │   │   │   │   │   │   │   │   └── 📁 [attachmentRef]
│   │   │   │   │   │   │   │   │       ├── 📄 route.test.ts
│   │   │   │   │   │   │   │   │       └── 📄 route.ts
│   │   │   │   │   │   │   │   ├── 📁 comments
│   │   │   │   │   │   │   │   │   ├── 📁 [commentId]
│   │   │   │   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   │   │   ├── 📁 messages
│   │   │   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   │   │   ├── 📁 mute
│   │   │   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   │   │   ├── 📁 participants
│   │   │   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   │   │   ├── 📁 read
│   │   │   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   │   ├── 📄 rest-mutations.test.ts
│   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   ├── 📁 stream
│   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   └── 📁 unread-count
│   │   │   │   │   │       └── 📄 route.ts
│   │   │   │   │   ├── 📁 teams
│   │   │   │   │   │   └── 📁 events
│   │   │   │   │   │       ├── 📄 route.test.ts
│   │   │   │   │   │       └── 📄 route.ts
│   │   │   │   │   ├── 📁 telegram
│   │   │   │   │   │   └── 📁 events
│   │   │   │   │   │       └── 📄 route.ts
│   │   │   │   │   ├── 📁 threads
│   │   │   │   │   │   ├── 📁 [id]
│   │   │   │   │   │   │   ├── 📁 archive
│   │   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   │   ├── 📁 trash
│   │   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   │   ├── 📁 unarchive
│   │   │   │   │   │   │   │   ├── 📄 route.test.ts
│   │   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   │   ├── 📁 untrash
│   │   │   │   │   │   │   │   ├── 📄 route.test.ts
│   │   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   │   ├── 📄 route.test.ts
│   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   ├── 📁 all
│   │   │   │   │   │   │   ├── 📄 route.test.ts
│   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   ├── 📁 basic
│   │   │   │   │   │   │   ├── 📄 route.test.ts
│   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   ├── 📁 batch
│   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   ├── 📄 route.test.ts
│   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   ├── 📁 unsubscribe
│   │   │   │   │   │   ├── 📄 route.test.ts
│   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   ├── 📁 user
│   │   │   │   │   │   ├── 📁 account
│   │   │   │   │   │   │   ├── 📄 route.test.ts
│   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   ├── 📁 ai-automation-status
│   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   ├── 📁 api-keys
│   │   │   │   │   │   │   ├── 📄 route.test.ts
│   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   ├── 📁 automation-jobs
│   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   ├── 📁 availability
│   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   ├── 📁 booking-links
│   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   ├── 📁 bulk-inbox-action
│   │   │   │   │   │   │   └── 📁 [jobId]
│   │   │   │   │   │   │       └── 📄 route.ts
│   │   │   │   │   │   ├── 📁 calendar
│   │   │   │   │   │   │   └── 📁 upcoming-events
│   │   │   │   │   │   │       └── 📄 route.ts
│   │   │   │   │   │   ├── 📁 calendars
│   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   ├── 📁 categories
│   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   ├── 📁 categorize
│   │   │   │   │   │   │   └── 📁 senders
│   │   │   │   │   │   │       ├── 📁 batch
│   │   │   │   │   │   │       │   ├── 📁 simple
│   │   │   │   │   │   │       │   │   └── 📄 route.ts
│   │   │   │   │   │   │       │   ├── 📄 handle-batch.test.ts
│   │   │   │   │   │   │       │   ├── 📄 handle-batch.ts
│   │   │   │   │   │   │       │   └── 📄 route.ts
│   │   │   │   │   │   │       ├── 📁 categorized
│   │   │   │   │   │   │       │   └── 📄 route.ts
│   │   │   │   │   │   │       ├── 📁 progress
│   │   │   │   │   │   │       │   └── 📄 route.ts
│   │   │   │   │   │   │       ├── 📁 uncategorized
│   │   │   │   │   │   │       │   └── 📄 route.ts
│   │   │   │   │   │   │       └── 📄 types.ts
│   │   │   │   │   │   ├── 📁 cold-email
│   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   ├── 📁 complete-registration
│   │   │   │   │   │   │   ├── 📄 route.test.ts
│   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   ├── 📁 contacts
│   │   │   │   │   │   │   ├── 📁 photos
│   │   │   │   │   │   │   │   ├── 📄 route.test.ts
│   │   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   │   ├── 📄 route.test.ts
│   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   ├── 📁 debug
│   │   │   │   │   │   │   ├── 📁 follow-up
│   │   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   │   ├── 📁 memories
│   │   │   │   │   │   │   │   ├── 📄 route.test.ts
│   │   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   │   └── 📁 rules
│   │   │   │   │   │   │       └── 📄 route.ts
│   │   │   │   │   │   ├── 📁 digest-schedule
│   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   ├── 📁 digest-status
│   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   ├── 📁 draft-actions
│   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   ├── 📁 draft-cleanup-settings
│   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   ├── 📁 drafts
│   │   │   │   │   │   │   ├── 📁 [draftId]
│   │   │   │   │   │   │   │   ├── 📁 attachments
│   │   │   │   │   │   │   │   │   ├── 📁 [attachmentId]
│   │   │   │   │   │   │   │   │   │   ├── 📄 route.test.ts
│   │   │   │   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   │   │   │   ├── 📁 uploads
│   │   │   │   │   │   │   │   │   │   ├── 📁 [uploadId]
│   │   │   │   │   │   │   │   │   │   │   ├── 📄 route.test.ts
│   │   │   │   │   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   │   │   │   │   ├── 📄 route.test.ts
│   │   │   │   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   │   │   ├── 📄 route.test.ts
│   │   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   │   ├── 📄 route.test.ts
│   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   ├── 📁 drive
│   │   │   │   │   │   │   ├── 📁 connections
│   │   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   │   ├── 📁 filings
│   │   │   │   │   │   │   │   ├── 📄 route.test.ts
│   │   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   │   ├── 📁 folders
│   │   │   │   │   │   │   │   ├── 📁 [folderId]
│   │   │   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   │   ├── 📁 preview
│   │   │   │   │   │   │   │   ├── 📁 attachments
│   │   │   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   │   └── 📁 source-items
│   │   │   │   │   │   │       ├── 📁 [folderId]
│   │   │   │   │   │   │       │   └── 📄 route.ts
│   │   │   │   │   │   │       └── 📄 route.ts
│   │   │   │   │   │   ├── 📁 email-account
│   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   ├── 📁 email-accounts
│   │   │   │   │   │   │   ├── 📁 [emailAccountId]
│   │   │   │   │   │   │   │   ├── 📄 route.test.ts
│   │   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   ├── 📁 email-otp
│   │   │   │   │   │   │   ├── 📄 route.test.ts
│   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   ├── 📁 error-messages
│   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   ├── 📁 executed-rules
│   │   │   │   │   │   │   ├── 📁 batch
│   │   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   │   └── 📁 history
│   │   │   │   │   │   │       └── 📄 route.ts
│   │   │   │   │   │   ├── 📁 folders
│   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   ├── 📁 group
│   │   │   │   │   │   │   ├── 📁 [groupId]
│   │   │   │   │   │   │   │   ├── 📁 items
│   │   │   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   │   │   └── 📁 rules
│   │   │   │   │   │   │   │       └── 📄 route.ts
│   │   │   │   │   │   │   ├── 📄 route.test.ts
│   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   ├── 📁 labels
│   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   ├── 📁 mail-splits
│   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   ├── 📁 me
│   │   │   │   │   │   │   ├── 📄 route.test.ts
│   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   ├── 📁 meeting-briefs
│   │   │   │   │   │   │   ├── 📁 history
│   │   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   ├── 📁 meeting-recorder
│   │   │   │   │   │   │   ├── 📁 meetings
│   │   │   │   │   │   │   │   ├── 📁 [meetingId]
│   │   │   │   │   │   │   │   │   ├── 📁 draft
│   │   │   │   │   │   │   │   │   │   ├── 📄 route.test.ts
│   │   │   │   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   │   │   ├── 📄 route.test.ts
│   │   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   │   ├── 📁 upcoming
│   │   │   │   │   │   │   │   ├── 📄 route.test.ts
│   │   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   ├── 📁 messaging-channels
│   │   │   │   │   │   │   ├── 📁 [channelId]
│   │   │   │   │   │   │   │   └── 📁 targets
│   │   │   │   │   │   │   │       ├── 📄 route.test.ts
│   │   │   │   │   │   │   │       └── 📄 route.ts
│   │   │   │   │   │   │   ├── 📄 route.test.ts
│   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   ├── 📁 onboarding
│   │   │   │   │   │   │   └── 📁 processed-emails
│   │   │   │   │   │   │       ├── 📄 route.test.ts
│   │   │   │   │   │   │       └── 📄 route.ts
│   │   │   │   │   │   ├── 📁 organization-membership
│   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   ├── 📁 persona
│   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   ├── 📁 public-contact-context
│   │   │   │   │   │   │   └── 📁 [messageId]
│   │   │   │   │   │   │       ├── 📄 route.test.ts
│   │   │   │   │   │   │       └── 📄 route.ts
│   │   │   │   │   │   ├── 📁 rules
│   │   │   │   │   │   │   ├── 📁 [id]
│   │   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   │   ├── 📄 route.test.ts
│   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   ├── 📁 schedule
│   │   │   │   │   │   │   └── 📁 [id]
│   │   │   │   │   │   │       └── 📄 route.ts
│   │   │   │   │   │   ├── 📁 scheduled-emails
│   │   │   │   │   │   │   ├── 📁 [id]
│   │   │   │   │   │   │   │   ├── 📁 reminder
│   │   │   │   │   │   │   │   │   ├── 📄 route.test.ts
│   │   │   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   │   │   ├── 📁 retry
│   │   │   │   │   │   │   │   │   ├── 📄 route.test.ts
│   │   │   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   │   │   ├── 📄 route.test.ts
│   │   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   │   ├── 📄 route.test.ts
│   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   ├── 📁 send-as
│   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   ├── 📁 senders
│   │   │   │   │   │   │   ├── 📁 bulk
│   │   │   │   │   │   │   │   ├── 📄 route.test.ts
│   │   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   │   ├── 📁 status
│   │   │   │   │   │   │   │   ├── 📄 route.test.ts
│   │   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   │   └── 📁 unsubscribe
│   │   │   │   │   │   │       ├── 📄 route.test.ts
│   │   │   │   │   │   │       └── 📄 route.ts
│   │   │   │   │   │   ├── 📁 sent-message-opens
│   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   ├── 📁 settings
│   │   │   │   │   │   │   └── 📁 multi-account
│   │   │   │   │   │   │       ├── 📄 route.ts
│   │   │   │   │   │   │       └── 📄 validation.ts
│   │   │   │   │   │   ├── 📁 setup-progress
│   │   │   │   │   │   │   ├── 📄 route.test.ts
│   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   ├── 📁 signature
│   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   ├── 📁 signature-suggestions
│   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   ├── 📁 snippets
│   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   ├── 📁 snoozed-threads
│   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   ├── 📁 stats
│   │   │   │   │   │   │   ├── 📁 by-period
│   │   │   │   │   │   │   │   ├── 📄 controller.test.ts
│   │   │   │   │   │   │   │   ├── 📄 controller.ts
│   │   │   │   │   │   │   │   ├── 📄 route.ts
│   │   │   │   │   │   │   │   └── 📄 validation.ts
│   │   │   │   │   │   │   ├── 📁 email-actions
│   │   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   │   ├── 📁 load
│   │   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   │   ├── 📁 newsletters
│   │   │   │   │   │   │   │   ├── 📁 summary
│   │   │   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   │   │   ├── 📄 route.test.ts
│   │   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   │   ├── 📁 recipients
│   │   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   │   ├── 📁 response-time
│   │   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   │   ├── 📁 rule-stats
│   │   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   │   ├── 📁 sender-emails
│   │   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   │   ├── 📁 senders
│   │   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   │   └── 📄 helpers.ts
│   │   │   │   │   │   ├── 📁 thread-plans
│   │   │   │   │   │   │   ├── 📄 route.test.ts
│   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   └── 📁 trial-preview
│   │   │   │   │   │       ├── 📄 route.test.ts
│   │   │   │   │   │       └── 📄 route.ts
│   │   │   │   │   ├── 📁 v1
│   │   │   │   │   │   ├── 📁 [...path]
│   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   ├── 📁 openapi
│   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   ├── 📁 openapi.json
│   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   ├── 📁 rules
│   │   │   │   │   │   │   ├── 📁 [id]
│   │   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   │   ├── 📄 request.ts
│   │   │   │   │   │   │   ├── 📄 route.ts
│   │   │   │   │   │   │   ├── 📄 serializers.ts
│   │   │   │   │   │   │   ├── 📄 validation.test.ts
│   │   │   │   │   │   │   └── 📄 validation.ts
│   │   │   │   │   │   ├── 📁 senders
│   │   │   │   │   │   │   └── 📁 unsubscribe
│   │   │   │   │   │   │       ├── 📄 route.ts
│   │   │   │   │   │   │       └── 📄 validation.ts
│   │   │   │   │   │   ├── 📁 stats
│   │   │   │   │   │   │   ├── 📁 by-period
│   │   │   │   │   │   │   │   ├── 📄 route.ts
│   │   │   │   │   │   │   │   └── 📄 validation.ts
│   │   │   │   │   │   │   └── 📁 response-time
│   │   │   │   │   │   │       ├── 📄 route.ts
│   │   │   │   │   │   │       └── 📄 validation.ts
│   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   ├── 📁 voice
│   │   │   │   │   │   ├── 📁 live
│   │   │   │   │   │   │   └── 📁 session
│   │   │   │   │   │   │       └── 📄 route.ts
│   │   │   │   │   │   ├── 📁 speak
│   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   ├── 📁 status
│   │   │   │   │   │   │   └── 📄 route.ts
│   │   │   │   │   │   └── 📁 transcribe
│   │   │   │   │   │       └── 📄 route.ts
│   │   │   │   │   └── 📁 watch
│   │   │   │   │       ├── 📁 all
│   │   │   │   │       │   └── 📄 route.ts
│   │   │   │   │       ├── 📁 unwatch
│   │   │   │   │       │   └── 📄 route.ts
│   │   │   │   │       └── 📄 route.ts
│   │   │   │   ├── 📁 auth-callback
│   │   │   │   │   ├── 📄 AuthCallbackHandoff.tsx
│   │   │   │   │   └── 📄 page.tsx
│   │   │   │   ├── 📁 book
│   │   │   │   │   ├── 📁 [slug]
│   │   │   │   │   │   ├── 📄 BookingPageClient.tsx
│   │   │   │   │   │   ├── 📄 BookingSidebar.tsx
│   │   │   │   │   │   ├── 📄 PickTimeStep.tsx
│   │   │   │   │   │   ├── 📄 booking-helpers.test.ts
│   │   │   │   │   │   ├── 📄 booking-helpers.ts
│   │   │   │   │   │   ├── 📄 metadata.test.ts
│   │   │   │   │   │   ├── 📄 metadata.ts
│   │   │   │   │   │   ├── 📄 opengraph-image.test.tsx
│   │   │   │   │   │   ├── 📄 opengraph-image.tsx
│   │   │   │   │   │   ├── 📄 page.tsx
│   │   │   │   │   │   ├── 📄 twitter-image.tsx
│   │   │   │   │   │   └── 📄 useAvailability.ts
│   │   │   │   │   ├── 📁 cancel
│   │   │   │   │   │   └── 📁 [id]
│   │   │   │   │   │       ├── 📄 CancelBookingClient.tsx
│   │   │   │   │   │       └── 📄 page.tsx
│   │   │   │   │   └── 📁 reschedule
│   │   │   │   │       └── 📁 [id]
│   │   │   │   │           ├── 📄 RescheduleBookingClient.tsx
│   │   │   │   │           └── 📄 page.tsx
│   │   │   │   ├── 📁 llms.txt
│   │   │   │   │   └── 📄 route.ts
│   │   │   │   ├── 📁 mcp
│   │   │   │   │   └── 📄 route.ts
│   │   │   │   ├── 📁 openapi.json
│   │   │   │   │   └── 📄 route.ts
│   │   │   │   ├── 📁 organizations
│   │   │   │   │   └── 📁 invitations
│   │   │   │   │       └── 📁 [invitationId]
│   │   │   │   │           └── 📁 accept
│   │   │   │   │               ├── 📄 AcceptInvitation.test.tsx
│   │   │   │   │               ├── 📄 AcceptInvitation.tsx
│   │   │   │   │               ├── 📄 page.test.tsx
│   │   │   │   │               └── 📄 page.tsx
│   │   │   │   ├── 📁 t
│   │   │   │   │   └── 📁 [token]
│   │   │   │   │       └── 📄 route.ts
│   │   │   │   ├── 📄 global-error.tsx
│   │   │   │   ├── 🖼️ icon.png
│   │   │   │   ├── 📄 layout.tsx
│   │   │   │   ├── 📄 manifest.ts
│   │   │   │   ├── 📄 not-found.tsx
│   │   │   │   ├── 🖼️ opengraph-image.jpg
│   │   │   │   ├── 📄 robots.test.ts
│   │   │   │   ├── 📄 robots.ts
│   │   │   │   ├── 📄 startup-image.ts
│   │   │   │   ├── 📄 sw.ts
│   │   │   │   └── 📄 utm.tsx
│   │   │   ├── 📁 components
│   │   │   │   ├── 📁 ai-elements
│   │   │   │   │   ├── 📄 code-block.tsx
│   │   │   │   │   ├── 📄 conversation.tsx
│   │   │   │   │   ├── 📄 loader.tsx
│   │   │   │   │   ├── 📄 message.tsx
│   │   │   │   │   ├── 📄 prompt-input.tsx
│   │   │   │   │   ├── 📄 reasoning.tsx
│   │   │   │   │   ├── 📄 response.tsx
│   │   │   │   │   ├── 📄 shimmer.tsx
│   │   │   │   │   ├── 📄 suggestion.tsx
│   │   │   │   │   └── 📄 tool.tsx
│   │   │   │   ├── 📁 assistant-chat
│   │   │   │   │   ├── 📄 ChatHistoryItem.test.tsx
│   │   │   │   │   ├── 📄 ChatHistoryItem.tsx
│   │   │   │   │   ├── 📄 DeleteChatDialog.tsx
│   │   │   │   │   ├── 📄 RenameChatDialog.tsx
│   │   │   │   │   ├── 📄 assistant-inline-email-response.test.tsx
│   │   │   │   │   ├── 📄 assistant-inline-email-response.tsx
│   │   │   │   │   ├── 📄 assistant-tag-normalization.test.ts
│   │   │   │   │   ├── 📄 assistant-tag-normalization.ts
│   │   │   │   │   ├── 📄 bulk-inbox-action-card.test.tsx
│   │   │   │   │   ├── 📄 bulk-inbox-action-card.tsx
│   │   │   │   │   ├── 📄 chat-history-types.ts
│   │   │   │   │   ├── 📄 chat.test.tsx
│   │   │   │   │   ├── 📄 chat.tsx
│   │   │   │   │   ├── 📄 email-lookup-context.test.ts
│   │   │   │   │   ├── 📄 email-lookup-context.tsx
│   │   │   │   │   ├── 📄 examples-dialog.tsx
│   │   │   │   │   ├── 📄 helpers.test.ts
│   │   │   │   │   ├── 📄 helpers.ts
│   │   │   │   │   ├── 📄 inline-email-action-context.tsx
│   │   │   │   │   ├── 📄 inline-email-card.test.tsx
│   │   │   │   │   ├── 📄 inline-email-card.tsx
│   │   │   │   │   ├── 📄 inline-rule-suggestion-card.tsx
│   │   │   │   │   ├── 📄 message-part.tsx
│   │   │   │   │   ├── 📄 messages.tsx
│   │   │   │   │   ├── 📄 messaging-channel-hint.tsx
│   │   │   │   │   ├── 📄 overview.tsx
│   │   │   │   │   ├── 📄 preview-attachment.tsx
│   │   │   │   │   ├── 📄 rule-summary-card.tsx
│   │   │   │   │   ├── 📄 tool-label.test.ts
│   │   │   │   │   ├── 📄 tool-label.ts
│   │   │   │   │   ├── 📄 tools.search-inbox-result.test.tsx
│   │   │   │   │   ├── 📄 tools.test.ts
│   │   │   │   │   ├── 📄 tools.tsx
│   │   │   │   │   └── 📄 types.ts
│   │   │   │   ├── 📁 bulk-archive
│   │   │   │   │   └── 📄 categoryIcons.ts
│   │   │   │   ├── 📁 charts
│   │   │   │   │   ├── 📄 DomainIcon.tsx
│   │   │   │   │   └── 📄 HorizontalBarChart.tsx
│   │   │   │   ├── 📁 drive
│   │   │   │   │   ├── 📄 FilingStatusCell.tsx
│   │   │   │   │   └── 📄 YesNoIndicator.tsx
│   │   │   │   ├── 📁 editor
│   │   │   │   │   ├── 📁 extensions
│   │   │   │   │   │   ├── 📄 LabelMention.tsx
│   │   │   │   │   │   └── 📄 MentionList.tsx
│   │   │   │   │   ├── 🎨 SimpleRichTextEditor.css
│   │   │   │   │   ├── 📄 SimpleRichTextEditor.tsx
│   │   │   │   │   ├── 📄 Tiptap.tsx
│   │   │   │   │   └── 📄 extensions.ts
│   │   │   │   ├── 📁 email-list
│   │   │   │   │   ├── 📄 AttachmentPreview.tsx
│   │   │   │   │   ├── 📄 CalendarInvitation.tsx
│   │   │   │   │   ├── 📄 EmailAttachments.tsx
│   │   │   │   │   ├── 📄 EmailContents.test.tsx
│   │   │   │   │   ├── 📄 EmailContents.tsx
│   │   │   │   │   ├── 📄 EmailDate.tsx
│   │   │   │   │   ├── 📄 EmailDetails.tsx
│   │   │   │   │   ├── 📄 EmailMessage.test.tsx
│   │   │   │   │   ├── 📄 EmailMessage.tsx
│   │   │   │   │   ├── 📄 EmailThread.test.tsx
│   │   │   │   │   ├── 📄 EmailThread.tsx
│   │   │   │   │   ├── 📄 OpenedConversationAttachments.tsx
│   │   │   │   │   ├── 📄 SentMessageOpenStatus.test.tsx
│   │   │   │   │   ├── 📄 SentMessageOpenStatus.tsx
│   │   │   │   │   ├── 📄 ThreadDeliveryStatus.test.tsx
│   │   │   │   │   ├── 📄 ThreadDeliveryStatus.tsx
│   │   │   │   │   ├── 📄 attachment-file-type.ts
│   │   │   │   │   ├── 📄 latest-scheduled-send.test.ts
│   │   │   │   │   ├── 📄 latest-scheduled-send.ts
│   │   │   │   │   └── 📄 types.ts
│   │   │   │   ├── 📁 feature-announcements
│   │   │   │   │   ├── 📄 AnnouncementDialog.tsx
│   │   │   │   │   ├── 📄 AnnouncementDialogDemo.tsx
│   │   │   │   │   ├── 📄 AnnouncementVideo.tsx
│   │   │   │   │   ├── 📄 FollowUpRemindersIllustration.tsx
│   │   │   │   │   └── 📄 MeetingBriefsIllustration.tsx
│   │   │   │   ├── 📁 kibo-ui
│   │   │   │   │   └── 📁 tree
│   │   │   │   │       └── 📄 index.tsx
│   │   │   │   ├── 📁 layouts
│   │   │   │   │   ├── 📄 BasicLayout.tsx
│   │   │   │   │   ├── 📄 BasicLayoutShell.tsx
│   │   │   │   │   ├── 📄 BlogLayout.tsx
│   │   │   │   │   └── 📄 ClientBasicLayout.tsx
│   │   │   │   ├── 📁 messaging
│   │   │   │   │   └── 📄 DeliveryChannelsSetting.tsx
│   │   │   │   ├── 📁 new-landing
│   │   │   │   │   ├── 📁 common
│   │   │   │   │   │   ├── 📄 Anchor.tsx
│   │   │   │   │   │   ├── 📄 Badge.tsx
│   │   │   │   │   │   ├── 📄 BlurFade.tsx
│   │   │   │   │   │   ├── 📄 Button.tsx
│   │   │   │   │   │   ├── 📄 Card.tsx
│   │   │   │   │   │   ├── 📄 CardWrapper.tsx
│   │   │   │   │   │   ├── 📄 DisplayCard.tsx
│   │   │   │   │   │   ├── 📄 HeroReveal.tsx
│   │   │   │   │   │   ├── 📄 Logo.tsx
│   │   │   │   │   │   ├── 📄 Section.tsx
│   │   │   │   │   │   ├── 📄 SectionLink.tsx
│   │   │   │   │   │   ├── 📄 Typography.tsx
│   │   │   │   │   │   └── 📄 WordReveal.tsx
│   │   │   │   │   ├── 📁 icons
│   │   │   │   │   │   ├── 📄 Analytics.tsx
│   │   │   │   │   │   ├── 📄 Apple.tsx
│   │   │   │   │   │   ├── 📄 AutoOrganize.tsx
│   │   │   │   │   │   ├── 📄 Bell.tsx
│   │   │   │   │   │   ├── 📄 Briefcase.tsx
│   │   │   │   │   │   ├── 📄 Calendar.tsx
│   │   │   │   │   │   ├── 📄 Chat.tsx
│   │   │   │   │   │   ├── 📄 ChatTwo.tsx
│   │   │   │   │   │   ├── 📄 Check.tsx
│   │   │   │   │   │   ├── 📄 Connect.tsx
│   │   │   │   │   │   ├── 📄 Envelope.tsx
│   │   │   │   │   │   ├── 📄 Fire.tsx
│   │   │   │   │   │   ├── 📄 Gmail.tsx
│   │   │   │   │   │   ├── 📄 Link.tsx
│   │   │   │   │   │   ├── 📄 Mail.tsx
│   │   │   │   │   │   ├── 📄 Megaphone.tsx
│   │   │   │   │   │   ├── 📄 Newsletter.tsx
│   │   │   │   │   │   ├── 📄 Outlook.tsx
│   │   │   │   │   │   ├── 📄 Play.tsx
│   │   │   │   │   │   ├── 📄 SnowFlake.tsx
│   │   │   │   │   │   ├── 📄 Sparkle.tsx
│   │   │   │   │   │   ├── 📄 SparkleBlue.tsx
│   │   │   │   │   │   ├── 📄 Team.tsx
│   │   │   │   │   │   └── 📄 Zap.tsx
│   │   │   │   │   ├── 📁 sections
│   │   │   │   │   │   ├── 📄 Awards.tsx
│   │   │   │   │   │   ├── 📄 BulkUnsubscribe.tsx
│   │   │   │   │   │   ├── 📄 EmailClient.tsx
│   │   │   │   │   │   ├── 📄 EverythingElseSection.tsx
│   │   │   │   │   │   ├── 📄 Footer.tsx
│   │   │   │   │   │   ├── 📄 Header.tsx
│   │   │   │   │   │   ├── 📄 ManageFromAnywhere.tsx
│   │   │   │   │   │   ├── 📄 OrganizedInbox.tsx
│   │   │   │   │   │   ├── 📄 PreWrittenDrafts.tsx
│   │   │   │   │   │   ├── 📄 Pricing.tsx
│   │   │   │   │   │   ├── 📄 StartedInMinutes.tsx
│   │   │   │   │   │   └── 📄 Testimonials.tsx
│   │   │   │   │   ├── 📄 BrandScroller.tsx
│   │   │   │   │   ├── 📄 CallToAction.tsx
│   │   │   │   │   ├── 📄 DesktopDownloadCta.tsx
│   │   │   │   │   ├── 📄 FooterLineLogo.tsx
│   │   │   │   │   ├── 📄 HeaderLinks.tsx
│   │   │   │   │   ├── 📄 LandingLink.tsx
│   │   │   │   │   ├── 📄 LanguageSwitcher.tsx
│   │   │   │   │   ├── 📄 LiquidGlassButton.tsx
│   │   │   │   │   ├── 📄 PatternBanner.tsx
│   │   │   │   │   └── 📄 UnicornScene.tsx
│   │   │   │   ├── 📁 sidebar-cards
│   │   │   │   │   ├── 📄 SidebarCardStack.test.tsx
│   │   │   │   │   ├── 📄 SidebarCardStack.tsx
│   │   │   │   │   ├── 📄 SidebarCards.tsx
│   │   │   │   │   └── 📄 useSignatureSidebarCard.tsx
│   │   │   │   ├── 📁 snippets
│   │   │   │   │   ├── 📄 SnippetForm.tsx
│   │   │   │   │   ├── 📄 SnippetPicker.tsx
│   │   │   │   │   └── 📄 SnippetsManager.tsx
│   │   │   │   ├── 📁 team-comments
│   │   │   │   │   ├── 📄 CommentComposer.test.tsx
│   │   │   │   │   ├── 📄 CommentComposer.tsx
│   │   │   │   │   ├── 📄 ConversationDiscussion.tsx
│   │   │   │   │   ├── 📄 ConversationParticipants.tsx
│   │   │   │   │   ├── 📄 PublisherDiscussion.tsx
│   │   │   │   │   ├── 📄 ShareConversationDialog.tsx
│   │   │   │   │   ├── 📄 use-conversation-discussion.ts
│   │   │   │   │   ├── 📄 use-team-comments-available.ts
│   │   │   │   │   └── 📄 use-team-nav.ts
│   │   │   │   ├── 📁 ui
│   │   │   │   │   ├── 📄 alert-dialog.tsx
│   │   │   │   │   ├── 📄 alert.tsx
│   │   │   │   │   ├── 📄 avatar.tsx
│   │   │   │   │   ├── 📄 badge.tsx
│   │   │   │   │   ├── 📄 button.tsx
│   │   │   │   │   ├── 📄 calendar.tsx
│   │   │   │   │   ├── 📄 card.tsx
│   │   │   │   │   ├── 📄 chart.test.ts
│   │   │   │   │   ├── 📄 chart.tsx
│   │   │   │   │   ├── 📄 checkbox.tsx
│   │   │   │   │   ├── 📄 collapsible.tsx
│   │   │   │   │   ├── 📄 command.tsx
│   │   │   │   │   ├── 📄 context-menu.tsx
│   │   │   │   │   ├── 📄 dialog.tsx
│   │   │   │   │   ├── 📄 dropdown-menu.tsx
│   │   │   │   │   ├── 📄 empty.tsx
│   │   │   │   │   ├── 📄 form.tsx
│   │   │   │   │   ├── 📄 hover-card.tsx
│   │   │   │   │   ├── 📄 input.tsx
│   │   │   │   │   ├── 📄 item.tsx
│   │   │   │   │   ├── 📄 label.tsx
│   │   │   │   │   ├── 📄 navigation-menu.tsx
│   │   │   │   │   ├── 📄 pagination.tsx
│   │   │   │   │   ├── 📄 popover.tsx
│   │   │   │   │   ├── 📄 progress.tsx
│   │   │   │   │   ├── 📄 resizable.tsx
│   │   │   │   │   ├── 📄 scroll-area.tsx
│   │   │   │   │   ├── 📄 select.tsx
│   │   │   │   │   ├── 📄 separator.tsx
│   │   │   │   │   ├── 📄 sheet.tsx
│   │   │   │   │   ├── 📄 sidebar.test.tsx
│   │   │   │   │   ├── 📄 sidebar.tsx
│   │   │   │   │   ├── 📄 skeleton.tsx
│   │   │   │   │   ├── 📄 switch.tsx
│   │   │   │   │   ├── 📄 table.tsx
│   │   │   │   │   ├── 📄 tabs.tsx
│   │   │   │   │   ├── 📄 textarea.tsx
│   │   │   │   │   └── 📄 tooltip.tsx
│   │   │   │   ├── 📁 voice
│   │   │   │   │   ├── 📄 AudioLevelBars.tsx
│   │   │   │   │   ├── 📄 VoiceInput.tsx
│   │   │   │   │   └── 📄 VoiceOverlay.tsx
│   │   │   │   ├── 📄 AccessDenied.tsx
│   │   │   │   ├── 📄 AccountCommandList.tsx
│   │   │   │   ├── 📄 AccountSwitcher.tsx
│   │   │   │   ├── 📄 Alert.tsx
│   │   │   │   ├── 📄 AppErrorBoundary.test.tsx
│   │   │   │   ├── 📄 AppErrorBoundary.tsx
│   │   │   │   ├── 📄 AppSidebarHeader.tsx
│   │   │   │   ├── 📄 Badge.tsx
│   │   │   │   ├── 📄 BrandIcons.tsx
│   │   │   │   ├── 📄 BulkArchiveCards.test.tsx
│   │   │   │   ├── 📄 BulkArchiveCards.tsx
│   │   │   │   ├── 📄 Button.tsx
│   │   │   │   ├── 📄 ButtonCheckbox.tsx
│   │   │   │   ├── 📄 ButtonList.tsx
│   │   │   │   ├── 📄 ButtonListSurvey.tsx
│   │   │   │   ├── 📄 CategorySelect.tsx
│   │   │   │   ├── 📄 Checkbox.tsx
│   │   │   │   ├── 📄 ClientOnly.tsx
│   │   │   │   ├── 📄 Combobox.tsx
│   │   │   │   ├── 📄 CommandK.test.tsx
│   │   │   │   ├── 📄 CommandK.tsx
│   │   │   │   ├── 📄 Confetti.tsx
│   │   │   │   ├── 📄 ConfirmDialog.tsx
│   │   │   │   ├── 📄 Container.tsx
│   │   │   │   ├── 📄 ConversionAnalytics.tsx
│   │   │   │   ├── 📄 CookieConsent.tsx
│   │   │   │   ├── 📄 CopyInput.tsx
│   │   │   │   ├── 📄 CrispChat.tsx
│   │   │   │   ├── 📄 DatePickerWithRange.tsx
│   │   │   │   ├── 📄 DelayInputControls.tsx
│   │   │   │   ├── 📄 DesktopUpdateMenuItem.test.tsx
│   │   │   │   ├── 📄 DesktopUpdateMenuItem.tsx
│   │   │   │   ├── 📄 EmailCell.tsx
│   │   │   │   ├── 📄 EmailMessageCell.tsx
│   │   │   │   ├── 📄 EmailMessageCellActions.test.ts
│   │   │   │   ├── 📄 EmailMessageCellActions.ts
│   │   │   │   ├── 📄 EmailMessageCellLabels.test.ts
│   │   │   │   ├── 📄 EmailMessageCellLabels.ts
│   │   │   │   ├── 📄 EmailStatsPreloader.tsx
│   │   │   │   ├── 📄 EmailViewer.tsx
│   │   │   │   ├── 📄 EnableFeatureCard.tsx
│   │   │   │   ├── 📄 EndTrialButton.tsx
│   │   │   │   ├── 📄 ErrorBoundary.tsx
│   │   │   │   ├── 📄 ErrorDisplay.tsx
│   │   │   │   ├── 📄 ErrorPage.tsx
│   │   │   │   ├── 📄 ExpandableText.tsx
│   │   │   │   ├── 📄 FeatureIcon.tsx
│   │   │   │   ├── 📄 FeedbackDialog.tsx
│   │   │   │   ├── 📄 FolderSelector.tsx
│   │   │   │   ├── 📄 Form.tsx
│   │   │   │   ├── 📄 GroupedTable.tsx
│   │   │   │   ├── 📄 HoverCard.tsx
│   │   │   │   ├── 📄 InlineActionButton.tsx
│   │   │   │   ├── 📄 Input.tsx
│   │   │   │   ├── 📄 InviteMemberModal.tsx
│   │   │   │   ├── 📄 Kbd.tsx
│   │   │   │   ├── 📄 LabelBadges.tsx
│   │   │   │   ├── 📄 LabelCombobox.tsx
│   │   │   │   ├── 📄 LabelsSubMenu.tsx
│   │   │   │   ├── 📄 LandingErrorBoundary.tsx
│   │   │   │   ├── 📄 LazyMuxVideo.tsx
│   │   │   │   ├── 📄 List.tsx
│   │   │   │   ├── 📄 ListCard.tsx
│   │   │   │   ├── 📄 Loading.tsx
│   │   │   │   ├── 📄 LoadingContent.test.tsx
│   │   │   │   ├── 📄 LoadingContent.tsx
│   │   │   │   ├── 📄 Logo.tsx
│   │   │   │   ├── 📄 MultiSelectFilter.tsx
│   │   │   │   ├── 📄 MuxVideo.tsx
│   │   │   │   ├── 📄 NavUser.tsx
│   │   │   │   ├── 📄 Notice.tsx
│   │   │   │   ├── 📄 OnboardingModal.tsx
│   │   │   │   ├── 📄 PageHeader.tsx
│   │   │   │   ├── 📄 PageHeaderVideoButton.tsx
│   │   │   │   ├── 📄 PageWrapper.tsx
│   │   │   │   ├── 📄 PanelResizeHandle.test.tsx
│   │   │   │   ├── 📄 PanelResizeHandle.tsx
│   │   │   │   ├── 📄 PermissionsConsent.tsx
│   │   │   │   ├── 📄 PersonWithLogo.tsx
│   │   │   │   ├── 📄 PlanBadge.tsx
│   │   │   │   ├── 📄 PremiumAlert.test.tsx
│   │   │   │   ├── 📄 PremiumAlert.tsx
│   │   │   │   ├── 📄 PremiumCard.tsx
│   │   │   │   ├── 📄 ProfileImage.tsx
│   │   │   │   ├── 📄 ProgressPanel.tsx
│   │   │   │   ├── 📄 RadioCardGroup.tsx
│   │   │   │   ├── 📄 ReferralDialog.tsx
│   │   │   │   ├── 📄 RuleActions.tsx
│   │   │   │   ├── 📄 ScrollableFadeContainer.tsx
│   │   │   │   ├── 📄 SearchForm.tsx
│   │   │   │   ├── 📄 Select.tsx
│   │   │   │   ├── 📄 SenderIcon.test.tsx
│   │   │   │   ├── 📄 SenderIcon.tsx
│   │   │   │   ├── 📄 SettingCard.tsx
│   │   │   │   ├── 📄 SettingsSection.tsx
│   │   │   │   ├── 📄 SetupCard.tsx
│   │   │   │   ├── 📄 SetupProgressCard.tsx
│   │   │   │   ├── 📄 ShortcutTooltipContent.tsx
│   │   │   │   ├── 📄 SideNav.tsx
│   │   │   │   ├── 📄 SideNavMenu.tsx
│   │   │   │   ├── 📄 SideNavWithTopNav.tsx
│   │   │   │   ├── 📄 SidebarRight.tsx
│   │   │   │   ├── 📄 SlackNotificationTargetSelect.tsx
│   │   │   │   ├── 📄 StatsCards.tsx
│   │   │   │   ├── 📄 TabSelect.tsx
│   │   │   │   ├── 📄 TablePagination.tsx
│   │   │   │   ├── 📄 TabsToolbar.tsx
│   │   │   │   ├── 📄 TagInput.tsx
│   │   │   │   ├── 📄 TimePicker.tsx
│   │   │   │   ├── 📄 TimezoneDetector.test.ts
│   │   │   │   ├── 📄 TimezoneDetector.tsx
│   │   │   │   ├── 📄 TimezoneDetector.utils.ts
│   │   │   │   ├── 📄 Toast.tsx
│   │   │   │   ├── 📄 Toast.undo.test.ts
│   │   │   │   ├── 📄 Toggle.tsx
│   │   │   │   ├── 📄 Tooltip.tsx
│   │   │   │   ├── 📄 TooltipExplanation.tsx
│   │   │   │   ├── 📄 TopBar.tsx
│   │   │   │   ├── 📄 TopSection.tsx
│   │   │   │   ├── 📄 TruncatedTooltipText.tsx
│   │   │   │   ├── 📄 Typography.tsx
│   │   │   │   ├── 📄 UpgradeToPlusButton.tsx
│   │   │   │   ├── 📄 VideoCard.tsx
│   │   │   │   ├── 📄 VideoPlayerDialog.tsx
│   │   │   │   ├── 📄 ViewEmailButton.tsx
│   │   │   │   ├── 📄 WebhookDocumentation.tsx
│   │   │   │   ├── 📄 YouTubeVideo.tsx
│   │   │   │   ├── 📄 app-error-boundary-log-context.test.ts
│   │   │   │   ├── 📄 app-error-boundary-log-context.ts
│   │   │   │   ├── 📄 chat-sidebar-width.ts
│   │   │   │   └── 📄 theme-provider.tsx
│   │   │   ├── 📁 ee
│   │   │   │   ├── 📁 billing
│   │   │   │   │   ├── 📁 apple
│   │   │   │   │   │   ├── 📄 index.test.ts
│   │   │   │   │   │   ├── 📄 index.ts
│   │   │   │   │   │   ├── 📄 local-testing.ts
│   │   │   │   │   │   └── 📄 root-certificates.ts
│   │   │   │   │   ├── 📁 lemon
│   │   │   │   │   │   └── 📄 index.ts
│   │   │   │   │   └── 📁 stripe
│   │   │   │   │       ├── 📄 ai-overage.test.ts
│   │   │   │   │       ├── 📄 ai-overage.ts
│   │   │   │   │       ├── 📄 disputes.test.ts
│   │   │   │   │       ├── 📄 disputes.ts
│   │   │   │   │       ├── 📄 index.test.ts
│   │   │   │   │       ├── 📄 index.ts
│   │   │   │   │       ├── 📄 invoice-email.test.ts
│   │   │   │   │       ├── 📄 invoice-email.ts
│   │   │   │   │       ├── 📄 loops-events.test.ts
│   │   │   │   │       ├── 📄 loops-events.ts
│   │   │   │   │       ├── 📄 payments.test.ts
│   │   │   │   │       ├── 📄 payments.ts
│   │   │   │   │       ├── 📄 posthog-events.test.ts
│   │   │   │   │       ├── 📄 posthog-events.ts
│   │   │   │   │       ├── 📄 refunds.test.ts
│   │   │   │   │       ├── 📄 refunds.ts
│   │   │   │   │       ├── 📄 sync-stripe.test.ts
│   │   │   │   │       └── 📄 sync-stripe.ts
│   │   │   │   └── 📝 LICENSE.md
│   │   │   ├── 📁 hooks
│   │   │   │   ├── 📄 use-mobile.tsx
│   │   │   │   ├── 📄 useAccounts.ts
│   │   │   │   ├── 📄 useActionTiming.ts
│   │   │   │   ├── 📄 useAdminTopSpenders.ts
│   │   │   │   ├── 📄 useAiAutomationStatus.ts
│   │   │   │   ├── 📄 useAnalytics.test.ts
│   │   │   │   ├── 📄 useAnalytics.ts
│   │   │   │   ├── 📄 useApiKeys.ts
│   │   │   │   ├── 📄 useAutomationJob.ts
│   │   │   │   ├── 📄 useBeforeUnload.ts
│   │   │   │   ├── 📄 useBookingLinks.ts
│   │   │   │   ├── 📄 useBulkInboxActionJob.ts
│   │   │   │   ├── 📄 useCalendarUpcomingEvents.tsx
│   │   │   │   ├── 📄 useCalendars.ts
│   │   │   │   ├── 📄 useChatMessages.ts
│   │   │   │   ├── 📄 useChats.ts
│   │   │   │   ├── 📄 useCommandPaletteCommands.ts
│   │   │   │   ├── 📄 useContactPhoto.ts
│   │   │   │   ├── 📄 useCookieConsent.ts
│   │   │   │   ├── 📄 useCurrentOrganization.ts
│   │   │   │   ├── 📄 useDefaultAvailability.ts
│   │   │   │   ├── 📄 useDesktopUpdateStatus.ts
│   │   │   │   ├── 📄 useDialogState.ts
│   │   │   │   ├── 📄 useDisplayedEmail.ts
│   │   │   │   ├── 📄 useDraftSaveInFlight.ts
│   │   │   │   ├── 📄 useDriveConnections.ts
│   │   │   │   ├── 📄 useDriveFolders.ts
│   │   │   │   ├── 📄 useDriveSourceChildren.ts
│   │   │   │   ├── 📄 useDriveSourceItems.ts
│   │   │   │   ├── 📄 useDriveSubfolders.ts
│   │   │   │   ├── 📄 useEmailAccountFull.ts
│   │   │   │   ├── 📄 useExecutedRules.tsx
│   │   │   │   ├── 📄 useExecutedRulesCount.ts
│   │   │   │   ├── 📄 useFeatureFlags.ts
│   │   │   │   ├── 📄 useFilingActivity.ts
│   │   │   │   ├── 📄 useFilingPreviewAttachments.ts
│   │   │   │   ├── 📄 useFolders.ts
│   │   │   │   ├── 📄 useHiddenDraftMessageIds.ts
│   │   │   │   ├── 📄 useIntegrationArgOptions.ts
│   │   │   │   ├── 📄 useIntegrations.ts
│   │   │   │   ├── 📄 useIsOnline.ts
│   │   │   │   ├── 📄 useLabelCounts.ts
│   │   │   │   ├── 📄 useLabels.test.ts
│   │   │   │   ├── 📄 useLabels.ts
│   │   │   │   ├── 📄 useLocalReplyDraft.test.tsx
│   │   │   │   ├── 📄 useLocalReplyDraft.ts
│   │   │   │   ├── 📄 useMailSettings.test.tsx
│   │   │   │   ├── 📄 useMailSettings.ts
│   │   │   │   ├── 📄 useMeetingBriefs.ts
│   │   │   │   ├── 📄 useMeetingRecorder.ts
│   │   │   │   ├── 📄 useMessages.ts
│   │   │   │   ├── 📄 useMessagesBatch.ts
│   │   │   │   ├── 📄 useMessagingChannels.ts
│   │   │   │   ├── 📄 useModal.tsx
│   │   │   │   ├── 📄 useOrgAccess.ts
│   │   │   │   ├── 📄 useOrgSWR.ts
│   │   │   │   ├── 📄 useOrgStatsEmailBuckets.ts
│   │   │   │   ├── 📄 useOrgStatsRulesBuckets.ts
│   │   │   │   ├── 📄 useOrgStatsTotals.ts
│   │   │   │   ├── 📄 useOrganization.ts
│   │   │   │   ├── 📄 useOrganizationMembers.ts
│   │   │   │   ├── 📄 useOrganizationMembership.test.ts
│   │   │   │   ├── 📄 useOrganizationMembership.ts
│   │   │   │   ├── 📄 useOrganizationRules.ts
│   │   │   │   ├── 📄 usePersona.ts
│   │   │   │   ├── 📄 usePremium.test.ts
│   │   │   │   ├── 📄 usePremium.ts
│   │   │   │   ├── 📄 useProductAnalytics.ts
│   │   │   │   ├── 📄 useProviderDraftAutosave.test.ts
│   │   │   │   ├── 📄 useProviderDraftAutosave.ts
│   │   │   │   ├── 📄 useReplyDraftPersistence.test.tsx
│   │   │   │   ├── 📄 useReplyDraftPersistence.ts
│   │   │   │   ├── 📄 useReplyDrafts.test.tsx
│   │   │   │   ├── 📄 useReplyDrafts.ts
│   │   │   │   ├── 📄 useRule.tsx
│   │   │   │   ├── 📄 useRules.tsx
│   │   │   │   ├── 📄 useScheduledEmailActions.test.tsx
│   │   │   │   ├── 📄 useScheduledEmailActions.ts
│   │   │   │   ├── 📄 useSentMessageOpens.ts
│   │   │   │   ├── 📄 useSentWithSignatureToggle.ts
│   │   │   │   ├── 📄 useSettingsDialog.ts
│   │   │   │   ├── 📄 useSetupProgress.ts
│   │   │   │   ├── 📄 useSignupEvent.tsx
│   │   │   │   ├── 📄 useSlackConnect.ts
│   │   │   │   ├── 📄 useSnippets.ts
│   │   │   │   ├── 📄 useTableKeyboardNavigation.ts
│   │   │   │   ├── 📄 useThread.test.tsx
│   │   │   │   ├── 📄 useThread.ts
│   │   │   │   ├── 📄 useThreadPlans.ts
│   │   │   │   ├── 📄 useThreads.ts
│   │   │   │   ├── 📄 useThreadsByIds.ts
│   │   │   │   ├── 📄 useToggleSelect.test.ts
│   │   │   │   ├── 📄 useToggleSelect.ts
│   │   │   │   ├── 📄 useUser.ts
│   │   │   │   ├── 📄 useVideoAnalytics.ts
│   │   │   │   ├── 📄 useVideoProgressMilestones.ts
│   │   │   │   ├── 📄 useVoiceDictation.ts
│   │   │   │   ├── 📄 useVoiceLive.ts
│   │   │   │   └── 📄 useVoiceStatus.ts
│   │   │   ├── 📁 lib
│   │   │   │   ├── 📁 commands
│   │   │   │   │   ├── 📄 fuzzy-search.ts
│   │   │   │   │   └── 📄 types.ts
│   │   │   │   └── 📁 shortcuts
│   │   │   │       ├── 📄 ShortcutsProvider.tsx
│   │   │   │       ├── 📄 registry.test.ts
│   │   │   │       ├── 📄 registry.ts
│   │   │   │       ├── 📄 useShortcuts.test.tsx
│   │   │   │       └── 📄 useShortcuts.ts
│   │   │   ├── 📁 locales
│   │   │   │   ├── 📁 de
│   │   │   │   │   ├── 📄 landing.po
│   │   │   │   │   └── 📄 messages.po
│   │   │   │   ├── 📁 en
│   │   │   │   │   ├── 📄 landing.po
│   │   │   │   │   └── 📄 messages.po
│   │   │   │   ├── 📁 es
│   │   │   │   │   ├── 📄 landing.po
│   │   │   │   │   └── 📄 messages.po
│   │   │   │   ├── 📁 fr
│   │   │   │   │   ├── 📄 landing.po
│   │   │   │   │   └── 📄 messages.po
│   │   │   │   ├── 📁 it
│   │   │   │   │   ├── 📄 landing.po
│   │   │   │   │   └── 📄 messages.po
│   │   │   │   ├── 📁 ja
│   │   │   │   │   ├── 📄 landing.po
│   │   │   │   │   └── 📄 messages.po
│   │   │   │   ├── 📁 ko
│   │   │   │   │   ├── 📄 landing.po
│   │   │   │   │   └── 📄 messages.po
│   │   │   │   ├── 📁 nl
│   │   │   │   │   ├── 📄 landing.po
│   │   │   │   │   └── 📄 messages.po
│   │   │   │   ├── 📁 pl
│   │   │   │   │   ├── 📄 landing.po
│   │   │   │   │   └── 📄 messages.po
│   │   │   │   ├── 📁 pt-BR
│   │   │   │   │   ├── 📄 landing.po
│   │   │   │   │   └── 📄 messages.po
│   │   │   │   ├── 📁 tr
│   │   │   │   │   ├── 📄 landing.po
│   │   │   │   │   └── 📄 messages.po
│   │   │   │   └── 📁 zh-CN
│   │   │   │       ├── 📄 landing.po
│   │   │   │       └── 📄 messages.po
│   │   │   ├── 📁 prisma
│   │   │   │   ├── 📁 migrations
│   │   │   │   │   ├── 📁 20230730073019_init
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20230804105315_rule_name
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20230804140051_cascade_delete_executed_rule
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20230913192346_lemon_squeezy
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20230919082654_ai_model
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20231027022923_unique_account
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20231112182812_onboarding_flag
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20231207000800_settings
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20231213064514_newsletter_status
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20231219225431_unsubscribe_credits
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20231229221011_remove_summarize_action
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20240101222135_cold_email_blocker
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20240116235134_shared_premium
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20240122015840_remove_old_fields
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20240131044439_onboarding_answers
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20240208223501_ai_threads
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20240317133130_ai_provider
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20240319131634_executed_actions
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20240319151146_unique_executed_rule
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20240319151147_migrate_actions
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20240319151148_delete_deprecated_fields
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20240322094912_behaviour_profile
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20240323230604_last_login
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20240323230633_utm
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20240418150351_license_key
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20240424111051_groups
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20240426150851_rule_type
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20240507211259_premium_admin
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20240509085010_automate_default_off
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20240513103627_mark_not_cold_email
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20240516112326_remove_newsletter_cold_email
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20240516112350_cold_email_model
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20240528083708_summary_email
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20240528181840_premium_basic
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20240624075134_argument_prompt
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20240728084326_api_key
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20240730122310_copilot_tier
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20240820220244_ai_api_key
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20240917021039_rule_prompt
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20240917232302_disable_rule
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20241008234839_error_messages
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20241020163727_app_onboarding
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20241023204900_category
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20241027173153_category_filter
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20241031212440_auto_categorize_senders
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20241107151035_applying_execute_status
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20241107152409_remove_default_executed_status
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20241119163400_categorize_date_range
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20241125052523_remove_categorized_time
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20241128034952_migrate_prompt_fields
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20241216093030_upgrade_to_v6
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20241218123405_multi_conditions
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20241219122254_rename_to_conditional_operator
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20241219190656_deprecate_rule_type
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20241219192522_optional_deprecated_rule_type
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20241230180925_call_webhook_action
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20241230204311_action_webhook_url
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20250112081255_pending_invite
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20250116101856_mark_read_action
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20250128141602_cascade_delete_group
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20250130215802_read_cold_emails
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20250202092329_reply_tracker
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20250202154501_remove_deprecated_action
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20250203174037_reply_tracker_sent_at
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20250204162638_email_token
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20250204191020_remove_email_token_action
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20250209113928_non_null_email
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20250210224905_summary_indexes
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20250210225300_tracker_indexes
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20250212125908_signature
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20250223190244_draft_replies
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20250227135610_payments
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20250227135758_processor_type_enum
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20250227142620_payment_tax
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20250227144751_remove_default_timestamps_from_payment
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20250227173229_remove_prompt_history
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20250309095123_cleaner
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20250311110807_job_details
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20250312172635_skips
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20250316155443_email_message
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20250316155944_remove_size_estimate
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20250316201459_remove_to_domain
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20250324221721_skip_conversations
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20250324222007_skipconversation
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20250403104153_unique_knowledge_title
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20250406111823_track_thread_action
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20250406111915_migrate_track_replies_to_actions
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20250408111051_newsletter_learned_patterns
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20250410110949_remove_deprecated
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20250410111325_remove_deprecated_onboarding
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20250410132704_remove_rule_type
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20250414091625_rule_system_type
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20250414103126_migrate_system_rule_types
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20250415162053_draft_score
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20250417135524_writing_style
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20250420131728_email_account_settings
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20250429192105_mutli_email
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20250430094808_remove_cleanupjob_email
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20250502155551_lemon_subscription_status
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20250504061506_drop_old_userids
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20250506025728_stripe
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20250509151934_remove_deprecated
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20250519090915_add_exclude_to_group_item
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20250521104911_chat
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20250521132820_message_parts
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20250606102158_onboarding_answers
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20250609204102_rule_history
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20250610100452_add_outlook_subscription_id
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20250612142528_referrals
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20250616122919_add_digest
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20250627111946_update_digest
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20250722084939_schedule_actions
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20250804163003_better_auth
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20250811130806_add_move_folder_action
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20250812130230_persona_analysis
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20250812223533_add_folder_id
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20250813214639_email_account_role
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20250819125304_add_include_referral_signature
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20250904131746_add_sso_and_organizations
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20250912071705_calendar
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20250916133642_default_signature_enabled
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20250916180645_company_size
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20250918194235_update_org_tables_to_email_account
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20251001142931_mcp
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20251001203533_convert_automate_false_to_disabled
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20251003000636_default_rule_automate
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20251005093547_label_id
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20251009133100_add_system_type_enum_values
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20251009133101_migrate_cold_email_to_rules
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20251009133154_system_type_expansion
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20251010143722_remove_track_thread_action
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20251013003655_cascade_delete_digest_item
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20251016181540_email_message_name
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20251021123040_drop_executed_rule_unique
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20251021213524_better_auth_refresh_token_expires_at
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20251022094717_add_multi_rule_selection_enabled
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20251024092349_match_metadata
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20251030010539_indexes
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20251110013724_add_outlook_subscription_history
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20251116165134_add_timezone_and_booking_link
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20251204222441_fromname_index
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20251207172822_response_time
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20251209013008_referral_signature_off
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20251209071346_response_time_mins
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20251210202624_meeting_briefs
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20251215004700_brief_status
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20251219012216_add_notify_sender_action_type
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20251221132935_drive
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20251222222738_add_filing_preview_support
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20251223000001_rename_notification_token_to_message_id
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260101221942_account_disconnected_at
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260103000000_migrate_cold_emails_to_group_items
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260104000000_add_label_removed_to_group_item_source
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260107163249_remove_index
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260109163518_newsletter_sender_name
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260111000000_add_follow_up_reminders
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260113000000_update_conversation_rule_defaults
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260114000000_follow_up_days_to_float
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260115091612_follow_up_index
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260121000000_announcement_dismissed_at
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260122000000_add_followup_draft_id
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260126000000_add_allow_org_admin_analytics
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260126000001_enforce_single_org_per_email
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260208000000_add_messaging_channels
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260209000000_add_send_document_filings
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260209111238_add_executed_rule_created_at_index
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260210000000_add_bot_user_id_to_messaging_channel
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260210100000_add_plus_tier
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260214000000_chat_compaction_memory
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260217000000_add_dismissed_hints
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260219024141_automation_jobs
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260225000000_add_label_added_source
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260228000000_add_messaging_provider_values
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260228000000_draft_confidence_enum
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260302120000_add_stripe_ai_overage_checkpoint
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260311120000_account_scoped_api_keys
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260311130000_add_attachment_sources
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260315000000_add_action_static_attachments
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260316000000_add_draft_generation_metadata
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260316134000_hidden_ai_draft_links
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260317113949_add_reply_memories
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260318121000_add_executed_action_draft_context_metadata
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260319090000_reply_memory_learning_rework
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260319120000_add_filing_confirmation_email
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260322000000_add_sender_classification
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260323170000_chat_add_name
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260325043000_add_messaging_rule_actions
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260326090000_add_draft_messaging_action_type
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260327183000_add_chat_rule_revisions
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260404103000_enforce_messaging_channel_ownership
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260405123000_add_messaging_routes
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260407153000_add_apple_iap
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260419104529_add_stripe_trial_converted_at
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260419120000_drop_completed_app_onboarding_at
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260421000000_add_stripe_cancellation_initiated_at
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260421120000_add_digest_followup_messaging_routes
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260422220000_add_payment_premiumid_createdat_index
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260423120000_add_scheduled_check_ins_route
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260423121000_backfill_scheduled_check_ins_routes
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260426000000_add_admin_premium_grants
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260430120000_add_star_rule_action
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260430181500_add_selected_action_attachments
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260503110000_add_query_performance_indexes
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260505093300_unique_pending_digest_per_account
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260505095800_document_filing_attachment_unique
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260505120000_add_sensitive_data_policy
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260505130000_add_chat_deleted_at
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260506120000_add_booking_scheduling
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260507120000_add_draft_cleanup_days
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260507150000_add_scim_provider
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260511120000_add_draft_email_status
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260512120000_add_draft_send_log_sent_text
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260513120000_backfill_booking_slot_interval
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260514120000_add_follow_up_notifications
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260526130000_add_draft_send_log_similarity_metadata
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260607120000_add_organization_rules
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260621140000_booking_availability_schedules
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260630000000_enforce_organization_owner
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260707120000_rules_revision_ignore_learned_patterns
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260711120000_add_delete_action_type
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260714120000_add_stripe_invoice_emails
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260717211500_add_newsletter_email_lookup_index
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260717220000_add_apple_offer_discount_type
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260717220000_merge_newsletter_email_duplicates
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260728120000_add_executed_action_outcomes
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260728130000_meeting_recorder
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260728130000_remove_internal_cold_email_patterns
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260728170000_normalize_group_item_values
│   │   │   │   │   │   ├── 📝 README.md
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260729020000_meeting_recorder_cancelling
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260729120000_meeting_recording_media_deletion_index
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260730235900_meeting_recording_no_shows
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260731120000_add_mobile_push_notifications
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260731180000_add_chat_message_metadata
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260802010000_add_last_inbox_health_email_at
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260807020000_add_meeting_recording_bot_name
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260810000000_add_integration_action
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260810090000_default_meeting_recorder_all
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260811120000_add_mail_splits_and_prefs
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260811160000_make_mail_split_order_unique
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260811220000_drop_mail_hint_bar_dismissed
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260814190000_add_public_contact_history
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260815120000_add_snoozed_threads
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260822220000_make_sso_provider_organization_unique
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260824110000_add_executed_action_tracking
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260824110000_add_mail_mutation_receipts
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260824110100_add_snooze_mutation_index
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260824111000_index_executed_action_sent_message_ids
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260825190000_rename_email_send_operations
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260828013000_meeting_recording_account_ownership
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260901000000_add_all_accounts_preference
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260901010000_seed_default_mail_splits
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260902120000_update_default_cold_email_prompt
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260903130000_add_document_filing_notification_batch
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260905210000_scheduled_email_replies
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260906120000_clarify_cold_email_onboarding
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260907120000_add_mail_expanded_preview
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260907120000_add_sent_with_signature
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260907140000_add_hidden_mail_splits
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260907190000_mail_split_multi_value
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260908120000_clarify_marketing_rule_default
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260908120000_email_otp_sign_in
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260908150000_email_otp_session_version
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260908180000_unify_mail_splits
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260910000000_split_inbox_filters
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260911120000_add_sent_message_open_tracking
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260911120000_schedule_new_messages
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260911180000_add_mcp_oauth_server
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260911190000_upgrade_better_auth_17
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260911200000_complete_auth_17_schema
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260911210000_validate_sso_provider_owner
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260912120000_add_senders_unsubscribe_api_key_scope
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260914120000_add_snippets
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260915113000_add_stripe_cancel_at
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260915223000_compose_drafts
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260916040000_remove_compose_drafts
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260917120000_add_otp_system_type
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260918120000_add_user_classifier_enabled
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260919040000_add_onboarding_paywall_variant
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260919121000_remove_onboarding_paywall_variant
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260919210000_add_email_send_operation_attachment_ids
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260919210000_remove_contradicted_ai_patterns_on_custom_rules
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260919233000_rename_classifier_to_decision_model
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260920100000_clear_inline_user_images
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260922120000_add_custom_mcp_servers
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260924120000_remove_misfiled_cold_email_patterns
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260925120000_add_mcp_auth_type_none
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260926120000_add_mobile_push_token_type
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260926120000_scheduled_email_held_for_undo
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20260928150000_add_mailbox_push_to_mobile_token
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20261002120000_add_pending_premium_grant
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20261002180000_availability_schedule_uses_account_timezone
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20261006120000_team_comments
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20261007120000_add_chat_active_stream_id
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20261007210000_remember_loops_email_source
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20261009120000_scheduled_email_draft_message_ids
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20261010120000_drop_email_send_operation_attachment_ids
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20261015120000_user_signup_intent
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20261019120000_add_fcm_mobile_push_token_type
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20261019120000_email_account_draft_docs_urls
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20261019130000_index_executed_rule_updated_at
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20261019150000_index_executed_action_draft_status
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20261019150100_draft_status_user_edited
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20261024120000_email_account_sort_order
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20261030200000_add_email_signatures
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20261101120000_add_signature_suggestions
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20261101180000_track_follow_up_draft_content
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20261101180100_index_follow_up_draft_cleanup
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20261102120000_index_executed_action_draft_rule
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20261102130000_add_stripe_cancellation_feedback
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20261103120000_add_draft_status_cleanup_skipped
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20261103120100_skip_disconnected_account_draft_cleanup
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20261104120000_tune_autovacuum_analyze_executed_tables
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20261105120000_add_mail_inbox_bundles
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20261108120000_add_mail_setup
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20261110120000_mail_split_filter_to
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20261110130000_chat_action_totals
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   ├── 📁 20261110150000_add_bulk_inbox_action_job
│   │   │   │   │   │   └── 📄 migration.sql
│   │   │   │   │   └── ⚙️ migration_lock.toml
│   │   │   │   └── 📄 schema.prisma
│   │   │   ├── 📁 providers
│   │   │   │   ├── 📄 AppProviders.tsx
│   │   │   │   ├── 📄 ChatProvider.test.tsx
│   │   │   │   ├── 📄 ChatProvider.tsx
│   │   │   │   ├── 📄 ComposeModalProvider.tsx
│   │   │   │   ├── 📄 EmailAccountProvider.test.tsx
│   │   │   │   ├── 📄 EmailAccountProvider.tsx
│   │   │   │   ├── 📄 EmailLabelsProvider.tsx
│   │   │   │   ├── 📄 GlobalProviders.test.tsx
│   │   │   │   ├── 📄 GlobalProviders.tsx
│   │   │   │   ├── 📄 LinguiClientProvider.tsx
│   │   │   │   ├── 📄 PostHogProvider.tsx
│   │   │   │   ├── 📄 SWRProvider.test.tsx
│   │   │   │   ├── 📄 SWRProvider.tsx
│   │   │   │   ├── 📄 StatLoaderProvider.test.tsx
│   │   │   │   ├── 📄 StatLoaderProvider.tsx
│   │   │   │   ├── 📄 email-label-types.ts
│   │   │   │   ├── 📄 swr-error.test.ts
│   │   │   │   ├── 📄 swr-error.ts
│   │   │   │   ├── 📄 swr-fetcher.test.ts
│   │   │   │   ├── 📄 swr-fetcher.ts
│   │   │   │   ├── 📄 useCloseComposeOnMailExit.test.ts
│   │   │   │   └── 📄 useCloseComposeOnMailExit.ts
│   │   │   ├── 📁 public
│   │   │   │   ├── 📁 .well-known
│   │   │   │   │   ├── ⚙️ microsoft-identity-association.json
│   │   │   │   │   └── 📄 openai-apps-challenge
│   │   │   │   ├── 📁 brand
│   │   │   │   │   ├── 📦 inbox-zero-brand-assets.zip
│   │   │   │   │   ├── 🖼️ inbox-zero-icon.png
│   │   │   │   │   ├── 🖼️ inbox-zero-wordmark-dark.png
│   │   │   │   │   ├── 🖼️ inbox-zero-wordmark-dark.svg
│   │   │   │   │   ├── 🖼️ inbox-zero-wordmark-light.png
│   │   │   │   │   └── 🖼️ inbox-zero-wordmark-light.svg
│   │   │   │   ├── 📁 icons
│   │   │   │   │   ├── 🖼️ icon-192x192.png
│   │   │   │   │   └── 🖼️ icon-512x512.png
│   │   │   │   ├── 📁 images
│   │   │   │   │   ├── 📁 announcements
│   │   │   │   │   │   └── 🖼️ follow-up-reminders-illustration.svg
│   │   │   │   │   ├── 📁 assistant
│   │   │   │   │   │   └── 🖼️ digest.png
│   │   │   │   │   ├── 📁 blog
│   │   │   │   │   │   ├── 🖼️ elie-profile.jpg
│   │   │   │   │   │   ├── 🖼️ inbox-zero-growth.png
│   │   │   │   │   │   ├── 🖼️ messy-vs-clean-inbox.png
│   │   │   │   │   │   └── 🖼️ ricardo-batista-profile.png
│   │   │   │   │   ├── 📁 case-studies
│   │   │   │   │   │   └── 📁 clicks-talent
│   │   │   │   │   │       ├── 🖼️ ab-lieberman.png
│   │   │   │   │   │       └── 🖼️ company.png
│   │   │   │   │   ├── 📁 home
│   │   │   │   │   │   ├── 📁 testimonials
│   │   │   │   │   │   │   └── 🖼️ steve-rad.png
│   │   │   │   │   │   ├── 🖼️ ai-email-assistant.png
│   │   │   │   │   │   ├── 🖼️ bulk-unsubscriber.png
│   │   │   │   │   │   ├── 🖼️ cold-email-blocker.png
│   │   │   │   │   │   ├── 🖼️ email-analytics.png
│   │   │   │   │   │   ├── 🖼️ mail.png
│   │   │   │   │   │   ├── 🖼️ product-hunt-badge.svg
│   │   │   │   │   │   ├── 🖼️ realtor-gmail.png
│   │   │   │   │   │   ├── 🖼️ reply-zero.png
│   │   │   │   │   │   ├── 🖼️ soc2.png
│   │   │   │   │   │   └── 🖼️ soc2.svg
│   │   │   │   │   ├── 📁 illustrations
│   │   │   │   │   │   ├── 🖼️ business-success-chart.svg
│   │   │   │   │   │   ├── 🖼️ calling-help.svg
│   │   │   │   │   │   ├── 🖼️ communication.svg
│   │   │   │   │   │   ├── 🖼️ falling.svg
│   │   │   │   │   │   ├── 🖼️ home-office.svg
│   │   │   │   │   │   └── 🖼️ working-vacation.svg
│   │   │   │   │   ├── 📁 logos
│   │   │   │   │   │   ├── 🖼️ bytedance.svg
│   │   │   │   │   │   ├── 🖼️ doac.svg
│   │   │   │   │   │   ├── 🖼️ joco.svg
│   │   │   │   │   │   ├── 🖼️ netflix.svg
│   │   │   │   │   │   └── 🖼️ resend.svg
│   │   │   │   │   ├── 📁 meetings
│   │   │   │   │   │   └── 🖼️ inbox-zero-notetaker.jpg
│   │   │   │   │   ├── 📁 new-landing
│   │   │   │   │   │   ├── 📁 awards
│   │   │   │   │   │   │   ├── 🖼️ github-stars-award.png
│   │   │   │   │   │   │   ├── 🖼️ github-trending-award.png
│   │   │   │   │   │   │   ├── 🖼️ product-hunt-award.png
│   │   │   │   │   │   │   └── 🖼️ soc-award.png
│   │   │   │   │   │   ├── 📁 logos
│   │   │   │   │   │   │   ├── 🖼️ alta.svg
│   │   │   │   │   │   │   ├── 🖼️ bytedance.svg
│   │   │   │   │   │   │   ├── 🖼️ compass.svg
│   │   │   │   │   │   │   ├── 🖼️ doac.svg
│   │   │   │   │   │   │   ├── 🖼️ joco.svg
│   │   │   │   │   │   │   ├── 🖼️ kw.svg
│   │   │   │   │   │   │   ├── 🖼️ netflix.svg
│   │   │   │   │   │   │   ├── 🖼️ resend.svg
│   │   │   │   │   │   │   └── 🖼️ wix.svg
│   │   │   │   │   │   ├── 🖼️ an-organized-inbox-mobile.png
│   │   │   │   │   │   ├── 🖼️ an-organized-inbox.png
│   │   │   │   │   │   ├── 🖼️ bulk-unsubscribe-mobile.png
│   │   │   │   │   │   ├── 🖼️ bulk-unsubscribe.png
│   │   │   │   │   │   ├── 🖼️ buy-back-time-bg.png
│   │   │   │   │   │   ├── 🖼️ create-rules.png
│   │   │   │   │   │   ├── 🖼️ inbox-zero-mail.webp
│   │   │   │   │   │   ├── 🖼️ integrations.png
│   │   │   │   │   │   ├── 🖼️ metrics.svg
│   │   │   │   │   │   ├── 🖼️ new-message.png
│   │   │   │   │   │   ├── 🖼️ pre-written-drafts-mobile.png
│   │   │   │   │   │   ├── 🖼️ pre-written-drafts.png
│   │   │   │   │   │   └── 🖼️ video-thumbnail.webp
│   │   │   │   │   ├── 📁 onboarding
│   │   │   │   │   │   ├── 🖼️ bulk-unsubscribe.png
│   │   │   │   │   │   ├── 🖼️ digest.png
│   │   │   │   │   │   ├── 🖼️ draft.png
│   │   │   │   │   │   ├── 🖼️ extension.png
│   │   │   │   │   │   └── 🖼️ newsletters.png
│   │   │   │   │   ├── 📁 product
│   │   │   │   │   │   ├── 🖼️ google-calendar.svg
│   │   │   │   │   │   └── 🖼️ outlook-calendar.svg
│   │   │   │   │   ├── 📁 testimonials
│   │   │   │   │   │   ├── 🖼️ joel.jpeg
│   │   │   │   │   │   ├── 🖼️ jonnilundy.jpg
│   │   │   │   │   │   ├── 🖼️ joseph-gonzalez-iFgRcqHznqg-unsplash.jpg
│   │   │   │   │   │   ├── 🖼️ midas-hofstra-a6PMA5JEmWE-unsplash.jpg
│   │   │   │   │   │   ├── 🖼️ slim.png
│   │   │   │   │   │   ├── 🖼️ steventey.jpg
│   │   │   │   │   │   ├── 🖼️ valentine.png
│   │   │   │   │   │   ├── 🖼️ will.jpeg
│   │   │   │   │   │   └── 🖼️ yoni.jpeg
│   │   │   │   │   ├── 🖼️ google.svg
│   │   │   │   │   ├── 🖼️ microsoft.svg
│   │   │   │   │   ├── 🖼️ reach-inbox-zero.png
│   │   │   │   │   ├── 🖼️ slack.svg
│   │   │   │   │   ├── 🖼️ teams.png
│   │   │   │   │   └── 🖼️ telegram.svg
│   │   │   │   ├── 📁 splash_screens
│   │   │   │   │   ├── 🖼️ 10.2__iPad_landscape.png
│   │   │   │   │   ├── 🖼️ 10.2__iPad_portrait.png
│   │   │   │   │   ├── 🖼️ 10.5__iPad_Air_landscape.png
│   │   │   │   │   ├── 🖼️ 10.5__iPad_Air_portrait.png
│   │   │   │   │   ├── 🖼️ 10.9__iPad_Air_landscape.png
│   │   │   │   │   ├── 🖼️ 10.9__iPad_Air_portrait.png
│   │   │   │   │   ├── 🖼️ 11__iPad_Pro_M4_landscape.png
│   │   │   │   │   ├── 🖼️ 11__iPad_Pro_M4_portrait.png
│   │   │   │   │   ├── 🖼️ 11__iPad_Pro__10.5__iPad_Pro_landscape.png
│   │   │   │   │   ├── 🖼️ 11__iPad_Pro__10.5__iPad_Pro_portrait.png
│   │   │   │   │   ├── 🖼️ 12.9__iPad_Pro_landscape.png
│   │   │   │   │   ├── 🖼️ 12.9__iPad_Pro_portrait.png
│   │   │   │   │   ├── 🖼️ 13__iPad_Pro_M4_landscape.png
│   │   │   │   │   ├── 🖼️ 13__iPad_Pro_M4_portrait.png
│   │   │   │   │   ├── 🖼️ 4__iPhone_SE__iPod_touch_5th_generation_and_later_landscape.png
│   │   │   │   │   ├── 🖼️ 4__iPhone_SE__iPod_touch_5th_generation_and_later_portrait.png
│   │   │   │   │   ├── 🖼️ 8.3__iPad_Mini_landscape.png
│   │   │   │   │   ├── 🖼️ 8.3__iPad_Mini_portrait.png
│   │   │   │   │   ├── 🖼️ 9.7__iPad_Pro__7.9__iPad_mini__9.7__iPad_Air__9.7__iPad_landscape.png
│   │   │   │   │   ├── 🖼️ 9.7__iPad_Pro__7.9__iPad_mini__9.7__iPad_Air__9.7__iPad_portrait.png
│   │   │   │   │   ├── 🖼️ iPhone_11_Pro_Max__iPhone_XS_Max_landscape.png
│   │   │   │   │   ├── 🖼️ iPhone_11_Pro_Max__iPhone_XS_Max_portrait.png
│   │   │   │   │   ├── 🖼️ iPhone_11__iPhone_XR_landscape.png
│   │   │   │   │   ├── 🖼️ iPhone_11__iPhone_XR_portrait.png
│   │   │   │   │   ├── 🖼️ iPhone_13_mini__iPhone_12_mini__iPhone_11_Pro__iPhone_XS__iPhone_X_landscape.png
│   │   │   │   │   ├── 🖼️ iPhone_13_mini__iPhone_12_mini__iPhone_11_Pro__iPhone_XS__iPhone_X_portrait.png
│   │   │   │   │   ├── 🖼️ iPhone_14_Plus__iPhone_13_Pro_Max__iPhone_12_Pro_Max_landscape.png
│   │   │   │   │   ├── 🖼️ iPhone_14_Plus__iPhone_13_Pro_Max__iPhone_12_Pro_Max_portrait.png
│   │   │   │   │   ├── 🖼️ iPhone_14__iPhone_13_Pro__iPhone_13__iPhone_12_Pro__iPhone_12_landscape.png
│   │   │   │   │   ├── 🖼️ iPhone_14__iPhone_13_Pro__iPhone_13__iPhone_12_Pro__iPhone_12_portrait.png
│   │   │   │   │   ├── 🖼️ iPhone_15_Pro_Max__iPhone_15_Plus__iPhone_14_Pro_Max_landscape.png
│   │   │   │   │   ├── 🖼️ iPhone_15_Pro_Max__iPhone_15_Plus__iPhone_14_Pro_Max_portrait.png
│   │   │   │   │   ├── 🖼️ iPhone_15_Pro__iPhone_15__iPhone_14_Pro_landscape.png
│   │   │   │   │   ├── 🖼️ iPhone_15_Pro__iPhone_15__iPhone_14_Pro_portrait.png
│   │   │   │   │   ├── 🖼️ iPhone_8_Plus__iPhone_7_Plus__iPhone_6s_Plus__iPhone_6_Plus_landscape.png
│   │   │   │   │   ├── 🖼️ iPhone_8_Plus__iPhone_7_Plus__iPhone_6s_Plus__iPhone_6_Plus_portrait.png
│   │   │   │   │   ├── 🖼️ iPhone_8__iPhone_7__iPhone_6s__iPhone_6__4.7__iPhone_SE_landscape.png
│   │   │   │   │   ├── 🖼️ iPhone_8__iPhone_7__iPhone_6s__iPhone_6__4.7__iPhone_SE_portrait.png
│   │   │   │   │   └── 🖼️ icon.png
│   │   │   │   └── 🖼️ logo-wordmark.png
│   │   │   ├── 📁 scripts
│   │   │   │   ├── 📁 emulator
│   │   │   │   │   ├── 📝 README.md
│   │   │   │   │   ├── ⚙️ compose.yml
│   │   │   │   │   ├── 📄 fixtures.mjs
│   │   │   │   │   ├── 📄 provider.mjs
│   │   │   │   │   ├── 📄 proxy.mjs
│   │   │   │   │   ├── 📄 proxy.test.mjs
│   │   │   │   │   ├── 📄 stack.mjs
│   │   │   │   │   ├── 📄 startup-ownership.mjs
│   │   │   │   │   └── 📄 startup-ownership.test.mjs
│   │   │   │   ├── 📁 eval-report
│   │   │   │   │   ├── 📄 aggregate.test.ts
│   │   │   │   │   ├── 📄 aggregate.ts
│   │   │   │   │   ├── 📄 generate-eval-report.ts
│   │   │   │   │   ├── 📄 render-html.test.ts
│   │   │   │   │   └── 📄 render-html.ts
│   │   │   │   ├── 📁 lib
│   │   │   │   │   └── 📄 source-files.js
│   │   │   │   ├── 📁 local-dev
│   │   │   │   │   ├── 📄 environment.test.ts
│   │   │   │   │   ├── 📄 environment.ts
│   │   │   │   │   ├── 📄 lock.test.ts
│   │   │   │   │   ├── 📄 lock.ts
│   │   │   │   │   ├── 📄 processes.test.ts
│   │   │   │   │   ├── 📄 processes.ts
│   │   │   │   │   ├── 📄 redis-http.test.ts
│   │   │   │   │   └── 📄 redis-http.ts
│   │   │   │   ├── 📄 build-mcp-app.mjs
│   │   │   │   ├── 📄 build-playwright-pr-comment.ts
│   │   │   │   ├── 📄 check-client-redirects.js
│   │   │   │   ├── 📄 check-client-redirects.test.ts
│   │   │   │   ├── 📄 check-enum-imports.js
│   │   │   │   ├── 📄 check-server-action-exports.js
│   │   │   │   ├── 📄 check-test-fixtures.ts
│   │   │   │   ├── 📄 cleanup-legacy-label-removal-exclusions.ts
│   │   │   │   ├── 📄 docker-replace-in-prerender.test.ts
│   │   │   │   ├── 📄 emulate-seed.test.ts
│   │   │   │   ├── 📄 emulate-seed.ts
│   │   │   │   ├── 📄 eval-ablate.ts
│   │   │   │   ├── 📄 eval-compare-runs.ts
│   │   │   │   ├── 📄 eval-pool-ablations.ts
│   │   │   │   ├── 📄 generate-llm-pricing.ts
│   │   │   │   ├── 📄 generate-playwright-report-dashboard.test.ts
│   │   │   │   ├── 📄 generate-playwright-report-dashboard.ts
│   │   │   │   ├── 📄 local-dev.ts
│   │   │   │   ├── 📄 measure-playwright-selection.mjs
│   │   │   │   ├── 📄 migrate-microsoft-provider-account-ids.ts
│   │   │   │   ├── 📄 playwright-pr-comment.test.ts
│   │   │   │   ├── 📄 playwright-pr-comment.ts
│   │   │   │   ├── 📄 playwright-report-dashboard.test.ts
│   │   │   │   ├── 📄 playwright-report-dashboard.ts
│   │   │   │   ├── 📄 playwright-screenshot-diff.test.ts
│   │   │   │   ├── 📄 playwright-screenshot-diff.ts
│   │   │   │   ├── 📄 png-validation.test.ts
│   │   │   │   ├── 📄 png-validation.ts
│   │   │   │   ├── 📄 purge-orphaned-tinybird-data.ts
│   │   │   │   ├── 📄 run-llm-emulator.ts
│   │   │   │   ├── 📄 run-recall-emulator.ts
│   │   │   │   ├── 📄 run-stripe-emulator.ts
│   │   │   │   ├── 📄 setup-telegram-bot.ts
│   │   │   │   ├── 📄 todoist-mcp-emulator.ts
│   │   │   │   ├── 📄 vercel-ignore-build.sh
│   │   │   │   └── 📄 write-emulate-seed.ts
│   │   │   ├── 📁 specs
│   │   │   │   ├── 📝 README.md
│   │   │   │   ├── 📄 compose-send.qnt
│   │   │   │   └── 📄 compose-send.test.ts
│   │   │   ├── 📁 store
│   │   │   │   ├── 📄 ai-categorize-sender-queue.ts
│   │   │   │   ├── 📄 ai-queue.ts
│   │   │   │   ├── 📄 archive-sender-queue.test.tsx
│   │   │   │   ├── 📄 archive-sender-queue.ts
│   │   │   │   ├── 📄 command-palette.ts
│   │   │   │   ├── 📄 delete-sender-queue.ts
│   │   │   │   ├── 📄 fetch-sender-threads.test.ts
│   │   │   │   ├── 📄 fetch-sender-threads.ts
│   │   │   │   ├── 📄 index.ts
│   │   │   │   ├── 📄 mail-preview.ts
│   │   │   │   ├── 📄 mail-search-history.test.ts
│   │   │   │   ├── 📄 mail-search-history.ts
│   │   │   │   ├── 📄 mark-read-sender-queue.ts
│   │   │   │   ├── 📄 prefixed-storage.test.ts
│   │   │   │   ├── 📄 prefixed-storage.ts
│   │   │   │   ├── 📄 sender-queue.test.ts
│   │   │   │   └── 📄 sender-queue.ts
│   │   │   ├── 📁 styles
│   │   │   │   ├── 📄 aeonik-medium.woff
│   │   │   │   ├── 🎨 globals.css
│   │   │   │   └── 🎨 scrollbar.css
│   │   │   ├── 📁 types
│   │   │   │   ├── 📄 gmail-api-parse-message.d.ts
│   │   │   │   ├── 📄 jsdom-cjs.d.ts
│   │   │   │   ├── 📄 mdx.d.ts
│   │   │   │   └── 📄 po.d.ts
│   │   │   ├── 📁 utils
│   │   │   │   ├── 📁 __mocks__
│   │   │   │   │   ├── 📄 email-provider.ts
│   │   │   │   │   └── 📄 prisma.ts
│   │   │   │   ├── 📁 actions
│   │   │   │   │   ├── 📁 __tests__
│   │   │   │   │   │   ├── 📄 copy-rules-action.test.ts
│   │   │   │   │   │   ├── 📄 invitation-actions.test.ts
│   │   │   │   │   │   └── 📄 organization-actions.test.ts
│   │   │   │   │   ├── 📄 admin.test.ts
│   │   │   │   │   ├── 📄 admin.ts
│   │   │   │   │   ├── 📄 admin.validation.ts
│   │   │   │   │   ├── 📄 ai-rule.test.ts
│   │   │   │   │   ├── 📄 ai-rule.ts
│   │   │   │   │   ├── 📄 ai-rule.validation.ts
│   │   │   │   │   ├── 📄 all-accounts.test.ts
│   │   │   │   │   ├── 📄 all-accounts.ts
│   │   │   │   │   ├── 📄 all-accounts.validation.ts
│   │   │   │   │   ├── 📄 announcements.ts
│   │   │   │   │   ├── 📄 announcements.validation.ts
│   │   │   │   │   ├── 📄 api-key.test.ts
│   │   │   │   │   ├── 📄 api-key.ts
│   │   │   │   │   ├── 📄 api-key.validation.ts
│   │   │   │   │   ├── 📄 assess.ts
│   │   │   │   │   ├── 📄 assistant-chat-bulk-inbox-action.test.ts
│   │   │   │   │   ├── 📄 assistant-chat-confirmation.ts
│   │   │   │   │   ├── 📄 assistant-chat-create-rule.test.ts
│   │   │   │   │   ├── 📄 assistant-chat.server-action-boundary.test.ts
│   │   │   │   │   ├── 📄 assistant-chat.test.ts
│   │   │   │   │   ├── 📄 assistant-chat.ts
│   │   │   │   │   ├── 📄 assistant-chat.validation.test.ts
│   │   │   │   │   ├── 📄 assistant-chat.validation.ts
│   │   │   │   │   ├── 📄 attachment-sources.ts
│   │   │   │   │   ├── 📄 attachment-sources.validation.ts
│   │   │   │   │   ├── 📄 automation-jobs.helpers.ts
│   │   │   │   │   ├── 📄 automation-jobs.test.ts
│   │   │   │   │   ├── 📄 automation-jobs.ts
│   │   │   │   │   ├── 📄 automation-jobs.validation.ts
│   │   │   │   │   ├── 📄 booking.test.ts
│   │   │   │   │   ├── 📄 booking.ts
│   │   │   │   │   ├── 📄 booking.validation.test.ts
│   │   │   │   │   ├── 📄 booking.validation.ts
│   │   │   │   │   ├── 📄 calendar-invitation.ts
│   │   │   │   │   ├── 📄 calendar-invitation.validation.ts
│   │   │   │   │   ├── 📄 calendar.ts
│   │   │   │   │   ├── 📄 calendar.validation.ts
│   │   │   │   │   ├── 📄 categorize.test.ts
│   │   │   │   │   ├── 📄 categorize.ts
│   │   │   │   │   ├── 📄 categorize.validation.ts
│   │   │   │   │   ├── 📄 chat.ts
│   │   │   │   │   ├── 📄 chat.validation.ts
│   │   │   │   │   ├── 📄 clean.test.ts
│   │   │   │   │   ├── 📄 clean.ts
│   │   │   │   │   ├── 📄 clean.validation.ts
│   │   │   │   │   ├── 📄 cold-email.test.ts
│   │   │   │   │   ├── 📄 cold-email.ts
│   │   │   │   │   ├── 📄 cold-email.validation.ts
│   │   │   │   │   ├── 📄 draft-attachments.validation.ts
│   │   │   │   │   ├── 📄 draft-reply.ts
│   │   │   │   │   ├── 📄 drive.ts
│   │   │   │   │   ├── 📄 drive.validation.ts
│   │   │   │   │   ├── 📄 email-account-cookie.test.ts
│   │   │   │   │   ├── 📄 email-account-cookie.ts
│   │   │   │   │   ├── 📄 email-account.test.ts
│   │   │   │   │   ├── 📄 email-account.ts
│   │   │   │   │   ├── 📄 email-account.validation.ts
│   │   │   │   │   ├── 📄 email-otp.ts
│   │   │   │   │   ├── 📄 email-otp.validation.ts
│   │   │   │   │   ├── 📄 error-handling.test.ts
│   │   │   │   │   ├── 📄 error-handling.ts
│   │   │   │   │   ├── 📄 error-messages.ts
│   │   │   │   │   ├── 📄 feedback.test.ts
│   │   │   │   │   ├── 📄 feedback.ts
│   │   │   │   │   ├── 📄 feedback.validation.ts
│   │   │   │   │   ├── 📄 follow-up-reminders.test.ts
│   │   │   │   │   ├── 📄 follow-up-reminders.ts
│   │   │   │   │   ├── 📄 follow-up-reminders.validation.ts
│   │   │   │   │   ├── 📄 group.ts
│   │   │   │   │   ├── 📄 group.validation.ts
│   │   │   │   │   ├── 📄 hints.ts
│   │   │   │   │   ├── 📄 hints.validation.ts
│   │   │   │   │   ├── 📄 knowledge.ts
│   │   │   │   │   ├── 📄 knowledge.validation.ts
│   │   │   │   │   ├── 📄 local-mail-sync.validation.ts
│   │   │   │   │   ├── 📄 locale.ts
│   │   │   │   │   ├── 📄 locale.validation.ts
│   │   │   │   │   ├── 📄 mail-bulk-action.constants.ts
│   │   │   │   │   ├── 📄 mail-bulk-action.test.ts
│   │   │   │   │   ├── 📄 mail-bulk-action.ts
│   │   │   │   │   ├── 📄 mail-bulk-action.validation.ts
│   │   │   │   │   ├── 📄 mail-draft.test.ts
│   │   │   │   │   ├── 📄 mail-mailbox-item.test.ts
│   │   │   │   │   ├── 📄 mail-split.test.ts
│   │   │   │   │   ├── 📄 mail-split.ts
│   │   │   │   │   ├── 📄 mail-split.validation.test.ts
│   │   │   │   │   ├── 📄 mail-split.validation.ts
│   │   │   │   │   ├── 📄 mail.ts
│   │   │   │   │   ├── 📄 mail.validation.ts
│   │   │   │   │   ├── 📄 mcp.test.ts
│   │   │   │   │   ├── 📄 mcp.ts
│   │   │   │   │   ├── 📄 mcp.validation.ts
│   │   │   │   │   ├── 📄 meeting-briefs.ts
│   │   │   │   │   ├── 📄 meeting-briefs.validation.ts
│   │   │   │   │   ├── 📄 meeting-recorder.test.ts
│   │   │   │   │   ├── 📄 meeting-recorder.ts
│   │   │   │   │   ├── 📄 meeting-recorder.validation.ts
│   │   │   │   │   ├── 📄 messaging-channels.test.ts
│   │   │   │   │   ├── 📄 messaging-channels.ts
│   │   │   │   │   ├── 📄 messaging-channels.validation.ts
│   │   │   │   │   ├── 📄 onboarding.test.ts
│   │   │   │   │   ├── 📄 onboarding.ts
│   │   │   │   │   ├── 📄 onboarding.validation.ts
│   │   │   │   │   ├── 📄 organization-rule.ts
│   │   │   │   │   ├── 📄 organization-rule.validation.test.ts
│   │   │   │   │   ├── 📄 organization-rule.validation.ts
│   │   │   │   │   ├── 📄 organization.test.ts
│   │   │   │   │   ├── 📄 organization.ts
│   │   │   │   │   ├── 📄 organization.validation.ts
│   │   │   │   │   ├── 📄 permissions.ts
│   │   │   │   │   ├── 📄 persona-background.test.ts
│   │   │   │   │   ├── 📄 premium.test.ts
│   │   │   │   │   ├── 📄 premium.ts
│   │   │   │   │   ├── 📄 premium.validation.ts
│   │   │   │   │   ├── 📄 render-html.validation.ts
│   │   │   │   │   ├── 📄 report.ts
│   │   │   │   │   ├── 📄 rule.test.ts
│   │   │   │   │   ├── 📄 rule.ts
│   │   │   │   │   ├── 📄 rule.validation.test.ts
│   │   │   │   │   ├── 📄 rule.validation.ts
│   │   │   │   │   ├── 📄 safe-action.ts
│   │   │   │   │   ├── 📄 scheduled-email.ts
│   │   │   │   │   ├── 📄 scheduled-email.validation.ts
│   │   │   │   │   ├── 📄 scim.test.ts
│   │   │   │   │   ├── 📄 scim.ts
│   │   │   │   │   ├── 📄 scim.validation.ts
│   │   │   │   │   ├── 📄 settings.test.ts
│   │   │   │   │   ├── 📄 settings.ts
│   │   │   │   │   ├── 📄 settings.validation.ts
│   │   │   │   │   ├── 📄 signature.ts
│   │   │   │   │   ├── 📄 signature.validation.ts
│   │   │   │   │   ├── 📄 snippet.ts
│   │   │   │   │   ├── 📄 snippet.validation.ts
│   │   │   │   │   ├── 📄 snooze.validation.test.ts
│   │   │   │   │   ├── 📄 snooze.validation.ts
│   │   │   │   │   ├── 📄 sso.test.ts
│   │   │   │   │   ├── 📄 sso.ts
│   │   │   │   │   ├── 📄 sso.validation.ts
│   │   │   │   │   ├── 📄 stats-loading.test.ts
│   │   │   │   │   ├── 📄 stats-loading.ts
│   │   │   │   │   ├── 📄 team-comments.ts
│   │   │   │   │   ├── 📄 team-comments.validation.ts
│   │   │   │   │   ├── 📄 translate.ts
│   │   │   │   │   ├── 📄 translate.validation.ts
│   │   │   │   │   ├── 📄 unsubscriber.ts
│   │   │   │   │   ├── 📄 unsubscriber.validation.ts
│   │   │   │   │   ├── 📄 user.test.ts
│   │   │   │   │   ├── 📄 user.ts
│   │   │   │   │   ├── 📄 user.validation.ts
│   │   │   │   │   ├── 📄 webhook.test.ts
│   │   │   │   │   └── 📄 webhook.ts
│   │   │   │   ├── 📁 agent-markdown
│   │   │   │   │   ├── 📄 accept.test.ts
│   │   │   │   │   ├── 📄 accept.ts
│   │   │   │   │   └── 📄 content.ts
│   │   │   │   ├── 📁 ai
│   │   │   │   │   ├── 📁 assistant
│   │   │   │   │   │   ├── 📁 tools
│   │   │   │   │   │   │   ├── 📁 rules
│   │   │   │   │   │   │   │   ├── 📄 add-to-knowledge-base-tool.ts
│   │   │   │   │   │   │   │   ├── 📄 create-rule-tool.ts
│   │   │   │   │   │   │   │   ├── 📄 delete-rule-tool.ts
│   │   │   │   │   │   │   │   ├── 📄 get-learned-patterns-tool.ts
│   │   │   │   │   │   │   │   ├── 📄 get-rule-execution-for-message-tool.ts
│   │   │   │   │   │   │   │   ├── 📄 get-user-rules-and-settings-tool.ts
│   │   │   │   │   │   │   │   ├── 📄 shared.ts
│   │   │   │   │   │   │   │   ├── 📄 test-rules-on-email-tool.test.ts
│   │   │   │   │   │   │   │   ├── 📄 test-rules-on-email-tool.ts
│   │   │   │   │   │   │   │   ├── 📄 update-learned-patterns-tool.test.ts
│   │   │   │   │   │   │   │   ├── 📄 update-learned-patterns-tool.ts
│   │   │   │   │   │   │   │   ├── 📄 update-personal-instructions-tool.test.ts
│   │   │   │   │   │   │   │   ├── 📄 update-personal-instructions-tool.ts
│   │   │   │   │   │   │   │   └── 📄 update-rule-tool.ts
│   │   │   │   │   │   │   └── 📁 settings
│   │   │   │   │   │   │       ├── 📄 get-assistant-capabilities-tool.ts
│   │   │   │   │   │   │       ├── 📄 shared.ts
│   │   │   │   │   │   │       └── 📄 update-assistant-settings-tool.ts
│   │   │   │   │   │   ├── 📄 bulk-inbox-action-status.ts
│   │   │   │   │   │   ├── 📄 cache-breakpoints.test.ts
│   │   │   │   │   │   ├── 📄 cache-breakpoints.ts
│   │   │   │   │   │   ├── 📄 chat-action-totals.ts
│   │   │   │   │   │   ├── 📄 chat-bulk-inbox-tool.test.ts
│   │   │   │   │   │   ├── 📄 chat-bulk-inbox-tool.ts
│   │   │   │   │   │   ├── 📄 chat-calendar-tools.ts
│   │   │   │   │   │   ├── 📄 chat-context-validation.test.ts
│   │   │   │   │   │   ├── 📄 chat-context-validation.ts
│   │   │   │   │   │   ├── 📄 chat-folder-tools.test.ts
│   │   │   │   │   │   ├── 📄 chat-folder-tools.ts
│   │   │   │   │   │   ├── 📄 chat-inbox-tools.test.ts
│   │   │   │   │   │   ├── 📄 chat-inbox-tools.ts
│   │   │   │   │   │   ├── 📄 chat-label-tools.test.ts
│   │   │   │   │   │   ├── 📄 chat-label-tools.ts
│   │   │   │   │   │   ├── 📄 chat-mail-screen-tool.ts
│   │   │   │   │   │   ├── 📄 chat-memory-policy.test.ts
│   │   │   │   │   │   ├── 📄 chat-memory-policy.ts
│   │   │   │   │   │   ├── 📄 chat-memory-tools.ts
│   │   │   │   │   │   ├── 📄 chat-provider-google.ts
│   │   │   │   │   │   ├── 📄 chat-provider-microsoft.ts
│   │   │   │   │   │   ├── 📄 chat-provider-shared.ts
│   │   │   │   │   │   ├── 📄 chat-response-guard.test.ts
│   │   │   │   │   │   ├── 📄 chat-response-guard.ts
│   │   │   │   │   │   ├── 📄 chat-rule-state.ts
│   │   │   │   │   │   ├── 📄 chat-rule-tools.test.ts
│   │   │   │   │   │   ├── 📄 chat-seen-rules-revision.ts
│   │   │   │   │   │   ├── 📄 chat-settings-tools.test.ts
│   │   │   │   │   │   ├── 📄 chat-split-inbox-tool.test.ts
│   │   │   │   │   │   ├── 📄 chat-split-inbox-tool.ts
│   │   │   │   │   │   ├── 📄 chat-tool-guards.test.ts
│   │   │   │   │   │   ├── 📄 chat-tool-guards.ts
│   │   │   │   │   │   ├── 📄 chat.test.ts
│   │   │   │   │   │   ├── 📄 chat.ts
│   │   │   │   │   │   ├── 📄 compact.test.ts
│   │   │   │   │   │   ├── 📄 compact.ts
│   │   │   │   │   │   ├── 📄 final-reply-step.test.ts
│   │   │   │   │   │   ├── 📄 final-reply-step.ts
│   │   │   │   │   │   ├── 📄 get-inbox-stats-for-chat-context.ts
│   │   │   │   │   │   ├── 📄 get-recent-chat-memories.ts
│   │   │   │   │   │   ├── 📄 inline-email-actions.test.ts
│   │   │   │   │   │   ├── 📄 inline-email-actions.ts
│   │   │   │   │   │   ├── 📄 mail-screen-action.test.ts
│   │   │   │   │   │   ├── 📄 mail-screen-action.ts
│   │   │   │   │   │   ├── 📄 mail-view-context.ts
│   │   │   │   │   │   ├── 📄 manage-inbox-actions.ts
│   │   │   │   │   │   ├── 📄 tool-error-visibility.ts
│   │   │   │   │   │   ├── 📄 trim-stale-tool-results.test.ts
│   │   │   │   │   │   └── 📄 trim-stale-tool-results.ts
│   │   │   │   │   ├── 📁 automation-jobs
│   │   │   │   │   │   └── 📄 generate-check-in-message.ts
│   │   │   │   │   ├── 📁 bulk-inbox-action
│   │   │   │   │   │   └── 📄 filter-emails.ts
│   │   │   │   │   ├── 📁 calendar
│   │   │   │   │   │   ├── 📄 availability.test.ts
│   │   │   │   │   │   └── 📄 availability.ts
│   │   │   │   │   ├── 📁 categorize-sender
│   │   │   │   │   │   ├── 📄 ai-categorize-senders.ts
│   │   │   │   │   │   ├── 📄 ai-categorize-single-sender.ts
│   │   │   │   │   │   └── 📄 format-categories.ts
│   │   │   │   │   ├── 📁 choose-rule
│   │   │   │   │   │   ├── 📄 ai-choose-args.ts
│   │   │   │   │   │   ├── 📄 ai-choose-rule.test.ts
│   │   │   │   │   │   ├── 📄 ai-choose-rule.ts
│   │   │   │   │   │   ├── 📄 ai-detect-recurring-pattern.test.ts
│   │   │   │   │   │   ├── 📄 ai-detect-recurring-pattern.ts
│   │   │   │   │   │   ├── 📄 analyze-sender-pattern.ts
│   │   │   │   │   │   ├── 📄 bulk-process-emails.ts
│   │   │   │   │   │   ├── 📄 choose-args.security.test.ts
│   │   │   │   │   │   ├── 📄 choose-args.test.ts
│   │   │   │   │   │   ├── 📄 choose-args.ts
│   │   │   │   │   │   ├── 📄 draft-management.test.ts
│   │   │   │   │   │   ├── 📄 draft-management.ts
│   │   │   │   │   │   ├── 📄 execute.test.ts
│   │   │   │   │   │   ├── 📄 execute.ts
│   │   │   │   │   │   ├── 📄 match-rules.test.ts
│   │   │   │   │   │   ├── 📄 match-rules.ts
│   │   │   │   │   │   ├── 📄 retry-failed-actions.test.ts
│   │   │   │   │   │   ├── 📄 retry-failed-actions.ts
│   │   │   │   │   │   ├── 📄 run-rules.test.ts
│   │   │   │   │   │   ├── 📄 run-rules.ts
│   │   │   │   │   │   ├── 📄 selection-metadata-summary.ts
│   │   │   │   │   │   └── 📄 types.ts
│   │   │   │   │   ├── 📁 clean
│   │   │   │   │   │   └── 📄 ai-clean.ts
│   │   │   │   │   ├── 📁 digest
│   │   │   │   │   │   └── 📄 summarize-email-for-digest.ts
│   │   │   │   │   ├── 📁 document-filing
│   │   │   │   │   │   ├── 📄 analyze-document.ts
│   │   │   │   │   │   └── 📄 parse-filing-reply.ts
│   │   │   │   │   ├── 📁 group
│   │   │   │   │   │   ├── 📄 find-newsletters.test.ts
│   │   │   │   │   │   ├── 📄 find-newsletters.ts
│   │   │   │   │   │   ├── 📄 find-receipts.test.ts
│   │   │   │   │   │   └── 📄 find-receipts.ts
│   │   │   │   │   ├── 📁 knowledge
│   │   │   │   │   │   ├── 📄 analyze-persona.ts
│   │   │   │   │   │   ├── 📄 extract-from-email-history.test.ts
│   │   │   │   │   │   ├── 📄 extract-from-email-history.ts
│   │   │   │   │   │   ├── 📄 extract.ts
│   │   │   │   │   │   ├── 📄 persona.ts
│   │   │   │   │   │   ├── 📄 schedule-account-analysis.ts
│   │   │   │   │   │   ├── 📄 select-writing-style-samples.test.ts
│   │   │   │   │   │   ├── 📄 select-writing-style-samples.ts
│   │   │   │   │   │   └── 📄 writing-style.ts
│   │   │   │   │   ├── 📁 mcp
│   │   │   │   │   │   ├── 📄 docs-tools.ts
│   │   │   │   │   │   ├── 📄 mcp-agent.ts
│   │   │   │   │   │   ├── 📄 mcp-tools.test.ts
│   │   │   │   │   │   └── 📄 mcp-tools.ts
│   │   │   │   │   ├── 📁 meeting-briefs
│   │   │   │   │   │   ├── 📄 generate-briefing.test.ts
│   │   │   │   │   │   ├── 📄 generate-briefing.ts
│   │   │   │   │   │   ├── 📄 perplexity.test.ts
│   │   │   │   │   │   ├── 📄 perplexity.ts
│   │   │   │   │   │   └── 📄 research.test.ts
│   │   │   │   │   ├── 📁 meeting-recorder
│   │   │   │   │   │   ├── 📄 draft-meeting-follow-up.ts
│   │   │   │   │   │   ├── 📄 summarize-meeting.test.ts
│   │   │   │   │   │   └── 📄 summarize-meeting.ts
│   │   │   │   │   ├── 📁 reply
│   │   │   │   │   │   ├── 📄 determine-thread-status.test.ts
│   │   │   │   │   │   ├── 📄 determine-thread-status.ts
│   │   │   │   │   │   ├── 📄 draft-attribution.ts
│   │   │   │   │   │   ├── 📄 draft-confidence.test.ts
│   │   │   │   │   │   ├── 📄 draft-confidence.ts
│   │   │   │   │   │   ├── 📄 draft-context-metadata.ts
│   │   │   │   │   │   ├── 📄 draft-follow-up.ts
│   │   │   │   │   │   ├── 📄 draft-reply.formatting.test.ts
│   │   │   │   │   │   ├── 📄 draft-reply.ts
│   │   │   │   │   │   ├── 📄 extract-reply-memories.ts
│   │   │   │   │   │   ├── 📄 generate-nudge.ts
│   │   │   │   │   │   ├── 📄 reply-context-collector.test.ts
│   │   │   │   │   │   ├── 📄 reply-context-collector.ts
│   │   │   │   │   │   ├── 📄 reply-memory.test.ts
│   │   │   │   │   │   ├── 📄 reply-memory.ts
│   │   │   │   │   │   ├── 📄 select-reply-memories.ts
│   │   │   │   │   │   └── 📄 summarize-learned-writing-style.ts
│   │   │   │   │   ├── 📁 report
│   │   │   │   │   │   ├── 📄 analyze-email-behavior.ts
│   │   │   │   │   │   ├── 📄 analyze-label-optimization.ts
│   │   │   │   │   │   ├── 📄 build-user-persona.ts
│   │   │   │   │   │   ├── 📄 fetch.ts
│   │   │   │   │   │   ├── 📄 generate-actionable-recommendations.ts
│   │   │   │   │   │   ├── 📄 generate-executive-summary.ts
│   │   │   │   │   │   ├── 📄 response-patterns.ts
│   │   │   │   │   │   └── 📄 summarize-emails.ts
│   │   │   │   │   ├── 📁 rule
│   │   │   │   │   │   ├── 📄 action-availability.test.ts
│   │   │   │   │   │   ├── 📄 action-availability.ts
│   │   │   │   │   │   ├── 📄 create-rule-schema.test.ts
│   │   │   │   │   │   ├── 📄 create-rule-schema.ts
│   │   │   │   │   │   ├── 📄 prompt-to-rules.ts
│   │   │   │   │   │   └── 📄 rule-condition-descriptions.ts
│   │   │   │   │   ├── 📁 senders
│   │   │   │   │   │   ├── 📄 unsubscribe-page.test.ts
│   │   │   │   │   │   └── 📄 unsubscribe-page.ts
│   │   │   │   │   ├── 📁 split
│   │   │   │   │   │   └── 📄 prompt-to-split.ts
│   │   │   │   │   ├── 📄 action-attachments.test.ts
│   │   │   │   │   ├── 📄 action-attachments.ts
│   │   │   │   │   ├── 📄 actions.test.ts
│   │   │   │   │   ├── 📄 actions.ts
│   │   │   │   │   ├── 📄 automated-archive-exception.test.ts
│   │   │   │   │   ├── 📄 automated-archive-exception.ts
│   │   │   │   │   ├── 📄 content-sanitizer.ts
│   │   │   │   │   ├── 📄 draft-cleanup-settings.ts
│   │   │   │   │   ├── 📄 draft-cleanup.test.ts
│   │   │   │   │   ├── 📄 draft-cleanup.ts
│   │   │   │   │   ├── 📄 executed-action-outcome.ts
│   │   │   │   │   ├── 📄 helpers.test.ts
│   │   │   │   │   ├── 📄 helpers.ts
│   │   │   │   │   ├── 📄 public-contact-context-schema.test.ts
│   │   │   │   │   ├── 📄 public-contact-context-schema.ts
│   │   │   │   │   ├── 📄 public-contact-context-store.test.ts
│   │   │   │   │   ├── 📄 public-contact-context-store.ts
│   │   │   │   │   ├── 📄 public-contact-context.test.ts
│   │   │   │   │   ├── 📄 public-contact-context.ts
│   │   │   │   │   ├── 📄 rule-generated-message.test.ts
│   │   │   │   │   ├── 📄 rule-generated-message.ts
│   │   │   │   │   ├── 📄 security.test.ts
│   │   │   │   │   ├── 📄 security.ts
│   │   │   │   │   ├── 📄 sending-action.ts
│   │   │   │   │   ├── 📄 translate-email.test.ts
│   │   │   │   │   ├── 📄 translate-email.ts
│   │   │   │   │   ├── 📄 types.ts
│   │   │   │   │   └── 📄 web-search.ts
│   │   │   │   ├── 📁 analytics
│   │   │   │   │   ├── 📄 auth-funnel.server.test.ts
│   │   │   │   │   ├── 📄 auth-funnel.server.ts
│   │   │   │   │   ├── 📄 auth-funnel.test.ts
│   │   │   │   │   ├── 📄 auth-funnel.ts
│   │   │   │   │   ├── 📄 client-conversions.test.ts
│   │   │   │   │   ├── 📄 client-conversions.ts
│   │   │   │   │   ├── 📄 client.test.ts
│   │   │   │   │   ├── 📄 client.ts
│   │   │   │   │   ├── 📄 composer-stability.ts
│   │   │   │   │   ├── 📄 conversion-events.ts
│   │   │   │   │   ├── 📄 desktop-health.test.ts
│   │   │   │   │   ├── 📄 desktop-health.ts
│   │   │   │   │   ├── 📄 mail-performance.test.ts
│   │   │   │   │   ├── 📄 mail-performance.ts
│   │   │   │   │   ├── 📄 mail-usage.test.ts
│   │   │   │   │   ├── 📄 mail-usage.ts
│   │   │   │   │   ├── 📄 product.test.ts
│   │   │   │   │   ├── 📄 product.ts
│   │   │   │   │   ├── 📄 rule-events.server.ts
│   │   │   │   │   ├── 📄 server-conversion-events.test.ts
│   │   │   │   │   ├── 📄 server-conversion-events.ts
│   │   │   │   │   ├── 📄 server-conversions.test.ts
│   │   │   │   │   ├── 📄 server-conversions.ts
│   │   │   │   │   └── 📄 summary-flush.ts
│   │   │   │   ├── 📁 attachments
│   │   │   │   │   ├── 📄 download-queue.test.ts
│   │   │   │   │   ├── 📄 download-queue.ts
│   │   │   │   │   ├── 📄 download.test.ts
│   │   │   │   │   ├── 📄 download.ts
│   │   │   │   │   ├── 📄 draft-attachments.ts
│   │   │   │   │   ├── 📄 opened-conversation.test.ts
│   │   │   │   │   ├── 📄 opened-conversation.ts
│   │   │   │   │   ├── 📄 rule.test.ts
│   │   │   │   │   ├── 📄 rule.ts
│   │   │   │   │   └── 📄 source-schema.ts
│   │   │   │   ├── 📁 audit
│   │   │   │   │   ├── 📄 context.test.ts
│   │   │   │   │   ├── 📄 context.ts
│   │   │   │   │   ├── 📄 delivery.test.ts
│   │   │   │   │   ├── 📄 delivery.ts
│   │   │   │   │   ├── 📄 prisma-extension.test.ts
│   │   │   │   │   └── 📄 prisma-extension.ts
│   │   │   │   ├── 📁 auth
│   │   │   │   │   ├── 📄 apple-client-secret.test.ts
│   │   │   │   │   ├── 📄 apple-client-secret.ts
│   │   │   │   │   ├── 📄 cleanup-invalid-tokens.test.ts
│   │   │   │   │   ├── 📄 cleanup-invalid-tokens.ts
│   │   │   │   │   ├── 📄 email-otp-setting.test.ts
│   │   │   │   │   ├── 📄 email-otp-setting.ts
│   │   │   │   │   ├── 📄 email-otp.test.ts
│   │   │   │   │   ├── 📄 email-otp.ts
│   │   │   │   │   ├── 📄 microsoft-account-subject.test.ts
│   │   │   │   │   ├── 📄 microsoft-account-subject.ts
│   │   │   │   │   ├── 📄 provider-account-subject.test.ts
│   │   │   │   │   ├── 📄 rename-email.test.ts
│   │   │   │   │   ├── 📄 rename-email.ts
│   │   │   │   │   ├── 📄 save-tokens.ts
│   │   │   │   │   ├── 📄 scim.test.ts
│   │   │   │   │   ├── 📄 scim.ts
│   │   │   │   │   ├── 📄 sso.test.ts
│   │   │   │   │   └── 📄 sso.ts
│   │   │   │   ├── 📁 automation-jobs
│   │   │   │   │   ├── 📄 cron.test.ts
│   │   │   │   │   ├── 📄 cron.ts
│   │   │   │   │   ├── 📄 defaults.ts
│   │   │   │   │   ├── 📄 describe.ts
│   │   │   │   │   ├── 📄 destination.test.ts
│   │   │   │   │   ├── 📄 destination.ts
│   │   │   │   │   ├── 📄 execute.test.ts
│   │   │   │   │   ├── 📄 execute.ts
│   │   │   │   │   ├── 📄 message.test.ts
│   │   │   │   │   ├── 📄 message.ts
│   │   │   │   │   ├── 📄 messaging-channel.ts
│   │   │   │   │   ├── 📄 messaging.test.ts
│   │   │   │   │   ├── 📄 messaging.ts
│   │   │   │   │   ├── 📄 slack.test.ts
│   │   │   │   │   ├── 📄 slack.ts
│   │   │   │   │   ├── 📄 stale.test.ts
│   │   │   │   │   └── 📄 stale.ts
│   │   │   │   ├── 📁 booking
│   │   │   │   │   ├── 📄 emails.test.ts
│   │   │   │   │   ├── 📄 emails.ts
│   │   │   │   │   ├── 📄 location.ts
│   │   │   │   │   ├── 📄 policy.ts
│   │   │   │   │   ├── 📄 public-rate-limit.test.ts
│   │   │   │   │   ├── 📄 public-rate-limit.ts
│   │   │   │   │   ├── 📄 public.test.ts
│   │   │   │   │   ├── 📄 public.ts
│   │   │   │   │   ├── 📄 slug.test.ts
│   │   │   │   │   └── 📄 slug.ts
│   │   │   │   ├── 📁 bulk-archive
│   │   │   │   │   ├── 📄 get-archive-candidates.test.ts
│   │   │   │   │   └── 📄 get-archive-candidates.ts
│   │   │   │   ├── 📁 bulk-inbox-action
│   │   │   │   │   ├── 📄 enqueue.ts
│   │   │   │   │   ├── 📄 process-job.test.ts
│   │   │   │   │   ├── 📄 process-job.ts
│   │   │   │   │   ├── 📄 resume-stalled-job.test.ts
│   │   │   │   │   ├── 📄 resume-stalled-job.ts
│   │   │   │   │   ├── 📄 search.ts
│   │   │   │   │   └── 📄 validation.ts
│   │   │   │   ├── 📁 calendar
│   │   │   │   │   ├── 📁 invitations
│   │   │   │   │   │   ├── 📄 constants.ts
│   │   │   │   │   │   ├── 📄 content.ts
│   │   │   │   │   │   ├── 📄 detection.test.ts
│   │   │   │   │   │   ├── 📄 detection.ts
│   │   │   │   │   │   ├── 📄 format-time.test.ts
│   │   │   │   │   │   ├── 📄 format-time.ts
│   │   │   │   │   │   ├── 📄 parser.test.ts
│   │   │   │   │   │   ├── 📄 parser.ts
│   │   │   │   │   │   ├── 📄 providers.test.ts
│   │   │   │   │   │   ├── 📄 service.test.ts
│   │   │   │   │   │   └── 📄 service.ts
│   │   │   │   │   ├── 📁 providers
│   │   │   │   │   │   ├── 📄 google-availability.test.ts
│   │   │   │   │   │   ├── 📄 google-availability.ts
│   │   │   │   │   │   ├── 📄 google-calendar-id.ts
│   │   │   │   │   │   ├── 📄 google-events.test.ts
│   │   │   │   │   │   ├── 📄 google-events.ts
│   │   │   │   │   │   ├── 📄 google.test.ts
│   │   │   │   │   │   ├── 📄 google.ts
│   │   │   │   │   │   ├── 📄 microsoft-availability.test.ts
│   │   │   │   │   │   ├── 📄 microsoft-availability.ts
│   │   │   │   │   │   ├── 📄 microsoft-events.test.ts
│   │   │   │   │   │   ├── 📄 microsoft-events.ts
│   │   │   │   │   │   ├── 📄 microsoft.test.ts
│   │   │   │   │   │   └── 📄 microsoft.ts
│   │   │   │   │   ├── 📄 availability-error.test.ts
│   │   │   │   │   ├── 📄 availability-error.ts
│   │   │   │   │   ├── 📄 availability-types.ts
│   │   │   │   │   ├── 📄 client.test.ts
│   │   │   │   │   ├── 📄 client.ts
│   │   │   │   │   ├── 📄 constants.ts
│   │   │   │   │   ├── 📄 event-provider.ts
│   │   │   │   │   ├── 📄 event-types.ts
│   │   │   │   │   ├── 📄 event-writer.test.ts
│   │   │   │   │   ├── 📄 event-writer.ts
│   │   │   │   │   ├── 📄 fetch-events-in-window.test.ts
│   │   │   │   │   ├── 📄 fetch-events-in-window.ts
│   │   │   │   │   ├── 📄 handle-calendar-callback.test.ts
│   │   │   │   │   ├── 📄 handle-calendar-callback.ts
│   │   │   │   │   ├── 📄 oauth-callback-helpers.test.ts
│   │   │   │   │   ├── 📄 oauth-callback-helpers.ts
│   │   │   │   │   ├── 📄 oauth-types.ts
│   │   │   │   │   ├── 📄 save-calendar-tokens.ts
│   │   │   │   │   ├── 📄 timezone-helpers.test.ts
│   │   │   │   │   ├── 📄 timezone-helpers.ts
│   │   │   │   │   ├── 📄 unified-availability.test.ts
│   │   │   │   │   ├── 📄 unified-availability.ts
│   │   │   │   │   ├── 📄 video-conference-link.test.ts
│   │   │   │   │   └── 📄 video-conference-link.ts
│   │   │   │   ├── 📁 categorize
│   │   │   │   │   └── 📁 senders
│   │   │   │   │       ├── 📄 archive-category.test.ts
│   │   │   │   │       ├── 📄 archive-category.ts
│   │   │   │   │       ├── 📄 batch-validation.ts
│   │   │   │   │       ├── 📄 categorize.test.ts
│   │   │   │   │       ├── 📄 categorize.ts
│   │   │   │   │       ├── 📄 get-category-overview.test.ts
│   │   │   │   │       ├── 📄 get-category-overview.ts
│   │   │   │   │       ├── 📄 get-senders.ts
│   │   │   │   │       ├── 📄 get-uncategorized-senders.test.ts
│   │   │   │   │       ├── 📄 get-uncategorized-senders.ts
│   │   │   │   │       ├── 📄 start-bulk-categorization.test.ts
│   │   │   │   │       └── 📄 start-bulk-categorization.ts
│   │   │   │   ├── 📁 chat
│   │   │   │   │   ├── 📄 active-run.test.ts
│   │   │   │   │   ├── 📄 active-run.ts
│   │   │   │   │   ├── 📄 soft-delete.test.ts
│   │   │   │   │   └── 📄 soft-delete.ts
│   │   │   │   ├── 📁 cold-email
│   │   │   │   │   ├── 📄 cold-email-blocker-enabled.ts
│   │   │   │   │   ├── 📄 cold-email-rule.ts
│   │   │   │   │   ├── 📄 exclude-replied-sender.test.ts
│   │   │   │   │   ├── 📄 exclude-replied-sender.ts
│   │   │   │   │   ├── 📄 has-prior-contact.test.ts
│   │   │   │   │   ├── 📄 has-prior-contact.ts
│   │   │   │   │   ├── 📄 has-user-sent-email.test.ts
│   │   │   │   │   ├── 📄 has-user-sent-email.ts
│   │   │   │   │   ├── 📄 is-cold-email.test.ts
│   │   │   │   │   ├── 📄 is-cold-email.ts
│   │   │   │   │   ├── 📄 prompt.ts
│   │   │   │   │   ├── 📄 send-notification.test.ts
│   │   │   │   │   └── 📄 send-notification.ts
│   │   │   │   ├── 📁 constants
│   │   │   │   │   └── 📄 user-roles.ts
│   │   │   │   ├── 📁 decision-model
│   │   │   │   │   ├── 📄 categorize-sender.test.ts
│   │   │   │   │   ├── 📄 categorize-sender.ts
│   │   │   │   │   ├── 📄 choose-rule.test.ts
│   │   │   │   │   ├── 📄 choose-rule.ts
│   │   │   │   │   ├── 📄 cold-email.test.ts
│   │   │   │   │   ├── 📄 cold-email.ts
│   │   │   │   │   ├── 📄 decision-model.test.ts
│   │   │   │   │   ├── 📄 decision-model.ts
│   │   │   │   │   ├── 📄 email-state.ts
│   │   │   │   │   ├── 📄 recurring-pattern.test.ts
│   │   │   │   │   ├── 📄 recurring-pattern.ts
│   │   │   │   │   ├── 📄 reply-memory-selection.test.ts
│   │   │   │   │   ├── 📄 reply-memory-selection.ts
│   │   │   │   │   ├── 📄 system-one.test.ts
│   │   │   │   │   ├── 📄 system-one.ts
│   │   │   │   │   ├── 📄 thread-status.test.ts
│   │   │   │   │   ├── 📄 thread-status.ts
│   │   │   │   │   ├── 📄 unsubscribe-page.test.ts
│   │   │   │   │   └── 📄 unsubscribe-page.ts
│   │   │   │   ├── 📁 desktop
│   │   │   │   │   ├── 📄 desktop-version.test.ts
│   │   │   │   │   ├── 📄 desktop-version.ts
│   │   │   │   │   ├── 📄 github-release.test.ts
│   │   │   │   │   └── 📄 github-release.ts
│   │   │   │   ├── 📁 digest
│   │   │   │   │   ├── 📄 claim-pending-digests.ts
│   │   │   │   │   ├── 📄 delivery-state.test.ts
│   │   │   │   │   ├── 📄 delivery-state.ts
│   │   │   │   │   ├── 📄 format.ts
│   │   │   │   │   ├── 📄 index.ts
│   │   │   │   │   ├── 📄 schedule.test.ts
│   │   │   │   │   ├── 📄 schedule.ts
│   │   │   │   │   ├── 📄 send-digest.test.ts
│   │   │   │   │   ├── 📄 send-digest.ts
│   │   │   │   │   ├── 📄 summary-limit.test.ts
│   │   │   │   │   └── 📄 summary-limit.ts
│   │   │   │   ├── 📁 dlp
│   │   │   │   │   ├── 📄 policy.server.test.ts
│   │   │   │   │   ├── 📄 policy.server.ts
│   │   │   │   │   ├── 📄 sensitive-content.test.ts
│   │   │   │   │   └── 📄 sensitive-content.ts
│   │   │   │   ├── 📁 docs-sources
│   │   │   │   │   ├── 📄 docs-index.test.ts
│   │   │   │   │   ├── 📄 docs-index.ts
│   │   │   │   │   ├── 📄 fetch-docs.test.ts
│   │   │   │   │   ├── 📄 fetch-docs.ts
│   │   │   │   │   ├── 📄 page-text.ts
│   │   │   │   │   ├── 📄 url.test.ts
│   │   │   │   │   └── 📄 url.ts
│   │   │   │   ├── 📁 drive
│   │   │   │   │   ├── 📁 providers
│   │   │   │   │   │   ├── 📄 google.ts
│   │   │   │   │   │   ├── 📄 microsoft.test.ts
│   │   │   │   │   │   └── 📄 microsoft.ts
│   │   │   │   │   ├── 📄 client.test.ts
│   │   │   │   │   ├── 📄 client.ts
│   │   │   │   │   ├── 📄 constants.ts
│   │   │   │   │   ├── 📄 document-extraction.test.ts
│   │   │   │   │   ├── 📄 document-extraction.ts
│   │   │   │   │   ├── 📄 filing-engine.test.ts
│   │   │   │   │   ├── 📄 filing-engine.ts
│   │   │   │   │   ├── 📄 filing-messaging-notifications.test.ts
│   │   │   │   │   ├── 📄 filing-messaging-notifications.ts
│   │   │   │   │   ├── 📄 filing-notifications.test.ts
│   │   │   │   │   ├── 📄 filing-notifications.ts
│   │   │   │   │   ├── 📄 folder-utils.test.ts
│   │   │   │   │   ├── 📄 folder-utils.ts
│   │   │   │   │   ├── 📄 handle-drive-callback.ts
│   │   │   │   │   ├── 📄 handle-filing-reply.test.ts
│   │   │   │   │   ├── 📄 handle-filing-reply.ts
│   │   │   │   │   ├── 📄 process-filing-attachments.test.ts
│   │   │   │   │   ├── 📄 process-filing-attachments.ts
│   │   │   │   │   ├── 📄 provider.ts
│   │   │   │   │   ├── 📄 scopes.ts
│   │   │   │   │   ├── 📄 source-items.test.ts
│   │   │   │   │   ├── 📄 source-items.ts
│   │   │   │   │   ├── 📄 types.ts
│   │   │   │   │   ├── 📄 url.test.ts
│   │   │   │   │   └── 📄 url.ts
│   │   │   │   ├── 📁 email
│   │   │   │   │   ├── 📁 sent-message-open
│   │   │   │   │   │   ├── 📄 sent-message-open.server.test.ts
│   │   │   │   │   │   ├── 📄 sent-message-open.server.ts
│   │   │   │   │   │   ├── 📄 sent-message-open.test.ts
│   │   │   │   │   │   └── 📄 sent-message-open.ts
│   │   │   │   │   ├── 📄 bulk-action-tracking.ts
│   │   │   │   │   ├── 📄 complete-thread.test.ts
│   │   │   │   │   ├── 📄 complete-thread.ts
│   │   │   │   │   ├── 📄 compose-draft.test.ts
│   │   │   │   │   ├── 📄 compose-draft.ts
│   │   │   │   │   ├── 📄 compose-signature.test.ts
│   │   │   │   │   ├── 📄 compose-signature.ts
│   │   │   │   │   ├── 📄 connected-accounts.test.ts
│   │   │   │   │   ├── 📄 connected-accounts.ts
│   │   │   │   │   ├── 📄 contact.test.ts
│   │   │   │   │   ├── 📄 contact.ts
│   │   │   │   │   ├── 📄 default-signature.ts
│   │   │   │   │   ├── 📄 draft-attachment-upload.test.ts
│   │   │   │   │   ├── 📄 draft-attachment-upload.ts
│   │   │   │   │   ├── 📄 draft-recipients.test.ts
│   │   │   │   │   ├── 📄 draft-recipients.ts
│   │   │   │   │   ├── 📄 durable-email-send.test.ts
│   │   │   │   │   ├── 📄 durable-email-send.ts
│   │   │   │   │   ├── 📄 durable-email-send.validation.ts
│   │   │   │   │   ├── 📄 email-send-operation.ts
│   │   │   │   │   ├── 📄 forward-message.ts
│   │   │   │   │   ├── 📄 get-formatted-sender-address.ts
│   │   │   │   │   ├── 📄 google.test.ts
│   │   │   │   │   ├── 📄 google.ts
│   │   │   │   │   ├── 📄 image-proxy-config.test.ts
│   │   │   │   │   ├── 📄 image-proxy-config.ts
│   │   │   │   │   ├── 📄 image-proxy.server.test.ts
│   │   │   │   │   ├── 📄 image-proxy.server.ts
│   │   │   │   │   ├── 📄 inline-image-cache.ts
│   │   │   │   │   ├── 📄 is-provider-rate-limit-error.test.ts
│   │   │   │   │   ├── 📄 is-provider-rate-limit-error.ts
│   │   │   │   │   ├── 📄 latest-message.test.ts
│   │   │   │   │   ├── 📄 latest-message.ts
│   │   │   │   │   ├── 📄 local-mail-sync-adapters.test.ts
│   │   │   │   │   ├── 📄 local-mail-sync-budget.test.ts
│   │   │   │   │   ├── 📄 local-mail-sync-budget.ts
│   │   │   │   │   ├── 📄 local-mail-sync-types.ts
│   │   │   │   │   ├── 📄 local-mail-sync.test.ts
│   │   │   │   │   ├── 📄 local-mail-sync.ts
│   │   │   │   │   ├── 📄 mailbox-sync.test.ts
│   │   │   │   │   ├── 📄 mailbox-sync.ts
│   │   │   │   │   ├── 📄 message-timestamp.test.ts
│   │   │   │   │   ├── 📄 message-timestamp.ts
│   │   │   │   │   ├── 📄 microsoft.test.ts
│   │   │   │   │   ├── 📄 microsoft.ts
│   │   │   │   │   ├── 📄 notify-lapsed-watches.test.ts
│   │   │   │   │   ├── 📄 notify-lapsed-watches.ts
│   │   │   │   │   ├── 📄 outgoing-inline-images.test.ts
│   │   │   │   │   ├── 📄 outgoing-inline-images.ts
│   │   │   │   │   ├── 📄 parse-message-reply.test.ts
│   │   │   │   │   ├── 📄 parse-message-reply.ts
│   │   │   │   │   ├── 📄 prepare-html.client.test.ts
│   │   │   │   │   ├── 📄 prepare-html.client.ts
│   │   │   │   │   ├── 📄 preserved-blocks.ts
│   │   │   │   │   ├── 📄 provider-health.test.ts
│   │   │   │   │   ├── 📄 provider-health.ts
│   │   │   │   │   ├── 📄 provider-types.ts
│   │   │   │   │   ├── 📄 provider.test.ts
│   │   │   │   │   ├── 📄 provider.ts
│   │   │   │   │   ├── 📄 quoted-plain-text.test.ts
│   │   │   │   │   ├── 📄 quoted-plain-text.ts
│   │   │   │   │   ├── 📄 rate-limit-mode-error.ts
│   │   │   │   │   ├── 📄 rate-limit.test.ts
│   │   │   │   │   ├── 📄 rate-limit.ts
│   │   │   │   │   ├── 📄 read-compose-draft.test.ts
│   │   │   │   │   ├── 📄 read-compose-draft.ts
│   │   │   │   │   ├── 📄 render-safe-links.test.ts
│   │   │   │   │   ├── 📄 render-safe-links.ts
│   │   │   │   │   ├── 📄 reply-all.test.ts
│   │   │   │   │   ├── 📄 reply-all.ts
│   │   │   │   │   ├── 📄 reply-body-html.ts
│   │   │   │   │   ├── 📄 reply-body.test.ts
│   │   │   │   │   ├── 📄 reply-body.ts
│   │   │   │   │   ├── 📄 reply-quote.ts
│   │   │   │   │   ├── 📄 rewrite-html.test.ts
│   │   │   │   │   ├── 📄 rewrite-html.ts
│   │   │   │   │   ├── 📄 send-as.test.ts
│   │   │   │   │   ├── 📄 send-as.ts
│   │   │   │   │   ├── 📄 send-notification-email.ts
│   │   │   │   │   ├── 📄 send-operation-policy.ts
│   │   │   │   │   ├── 📄 sent-message-id.ts
│   │   │   │   │   ├── 📄 sent-signatures.test.ts
│   │   │   │   │   ├── 📄 sent-signatures.ts
│   │   │   │   │   ├── 📄 sent-with-footer.ts
│   │   │   │   │   ├── 📄 signature-extraction.test.ts
│   │   │   │   │   ├── 📄 signature-extraction.ts
│   │   │   │   │   ├── 📄 signature-normalization.test.ts
│   │   │   │   │   ├── 📄 signature-normalization.ts
│   │   │   │   │   ├── 📄 signature-suggestions.test.ts
│   │   │   │   │   ├── 📄 signature-suggestions.ts
│   │   │   │   │   ├── 📄 split-email-content.client.test.ts
│   │   │   │   │   ├── 📄 split-email-content.client.ts
│   │   │   │   │   ├── 📄 subject.test.ts
│   │   │   │   │   ├── 📄 subject.ts
│   │   │   │   │   ├── 📄 thread-not-found.ts
│   │   │   │   │   ├── 📄 threading.test.ts
│   │   │   │   │   ├── 📄 threading.ts
│   │   │   │   │   ├── 📄 types.ts
│   │   │   │   │   ├── 📄 watch-manager.test.ts
│   │   │   │   │   ├── 📄 watch-manager.ts
│   │   │   │   │   └── 📄 whitelist.ts
│   │   │   │   ├── 📁 error-messages
│   │   │   │   │   ├── 📄 index.test.ts
│   │   │   │   │   └── 📄 index.ts
│   │   │   │   ├── 📁 filebot
│   │   │   │   │   ├── 📄 is-filebot-email.test.ts
│   │   │   │   │   └── 📄 is-filebot-email.ts
│   │   │   │   ├── 📁 follow-up
│   │   │   │   │   ├── 📄 cleanup.test.ts
│   │   │   │   │   ├── 📄 cleanup.ts
│   │   │   │   │   ├── 📄 copy.test.ts
│   │   │   │   │   ├── 📄 copy.ts
│   │   │   │   │   ├── 📄 follow-up-actions.test.ts
│   │   │   │   │   ├── 📄 follow-up-actions.ts
│   │   │   │   │   ├── 📄 generate-draft.test.ts
│   │   │   │   │   ├── 📄 generate-draft.ts
│   │   │   │   │   ├── 📄 labels.test.ts
│   │   │   │   │   ├── 📄 labels.ts
│   │   │   │   │   ├── 📄 notification-deliveries.ts
│   │   │   │   │   ├── 📄 process.test.ts
│   │   │   │   │   ├── 📄 process.ts
│   │   │   │   │   ├── 📄 send-follow-up-notification.test.ts
│   │   │   │   │   └── 📄 send-follow-up-notification.ts
│   │   │   │   ├── 📁 gmail
│   │   │   │   │   ├── 📄 attachment-provider-stream.test.ts
│   │   │   │   │   ├── 📄 attachment-stream.test.ts
│   │   │   │   │   ├── 📄 attachment-stream.ts
│   │   │   │   │   ├── 📄 attachment.ts
│   │   │   │   │   ├── 📄 batch-with-retry.ts
│   │   │   │   │   ├── 📄 batch.test.ts
│   │   │   │   │   ├── 📄 batch.ts
│   │   │   │   │   ├── 📄 client.test.ts
│   │   │   │   │   ├── 📄 client.ts
│   │   │   │   │   ├── 📄 complete-thread.test.ts
│   │   │   │   │   ├── 📄 constants.ts
│   │   │   │   │   ├── 📄 contact.test.ts
│   │   │   │   │   ├── 📄 contact.ts
│   │   │   │   │   ├── 📄 decode.test.ts
│   │   │   │   │   ├── 📄 decode.ts
│   │   │   │   │   ├── 📄 draft-attachments.test.ts
│   │   │   │   │   ├── 📄 draft-attachments.ts
│   │   │   │   │   ├── 📄 draft-send.test.ts
│   │   │   │   │   ├── 📄 draft.test.ts
│   │   │   │   │   ├── 📄 draft.ts
│   │   │   │   │   ├── 📄 embedded-inline.test.ts
│   │   │   │   │   ├── 📄 filter.test.ts
│   │   │   │   │   ├── 📄 filter.ts
│   │   │   │   │   ├── 📄 forward.test.ts
│   │   │   │   │   ├── 📄 forward.ts
│   │   │   │   │   ├── 📄 history.ts
│   │   │   │   │   ├── 📄 label-colors.ts
│   │   │   │   │   ├── 📄 label-validation.test.ts
│   │   │   │   │   ├── 📄 label-validation.ts
│   │   │   │   │   ├── 📄 label.test.ts
│   │   │   │   │   ├── 📄 label.ts
│   │   │   │   │   ├── 📄 local-mail-sync.test.ts
│   │   │   │   │   ├── 📄 local-mail-sync.ts
│   │   │   │   │   ├── 📄 mail-send.test.ts
│   │   │   │   │   ├── 📄 mail.test.ts
│   │   │   │   │   ├── 📄 mail.ts
│   │   │   │   │   ├── 📄 mailbox-sync.test.ts
│   │   │   │   │   ├── 📄 mailbox-sync.ts
│   │   │   │   │   ├── 📄 message-bodies.bench.ts
│   │   │   │   │   ├── 📄 message-bodies.test.ts
│   │   │   │   │   ├── 📄 message-bodies.ts
│   │   │   │   │   ├── 📄 message.test.ts
│   │   │   │   │   ├── 📄 message.ts
│   │   │   │   │   ├── 📄 oauth.test.ts
│   │   │   │   │   ├── 📄 oauth.ts
│   │   │   │   │   ├── 📄 permissions.test.ts
│   │   │   │   │   ├── 📄 permissions.ts
│   │   │   │   │   ├── 📄 reply.test.ts
│   │   │   │   │   ├── 📄 reply.ts
│   │   │   │   │   ├── 📄 resumable-draft-upload.ts
│   │   │   │   │   ├── 📄 retry.test.ts
│   │   │   │   │   ├── 📄 retry.ts
│   │   │   │   │   ├── 📄 scopes.test.ts
│   │   │   │   │   ├── 📄 scopes.ts
│   │   │   │   │   ├── 📄 settings.ts
│   │   │   │   │   ├── 📄 signature-settings.ts
│   │   │   │   │   ├── 📄 snippet.test.ts
│   │   │   │   │   ├── 📄 snippet.ts
│   │   │   │   │   ├── 📄 spam.test.ts
│   │   │   │   │   ├── 📄 spam.ts
│   │   │   │   │   ├── 📄 sync-messages.test.ts
│   │   │   │   │   ├── 📄 sync-messages.ts
│   │   │   │   │   ├── 📄 thread.test.ts
│   │   │   │   │   ├── 📄 thread.ts
│   │   │   │   │   ├── 📄 trash.ts
│   │   │   │   │   ├── 📄 watch.test.ts
│   │   │   │   │   └── 📄 watch.ts
│   │   │   │   ├── 📁 group
│   │   │   │   │   ├── 📄 find-matching-group.test.ts
│   │   │   │   │   ├── 📄 find-matching-group.ts
│   │   │   │   │   ├── 📄 group-item.test.ts
│   │   │   │   │   └── 📄 group-item.ts
│   │   │   │   ├── 📁 i18n
│   │   │   │   │   ├── 📄 date-fns-locale.ts
│   │   │   │   │   ├── 📄 landing.test.ts
│   │   │   │   │   ├── 📄 landing.ts
│   │   │   │   │   ├── 📄 locales.ts
│   │   │   │   │   ├── 📄 macro-compile.test.ts
│   │   │   │   │   ├── 📄 server.test.ts
│   │   │   │   │   └── 📄 server.ts
│   │   │   │   ├── 📁 label
│   │   │   │   │   ├── 📄 apply-label-to-thread.ts
│   │   │   │   │   ├── 📄 apply-thread-labels.test.ts
│   │   │   │   │   ├── 📄 apply-thread-labels.ts
│   │   │   │   │   ├── 📄 compare-labels.test.ts
│   │   │   │   │   ├── 📄 compare-labels.ts
│   │   │   │   │   ├── 📄 find-label-by-name.test.ts
│   │   │   │   │   ├── 📄 find-label-by-name.ts
│   │   │   │   │   ├── 📄 find-nested-label-matches.ts
│   │   │   │   │   ├── 📄 normalize-label-name.test.ts
│   │   │   │   │   ├── 📄 normalize-label-name.ts
│   │   │   │   │   ├── 📄 reset-label-colors.test.ts
│   │   │   │   │   ├── 📄 reset-label-colors.ts
│   │   │   │   │   ├── 📄 resolve-label.test.ts
│   │   │   │   │   └── 📄 resolve-label.ts
│   │   │   │   ├── 📁 llms
│   │   │   │   │   ├── 📄 caching.test.ts
│   │   │   │   │   ├── 📄 caching.ts
│   │   │   │   │   ├── 📄 cli-provider.test.ts
│   │   │   │   │   ├── 📄 cli-provider.ts
│   │   │   │   │   ├── 📄 config.ts
│   │   │   │   │   ├── 📄 fallback.test.ts
│   │   │   │   │   ├── 📄 index.generate-object.test.ts
│   │   │   │   │   ├── 📄 index.handle-error.test.ts
│   │   │   │   │   ├── 📄 index.openrouter-cost.test.ts
│   │   │   │   │   ├── 📄 index.test.ts
│   │   │   │   │   ├── 📄 index.tool-call-agent-stream.test.ts
│   │   │   │   │   ├── 📄 index.ts
│   │   │   │   │   ├── 📄 model-id.ts
│   │   │   │   │   ├── 📄 model-usage-guard.test.ts
│   │   │   │   │   ├── 📄 model-usage-guard.ts
│   │   │   │   │   ├── 📄 model.test.ts
│   │   │   │   │   ├── 📄 model.ts
│   │   │   │   │   ├── 📄 ollama-guidance.ts
│   │   │   │   │   ├── 📄 pricing.generated.ts
│   │   │   │   │   ├── 📄 retry.test.ts
│   │   │   │   │   ├── 📄 retry.ts
│   │   │   │   │   ├── 📄 sensitive-content.test.ts
│   │   │   │   │   ├── 📄 sensitive-content.ts
│   │   │   │   │   ├── 📄 strict-optional.test.ts
│   │   │   │   │   ├── 📄 strict-optional.ts
│   │   │   │   │   ├── 📄 supported-model-pricing.ts
│   │   │   │   │   ├── 📄 types.ts
│   │   │   │   │   ├── 📄 use-cases.test.ts
│   │   │   │   │   └── 📄 use-cases.ts
│   │   │   │   ├── 📁 mail-api
│   │   │   │   │   ├── 📄 assistant-state.test.ts
│   │   │   │   │   ├── 📄 assistant-state.ts
│   │   │   │   │   ├── 📄 authorization.test.ts
│   │   │   │   │   ├── 📄 authorization.ts
│   │   │   │   │   ├── 📄 observations.test.ts
│   │   │   │   │   ├── 📄 observations.ts
│   │   │   │   │   ├── 📄 operations.test.ts
│   │   │   │   │   ├── 📄 operations.ts
│   │   │   │   │   ├── 📄 source.test.ts
│   │   │   │   │   ├── 📄 source.ts
│   │   │   │   │   └── 📄 splits.ts
│   │   │   │   ├── 📁 mail-engine
│   │   │   │   │   ├── 📄 MailEngineConnectionBanner.tsx
│   │   │   │   │   ├── 📄 MailEngineHost.test.tsx
│   │   │   │   │   ├── 📄 MailEngineHost.tsx
│   │   │   │   │   ├── 📄 active-client.test.ts
│   │   │   │   │   ├── 📄 active-client.ts
│   │   │   │   │   ├── 📄 admission-notice.test.ts
│   │   │   │   │   ├── 📄 admission-notice.ts
│   │   │   │   │   ├── 📄 clear-local-mail-account.test.ts
│   │   │   │   │   ├── 📄 clear-local-mail-account.ts
│   │   │   │   │   ├── 📄 command-status.test.ts
│   │   │   │   │   ├── 📄 command-status.ts
│   │   │   │   │   ├── 📄 connection-notice.test.ts
│   │   │   │   │   ├── 📄 connection-notice.ts
│   │   │   │   │   ├── 📄 conversation-thread.test.ts
│   │   │   │   │   ├── 📄 conversation-thread.ts
│   │   │   │   │   ├── 📄 coverage.test.ts
│   │   │   │   │   ├── 📄 coverage.ts
│   │   │   │   │   ├── 📄 create-browser-engine.test.ts
│   │   │   │   │   ├── 📄 create-browser-engine.ts
│   │   │   │   │   ├── 📄 desktop-ipc.test.ts
│   │   │   │   │   ├── 📄 desktop-ipc.ts
│   │   │   │   │   ├── 📄 discard-mailbox-draft.test.ts
│   │   │   │   │   ├── 📄 discard-mailbox-draft.ts
│   │   │   │   │   ├── 📄 draft-content.test.ts
│   │   │   │   │   ├── 📄 draft-content.ts
│   │   │   │   │   ├── 📄 engine-delivery.test.ts
│   │   │   │   │   ├── 📄 engine-delivery.ts
│   │   │   │   │   ├── 📄 engine-worker.ts
│   │   │   │   │   ├── 📄 follow-mailbox-changes.test.ts
│   │   │   │   │   ├── 📄 follow-mailbox-changes.ts
│   │   │   │   │   ├── 📄 http.test.ts
│   │   │   │   │   ├── 📄 http.ts
│   │   │   │   │   ├── 📄 label-count-targets.test.ts
│   │   │   │   │   ├── 📄 label-count-targets.ts
│   │   │   │   │   ├── 📄 list-thread.test.ts
│   │   │   │   │   ├── 📄 list-thread.ts
│   │   │   │   │   ├── 📄 mutation-change.test.ts
│   │   │   │   │   ├── 📄 mutation-change.ts
│   │   │   │   │   ├── 📄 owner-lock.test.ts
│   │   │   │   │   ├── 📄 owner-lock.ts
│   │   │   │   │   ├── 📄 reply-drafts.test.ts
│   │   │   │   │   ├── 📄 reply-drafts.ts
│   │   │   │   │   ├── 📄 runtime-mode.test.ts
│   │   │   │   │   ├── 📄 runtime-mode.ts
│   │   │   │   │   ├── 📄 startup-error.ts
│   │   │   │   │   ├── 📄 startup-failure.test.ts
│   │   │   │   │   ├── 📄 startup-failure.ts
│   │   │   │   │   ├── 📄 storage-pressure.test.ts
│   │   │   │   │   ├── 📄 storage-pressure.ts
│   │   │   │   │   ├── 📄 submit-conversations.test.ts
│   │   │   │   │   ├── 📄 submit-conversations.ts
│   │   │   │   │   ├── 📄 tab-channel.test.ts
│   │   │   │   │   ├── 📄 tab-channel.ts
│   │   │   │   │   ├── 📄 thread-mail-mutations.test.ts
│   │   │   │   │   ├── 📄 thread-mail-mutations.ts
│   │   │   │   │   ├── 📄 threads-query.test.ts
│   │   │   │   │   ├── 📄 threads-query.ts
│   │   │   │   │   ├── 📄 wasm-sqlite-startup.test.ts
│   │   │   │   │   ├── 📄 wasm-sqlite.test.ts
│   │   │   │   │   ├── 📄 wasm-sqlite.ts
│   │   │   │   │   ├── 📄 wipe-local-mailbox.test.ts
│   │   │   │   │   ├── 📄 wipe-local-mailbox.ts
│   │   │   │   │   ├── 📄 worker-protocol.test.ts
│   │   │   │   │   ├── 📄 worker-protocol.ts
│   │   │   │   │   ├── 📄 worker-session.test.ts
│   │   │   │   │   └── 📄 worker-session.ts
│   │   │   │   ├── 📁 mcp
│   │   │   │   │   ├── 📁 providers
│   │   │   │   │   │   ├── 📄 composio.test.ts
│   │   │   │   │   │   ├── 📄 composio.ts
│   │   │   │   │   │   ├── 📄 registry.ts
│   │   │   │   │   │   └── 📄 types.ts
│   │   │   │   │   ├── 📄 access.ts
│   │   │   │   │   ├── 📄 account-selection.test.ts
│   │   │   │   │   ├── 📄 account-selection.ts
│   │   │   │   │   ├── 📄 call-tool.test.ts
│   │   │   │   │   ├── 📄 call-tool.ts
│   │   │   │   │   ├── 📄 config.test.ts
│   │   │   │   │   ├── 📄 config.ts
│   │   │   │   │   ├── 📄 connections.test.ts
│   │   │   │   │   ├── 📄 connections.ts
│   │   │   │   │   ├── 📄 email-tools.test.ts
│   │   │   │   │   ├── 📄 email-tools.ts
│   │   │   │   │   ├── 📄 http.test.ts
│   │   │   │   │   ├── 📄 http.ts
│   │   │   │   │   ├── 📄 integrations.ts
│   │   │   │   │   ├── 📄 list-tools.ts
│   │   │   │   │   ├── 📄 mail-client-bundle.ts
│   │   │   │   │   ├── 📄 mail-client-contract.ts
│   │   │   │   │   ├── 📄 mail-client-ui.ts
│   │   │   │   │   ├── 📄 mail-client.test.ts
│   │   │   │   │   ├── 📄 mail-client.ts
│   │   │   │   │   ├── 📄 oauth-flow.test.ts
│   │   │   │   │   ├── 📄 oauth-grant.test.ts
│   │   │   │   │   ├── 📄 oauth-provider.ts
│   │   │   │   │   ├── 📄 oauth-registration.test.ts
│   │   │   │   │   ├── 📄 oauth-registration.ts
│   │   │   │   │   ├── 📄 oauth.test.ts
│   │   │   │   │   ├── 📄 oauth.ts
│   │   │   │   │   ├── 📄 rate-limit.ts
│   │   │   │   │   ├── 📄 resolve-integration.ts
│   │   │   │   │   ├── 📄 safe-fetch.test.ts
│   │   │   │   │   ├── 📄 safe-fetch.ts
│   │   │   │   │   ├── 📄 server-connection.ts
│   │   │   │   │   ├── 📄 server-transport.test.ts
│   │   │   │   │   ├── 📄 server-url.ts
│   │   │   │   │   ├── 📄 server.test.ts
│   │   │   │   │   ├── 📄 server.ts
│   │   │   │   │   ├── 📄 sync-tools.test.ts
│   │   │   │   │   ├── 📄 sync-tools.ts
│   │   │   │   │   ├── 📄 tier-access.ts
│   │   │   │   │   ├── 📄 tool-name.ts
│   │   │   │   │   ├── 📄 tool-specs-messages.ts
│   │   │   │   │   ├── 📄 tool-specs.test.ts
│   │   │   │   │   ├── 📄 tool-specs.ts
│   │   │   │   │   ├── 📄 transport.ts
│   │   │   │   │   ├── 📄 verify-token.test.ts
│   │   │   │   │   └── 📄 verify-token.ts
│   │   │   │   ├── 📁 meeting-briefs
│   │   │   │   │   ├── 📄 attendees.test.ts
│   │   │   │   │   ├── 📄 attendees.ts
│   │   │   │   │   ├── 📄 fetch-upcoming-events.test.ts
│   │   │   │   │   ├── 📄 fetch-upcoming-events.ts
│   │   │   │   │   ├── 📄 gather-context.test.ts
│   │   │   │   │   ├── 📄 gather-context.ts
│   │   │   │   │   ├── 📄 process.ts
│   │   │   │   │   ├── 📄 recipient-context.test.ts
│   │   │   │   │   ├── 📄 recipient-context.ts
│   │   │   │   │   ├── 📄 send-briefing.test.ts
│   │   │   │   │   └── 📄 send-briefing.ts
│   │   │   │   ├── 📁 meeting-recorder
│   │   │   │   │   ├── 📄 attendees.test.ts
│   │   │   │   │   ├── 📄 attendees.ts
│   │   │   │   │   ├── 📄 bot-provider.test.ts
│   │   │   │   │   ├── 📄 bot-provider.ts
│   │   │   │   │   ├── 📄 config.ts
│   │   │   │   │   ├── 📄 create-bot-provider.ts
│   │   │   │   │   ├── 📄 delete-media.test.ts
│   │   │   │   │   ├── 📄 delete-media.ts
│   │   │   │   │   ├── 📄 enqueue-processing.ts
│   │   │   │   │   ├── 📄 join-rule.test.ts
│   │   │   │   │   ├── 📄 join-rule.ts
│   │   │   │   │   ├── 📄 normalize-meeting-url.test.ts
│   │   │   │   │   ├── 📄 normalize-meeting-url.ts
│   │   │   │   │   ├── 📄 process-meeting.test.ts
│   │   │   │   │   ├── 📄 process-meeting.ts
│   │   │   │   │   ├── 📄 reconcile.test.ts
│   │   │   │   │   ├── 📄 reconcile.ts
│   │   │   │   │   ├── 📄 recording-lifecycle.test.ts
│   │   │   │   │   ├── 📄 recording-lifecycle.ts
│   │   │   │   │   ├── 📄 reply-context.test.ts
│   │   │   │   │   ├── 📄 reply-context.ts
│   │   │   │   │   ├── 📄 send-recap.test.ts
│   │   │   │   │   ├── 📄 send-recap.ts
│   │   │   │   │   ├── 📄 transcript-prompt.test.ts
│   │   │   │   │   ├── 📄 transcript-prompt.ts
│   │   │   │   │   ├── 📄 transition-recording.ts
│   │   │   │   │   └── 📄 webhook-handlers.ts
│   │   │   │   ├── 📁 messaging
│   │   │   │   │   ├── 📁 chat-sdk
│   │   │   │   │   │   ├── 📄 adapters.test.ts
│   │   │   │   │   │   ├── 📄 adapters.ts
│   │   │   │   │   │   ├── 📄 bot-attachments.test.ts
│   │   │   │   │   │   ├── 📄 bot.test.ts
│   │   │   │   │   │   ├── 📄 bot.ts
│   │   │   │   │   │   ├── 📄 link-code-consume.test.ts
│   │   │   │   │   │   ├── 📄 link-code-consume.ts
│   │   │   │   │   │   ├── 📄 link-code.test.ts
│   │   │   │   │   │   ├── 📄 link-code.ts
│   │   │   │   │   │   ├── 📄 teams-config.ts
│   │   │   │   │   │   └── 📄 webhook-route.ts
│   │   │   │   │   ├── 📁 providers
│   │   │   │   │   │   ├── 📁 slack
│   │   │   │   │   │   │   ├── 📁 messages
│   │   │   │   │   │   │   │   ├── 📄 app-home.ts
│   │   │   │   │   │   │   │   ├── 📄 digest.ts
│   │   │   │   │   │   │   │   ├── 📄 document-filing.ts
│   │   │   │   │   │   │   │   ├── 📄 follow-up-reminder.test.ts
│   │   │   │   │   │   │   │   ├── 📄 follow-up-reminder.ts
│   │   │   │   │   │   │   │   └── 📄 meeting-briefing.ts
│   │   │   │   │   │   │   ├── 📄 app-home.ts
│   │   │   │   │   │   │   ├── 📄 channels.ts
│   │   │   │   │   │   │   ├── 📄 client.ts
│   │   │   │   │   │   │   ├── 📄 constants.ts
│   │   │   │   │   │   │   ├── 📄 format.test.ts
│   │   │   │   │   │   │   ├── 📄 format.ts
│   │   │   │   │   │   │   ├── 📄 handle-slack-callback.ts
│   │   │   │   │   │   │   ├── 📄 send-onboarding-direct-message.ts
│   │   │   │   │   │   │   ├── 📄 send.test.ts
│   │   │   │   │   │   │   ├── 📄 send.ts
│   │   │   │   │   │   │   ├── 📄 slash-commands.test.ts
│   │   │   │   │   │   │   ├── 📄 slash-commands.ts
│   │   │   │   │   │   │   ├── 📄 uninstall.test.ts
│   │   │   │   │   │   │   ├── 📄 uninstall.ts
│   │   │   │   │   │   │   ├── 📄 users.ts
│   │   │   │   │   │   │   ├── 📄 verify-signature.test.ts
│   │   │   │   │   │   │   └── 📄 verify-signature.ts
│   │   │   │   │   │   ├── 📁 teams
│   │   │   │   │   │   │   ├── 📄 welcome.test.ts
│   │   │   │   │   │   │   └── 📄 welcome.ts
│   │   │   │   │   │   └── 📁 telegram
│   │   │   │   │   │       ├── 📄 api.ts
│   │   │   │   │   │       ├── 📄 bot-config.ts
│   │   │   │   │   │       ├── 📄 format.test.ts
│   │   │   │   │   │       └── 📄 format.ts
│   │   │   │   │   ├── 📄 action-event-identifiers.test.ts
│   │   │   │   │   ├── 📄 action-event-identifiers.ts
│   │   │   │   │   ├── 📄 channel-validity.test.ts
│   │   │   │   │   ├── 📄 channel-validity.ts
│   │   │   │   │   ├── 📄 pending-email-preview.test.ts
│   │   │   │   │   ├── 📄 pending-email-preview.ts
│   │   │   │   │   ├── 📄 platforms.ts
│   │   │   │   │   ├── 📄 prompt-commands.test.ts
│   │   │   │   │   ├── 📄 prompt-commands.ts
│   │   │   │   │   ├── 📄 routes.test.ts
│   │   │   │   │   ├── 📄 routes.ts
│   │   │   │   │   ├── 📄 rule-notifications.test.ts
│   │   │   │   │   ├── 📄 rule-notifications.ts
│   │   │   │   │   └── 📄 slack-routes.ts
│   │   │   │   ├── 📁 mobile-auth
│   │   │   │   │   ├── 📄 app-callback-url.test.ts
│   │   │   │   │   ├── 📄 app-callback-url.ts
│   │   │   │   │   ├── 📄 native-auth-plugin.test.ts
│   │   │   │   │   ├── 📄 native-auth-plugin.ts
│   │   │   │   │   ├── 📄 oauth-code.test.ts
│   │   │   │   │   ├── 📄 oauth-code.ts
│   │   │   │   │   ├── 📄 pkce.ts
│   │   │   │   │   ├── 📄 provider-completion.test.ts
│   │   │   │   │   ├── 📄 provider-completion.ts
│   │   │   │   │   ├── 📄 providers.ts
│   │   │   │   │   ├── 📄 rate-limit-error.ts
│   │   │   │   │   ├── 📄 session-cookie.ts
│   │   │   │   │   ├── 📄 set-cookie.test.ts
│   │   │   │   │   ├── 📄 set-cookie.ts
│   │   │   │   │   ├── 📄 start-social.test.ts
│   │   │   │   │   ├── 📄 start-social.ts
│   │   │   │   │   ├── 📄 url.test.ts
│   │   │   │   │   └── 📄 url.ts
│   │   │   │   ├── 📁 oauth
│   │   │   │   │   ├── 📄 account-linking-redirect.test.ts
│   │   │   │   │   ├── 📄 account-linking-redirect.ts
│   │   │   │   │   ├── 📄 account-linking.test.ts
│   │   │   │   │   ├── 📄 account-linking.ts
│   │   │   │   │   ├── 📝 apple-mobile-login.md
│   │   │   │   │   ├── 📄 auth-callback-deduplication.test.ts
│   │   │   │   │   ├── 📄 auth-callback-deduplication.ts
│   │   │   │   │   ├── 📄 callback-validation.test.ts
│   │   │   │   │   ├── 📄 callback-validation.ts
│   │   │   │   │   ├── 📄 error-handler.ts
│   │   │   │   │   ├── 📄 linking-audit.ts
│   │   │   │   │   ├── 📄 login-providers.test.ts
│   │   │   │   │   ├── 📄 login-providers.ts
│   │   │   │   │   ├── 📄 microsoft-oauth.test.ts
│   │   │   │   │   ├── 📄 microsoft-oauth.ts
│   │   │   │   │   ├── 📄 provider-config.test.ts
│   │   │   │   │   ├── 📄 provider-config.ts
│   │   │   │   │   ├── 📄 reconnect-target.test.ts
│   │   │   │   │   ├── 📄 reconnect-target.ts
│   │   │   │   │   ├── 📄 redirect.test.ts
│   │   │   │   │   ├── 📄 redirect.ts
│   │   │   │   │   ├── 📄 state.test.ts
│   │   │   │   │   ├── 📄 state.ts
│   │   │   │   │   ├── 📄 verify.test.ts
│   │   │   │   │   └── 📄 verify.ts
│   │   │   │   ├── 📁 offline
│   │   │   │   │   ├── 📄 clear-mail-cache.test.ts
│   │   │   │   │   ├── 📄 clear-mail-cache.ts
│   │   │   │   │   ├── 📄 mail-cache.test.ts
│   │   │   │   │   └── 📄 mail-cache.ts
│   │   │   │   ├── 📁 organizations
│   │   │   │   │   ├── 📄 access.ts
│   │   │   │   │   ├── 📄 invitations.ts
│   │   │   │   │   ├── 📄 ownership.test.ts
│   │   │   │   │   ├── 📄 ownership.ts
│   │   │   │   │   ├── 📄 roles.ts
│   │   │   │   │   ├── 📄 rule-action-types.test.ts
│   │   │   │   │   ├── 📄 rule-action-types.ts
│   │   │   │   │   ├── 📄 rules.test.ts
│   │   │   │   │   └── 📄 rules.ts
│   │   │   │   ├── 📁 outbound-webhook
│   │   │   │   │   ├── 📄 action.ts
│   │   │   │   │   ├── 📄 call-webhook.test.ts
│   │   │   │   │   ├── 📄 call-webhook.ts
│   │   │   │   │   ├── 📄 url-validation.test.ts
│   │   │   │   │   └── 📄 url-validation.ts
│   │   │   │   ├── 📁 outlook
│   │   │   │   │   ├── 📄 admin-consent.test.ts
│   │   │   │   │   ├── 📄 admin-consent.ts
│   │   │   │   │   ├── 📄 assistant-search.test.ts
│   │   │   │   │   ├── 📄 assistant-search.ts
│   │   │   │   │   ├── 📄 attachment.test.ts
│   │   │   │   │   ├── 📄 attachment.ts
│   │   │   │   │   ├── 📄 backfill-recent-messages.test.ts
│   │   │   │   │   ├── 📄 backfill-recent-messages.ts
│   │   │   │   │   ├── 📄 batch.test.ts
│   │   │   │   │   ├── 📄 batch.ts
│   │   │   │   │   ├── 📄 calendar-client-occ.test.ts
│   │   │   │   │   ├── 📄 calendar-client-refresh-buffer.test.ts
│   │   │   │   │   ├── 📄 calendar-client.test.ts
│   │   │   │   │   ├── 📄 calendar-client.ts
│   │   │   │   │   ├── 📄 category-colors.test.ts
│   │   │   │   │   ├── 📄 category-colors.ts
│   │   │   │   │   ├── 📄 client-types.ts
│   │   │   │   │   ├── 📄 client.test.ts
│   │   │   │   │   ├── 📄 client.ts
│   │   │   │   │   ├── 📄 complete-thread.test.ts
│   │   │   │   │   ├── 📄 constants.ts
│   │   │   │   │   ├── 📄 contact.test.ts
│   │   │   │   │   ├── 📄 contact.ts
│   │   │   │   │   ├── 📄 draft-attachments.test.ts
│   │   │   │   │   ├── 📄 draft-attachments.ts
│   │   │   │   │   ├── 📄 draft-send.test.ts
│   │   │   │   │   ├── 📄 draft.test.ts
│   │   │   │   │   ├── 📄 draft.ts
│   │   │   │   │   ├── 📄 errors.test.ts
│   │   │   │   │   ├── 📄 errors.ts
│   │   │   │   │   ├── 📄 filter.ts
│   │   │   │   │   ├── 📄 folders.test.ts
│   │   │   │   │   ├── 📄 folders.ts
│   │   │   │   │   ├── 📄 inbox-sections.ts
│   │   │   │   │   ├── 📄 label-validation.test.ts
│   │   │   │   │   ├── 📄 label-validation.ts
│   │   │   │   │   ├── 📄 label.test.ts
│   │   │   │   │   ├── 📄 label.ts
│   │   │   │   │   ├── 📄 local-mail-sync.test.ts
│   │   │   │   │   ├── 📄 local-mail-sync.ts
│   │   │   │   │   ├── 📄 mail.test.ts
│   │   │   │   │   ├── 📄 mail.ts
│   │   │   │   │   ├── 📄 mailbox-sync.test.ts
│   │   │   │   │   ├── 📄 mailbox-sync.ts
│   │   │   │   │   ├── 📄 message.test.ts
│   │   │   │   │   ├── 📄 message.ts
│   │   │   │   │   ├── 📄 oauth.test.ts
│   │   │   │   │   ├── 📄 oauth.ts
│   │   │   │   │   ├── 📄 odata-escape.test.ts
│   │   │   │   │   ├── 📄 odata-escape.ts
│   │   │   │   │   ├── 📄 page-token.test.ts
│   │   │   │   │   ├── 📄 page-token.ts
│   │   │   │   │   ├── 📄 rate-limit-catch-up.test.ts
│   │   │   │   │   ├── 📄 rate-limit-catch-up.ts
│   │   │   │   │   ├── 📄 reply.test.ts
│   │   │   │   │   ├── 📄 reply.ts
│   │   │   │   │   ├── 📄 retry.test.ts
│   │   │   │   │   ├── 📄 retry.ts
│   │   │   │   │   ├── 📄 scopes.test.ts
│   │   │   │   │   ├── 📄 scopes.ts
│   │   │   │   │   ├── 📄 search-escape.ts
│   │   │   │   │   ├── 📄 search-scope.test.ts
│   │   │   │   │   ├── 📄 search-scope.ts
│   │   │   │   │   ├── 📄 spam.test.ts
│   │   │   │   │   ├── 📄 spam.ts
│   │   │   │   │   ├── 📄 subscription-history.test.ts
│   │   │   │   │   ├── 📄 subscription-history.ts
│   │   │   │   │   ├── 📄 subscription-manager.test.ts
│   │   │   │   │   ├── 📄 subscription-manager.ts
│   │   │   │   │   ├── 📄 thread-helpers.test.ts
│   │   │   │   │   ├── 📄 thread-helpers.ts
│   │   │   │   │   ├── 📄 thread-search-query.test.ts
│   │   │   │   │   ├── 📄 thread-search-query.ts
│   │   │   │   │   ├── 📄 thread.test.ts
│   │   │   │   │   ├── 📄 thread.ts
│   │   │   │   │   ├── 📄 trash.test.ts
│   │   │   │   │   ├── 📄 trash.ts
│   │   │   │   │   ├── 📄 upload-session.test.ts
│   │   │   │   │   ├── 📄 upload-session.ts
│   │   │   │   │   ├── 📄 watch.test.ts
│   │   │   │   │   └── 📄 watch.ts
│   │   │   │   ├── 📁 parse
│   │   │   │   │   ├── 📄 calender-event.test.ts
│   │   │   │   │   ├── 📄 calender-event.ts
│   │   │   │   │   ├── 📄 extract-reply.client.test.ts
│   │   │   │   │   ├── 📄 extract-reply.client.ts
│   │   │   │   │   ├── 📄 parseHtml.server.ts
│   │   │   │   │   ├── 📄 unsubscribe.test.ts
│   │   │   │   │   └── 📄 unsubscribe.ts
│   │   │   │   ├── 📁 playwright
│   │   │   │   │   ├── 📄 browser-diagnostics.test.ts
│   │   │   │   │   ├── 📄 browser-diagnostics.ts
│   │   │   │   │   ├── 📄 emulated-suite-selection.mjs
│   │   │   │   │   ├── 📄 emulated-suite-selection.test.mjs
│   │   │   │   │   ├── 📄 emulated-suite-targets.d.mts
│   │   │   │   │   ├── 📄 emulated-suite-targets.mjs
│   │   │   │   │   ├── 📄 emulated-suite-targets.test.mjs
│   │   │   │   │   ├── 📄 mail-inspect-command.test.ts
│   │   │   │   │   ├── 📄 mail-inspect-command.ts
│   │   │   │   │   └── 📄 todoist-transport.test.ts
│   │   │   │   ├── 📁 premium
│   │   │   │   │   ├── 📄 billing-access.test.ts
│   │   │   │   │   ├── 📄 billing-access.ts
│   │   │   │   │   ├── 📄 create-premium.ts
│   │   │   │   │   ├── 📄 digest.test.ts
│   │   │   │   │   ├── 📄 digest.ts
│   │   │   │   │   ├── 📄 index.test.ts
│   │   │   │   │   ├── 📄 index.ts
│   │   │   │   │   ├── 📄 limits.test.ts
│   │   │   │   │   ├── 📄 limits.ts
│   │   │   │   │   ├── 📄 rerun.ts
│   │   │   │   │   ├── 📄 seats.test.ts
│   │   │   │   │   ├── 📄 seats.ts
│   │   │   │   │   ├── 📄 server.test.ts
│   │   │   │   │   ├── 📄 server.ts
│   │   │   │   │   ├── 📄 unsubscribe-credits.test.ts
│   │   │   │   │   └── 📄 unsubscribe-credits.ts
│   │   │   │   ├── 📁 privacy
│   │   │   │   │   ├── 📄 reasoning-retention.test.ts
│   │   │   │   │   └── 📄 reasoning-retention.ts
│   │   │   │   ├── 📁 queue
│   │   │   │   │   ├── 📄 ai-queue.ts
│   │   │   │   │   ├── 📄 backend.ts
│   │   │   │   │   ├── 📄 bullmq.ts
│   │   │   │   │   ├── 📄 create-forwarding-queue-handler.test.ts
│   │   │   │   │   ├── 📄 create-forwarding-queue-handler.ts
│   │   │   │   │   ├── 📄 dispatch.test.ts
│   │   │   │   │   ├── 📄 dispatch.ts
│   │   │   │   │   ├── 📄 email-actions.test.ts
│   │   │   │   │   ├── 📄 email-actions.ts
│   │   │   │   │   ├── 📄 forward-to-internal-api.test.ts
│   │   │   │   │   ├── 📄 forward-to-internal-api.ts
│   │   │   │   │   ├── 📄 retry.ts
│   │   │   │   │   └── 📄 vercel.ts
│   │   │   │   ├── 📁 recall
│   │   │   │   │   ├── 📄 client.test.ts
│   │   │   │   │   ├── 📄 client.ts
│   │   │   │   │   ├── 📄 status.test.ts
│   │   │   │   │   ├── 📄 status.ts
│   │   │   │   │   ├── 📄 transcript.test.ts
│   │   │   │   │   ├── 📄 transcript.ts
│   │   │   │   │   └── 📄 types.ts
│   │   │   │   ├── 📁 redis
│   │   │   │   │   ├── 📄 account-validation.ts
│   │   │   │   │   ├── 📄 categorization-progress.test.ts
│   │   │   │   │   ├── 📄 categorization-progress.ts
│   │   │   │   │   ├── 📄 clean.ts
│   │   │   │   │   ├── 📄 clean.types.ts
│   │   │   │   │   ├── 📄 compose-session-draft.ts
│   │   │   │   │   ├── 📄 contact-photos.ts
│   │   │   │   │   ├── 📄 docs-cache.ts
│   │   │   │   │   ├── 📄 draft-attachment-upload.ts
│   │   │   │   │   ├── 📄 email-provider-rate-limit.test.ts
│   │   │   │   │   ├── 📄 email-provider-rate-limit.ts
│   │   │   │   │   ├── 📄 gmail-history-catch-up.ts
│   │   │   │   │   ├── 📄 index.ts
│   │   │   │   │   ├── 📄 local-mail-hints.test.ts
│   │   │   │   │   ├── 📄 local-mail-hints.ts
│   │   │   │   │   ├── 📄 message-processing.test.ts
│   │   │   │   │   ├── 📄 message-processing.ts
│   │   │   │   │   ├── 📄 messaging-link-code.test.ts
│   │   │   │   │   ├── 📄 messaging-link-code.ts
│   │   │   │   │   ├── 📄 oauth-code.test.ts
│   │   │   │   │   ├── 📄 oauth-code.ts
│   │   │   │   │   ├── 📄 outbound-thread-status.test.ts
│   │   │   │   │   ├── 📄 outbound-thread-status.ts
│   │   │   │   │   ├── 📄 outlook-rate-limit-catch-up.ts
│   │   │   │   │   ├── 📄 owned-lock.ts
│   │   │   │   │   ├── 📄 provider-issue-cleanup.test.ts
│   │   │   │   │   ├── 📄 provider-issue-cleanup.ts
│   │   │   │   │   ├── 📄 public-contact-context-lock.test.ts
│   │   │   │   │   ├── 📄 public-contact-context-lock.ts
│   │   │   │   │   ├── 📄 reply.test.ts
│   │   │   │   │   ├── 📄 reply.ts
│   │   │   │   │   ├── 📄 research-cache.ts
│   │   │   │   │   ├── 📄 subscriber.ts
│   │   │   │   │   ├── 📄 summary.ts
│   │   │   │   │   ├── 📄 thread-page-buffer-timeout.test.ts
│   │   │   │   │   ├── 📄 thread-page-buffer.test.ts
│   │   │   │   │   ├── 📄 thread-page-buffer.ts
│   │   │   │   │   ├── 📄 usage.test.ts
│   │   │   │   │   └── 📄 usage.ts
│   │   │   │   ├── 📁 referral
│   │   │   │   │   ├── 📄 referral-code.test.ts
│   │   │   │   │   ├── 📄 referral-code.ts
│   │   │   │   │   ├── 📄 referral-link.ts
│   │   │   │   │   ├── 📄 referral-tracking.ts
│   │   │   │   │   ├── 📄 signature.test.ts
│   │   │   │   │   └── 📄 signature.ts
│   │   │   │   ├── 📁 reply-tracker
│   │   │   │   │   ├── 📄 check-sender-reply-history.ts
│   │   │   │   │   ├── 📄 conversation-status-config.ts
│   │   │   │   │   ├── 📄 draft-similarity.test.ts
│   │   │   │   │   ├── 📄 draft-similarity.ts
│   │   │   │   │   ├── 📄 draft-tracking.test.ts
│   │   │   │   │   ├── 📄 draft-tracking.ts
│   │   │   │   │   ├── 📄 error-logging.test.ts
│   │   │   │   │   ├── 📄 error-logging.ts
│   │   │   │   │   ├── 📄 generate-draft.test.ts
│   │   │   │   │   ├── 📄 generate-draft.ts
│   │   │   │   │   ├── 📄 handle-conversation-status.test.ts
│   │   │   │   │   ├── 📄 handle-conversation-status.ts
│   │   │   │   │   ├── 📄 handle-outbound.test.ts
│   │   │   │   │   ├── 📄 handle-outbound.ts
│   │   │   │   │   ├── 📄 label-helpers.test.ts
│   │   │   │   │   ├── 📄 label-helpers.ts
│   │   │   │   │   ├── 📄 outbound.test.ts
│   │   │   │   │   ├── 📄 outbound.ts
│   │   │   │   │   ├── 📄 sender-reply-examples.test.ts
│   │   │   │   │   ├── 📄 sender-reply-examples.ts
│   │   │   │   │   ├── 📄 thread-status-context.test.ts
│   │   │   │   │   └── 📄 thread-status-context.ts
│   │   │   │   ├── 📁 retry
│   │   │   │   │   ├── 📄 get-retry-after-header.test.ts
│   │   │   │   │   ├── 📄 get-retry-after-header.ts
│   │   │   │   │   ├── 📄 is-fetch-error.ts
│   │   │   │   │   ├── 📄 provider-retry.test.ts
│   │   │   │   │   └── 📄 provider-retry.ts
│   │   │   │   ├── 📁 rule
│   │   │   │   │   ├── 📄 ai-sender-pattern-learning.test.ts
│   │   │   │   │   ├── 📄 ai-sender-pattern-learning.ts
│   │   │   │   │   ├── 📄 chat-rule-risk.test.ts
│   │   │   │   │   ├── 📄 check-sender-rule-history.test.ts
│   │   │   │   │   ├── 📄 check-sender-rule-history.ts
│   │   │   │   │   ├── 📄 classification-feedback.test.ts
│   │   │   │   │   ├── 📄 classification-feedback.ts
│   │   │   │   │   ├── 📄 consts.ts
│   │   │   │   │   ├── 📄 create-rule-condition.ts
│   │   │   │   │   ├── 📄 email-from-pattern.test.ts
│   │   │   │   │   ├── 📄 email-from-pattern.ts
│   │   │   │   │   ├── 📄 learned-patterns.test.ts
│   │   │   │   │   ├── 📄 learned-patterns.ts
│   │   │   │   │   ├── 📄 legacy-label-removal-exclusions.test.ts
│   │   │   │   │   ├── 📄 legacy-label-removal-exclusions.ts
│   │   │   │   │   ├── 📄 mapRulesToExtensionTabs.test.ts
│   │   │   │   │   ├── 📄 mapRulesToExtensionTabs.ts
│   │   │   │   │   ├── 📄 mobile-rule.test.ts
│   │   │   │   │   ├── 📄 mobile-rule.ts
│   │   │   │   │   ├── 📄 recipient-validation.ts
│   │   │   │   │   ├── 📄 record-label-removal-learning.test.ts
│   │   │   │   │   ├── 📄 record-label-removal-learning.ts
│   │   │   │   │   ├── 📄 rule-history.test.ts
│   │   │   │   │   ├── 📄 rule-history.ts
│   │   │   │   │   ├── 📄 rule.test.ts
│   │   │   │   │   ├── 📄 rule.ts
│   │   │   │   │   ├── 📄 sender-scope-overlap.test.ts
│   │   │   │   │   ├── 📄 sender-scope-overlap.ts
│   │   │   │   │   ├── 📄 sort.test.ts
│   │   │   │   │   ├── 📄 sort.ts
│   │   │   │   │   ├── 📄 static-from-risk.test.ts
│   │   │   │   │   ├── 📄 static-from-risk.ts
│   │   │   │   │   ├── 📄 toggle-rule.ts
│   │   │   │   │   └── 📄 types.ts
│   │   │   │   ├── 📁 scheduled-actions
│   │   │   │   │   ├── 📄 executor.test.ts
│   │   │   │   │   ├── 📄 executor.ts
│   │   │   │   │   ├── 📄 scheduler.test.ts
│   │   │   │   │   └── 📄 scheduler.ts
│   │   │   │   ├── 📁 scheduled-email
│   │   │   │   │   ├── 📄 service.test.ts
│   │   │   │   │   └── 📄 service.ts
│   │   │   │   ├── 📁 senders
│   │   │   │   │   ├── 📄 archive-existing.test.ts
│   │   │   │   │   ├── 📄 archive-existing.ts
│   │   │   │   │   ├── 📄 browser-unsubscribe.test.ts
│   │   │   │   │   ├── 📄 browser-unsubscribe.ts
│   │   │   │   │   ├── 📄 bulk-actions.test.ts
│   │   │   │   │   ├── 📄 bulk-actions.ts
│   │   │   │   │   ├── 📄 filters.test.ts
│   │   │   │   │   ├── 📄 filters.ts
│   │   │   │   │   ├── 📄 html-form-unsubscribe.test.ts
│   │   │   │   │   ├── 📄 html-form-unsubscribe.ts
│   │   │   │   │   ├── 📄 record.test.ts
│   │   │   │   │   ├── 📄 record.ts
│   │   │   │   │   ├── 📄 source.test.ts
│   │   │   │   │   ├── 📄 source.ts
│   │   │   │   │   ├── 📄 unsubscribe.test.ts
│   │   │   │   │   └── 📄 unsubscribe.ts
│   │   │   │   ├── 📁 snippets
│   │   │   │   │   ├── 📄 expand-snippet.test.ts
│   │   │   │   │   ├── 📄 expand-snippet.ts
│   │   │   │   │   ├── 📄 match-snippets.test.ts
│   │   │   │   │   ├── 📄 match-snippets.ts
│   │   │   │   │   ├── 📄 snippet-shortcut.test.ts
│   │   │   │   │   └── 📄 snippet-shortcut.ts
│   │   │   │   ├── 📁 snooze
│   │   │   │   │   ├── 📄 executor.test.ts
│   │   │   │   │   ├── 📄 executor.ts
│   │   │   │   │   ├── 📄 process-due.test.ts
│   │   │   │   │   ├── 📄 process-due.ts
│   │   │   │   │   ├── 📄 scheduler.test.ts
│   │   │   │   │   ├── 📄 scheduler.ts
│   │   │   │   │   ├── 📄 snooze.test.ts
│   │   │   │   │   ├── 📄 snooze.ts
│   │   │   │   │   └── 📄 unsnooze.ts
│   │   │   │   ├── 📁 split-inbox
│   │   │   │   │   ├── 📄 default-splits.server.test.ts
│   │   │   │   │   ├── 📄 default-splits.server.ts
│   │   │   │   │   ├── 📄 default-splits.test.ts
│   │   │   │   │   ├── 📄 default-splits.ts
│   │   │   │   │   ├── 📄 inbox-bundles.server.ts
│   │   │   │   │   ├── 📄 initial-splits.test.ts
│   │   │   │   │   ├── 📄 initial-splits.ts
│   │   │   │   │   ├── 📄 library.server.ts
│   │   │   │   │   ├── 📄 native-categories.ts
│   │   │   │   │   ├── 📄 sender-filter.test.ts
│   │   │   │   │   ├── 📄 sender-filter.ts
│   │   │   │   │   ├── 📄 settings.server.ts
│   │   │   │   │   ├── 📄 split-constants.ts
│   │   │   │   │   ├── 📄 split-counts.test.ts
│   │   │   │   │   ├── 📄 split-counts.ts
│   │   │   │   │   ├── 📄 split-filters.ts
│   │   │   │   │   ├── 📄 split-library.test.ts
│   │   │   │   │   ├── 📄 split-library.ts
│   │   │   │   │   ├── 📄 split-lock.ts
│   │   │   │   │   ├── 📄 split-query.test.ts
│   │   │   │   │   ├── 📄 split-query.ts
│   │   │   │   │   ├── 📄 split-senders.test.ts
│   │   │   │   │   ├── 📄 split-senders.ts
│   │   │   │   │   ├── 📄 splits.server.ts
│   │   │   │   │   ├── 📄 thread-matches-split.test.ts
│   │   │   │   │   └── 📄 thread-matches-split.ts
│   │   │   │   ├── 📁 sso
│   │   │   │   │   ├── 📄 extract-sso-provider-config-from-xml.test.ts
│   │   │   │   │   ├── 📄 extract-sso-provider-config-from-xml.ts
│   │   │   │   │   └── 📄 validate-idp-metadata.ts
│   │   │   │   ├── 📁 stats
│   │   │   │   │   └── 📁 response-time
│   │   │   │   │       ├── 📄 calculate.test.ts
│   │   │   │   │       ├── 📄 calculate.ts
│   │   │   │   │       ├── 📄 controller.test.ts
│   │   │   │   │       ├── 📄 controller.ts
│   │   │   │   │       └── 📄 validation.ts
│   │   │   │   ├── 📁 team-comments
│   │   │   │   │   ├── 📄 access.ts
│   │   │   │   │   ├── 📄 activity.ts
│   │   │   │   │   ├── 📄 comments.ts
│   │   │   │   │   ├── 📄 content.test.ts
│   │   │   │   │   ├── 📄 content.ts
│   │   │   │   │   ├── 📄 conversations.ts
│   │   │   │   │   ├── 📄 events.ts
│   │   │   │   │   ├── 📄 member-removal.ts
│   │   │   │   │   ├── 📄 mentions.test.ts
│   │   │   │   │   └── 📄 mentions.ts
│   │   │   │   ├── 📁 threads
│   │   │   │   │   ├── 📄 buffered-load.test.ts
│   │   │   │   │   ├── 📄 fetch-page.test.ts
│   │   │   │   │   ├── 📄 fetch-page.ts
│   │   │   │   │   ├── 📄 load-combined.test.ts
│   │   │   │   │   ├── 📄 load-combined.ts
│   │   │   │   │   ├── 📄 load.test.ts
│   │   │   │   │   ├── 📄 load.ts
│   │   │   │   │   ├── 📄 merge-paginated-sources.test.ts
│   │   │   │   │   ├── 📄 merge-paginated-sources.ts
│   │   │   │   │   ├── 📄 sort.ts
│   │   │   │   │   ├── 📄 thread-list-cache-key.ts
│   │   │   │   │   ├── 📄 validation.test.ts
│   │   │   │   │   └── 📄 validation.ts
│   │   │   │   ├── 📁 types
│   │   │   │   │   ├── 📄 mail.test.ts
│   │   │   │   │   └── 📄 mail.ts
│   │   │   │   ├── 📁 upstash
│   │   │   │   │   ├── 📄 categorize-senders.ts
│   │   │   │   │   ├── 📄 index.test.ts
│   │   │   │   │   └── 📄 index.ts
│   │   │   │   ├── 📁 user
│   │   │   │   │   ├── 📄 delete.test.ts
│   │   │   │   │   ├── 📄 delete.ts
│   │   │   │   │   ├── 📄 get.ts
│   │   │   │   │   ├── 📄 merge-account.test.ts
│   │   │   │   │   ├── 📄 merge-account.ts
│   │   │   │   │   ├── 📄 merge-premium.test.ts
│   │   │   │   │   ├── 📄 merge-premium.ts
│   │   │   │   │   ├── 📄 orphaned-account.test.ts
│   │   │   │   │   ├── 📄 orphaned-account.ts
│   │   │   │   │   └── 📄 validate.ts
│   │   │   │   ├── 📁 voice
│   │   │   │   │   ├── 📁 providers
│   │   │   │   │   │   ├── 📄 groq.ts
│   │   │   │   │   │   ├── 📄 openai.test.ts
│   │   │   │   │   │   └── 📄 openai.ts
│   │   │   │   │   ├── 📄 api-error.test.ts
│   │   │   │   │   ├── 📄 api-error.ts
│   │   │   │   │   ├── 📄 catalog.ts
│   │   │   │   │   ├── 📄 client-error.test.ts
│   │   │   │   │   ├── 📄 client-error.ts
│   │   │   │   │   ├── 📄 errors.ts
│   │   │   │   │   ├── 📄 factory.test.ts
│   │   │   │   │   ├── 📄 factory.ts
│   │   │   │   │   ├── 📄 http.test.ts
│   │   │   │   │   ├── 📄 http.ts
│   │   │   │   │   ├── 📄 instructions.ts
│   │   │   │   │   ├── 📄 limits.ts
│   │   │   │   │   ├── 📄 live-events.test.ts
│   │   │   │   │   ├── 📄 live-events.ts
│   │   │   │   │   ├── 📄 live-history.test.ts
│   │   │   │   │   ├── 📄 live-history.ts
│   │   │   │   │   ├── 📄 recording.test.ts
│   │   │   │   │   ├── 📄 recording.ts
│   │   │   │   │   ├── 📄 runtime.ts
│   │   │   │   │   ├── 📄 speakable.test.ts
│   │   │   │   │   ├── 📄 speakable.ts
│   │   │   │   │   ├── 📄 transcript.test.ts
│   │   │   │   │   ├── 📄 transcript.ts
│   │   │   │   │   ├── 📄 types.ts
│   │   │   │   │   ├── 📄 validation.test.ts
│   │   │   │   │   └── 📄 validation.ts
│   │   │   │   ├── 📁 webhook
│   │   │   │   │   ├── 📁 google
│   │   │   │   │   │   ├── 📄 fetch-sender-from-message.ts
│   │   │   │   │   │   ├── 📄 process-history-item.test.ts
│   │   │   │   │   │   ├── 📄 process-history-item.ts
│   │   │   │   │   │   ├── 📄 process-history.test.ts
│   │   │   │   │   │   ├── 📄 process-history.ts
│   │   │   │   │   │   ├── 📄 process-label-added-event.test.ts
│   │   │   │   │   │   ├── 📄 process-label-added-event.ts
│   │   │   │   │   │   ├── 📄 process-label-removed-event.test.ts
│   │   │   │   │   │   ├── 📄 process-label-removed-event.ts
│   │   │   │   │   │   └── 📄 types.ts
│   │   │   │   │   ├── 📁 outlook
│   │   │   │   │   │   ├── 📄 learn-label-removal.test.ts
│   │   │   │   │   │   ├── 📄 learn-label-removal.ts
│   │   │   │   │   │   ├── 📄 process-history.test.ts
│   │   │   │   │   │   ├── 📄 process-history.ts
│   │   │   │   │   │   ├── 📄 types.test.ts
│   │   │   │   │   │   └── 📄 types.ts
│   │   │   │   │   ├── 📄 error-handler.test.ts
│   │   │   │   │   ├── 📄 error-handler.ts
│   │   │   │   │   ├── 📄 process-history-item.test.ts
│   │   │   │   │   ├── 📄 process-history-item.ts
│   │   │   │   │   ├── 📄 process-history.test.ts
│   │   │   │   │   ├── 📄 process-history.ts
│   │   │   │   │   ├── 📄 validate-webhook-account.test.ts
│   │   │   │   │   └── 📄 validate-webhook-account.ts
│   │   │   │   ├── 📁 webhooks
│   │   │   │   │   ├── 📄 verify-standard-webhook.test.ts
│   │   │   │   │   └── 📄 verify-standard-webhook.ts
│   │   │   │   ├── 📄 account-linking.test.ts
│   │   │   │   ├── 📄 account-linking.ts
│   │   │   │   ├── 📄 account-switch-url.test.ts
│   │   │   │   ├── 📄 account-switch-url.ts
│   │   │   │   ├── 📄 account.test.ts
│   │   │   │   ├── 📄 account.ts
│   │   │   │   ├── 📄 action-display-messages.test.ts
│   │   │   │   ├── 📄 action-display-messages.ts
│   │   │   │   ├── 📄 action-display.test.ts
│   │   │   │   ├── 📄 action-display.tsx
│   │   │   │   ├── 📄 action-item.test.ts
│   │   │   │   ├── 📄 action-item.ts
│   │   │   │   ├── 📄 action-sort.test.ts
│   │   │   │   ├── 📄 action-sort.ts
│   │   │   │   ├── 📄 admin.test.ts
│   │   │   │   ├── 📄 admin.ts
│   │   │   │   ├── 📄 announcements.tsx
│   │   │   │   ├── 📄 api-auth.test.ts
│   │   │   │   ├── 📄 api-auth.ts
│   │   │   │   ├── 📄 api-key-scopes.ts
│   │   │   │   ├── 📄 api-key.ts
│   │   │   │   ├── 📄 api-middleware.test.ts
│   │   │   │   ├── 📄 api-middleware.ts
│   │   │   │   ├── 📄 apns.test.ts
│   │   │   │   ├── 📄 apns.ts
│   │   │   │   ├── 📄 app-review-demo.ts
│   │   │   │   ├── 📄 assess.test.ts
│   │   │   │   ├── 📄 assess.ts
│   │   │   │   ├── 📄 async.test.ts
│   │   │   │   ├── 📄 async.ts
│   │   │   │   ├── 📄 auth-client.test.ts
│   │   │   │   ├── 📄 auth-client.ts
│   │   │   │   ├── 📄 auth-cookies.ts
│   │   │   │   ├── 📄 auth-login-providers.test.ts
│   │   │   │   ├── 📄 auth-schema.test.ts
│   │   │   │   ├── 📄 auth-signup-policy.test.ts
│   │   │   │   ├── 📄 auth-signup-policy.ts
│   │   │   │   ├── 📄 auth.test.ts
│   │   │   │   ├── 📄 auth.ts
│   │   │   │   ├── 📄 auto-draft.ts
│   │   │   │   ├── 📄 automatic-reload.test.ts
│   │   │   │   ├── 📄 automatic-reload.ts
│   │   │   │   ├── 📄 braintrust.ts
│   │   │   │   ├── 📄 branding.ts
│   │   │   │   ├── 📄 brands.ts
│   │   │   │   ├── 📄 categories.ts
│   │   │   │   ├── 📄 category-config.tsx
│   │   │   │   ├── 📄 category.server.ts
│   │   │   │   ├── 📄 cleaner-feature.test.ts
│   │   │   │   ├── 📄 cleaner-feature.ts
│   │   │   │   ├── 📄 colors.ts
│   │   │   │   ├── 📄 condition.test.ts
│   │   │   │   ├── 📄 condition.ts
│   │   │   │   ├── 📄 config.ts
│   │   │   │   ├── 📄 connect-mailbox.test.ts
│   │   │   │   ├── 📄 connect-mailbox.ts
│   │   │   │   ├── 📄 cookie-consent.test.ts
│   │   │   │   ├── 📄 cookie-consent.ts
│   │   │   │   ├── 📄 cookies.server.ts
│   │   │   │   ├── 📄 cookies.test.ts
│   │   │   │   ├── 📄 cookies.ts
│   │   │   │   ├── 📄 cron.test.ts
│   │   │   │   ├── 📄 cron.ts
│   │   │   │   ├── 📄 crypto-compare.test.ts
│   │   │   │   ├── 📄 crypto-compare.ts
│   │   │   │   ├── 📄 date.test.ts
│   │   │   │   ├── 📄 date.ts
│   │   │   │   ├── 📄 delayed-actions.ts
│   │   │   │   ├── 📄 delete-email-action.ts
│   │   │   │   ├── 📄 desktop-app.test.ts
│   │   │   │   ├── 📄 desktop-app.ts
│   │   │   │   ├── 📄 dub.ts
│   │   │   │   ├── 📄 email-account-client.ts
│   │   │   │   ├── 📄 email-account-order.ts
│   │   │   │   ├── 📄 email-account.ts
│   │   │   │   ├── 📄 email-send-operation-retention.test.ts
│   │   │   │   ├── 📄 email-send-operation-retention.ts
│   │   │   │   ├── 📄 email.test.ts
│   │   │   │   ├── 📄 email.ts
│   │   │   │   ├── 📄 encryption-missing-env.test.ts
│   │   │   │   ├── 📄 encryption.test.ts
│   │   │   │   ├── 📄 encryption.ts
│   │   │   │   ├── 📄 error.server.ts
│   │   │   │   ├── 📄 error.test.ts
│   │   │   │   ├── 📄 error.ts
│   │   │   │   ├── 📄 fb.test.ts
│   │   │   │   ├── 📄 fb.ts
│   │   │   │   ├── 📄 fcm.test.ts
│   │   │   │   ├── 📄 fcm.ts
│   │   │   │   ├── 📄 fetch-email-accounts.test.ts
│   │   │   │   ├── 📄 fetch-email-accounts.ts
│   │   │   │   ├── 📄 fetch.ts
│   │   │   │   ├── 📄 filter-ignored-senders.test.ts
│   │   │   │   ├── 📄 filter-ignored-senders.ts
│   │   │   │   ├── 📄 get-email-from-message.test.ts
│   │   │   │   ├── 📄 get-email-from-message.ts
│   │   │   │   ├── 📄 hash.ts
│   │   │   │   ├── 📄 index.ts
│   │   │   │   ├── 📄 indexing.test.ts
│   │   │   │   ├── 📄 indexing.ts
│   │   │   │   ├── 📄 integration-action.server.test.ts
│   │   │   │   ├── 📄 integration-action.server.ts
│   │   │   │   ├── 📄 integration-action.ts
│   │   │   │   ├── 📄 internal-api.test.ts
│   │   │   │   ├── 📄 internal-api.ts
│   │   │   │   ├── 📄 label.server.ts
│   │   │   │   ├── 📄 label.ts
│   │   │   │   ├── 📄 log-error-with-dedupe.test.ts
│   │   │   │   ├── 📄 log-error-with-dedupe.ts
│   │   │   │   ├── 📄 logger-client.test.ts
│   │   │   │   ├── 📄 logger-client.ts
│   │   │   │   ├── 📄 logger-flush.ts
│   │   │   │   ├── 📄 logger.test.ts
│   │   │   │   ├── 📄 logger.ts
│   │   │   │   ├── 📄 mail.test.ts
│   │   │   │   ├── 📄 mail.ts
│   │   │   │   ├── 📄 mailbox-push.test.ts
│   │   │   │   ├── 📄 mailbox-push.ts
│   │   │   │   ├── 📄 mention.test.ts
│   │   │   │   ├── 📄 mention.ts
│   │   │   │   ├── 📄 middleware.test.ts
│   │   │   │   ├── 📄 middleware.ts
│   │   │   │   ├── 📄 mobile-push-retention.test.ts
│   │   │   │   ├── 📄 mobile-push-retention.ts
│   │   │   │   ├── 📄 mobile-push.test.ts
│   │   │   │   ├── 📄 mobile-push.ts
│   │   │   │   ├── 📄 mobile-review.test.ts
│   │   │   │   ├── 📄 mobile-review.ts
│   │   │   │   ├── 📄 otp-push.test.ts
│   │   │   │   ├── 📄 otp-push.ts
│   │   │   │   ├── 📄 otp.test.ts
│   │   │   │   ├── 📄 otp.ts
│   │   │   │   ├── 📄 panel-width.test.ts
│   │   │   │   ├── 📄 panel-width.ts
│   │   │   │   ├── 📄 path.test.ts
│   │   │   │   ├── 📄 path.ts
│   │   │   │   ├── 📄 permissions-check.test.ts
│   │   │   │   ├── 📄 permissions-check.ts
│   │   │   │   ├── 📄 posthog.test.ts
│   │   │   │   ├── 📄 posthog.ts
│   │   │   │   ├── 📄 prisma-extensions.test.ts
│   │   │   │   ├── 📄 prisma-extensions.ts
│   │   │   │   ├── 📄 prisma-helpers.test.ts
│   │   │   │   ├── 📄 prisma-helpers.ts
│   │   │   │   ├── 📄 prisma-retry.ts
│   │   │   │   ├── 📄 prisma.ts
│   │   │   │   ├── 📄 public-api-error.test.ts
│   │   │   │   ├── 📄 public-api-error.ts
│   │   │   │   ├── 📄 public-openapi.test.ts
│   │   │   │   ├── 📄 public-openapi.ts
│   │   │   │   ├── 📄 qstash.test.ts
│   │   │   │   ├── 📄 qstash.ts
│   │   │   │   ├── 📄 rate-limit.test.ts
│   │   │   │   ├── 📄 rate-limit.ts
│   │   │   │   ├── 📄 read-request-json.ts
│   │   │   │   ├── 📄 redact-fields.ts
│   │   │   │   ├── 📄 redirect.test.ts
│   │   │   │   ├── 📄 redirect.ts
│   │   │   │   ├── 📄 request-body.test.ts
│   │   │   │   ├── 📄 request-body.ts
│   │   │   │   ├── 📄 request-timing.ts
│   │   │   │   ├── 📄 risk.test.ts
│   │   │   │   ├── 📄 risk.ts
│   │   │   │   ├── 📄 rule-action-feature-gates.ts
│   │   │   │   ├── 📄 safe-reload.test.ts
│   │   │   │   ├── 📄 safe-reload.ts
│   │   │   │   ├── 📄 schedule-after-page-load.ts
│   │   │   │   ├── 📄 schedule.test.ts
│   │   │   │   ├── 📄 schedule.ts
│   │   │   │   ├── 📄 sender-stats.test.ts
│   │   │   │   ├── 📄 sender-stats.ts
│   │   │   │   ├── 📄 sentry-scrub.test.ts
│   │   │   │   ├── 📄 sentry-scrub.ts
│   │   │   │   ├── 📄 similarity-score.test.ts
│   │   │   │   ├── 📄 similarity-score.ts
│   │   │   │   ├── 📄 sleep.ts
│   │   │   │   ├── 📄 stale-deployment.test.ts
│   │   │   │   ├── 📄 stale-deployment.ts
│   │   │   │   ├── 📄 stats.ts
│   │   │   │   ├── 📄 string.test.ts
│   │   │   │   ├── 📄 string.ts
│   │   │   │   ├── 📄 stringify-email.test.ts
│   │   │   │   ├── 📄 stringify-email.ts
│   │   │   │   ├── 📄 stripe-amount.test.ts
│   │   │   │   ├── 📄 stripe-amount.ts
│   │   │   │   ├── 📄 swr-persistence.test.ts
│   │   │   │   ├── 📄 swr-persistence.ts
│   │   │   │   ├── 📄 swr.test.ts
│   │   │   │   ├── 📄 swr.ts
│   │   │   │   ├── 📄 template.test.ts
│   │   │   │   ├── 📄 template.ts
│   │   │   │   ├── 📄 terminology-messages.ts
│   │   │   │   ├── 📄 terminology.ts
│   │   │   │   ├── 📄 timezone.test.ts
│   │   │   │   ├── 📄 timezone.ts
│   │   │   │   ├── 📄 to-reply-push.test.ts
│   │   │   │   ├── 📄 to-reply-push.ts
│   │   │   │   ├── 📄 tokenize-search-query.ts
│   │   │   │   ├── 📄 tree-selection.test.ts
│   │   │   │   ├── 📄 tree-selection.ts
│   │   │   │   ├── 📄 types.ts
│   │   │   │   ├── 📄 unsubscribe.ts
│   │   │   │   ├── 📄 url.test.ts
│   │   │   │   ├── 📄 url.ts
│   │   │   │   ├── 📄 usage.test.ts
│   │   │   │   ├── 📄 usage.ts
│   │   │   │   ├── 📄 user.ts
│   │   │   │   ├── 📄 uuid.test.ts
│   │   │   │   ├── 📄 uuid.ts
│   │   │   │   ├── 📄 whitelist-inbox-zero.ts
│   │   │   │   └── 📄 zod.ts
│   │   │   ├── ⚙️ .env.example
│   │   │   ├── 📝 AGENTS.md
│   │   │   ├── 📝 CLAUDE.md
│   │   │   ├── ⚙️ components.json
│   │   │   ├── ⚙️ emulate.playwright.config.yaml
│   │   │   ├── ⚙️ emulate.playwright.microsoft.yaml
│   │   │   ├── 📄 entrypoint.sh
│   │   │   ├── 📄 env-legacy-llms.test.ts
│   │   │   ├── 📄 env-legacy-llms.ts
│   │   │   ├── 📄 env.test.ts
│   │   │   ├── 📄 env.ts
│   │   │   ├── 📄 instrumentation-client.ts
│   │   │   ├── 📄 instrumentation.ts
│   │   │   ├── 📄 lingui.config.ts
│   │   │   ├── 📄 mdx-components.tsx
│   │   │   ├── 📄 next.config.ts
│   │   │   ├── ⚙️ package.json
│   │   │   ├── 📄 playwright.config.mjs
│   │   │   ├── ⚙️ postcss.config.json
│   │   │   ├── 📄 prisma.config.test.ts
│   │   │   ├── 📄 prisma.config.ts
│   │   │   ├── 📄 proxy.test.ts
│   │   │   ├── 📄 proxy.ts
│   │   │   ├── 📄 sanity.cli.ts
│   │   │   ├── 📄 sanity.config.ts
│   │   │   ├── 📄 serwist.config.mjs
│   │   │   ├── 📄 serwist.config.test.ts
│   │   │   ├── 📄 tailwind.config.js
│   │   │   ├── ⚙️ tsconfig.eval-script.json
│   │   │   ├── ⚙️ tsconfig.json
│   │   │   ├── ⚙️ vercel.json
│   │   │   └── 📄 vitest.config.mts
│   │   └── 📁 worker
│   │       ├── 📁 src
│   │       │   ├── 📄 index.mjs
│   │       │   └── 📄 runtime.mjs
│   │       └── ⚙️ package.json
│   ├── 📁 charts
│   │   └── 📁 inbox-zero
│   │       ├── 📁 templates
│   │       │   ├── 📄 _helpers.tpl
│   │       │   ├── ⚙️ configmap.yaml
│   │       │   ├── ⚙️ cronjobs.yaml
│   │       │   ├── ⚙️ ingress.yaml
│   │       │   ├── ⚙️ migration-job.yaml
│   │       │   ├── ⚙️ postgresql.yaml
│   │       │   ├── ⚙️ redis-http.yaml
│   │       │   ├── ⚙️ redis.yaml
│   │       │   ├── ⚙️ secret.yaml
│   │       │   ├── ⚙️ serviceaccount.yaml
│   │       │   ├── ⚙️ web-deployment.yaml
│   │       │   ├── ⚙️ web-service.yaml
│   │       │   └── ⚙️ worker-deployment.yaml
│   │       ├── ⚙️ Chart.yaml
│   │       ├── 📝 README.md
│   │       └── ⚙️ values.yaml
│   ├── 📁 clawhub
│   │   ├── 📁 inbox-zero-api
│   │   │   ├── 📁 agents
│   │   │   │   └── ⚙️ openai.yaml
│   │   │   ├── 📁 references
│   │   │   │   └── 📝 cli-reference.md
│   │   │   └── 📝 SKILL.md
│   │   └── 📝 README.md
│   ├── 📁 copilot
│   │   ├── 📁 environments
│   │   │   └── 📁 addons
│   │   │       ├── ⚙️ addons.parameters.yml
│   │   │       ├── ⚙️ elasticache-redis.yml
│   │   │       └── ⚙️ rds.yml
│   │   ├── 📁 inbox-zero-ecs
│   │   │   └── ⚙️ manifest.yml
│   │   └── 📁 templates
│   │       └── ⚙️ webhook-gateway.yml
│   ├── 📁 docker
│   │   ├── 📁 scripts
│   │   │   ├── 📄 configure-rds-ca.sh
│   │   │   ├── 📄 migrate.sh
│   │   │   ├── 📄 prisma.config.ts
│   │   │   ├── 📄 publish-ghcr.sh
│   │   │   ├── 📄 replace-in-prerender.mjs
│   │   │   ├── 📄 replace-next-public-placeholders.sh
│   │   │   ├── 📄 replace-placeholder.sh
│   │   │   ├── 📄 run-local.sh
│   │   │   ├── 📄 start-worker.sh
│   │   │   └── 📄 start.sh
│   │   ├── 📄 Dockerfile.local
│   │   ├── 📄 Dockerfile.prod
│   │   └── ⚙️ docker-compose.local.yml
│   ├── 📁 docs
│   │   ├── 📁 api-reference
│   │   │   ├── 📁 endpoint
│   │   │   │   ├── 📄 delete-rules-id.mdx
│   │   │   │   ├── 📄 get-rules-id.mdx
│   │   │   │   ├── 📄 get-rules.mdx
│   │   │   │   ├── 📄 get-statsby-period.mdx
│   │   │   │   ├── 📄 get-statsresponse-time.mdx
│   │   │   │   ├── 📄 post-rules.mdx
│   │   │   │   ├── 📄 post-senders-unsubscribe.mdx
│   │   │   │   └── 📄 put-rules-id.mdx
│   │   │   ├── 📄 cli.mdx
│   │   │   ├── 📄 introduction.mdx
│   │   │   └── 📄 mcp.mdx
│   │   ├── 📁 changelog-entries
│   │   │   ├── 📄 2026-03-03.mdx
│   │   │   ├── 📄 2026-03-05.mdx
│   │   │   ├── 📄 2026-03-10.mdx
│   │   │   ├── 📄 2026-03-11.mdx
│   │   │   ├── 📄 2026-03-12.mdx
│   │   │   ├── 📄 2026-03-13.mdx
│   │   │   ├── 📄 2026-03-14.mdx
│   │   │   ├── 📄 2026-03-15.mdx
│   │   │   ├── 📄 2026-03-17.mdx
│   │   │   ├── 📄 2026-03-18.mdx
│   │   │   ├── 📄 2026-03-19.mdx
│   │   │   ├── 📄 2026-03-22.mdx
│   │   │   ├── 📄 2026-03-28.mdx
│   │   │   ├── 📄 2026-03-30.mdx
│   │   │   ├── 📄 2026-03-31.mdx
│   │   │   ├── 📄 2026-04-07.mdx
│   │   │   ├── 📄 2026-04-14.mdx
│   │   │   ├── 📄 2026-04-15.mdx
│   │   │   ├── 📄 2026-04-16.mdx
│   │   │   ├── 📄 2026-04-17.mdx
│   │   │   ├── 📄 2026-04-22.mdx
│   │   │   ├── 📄 2026-04-28.mdx
│   │   │   ├── 📄 2026-04-30.mdx
│   │   │   ├── 📄 2026-05-01.mdx
│   │   │   ├── 📄 2026-05-07.mdx
│   │   │   ├── 📄 2026-05-12.mdx
│   │   │   ├── 📄 2026-05-13.mdx
│   │   │   ├── 📄 2026-05-18.mdx
│   │   │   ├── 📄 2026-05-20.mdx
│   │   │   ├── 📄 2026-06-02.mdx
│   │   │   ├── 📄 2026-06-12.mdx
│   │   │   ├── 📄 2026-06-17.mdx
│   │   │   ├── 📄 2026-06-23.mdx
│   │   │   ├── 📄 2026-06-28.mdx
│   │   │   ├── 📄 2026-07-13.mdx
│   │   │   ├── 📄 2026-07-30.mdx
│   │   │   ├── 📄 2026-07-31.mdx
│   │   │   ├── 📄 2026-08-02.mdx
│   │   │   ├── 📄 2026-08-07.mdx
│   │   │   ├── 📄 2026-08-11.mdx
│   │   │   ├── 📄 2026-08-12.mdx
│   │   │   ├── 📄 2026-08-15.mdx
│   │   │   ├── 📄 2026-08-16.mdx
│   │   │   ├── 📄 2026-08-17.mdx
│   │   │   ├── 📄 2026-08-18.mdx
│   │   │   ├── 📄 2026-08-24.mdx
│   │   │   ├── 📄 2026-08-25.mdx
│   │   │   ├── 📄 2026-08-26.mdx
│   │   │   ├── 📄 2026-08-28.mdx
│   │   │   ├── 📄 2026-08-31.mdx
│   │   │   ├── 📄 2026-09-01.mdx
│   │   │   ├── 📄 2026-09-03.mdx
│   │   │   ├── 📄 2026-09-06.mdx
│   │   │   ├── 📄 2026-09-07.mdx
│   │   │   ├── 📄 2026-09-08.mdx
│   │   │   ├── 📄 2026-09-09.mdx
│   │   │   ├── 📄 2026-09-10.mdx
│   │   │   ├── 📄 2026-09-11.mdx
│   │   │   ├── 📄 2026-09-12.mdx
│   │   │   ├── 📄 2026-09-15.mdx
│   │   │   ├── 📄 2026-09-16.mdx
│   │   │   ├── 📄 2026-09-17.mdx
│   │   │   ├── 📄 2026-09-22.mdx
│   │   │   ├── 📄 2026-09-23.mdx
│   │   │   ├── 📄 2026-09-26.mdx
│   │   │   ├── 📄 2026-09-27.mdx
│   │   │   ├── 📄 2026-09-28.mdx
│   │   │   ├── 📄 2026-10-03.mdx
│   │   │   ├── 📄 2026-10-06.mdx
│   │   │   ├── 📄 2026-10-07.mdx
│   │   │   ├── 📄 2026-10-08.mdx
│   │   │   ├── 📄 2026-10-09.mdx
│   │   │   ├── 📄 2026-10-10.mdx
│   │   │   ├── 📄 2026-10-14.mdx
│   │   │   ├── 📄 2026-10-16.mdx
│   │   │   ├── 📄 2026-10-19.mdx
│   │   │   ├── 📄 2026-10-20.mdx
│   │   │   ├── 📄 2026-10-21.mdx
│   │   │   ├── 📄 2026-10-22.mdx
│   │   │   ├── 📄 2026-10-30.mdx
│   │   │   └── 📄 2026-10-31.mdx
│   │   ├── 📁 essentials
│   │   │   ├── 📄 ai-chat.mdx
│   │   │   ├── 📄 api-keys.mdx
│   │   │   ├── 📄 assistant-settings.mdx
│   │   │   ├── 📄 auto-file-attachments.mdx
│   │   │   ├── 📄 booking-links.mdx
│   │   │   ├── 📄 bulk-archiver.mdx
│   │   │   ├── 📄 bulk-email-unsubscriber.mdx
│   │   │   ├── 📄 calendar-integration.mdx
│   │   │   ├── 📄 call-webhook.mdx
│   │   │   ├── 📄 channels.mdx
│   │   │   ├── 📄 cold-email-blocker.mdx
│   │   │   ├── 📄 context-integrations.mdx
│   │   │   ├── 📄 deep-clean.mdx
│   │   │   ├── 📄 delayed-actions.mdx
│   │   │   ├── 📄 email-ai-personal-assistant.mdx
│   │   │   ├── 📄 email-analytics.mdx
│   │   │   ├── 📄 email-digest.mdx
│   │   │   ├── 📄 faq.mdx
│   │   │   ├── 📄 getting-started.mdx
│   │   │   ├── 📄 inbox-zero-tabs-extension.mdx
│   │   │   ├── 📄 mcp.mdx
│   │   │   ├── 📄 meeting-briefs.mdx
│   │   │   ├── 📄 meeting-recorder.mdx
│   │   │   ├── 📄 mobile-apps.mdx
│   │   │   ├── 📄 organizations.mdx
│   │   │   ├── 📄 outlook-guide.mdx
│   │   │   ├── 📄 reply-zero.mdx
│   │   │   ├── 📄 security-and-data.mdx
│   │   │   ├── 📄 slack-integration.mdx
│   │   │   ├── 📄 telegram-integration.mdx
│   │   │   └── 📄 troubleshooting.mdx
│   │   ├── 📁 hosting
│   │   │   ├── 📄 aws-copilot.mdx
│   │   │   ├── 📄 aws.mdx
│   │   │   ├── 📄 ec2-deployment.mdx
│   │   │   ├── 📄 environment-variables.mdx
│   │   │   ├── 📄 gcp-cloudflare-tunnel.mdx
│   │   │   ├── 📄 google-oauth.mdx
│   │   │   ├── 📄 google-pubsub.mdx
│   │   │   ├── 📄 image-proxy.mdx
│   │   │   ├── 📄 kubernetes.mdx
│   │   │   ├── 📄 llm-setup.mdx
│   │   │   ├── 📄 microsoft-oauth.mdx
│   │   │   ├── 📄 production-operations.mdx
│   │   │   ├── 📄 quick-start.mdx
│   │   │   ├── 📄 security-hardening.mdx
│   │   │   ├── 📄 self-hosting.mdx
│   │   │   ├── 📄 setup-cli-reference.mdx
│   │   │   ├── 📄 setup-guides.mdx
│   │   │   ├── 📄 sso.mdx
│   │   │   ├── 📄 terraform.mdx
│   │   │   ├── 📄 troubleshooting.mdx
│   │   │   └── 📄 vercel.mdx
│   │   ├── 📁 images
│   │   │   ├── 📁 self-hosting
│   │   │   │   ├── 📁 google-auth
│   │   │   │   │   ├── 🖼️ 1-create-oauth-client.png
│   │   │   │   │   ├── 🖼️ 10-enable-people-api.png
│   │   │   │   │   ├── 🖼️ 2-create-oauth-client.png
│   │   │   │   │   ├── 🖼️ 3-clientid-secret.png
│   │   │   │   │   ├── 🖼️ 4-internal.png
│   │   │   │   │   ├── 🖼️ 5-extenal-add-user.png
│   │   │   │   │   ├── 🖼️ 6-add-scopes.png
│   │   │   │   │   ├── 🖼️ 7-add-scopes.png
│   │   │   │   │   ├── 🖼️ 8-save-scopes.png
│   │   │   │   │   └── 🖼️ 9-enable-gmail-api.png
│   │   │   │   └── 📁 vercel
│   │   │   │       └── 🖼️ neon.png
│   │   │   ├── 🖼️ ai-personal-assistant-prompt.png
│   │   │   ├── 🖼️ ai-rules.png
│   │   │   ├── 🖼️ analytics.png
│   │   │   ├── 🖼️ automation-rule.png
│   │   │   ├── 🖼️ extension.png
│   │   │   ├── 🖼️ how-ai-rules-work.png
│   │   │   ├── 🖼️ labels.png
│   │   │   ├── 🖼️ newsletter-row.png
│   │   │   ├── 🖼️ settings-api-key.png
│   │   │   └── 🖼️ test-rules.png
│   │   ├── 📁 logo
│   │   │   ├── 🖼️ dark.svg
│   │   │   └── 🖼️ light.svg
│   │   ├── 📁 plans
│   │   │   ├── 📝 mail-engine-plan.md
│   │   │   └── 📝 team-comments-plan.md
│   │   ├── 📁 scripts
│   │   │   └── 📄 build-changelog.mjs
│   │   ├── 📁 slack
│   │   │   ├── ⚙️ manifest.yaml
│   │   │   └── 📄 setup.mdx
│   │   ├── 📁 teams
│   │   │   └── 📄 setup.mdx
│   │   ├── 📁 telegram
│   │   │   └── 📄 setup.mdx
│   │   ├── ⚙️ .gitignore
│   │   ├── 📝 better-auth-1.7-upgrade.md
│   │   ├── 📄 changelog.mdx
│   │   ├── 📄 contributing.mdx
│   │   ├── ⚙️ docs.json
│   │   ├── 🖼️ favicon.png
│   │   ├── 📄 introduction.mdx
│   │   ├── 📝 mail-api-splits.md
│   │   ├── 📝 mail-packages.md
│   │   └── ⚙️ openapi.json
│   ├── 📁 packages
│   │   ├── 📁 api
│   │   │   ├── 📁 src
│   │   │   │   ├── 📄 api-types.ts
│   │   │   │   ├── 📄 client.test.ts
│   │   │   │   ├── 📄 client.ts
│   │   │   │   ├── 📄 config.test.ts
│   │   │   │   ├── 📄 config.ts
│   │   │   │   ├── 📄 io.test.ts
│   │   │   │   ├── 📄 io.ts
│   │   │   │   ├── 📄 main.ts
│   │   │   │   └── 📄 output.ts
│   │   │   ├── ⚙️ .gitignore
│   │   │   ├── 📝 README.md
│   │   │   ├── ⚙️ package.json
│   │   │   ├── ⚙️ tsconfig.json
│   │   │   └── 📄 vitest.config.ts
│   │   ├── 📁 cli
│   │   │   ├── 📁 src
│   │   │   │   ├── 📁 aws-setup
│   │   │   │   │   ├── 📄 aws-cli.test.ts
│   │   │   │   │   ├── 📄 aws-cli.ts
│   │   │   │   │   ├── 📄 bedrock-manifest.test.ts
│   │   │   │   │   ├── 📄 bedrock.test.ts
│   │   │   │   │   ├── 📄 bedrock.ts
│   │   │   │   │   ├── 📄 google-pubsub.test.ts
│   │   │   │   │   ├── 📄 google-pubsub.ts
│   │   │   │   │   ├── 📄 manifest-secrets.test.ts
│   │   │   │   │   ├── 📄 ssm-urls.test.ts
│   │   │   │   │   └── 📄 ssm-urls.ts
│   │   │   │   ├── 📄 google-pubsub.test.ts
│   │   │   │   ├── 📄 google-pubsub.ts
│   │   │   │   ├── 📄 llm.ts
│   │   │   │   ├── 📄 main.ts
│   │   │   │   ├── 📄 setup-aws-google.test.ts
│   │   │   │   ├── 📄 setup-aws.test.ts
│   │   │   │   ├── 📄 setup-aws.ts
│   │   │   │   ├── 📄 setup-google.ts
│   │   │   │   ├── 📄 setup-ports-selection.test.ts
│   │   │   │   ├── 📄 setup-ports.test.ts
│   │   │   │   ├── 📄 setup-ports.ts
│   │   │   │   ├── 📄 setup-terraform.test.ts
│   │   │   │   ├── 📄 setup-terraform.ts
│   │   │   │   ├── 📄 setup-vercel.test.ts
│   │   │   │   ├── 📄 setup-vercel.ts
│   │   │   │   ├── 📄 utils.test.ts
│   │   │   │   └── 📄 utils.ts
│   │   │   ├── ⚙️ .gitignore
│   │   │   ├── 📝 README.md
│   │   │   ├── 📄 bun.lock
│   │   │   ├── ⚙️ package.json
│   │   │   ├── ⚙️ tsconfig.json
│   │   │   └── 📄 vitest.config.ts
│   │   ├── 📁 email-editor
│   │   │   ├── 📁 scripts
│   │   │   │   ├── 📄 clean-package.mjs
│   │   │   │   └── 📄 prepare-package.mjs
│   │   │   ├── 📁 src
│   │   │   │   ├── 📁 core
│   │   │   │   │   ├── 📄 email-body.test.ts
│   │   │   │   │   ├── 📄 email-body.ts
│   │   │   │   │   ├── 📄 email-html.test.ts
│   │   │   │   │   ├── 📄 email-html.ts
│   │   │   │   │   ├── 📄 email-profile.ts
│   │   │   │   │   └── 📄 sanitizer.test-utils.ts
│   │   │   │   ├── 📁 fixtures
│   │   │   │   │   └── 📄 email-html.ts
│   │   │   │   └── 📁 web
│   │   │   │       ├── 📁 squire
│   │   │   │       │   ├── 📄 SquireEmailEditor.test.tsx
│   │   │   │       │   ├── 📄 SquireEmailEditor.tsx
│   │   │   │       │   ├── 📄 placement.test.ts
│   │   │   │       │   ├── 📄 placement.ts
│   │   │   │       │   ├── 📄 selection-toolbar.tsx
│   │   │   │       │   └── 📄 slash-trigger.ts
│   │   │   │       ├── 🎨 EmailEditor.module.css
│   │   │   │       ├── 📄 EmailEditor.tsx
│   │   │   │       ├── 📄 css.d.ts
│   │   │   │       ├── 📄 link-panel.tsx
│   │   │   │       ├── 📄 preserved-block.tsx
│   │   │   │       ├── 📄 sanitize-dom.test.ts
│   │   │   │       ├── 📄 sanitize-dom.ts
│   │   │   │       └── 📄 toolbar.tsx
│   │   │   ├── 📝 README.md
│   │   │   ├── ⚙️ package.json
│   │   │   └── ⚙️ tsconfig.json
│   │   ├── 📁 image-proxy
│   │   │   ├── 📁 src
│   │   │   │   ├── 📄 node-safe-fetch.test.ts
│   │   │   │   ├── 📄 node-safe-fetch.ts
│   │   │   │   ├── 📄 proxy-service.test.ts
│   │   │   │   ├── 📄 proxy-service.ts
│   │   │   │   ├── 📄 proxy-url.test.ts
│   │   │   │   └── 📄 proxy-url.ts
│   │   │   ├── ⚙️ package.json
│   │   │   └── ⚙️ tsconfig.json
│   │   ├── 📁 loops
│   │   │   ├── 📁 src
│   │   │   │   ├── 📄 index.ts
│   │   │   │   ├── 📄 loops.test.ts
│   │   │   │   └── 📄 loops.ts
│   │   │   ├── 📝 README.md
│   │   │   ├── ⚙️ package.json
│   │   │   └── ⚙️ tsconfig.json
│   │   ├── 📁 mail-core
│   │   │   ├── 📁 scripts
│   │   │   │   ├── 📄 check-imports.mjs
│   │   │   │   ├── 📄 clean-package.mjs
│   │   │   │   ├── 📄 pack-consumer-smoke.mjs
│   │   │   │   ├── 📄 prepare-package.mjs
│   │   │   │   └── 📄 rewrite-relative-imports.mjs
│   │   │   ├── 📁 src
│   │   │   │   ├── 📁 ports
│   │   │   │   │   ├── 📄 assistant-source.ts
│   │   │   │   │   ├── 📄 mail-store.ts
│   │   │   │   │   ├── 📄 mailbox-source.ts
│   │   │   │   │   ├── 📄 operation-executor.ts
│   │   │   │   │   └── 📄 runtime.ts
│   │   │   │   ├── 📁 protocol
│   │   │   │   │   ├── 📄 backend-adapter.test.ts
│   │   │   │   │   ├── 📄 backend-adapter.ts
│   │   │   │   │   ├── 📄 mail-http.ts
│   │   │   │   │   ├── 📄 mail-ipc-client.test.ts
│   │   │   │   │   ├── 📄 mail-ipc-client.ts
│   │   │   │   │   ├── 📄 mail-ipc.ts
│   │   │   │   │   └── 📄 routed-backend-adapter.ts
│   │   │   │   ├── 📄 canonical.test.ts
│   │   │   │   ├── 📄 canonical.ts
│   │   │   │   ├── 📄 commands.ts
│   │   │   │   ├── 📄 drafts.ts
│   │   │   │   ├── 📄 effective-state.test.ts
│   │   │   │   ├── 📄 effective-state.ts
│   │   │   │   ├── 📄 engine.test.ts
│   │   │   │   ├── 📄 engine.ts
│   │   │   │   ├── 📄 identities.ts
│   │   │   │   ├── 📄 messages.test.ts
│   │   │   │   ├── 📄 messages.ts
│   │   │   │   ├── 📄 operations.ts
│   │   │   │   ├── 📄 optimistic-client.test.ts
│   │   │   │   ├── 📄 optimistic-client.ts
│   │   │   │   ├── 📄 queries.ts
│   │   │   │   ├── 📄 query-semantics.test.ts
│   │   │   │   ├── 📄 query-semantics.ts
│   │   │   │   ├── 📄 subscriptions.test.ts
│   │   │   │   ├── 📄 subscriptions.ts
│   │   │   │   └── 📄 sync.ts
│   │   │   ├── 📁 test-support
│   │   │   │   ├── 📄 reference-model.test.ts
│   │   │   │   ├── 📄 reference-model.ts
│   │   │   │   └── 📄 scenarios.ts
│   │   │   ├── 📝 README.md
│   │   │   ├── ⚙️ package.json
│   │   │   └── ⚙️ tsconfig.json
│   │   ├── 📁 mail-react
│   │   │   ├── 📁 scripts
│   │   │   │   ├── 📄 check-imports.mjs
│   │   │   │   ├── 📄 clean-package.mjs
│   │   │   │   └── 📄 prepare-package.mjs
│   │   │   ├── 📁 src
│   │   │   │   ├── 📄 MailEngineProvider.tsx
│   │   │   │   ├── 📄 use-conversation.ts
│   │   │   │   ├── 📄 use-mailbox-view.ts
│   │   │   │   ├── 📄 use-mailbox-window.ts
│   │   │   │   ├── 📄 use-operation.ts
│   │   │   │   └── 📄 use-query-snapshot.ts
│   │   │   ├── 📝 README.md
│   │   │   ├── ⚙️ package.json
│   │   │   └── ⚙️ tsconfig.json
│   │   ├── 📁 mail-sqlite
│   │   │   ├── 📁 scripts
│   │   │   │   ├── 📄 benchmark-body-compression.ts
│   │   │   │   ├── 📄 benchmark-queries.ts
│   │   │   │   ├── 📄 check-imports.mjs
│   │   │   │   ├── 📄 clean-package.mjs
│   │   │   │   └── 📄 prepare-package.mjs
│   │   │   ├── 📁 src
│   │   │   │   ├── 📄 capabilities.ts
│   │   │   │   ├── 📄 client-queries.test.ts
│   │   │   │   ├── 📄 contact-suggestions.performance.test.ts
│   │   │   │   ├── 📄 contact-suggestions.test.ts
│   │   │   │   ├── 📄 contact-suggestions.ts
│   │   │   │   ├── 📄 conversation-index.test.ts
│   │   │   │   ├── 📄 conversation-index.ts
│   │   │   │   ├── 📄 driver.ts
│   │   │   │   ├── 📄 engine-assistant.test.ts
│   │   │   │   ├── 📄 engine-bootstrap.test.ts
│   │   │   │   ├── 📄 engine-catch-up.test.ts
│   │   │   │   ├── 📄 engine-hydration.test.ts
│   │   │   │   ├── 📄 engine-retain-accounts.test.ts
│   │   │   │   ├── 📄 engine-retention.test.ts
│   │   │   │   ├── 📄 engine-search.test.ts
│   │   │   │   ├── 📄 engine-send-hold.test.ts
│   │   │   │   ├── 📄 mailbox-view-readers.ts
│   │   │   │   ├── 📄 maintenance.test.ts
│   │   │   │   ├── 📄 maintenance.ts
│   │   │   │   ├── 📄 message-body-codec.test.ts
│   │   │   │   ├── 📄 message-body-codec.ts
│   │   │   │   ├── 📄 message-body-migration.test.ts
│   │   │   │   ├── 📄 message-body-migration.ts
│   │   │   │   ├── 📄 message-search-index.test.ts
│   │   │   │   ├── 📄 message-search-index.ts
│   │   │   │   ├── 📄 migrations.test.ts
│   │   │   │   ├── 📄 migrations.ts
│   │   │   │   ├── 📄 node-sqlite.test.ts
│   │   │   │   ├── 📄 node-sqlite.ts
│   │   │   │   ├── 📄 queries.test.ts
│   │   │   │   ├── 📄 queries.ts
│   │   │   │   ├── 📄 query-corpus.test.ts
│   │   │   │   ├── 📄 search-text.test.ts
│   │   │   │   ├── 📄 search-text.ts
│   │   │   │   ├── 📄 store-diagnostics.test.ts
│   │   │   │   ├── 📄 store-purge-account.test.ts
│   │   │   │   ├── 📄 store-read-utils.ts
│   │   │   │   ├── 📄 store-search.test.ts
│   │   │   │   ├── 📄 store.test.ts
│   │   │   │   └── 📄 store.ts
│   │   │   ├── 📁 test-support
│   │   │   │   └── 📄 driver-contract.ts
│   │   │   ├── 📝 README.md
│   │   │   ├── ⚙️ package.json
│   │   │   └── ⚙️ tsconfig.json
│   │   ├── 📁 mail-ui
│   │   │   ├── 📁 src
│   │   │   │   ├── 📄 MailAccountSwitcherTrigger.tsx
│   │   │   │   ├── 📄 MailApp.tsx
│   │   │   │   ├── 📄 MailBody.tsx
│   │   │   │   ├── 📄 MailListToolbarSurface.tsx
│   │   │   │   ├── 📄 MailProductFrame.tsx
│   │   │   │   ├── 📄 MailReaderSurface.tsx
│   │   │   │   ├── 📄 MailSidebarRow.tsx
│   │   │   │   ├── 📄 MailThreadRow.tsx
│   │   │   │   ├── 📄 MailboxSurface.tsx
│   │   │   │   ├── 📄 host.ts
│   │   │   │   ├── 📄 image-preview.test.ts
│   │   │   │   ├── 📄 image-preview.ts
│   │   │   │   ├── 📄 inline-images.test.ts
│   │   │   │   ├── 📄 inline-images.ts
│   │   │   │   ├── 📄 linkify.test.ts
│   │   │   │   ├── 📄 linkify.ts
│   │   │   │   ├── 📄 prepare-inline-images.test.ts
│   │   │   │   ├── 📄 prepare-inline-images.ts
│   │   │   │   ├── 📄 safe-link-url.ts
│   │   │   │   ├── 📄 sanitize-html.test.ts
│   │   │   │   ├── 📄 sanitize-html.ts
│   │   │   │   └── 📄 utils.ts
│   │   │   ├── 📝 README.md
│   │   │   ├── ⚙️ package.json
│   │   │   └── ⚙️ tsconfig.json
│   │   ├── 📁 network
│   │   │   ├── 📁 src
│   │   │   │   ├── 📄 host-policy.test.ts
│   │   │   │   ├── 📄 host-policy.ts
│   │   │   │   ├── 📄 pinned-dns.ts
│   │   │   │   ├── 📄 safe-url.test.ts
│   │   │   │   └── 📄 safe-url.ts
│   │   │   ├── ⚙️ package.json
│   │   │   └── ⚙️ tsconfig.json
│   │   ├── 📁 scheduling
│   │   │   ├── 📁 src
│   │   │   │   ├── 📄 index.test.ts
│   │   │   │   └── 📄 index.ts
│   │   │   ├── ⚙️ package.json
│   │   │   └── ⚙️ tsconfig.json
│   │   ├── 📁 tinybird
│   │   │   ├── 📁 project
│   │   │   │   ├── 📁 datasources
│   │   │   │   │   ├── 📄 aiCall.datasource
│   │   │   │   │   └── 📄 email_action.datasource
│   │   │   │   ├── 📁 endpoints
│   │   │   │   │   ├── 📄 admin_ai_model_spend_by_period.pipe
│   │   │   │   │   ├── 📄 admin_ai_user_model_spend_by_period.pipe
│   │   │   │   │   ├── 📄 aiCalls.pipe
│   │   │   │   │   └── 📄 ai_generations_by_accounts_and_period.pipe
│   │   │   │   ├── 📁 pipes
│   │   │   │   │   ├── 📄 email_action_count.pipe
│   │   │   │   │   └── 📄 get_email_actions_by_period.pipe
│   │   │   │   └── ⚙️ tinybird.config.json
│   │   │   ├── 📁 src
│   │   │   │   ├── 📄 client.ts
│   │   │   │   ├── 📄 delete.test.ts
│   │   │   │   ├── 📄 delete.ts
│   │   │   │   ├── 📄 index.ts
│   │   │   │   ├── 📄 publish.ts
│   │   │   │   └── 📄 query.ts
│   │   │   ├── 📝 README.md
│   │   │   ├── ⚙️ package.json
│   │   │   └── ⚙️ tsconfig.json
│   │   ├── 📁 tinybird-ai-analytics
│   │   │   ├── 📁 src
│   │   │   │   ├── 📄 client.ts
│   │   │   │   ├── 📄 index.ts
│   │   │   │   ├── 📄 publish.ts
│   │   │   │   └── 📄 query.ts
│   │   │   ├── 📝 README.md
│   │   │   ├── ⚙️ package.json
│   │   │   └── ⚙️ tsconfig.json
│   │   ├── 📁 transactional-email
│   │   │   ├── 📁 emails
│   │   │   │   ├── 📁 components
│   │   │   │   │   ├── 📄 booking-email-layout.tsx
│   │   │   │   │   ├── 📄 inbox-zero-footer.tsx
│   │   │   │   │   ├── 📄 stats-email-footer.tsx
│   │   │   │   │   └── 📄 stats-email-layout.tsx
│   │   │   │   ├── 📄 action-required.tsx
│   │   │   │   ├── 📄 cold-email-notification.tsx
│   │   │   │   ├── 📄 digest.tsx
│   │   │   │   ├── 📄 guest-booking-confirmation.tsx
│   │   │   │   ├── 📄 guest-booking-rescheduled.tsx
│   │   │   │   ├── 📄 host-booking-cancellation.tsx
│   │   │   │   ├── 📄 host-booking-confirmation.tsx
│   │   │   │   ├── 📄 host-booking-rescheduled.tsx
│   │   │   │   ├── 📄 inbox-health.tsx
│   │   │   │   ├── 📄 invitation.tsx
│   │   │   │   ├── 📄 invoice.tsx
│   │   │   │   ├── 📄 meeting-briefing.tsx
│   │   │   │   ├── 📄 meeting-recap.tsx
│   │   │   │   ├── 📄 reconnection.tsx
│   │   │   │   └── 📄 summary.tsx
│   │   │   ├── 📁 src
│   │   │   │   ├── 📁 providers
│   │   │   │   │   ├── 📄 resend.test.ts
│   │   │   │   │   └── 📄 resend.ts
│   │   │   │   ├── 📄 client.ts
│   │   │   │   ├── 📄 contacts.ts
│   │   │   │   ├── 📄 delivery.test.ts
│   │   │   │   ├── 📄 delivery.ts
│   │   │   │   ├── 📄 index.ts
│   │   │   │   ├── 📄 provider.ts
│   │   │   │   ├── 📄 send.test.tsx
│   │   │   │   └── 📄 send.tsx
│   │   │   ├── 📝 README.md
│   │   │   ├── ⚙️ package.json
│   │   │   └── ⚙️ tsconfig.json
│   │   └── 📁 tsconfig
│   │       ├── ⚙️ base.json
│   │       ├── ⚙️ nextjs.json
│   │       └── ⚙️ package.json
│   ├── 📁 patches
│   │   ├── 📄 @sqlite.org__sqlite-wasm@3.54.1-build1.patch
│   │   └── 📝 README.md
│   ├── 📁 plugins
│   │   └── 📁 inbox-zero-mcp
│   │       ├── 📁 skills
│   │       │   └── 📁 inbox-zero-mcp
│   │       │       └── 📝 SKILL.md
│   │       ├── 📝 README.md
│   │       ├── ⚙️ mcp.json
│   │       └── ⚙️ plugin.json
│   ├── 📁 scripts
│   │   ├── 📄 dev-setup.ts
│   │   ├── 📄 install-private-build.mjs
│   │   ├── 📄 pnpm-install-without-desktop.sh
│   │   ├── 📄 publish-playwright-report.sh
│   │   ├── 📄 run-e2e-local.sh
│   │   └── 📄 sync-cursor-to-codex.sh
│   ├── 📁 skills
│   │   └── 📄 inbox-zero-api
│   ├── ⚙️ .coderabbit.yaml
│   ├── ⚙️ .cursorignore
│   ├── ⚙️ .dockerignore
│   ├── ⚙️ .gitignore
│   ├── ⚙️ .gitleaks.toml
│   ├── ⚙️ .gitleaksignore
│   ├── ⚙️ .ncurc.cjs
│   ├── ⚙️ .npmrc
│   ├── ⚙️ .nvmrc
│   ├── ⚙️ .private-build-revision
│   ├── 📝 AGENTS.md
│   ├── 📝 CLA.md
│   ├── 📝 CLAUDE.md
│   ├── 📄 LICENSE
│   ├── 📝 README.md
│   ├── 📝 SECURITY.md
│   ├── ⚙️ biome.json
│   ├── 📄 clone-marketing.sh
│   ├── ⚙️ docker-compose.dev.yml
│   ├── ⚙️ docker-compose.local.yml
│   ├── ⚙️ docker-compose.yml
│   ├── ⚙️ emulate.config.yaml
│   ├── ⚙️ konsistent.json
│   ├── ⚙️ package.json
│   ├── ⚙️ pnpm-lock.yaml
│   ├── ⚙️ pnpm-workspace.yaml
│   ├── ⚙️ skills-lock.json
│   ├── ⚙️ tsconfig.json
│   └── ⚙️ turbo.json
├── ⚙️ .gitkeep
└── 📝 README.md
```

---