# File Tree: enterprise_os

```
├── 📁 .github
│   └── 📁 workflows
│       ├── ⚙️ ci.yml
│       └── ⚙️ eval-regression.yml
├── 📁 backend
│   ├── 📁 alembic
│   │   ├── 📁 versions
│   │   │   ├── ⚙️ .gitkeep
│   │   │   └── 🐍 0001_initial_schema.py
│   │   ├── 🐍 env.py
│   │   └── 📄 script.py.mako
│   ├── 📁 app
│   │   ├── 📁 agents
│   │   │   ├── 📁 prompts
│   │   │   │   ├── 🐍 analytics_prompt.py
│   │   │   │   ├── 🐍 compliance_prompt.py
│   │   │   │   ├── 🐍 copywriter_prompt.py
│   │   │   │   ├── 🐍 strategist_prompt.py
│   │   │   │   └── 🐍 supervisor_prompt.py
│   │   │   ├── 📁 rubrics
│   │   │   │   ├── 🐍 compliance_rubric.py
│   │   │   │   ├── 🐍 platform_hook.py
│   │   │   │   └── 🐍 voice_fidelity.py
│   │   │   └── 📁 validators
│   │   │       ├── 🐍 campaign_schema.py
│   │   │       └── 🐍 platform_limits.py
│   │   ├── 📁 api
│   │   │   ├── 📁 v1
│   │   │   │   ├── 🐍 agents.py
│   │   │   │   ├── 🐍 analytics.py
│   │   │   │   ├── 🐍 approvals.py
│   │   │   │   ├── 🐍 auth.py
│   │   │   │   ├── 🐍 brands.py
│   │   │   │   ├── 🐍 campaigns.py
│   │   │   │   ├── 🐍 chat.py
│   │   │   │   ├── 🐍 mcp_servers.py
│   │   │   │   ├── 🐍 media.py
│   │   │   │   ├── 🐍 observability.py
│   │   │   │   ├── 🐍 router.py
│   │   │   │   ├── 🐍 runs.py
│   │   │   │   ├── 🐍 schedules.py
│   │   │   │   ├── 🐍 settings.py
│   │   │   │   ├── 🐍 skills.py
│   │   │   │   └── 🐍 users.py
│   │   │   └── 🐍 deps.py
│   │   ├── 📁 core
│   │   │   ├── 🐍 config.py
│   │   │   ├── 🐍 exceptions.py
│   │   │   ├── 🐍 idempotency.py
│   │   │   ├── 🐍 logging.py
│   │   │   ├── 🐍 rbac.py
│   │   │   ├── 🐍 security.py
│   │   │   └── 🐍 telemetry.py
│   │   ├── 📁 db
│   │   │   ├── 📁 models
│   │   │   │   ├── 🐍 analytics_event.py
│   │   │   │   ├── 🐍 approval.py
│   │   │   │   ├── 🐍 brand.py
│   │   │   │   ├── 🐍 campaign.py
│   │   │   │   ├── 🐍 chat.py
│   │   │   │   ├── 🐍 media_asset.py
│   │   │   │   ├── 🐍 platform_connection.py
│   │   │   │   ├── 🐍 run.py
│   │   │   │   ├── 🐍 schedule.py
│   │   │   │   └── 🐍 user.py
│   │   │   ├── 📁 repositories
│   │   │   │   ├── 🐍 approval_repo.py
│   │   │   │   ├── 🐍 base_repo.py
│   │   │   │   ├── 🐍 brand_repo.py
│   │   │   │   ├── 🐍 campaign_repo.py
│   │   │   │   ├── 🐍 chat_repo.py
│   │   │   │   ├── 🐍 media_repo.py
│   │   │   │   ├── 🐍 platform_connection_repo.py
│   │   │   │   └── 🐍 run_repo.py
│   │   │   ├── 🐍 __init__.py
│   │   │   ├── 🐍 base.py
│   │   │   └── 🐍 session.py
│   │   ├── 📁 integrations
│   │   │   ├── 📁 auth
│   │   │   │   └── 🐍 authlib_oauth.py
│   │   │   ├── 📁 browser
│   │   │   │   └── 🐍 playwright.py
│   │   │   ├── 📁 llm
│   │   │   │   ├── 🐍 model_router.py
│   │   │   │   └── 🐍 ollama_client.py
│   │   │   ├── 📁 media
│   │   │   │   ├── 📁 providers
│   │   │   │   │   ├── 🐍 image_provider.py
│   │   │   │   │   └── 🐍 video_provider.py
│   │   │   │   └── 🐍 ffmpeg.py
│   │   │   ├── 📁 social
│   │   │   │   ├── 🐍 base_adapter.py
│   │   │   │   ├── 🐍 facebook.py
│   │   │   │   ├── 🐍 google_business_profile.py
│   │   │   │   ├── 🐍 instagram.py
│   │   │   │   ├── 🐍 linkedin.py
│   │   │   │   ├── 🐍 pinterest.py
│   │   │   │   ├── 🐍 threads.py
│   │   │   │   ├── 🐍 x_twitter.py
│   │   │   │   └── 🐍 youtube.py
│   │   │   └── 📁 storage
│   │   │       └── 🐍 minio.py
│   │   ├── 📁 mcp
│   │   │   ├── 📁 registries
│   │   │   │   └── 🐍 toolset_registry.py
│   │   │   ├── 🐍 client.py
│   │   │   ├── 🐍 discovery.py
│   │   │   └── 🐍 host.py
│   │   ├── 📁 observability
│   │   │   ├── 📁 evals
│   │   │   │   ├── 🐍 golden_suite.py
│   │   │   │   ├── 🐍 rubric_judges.py
│   │   │   │   └── 🐍 trajectory_evals.py
│   │   │   ├── 🐍 langfuse.py
│   │   │   └── 🐍 otel.py
│   │   ├── 📁 orchestrator
│   │   │   ├── 📁 subgraphs
│   │   │   │   ├── 🐍 campaign_creative.py
│   │   │   │   ├── 🐍 closed_loop_eval.py
│   │   │   │   ├── 🐍 publishing_fanout.py
│   │   │   │   └── 🐍 research_strategy.py
│   │   │   ├── 📁 workers
│   │   │   │   ├── 🐍 agent_worker_factory.py
│   │   │   │   ├── 🐍 retry_policies.py
│   │   │   │   └── 🐍 tool_registry.py
│   │   │   ├── 🐍 checkpointer.py
│   │   │   ├── 🐍 graph.py
│   │   │   ├── 🐍 handoffs.py
│   │   │   ├── 🐍 routing.py
│   │   │   └── 🐍 state.py
│   │   ├── 📁 schemas
│   │   │   ├── 🐍 agent.py
│   │   │   ├── 🐍 analytics.py
│   │   │   ├── 🐍 approval.py
│   │   │   ├── 🐍 auth.py
│   │   │   ├── 🐍 brand.py
│   │   │   ├── 🐍 campaign.py
│   │   │   ├── 🐍 chat.py
│   │   │   ├── 🐍 common.py
│   │   │   ├── 🐍 mcp.py
│   │   │   ├── 🐍 media.py
│   │   │   ├── 🐍 run.py
│   │   │   ├── 🐍 schedule.py
│   │   │   ├── 🐍 settings.py
│   │   │   └── 🐍 skill.py
│   │   ├── 📁 services
│   │   │   ├── 🐍 analytics_service.py
│   │   │   ├── 🐍 approval_service.py
│   │   │   ├── 🐍 campaign_service.py
│   │   │   ├── 🐍 chat_service.py
│   │   │   ├── 🐍 media_service.py
│   │   │   ├── 🐍 publishing_service.py
│   │   │   ├── 🐍 run_service.py
│   │   │   ├── 🐍 sandbox_service.py
│   │   │   ├── 🐍 schedule_service.py
│   │   │   ├── 🐍 secret_service.py
│   │   │   └── 🐍 skill_service.py
│   │   ├── 📁 tasks
│   │   │   ├── 🐍 analytics_tasks.py
│   │   │   ├── 🐍 beat_schedule.py
│   │   │   ├── 🐍 celery_app.py
│   │   │   ├── 🐍 media_tasks.py
│   │   │   ├── 🐍 orchestrator_tasks.py
│   │   │   └── 🐍 publishing_tasks.py
│   │   └── 🐍 main.py
│   ├── 📁 mcp_servers
│   │   ├── 📁 analytics_server
│   │   │   ├── 🐍 main.py
│   │   │   └── 🐍 tools.py
│   │   ├── 📁 brand_rag_server
│   │   │   ├── 🐍 main.py
│   │   │   ├── 🐍 resources.py
│   │   │   └── 🐍 tools.py
│   │   ├── 📁 media_studio_server
│   │   │   ├── 🐍 main.py
│   │   │   └── 🐍 tasks_extension.py
│   │   └── 📁 social_gateway_server
│   │       ├── 📁 adapters
│   │       │   └── 🐍 __init__.py
│   │       ├── 🐍 main.py
│   │       └── 🐍 tools.py
│   ├── 📁 scripts
│   │   ├── 🐍 awaken_infrastructure.py
│   │   ├── 🐍 run_local_worker.py
│   │   ├── 🐍 seed_db.py
│   │   └── 🐍 validate_skills.py
│   ├── 📁 skills
│   │   ├── 📁 brand-voice-audit
│   │   │   ├── 📁 scripts
│   │   │   │   └── 🐍 check_tone.py
│   │   │   └── 📝 SKILL.md
│   │   ├── 📁 competitor-recon
│   │   │   ├── 📁 scripts
│   │   │   │   └── 🐍 parse_serp.py
│   │   │   └── 📝 SKILL.md
│   │   ├── 📁 media-compliance
│   │   │   ├── 📁 assets
│   │   │   │   └── ⚙️ aspect_ratio_rules.json
│   │   │   └── 📝 SKILL.md
│   │   └── 📁 multi-platform-copy
│   │       ├── 📁 references
│   │       │   └── 📝 PLATFORM_LIMITS.md
│   │       └── 📝 SKILL.md
│   ├── 📁 tests
│   │   ├── 📁 evals
│   │   │   └── 🐍 test_trajectory.py
│   │   ├── 📁 fixtures
│   │   │   └── ⚙️ sample_blueprint.json
│   │   ├── 📁 integration
│   │   │   ├── 🐍 test_api_v1_endpoints.py
│   │   │   ├── 🐍 test_chat_and_settings.py
│   │   │   ├── 🐍 test_graph.py
│   │   │   └── 🐍 test_hardening.py
│   │   └── 📁 unit
│   │       ├── 🐍 test_phase2_security_models.py
│   │       └── 🐍 test_state.py
│   ├── ⚙️ alembic.ini
│   └── ⚙️ pyproject.toml
├── 📁 docs
│   ├── 📁 runbooks
│   │   ├── 📝 incident-response.md
│   │   ├── 📝 local-dev.md
│   │   └── 📝 worker-sandbox.md
│   ├── 📝 agent-graphs.md
│   ├── 📝 api-contracts.md
│   ├── 📝 architecture.md
│   ├── 📝 mcp-and-skills.md
│   ├── 📝 observability.md
│   └── 📝 security-and-secrets.md
├── 📁 frontend
│   ├── 📁 public
│   │   └── ⚙️ .gitkeep
│   ├── 📁 src
│   │   ├── 📁 __tests__
│   │   │   └── 📄 chat-store.test.ts
│   │   ├── 📁 app
│   │   │   ├── 📁 (auth)
│   │   │   │   └── 📁 login
│   │   │   │       └── 📄 page.tsx
│   │   │   ├── 📁 (dashboard)
│   │   │   │   ├── 📁 agents
│   │   │   │   │   └── 📄 page.tsx
│   │   │   │   ├── 📁 analytics
│   │   │   │   │   └── 📄 page.tsx
│   │   │   │   ├── 📁 approvals
│   │   │   │   │   └── 📄 page.tsx
│   │   │   │   ├── 📁 brands
│   │   │   │   │   └── 📄 page.tsx
│   │   │   │   ├── 📁 campaigns
│   │   │   │   │   ├── 📁 [campaignId]
│   │   │   │   │   │   └── 📄 page.tsx
│   │   │   │   │   ├── 📁 new
│   │   │   │   │   │   └── 📄 page.tsx
│   │   │   │   │   └── 📄 page.tsx
│   │   │   │   ├── 📁 chat
│   │   │   │   │   └── 📄 page.tsx
│   │   │   │   ├── 📁 dashboard
│   │   │   │   │   └── 📄 page.tsx
│   │   │   │   ├── 📁 mcp-servers
│   │   │   │   │   └── 📄 page.tsx
│   │   │   │   ├── 📁 media
│   │   │   │   │   └── 📄 page.tsx
│   │   │   │   ├── 📁 observability
│   │   │   │   │   └── 📄 page.tsx
│   │   │   │   ├── 📁 runs
│   │   │   │   │   └── 📁 [runId]
│   │   │   │   │       └── 📄 page.tsx
│   │   │   │   ├── 📁 schedules
│   │   │   │   │   └── 📄 page.tsx
│   │   │   │   ├── 📁 settings
│   │   │   │   │   └── 📄 page.tsx
│   │   │   │   ├── 📁 skills
│   │   │   │   │   └── 📄 page.tsx
│   │   │   │   └── 📄 layout.tsx
│   │   │   ├── 📄 layout.tsx
│   │   │   └── 📄 page.tsx
│   │   ├── 📁 components
│   │   │   ├── 📁 agents
│   │   │   │   └── 📄 agent-card.tsx
│   │   │   ├── 📁 analytics
│   │   │   │   ├── 📄 anomaly-alert.tsx
│   │   │   │   └── 📄 kpi-charts.tsx
│   │   │   ├── 📁 approvals
│   │   │   │   ├── 📄 approval-card.tsx
│   │   │   │   ├── 📄 diff-viewer.tsx
│   │   │   │   └── 📄 resume-dialog.tsx
│   │   │   ├── 📁 campaigns
│   │   │   │   ├── 📄 blueprint-viewer.tsx
│   │   │   │   ├── 📄 campaign-form.tsx
│   │   │   │   └── 📄 campaign-list.tsx
│   │   │   ├── 📁 chat
│   │   │   │   ├── 📄 chat-composer.tsx
│   │   │   │   ├── 📄 chat-messages.tsx
│   │   │   │   └── 📄 chat-sidebar.tsx
│   │   │   ├── 📁 common
│   │   │   │   ├── 📄 json-schema-form.tsx
│   │   │   │   └── 📄 status-badge.tsx
│   │   │   ├── 📁 layout
│   │   │   │   ├── 📄 header.tsx
│   │   │   │   ├── 📄 sidebar.tsx
│   │   │   │   └── 📄 user-nav.tsx
│   │   │   ├── 📁 media
│   │   │   │   ├── 📄 asset-grid.tsx
│   │   │   │   └── 📄 upload-zone.tsx
│   │   │   ├── 📁 runs
│   │   │   │   ├── 📄 graph-visualizer.tsx
│   │   │   │   ├── 📄 node-timeline.tsx
│   │   │   │   └── 📄 tool-call-inspector.tsx
│   │   │   ├── 📁 skills
│   │   │   │   ├── 📄 skill-card.tsx
│   │   │   │   └── 📄 skill-editor.tsx
│   │   │   └── 📁 ui
│   │   │       └── 📄 button.tsx
│   │   ├── 📁 hooks
│   │   │   ├── 📄 use-approvals.ts
│   │   │   ├── 📄 use-campaigns.ts
│   │   │   ├── 📄 use-chat-stream.ts
│   │   │   └── 📄 use-run-stream.ts
│   │   ├── 📁 stores
│   │   │   ├── 📄 chat-store.ts
│   │   │   ├── 📄 run-store.ts
│   │   │   └── 📄 ui-store.ts
│   │   ├── 📁 styles
│   │   │   └── 🎨 globals.css
│   │   └── 📁 types
│   │       ├── 📄 api.ts
│   │       ├── 📄 graph.ts
│   │       └── 📄 models.ts
│   ├── ⚙️ .eslintrc.json
│   ├── 📄 next.config.ts
│   ├── ⚙️ package-lock.json
│   ├── ⚙️ package.json
│   ├── 📄 postcss.config.mjs
│   ├── 📄 tailwind.config.ts
│   ├── ⚙️ tsconfig.json
│   └── 📄 vitest.config.ts
├── 📁 infra
│   ├── 📁 compose
│   │   ├── ⚙️ docker-compose.dev.yml
│   │   └── ⚙️ docker-compose.prod.yml
│   ├── 📁 minio
│   │   └── ⚙️ .gitkeep
│   ├── 📁 observability
│   │   └── 📁 otel-collector
│   │       └── ⚙️ config.yaml
│   ├── 📁 ollama
│   │   └── ⚙️ .gitkeep
│   ├── 📁 podman
│   │   ├── 📄 frontend.Containerfile
│   │   ├── 📄 mcp.Containerfile
│   │   └── 📄 worker.Containerfile
│   ├── 📁 postgres
│   │   └── 📄 init.sql
│   ├── 📁 qdrant
│   │   └── ⚙️ .gitkeep
│   └── 📁 redis
│       └── ⚙️ .gitkeep
├── 📁 observability
│   ├── 📁 dashboards
│   │   └── ⚙️ langfuse-overview.json
│   ├── 📁 langfuse
│   │   └── ⚙️ .gitkeep
│   ├── 📁 otel-collector
│   │   └── ⚙️ config.yaml
│   └── 📝 README.md
├── 📁 packages
│   └── 📁 contracts
│       ├── 📁 generated
│       │   └── 📄 schema.ts
│       ├── 📄 index.ts
│       ├── ⚙️ openapi.json
│       ├── ⚙️ package-lock.json
│       └── ⚙️ package.json
├── ⚙️ .gitignore
├── 📝 Architecture Blueprint & Directory Specification.md
├── 📝 File Tree - enterprise_os.md
├── 📄 Makefile
├── 📝 README.md
├── 📝 agentic_brand_marketing_architecture_specification.md
├── ⚙️ docker-compose.yml
├── ⚙️ pyproject.toml
├── 📄 start.sh
├── 📄 start_agentic_system.sh
└── 📄 uv.lock
```

---