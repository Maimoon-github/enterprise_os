Viewed context.md:1-489
Viewed research%20findings.md:1-427
Viewed task%20plan,md:1-109
Listed directory sandbox
Viewed README.md:1-250
Viewed docker-compose.yaml:1-57
Listed directory sdk
Listed directory fern
Viewed generators.yml:1-49
Listed directory go
Viewed README.md:1-4
Listed directory js
Listed directory python
Searched for "F#"
Listed directory docker
Ran command: `find . -maxdepth 3 -iname "*docker*" -o -iname "*container*"`
Ran command: `find . -name "Dockerfile*" -o -name "*.docker*" -o -name "*seccomp*"`
Listed directory .github
Listed directory workflows
Viewed push-to-ghcr.yml:1-67
Listed directory cli
Listed directory evaluation
Listed directory examples
Listed directory agent_sandbox
Viewed client.py:1-150
Listed directory providers
Viewed __init__.py:1-100
Listed directory src
Listed directory api
Listed directory resources
Viewed README.md:1-100
Viewed Client.ts:1-150
Ran command: `find . -name "openapi.json"`
Ran command: `find /home/maimoon-amin/Antigravity\ code/enterprise_os -name "openapi.json"`
Listed directory __test__
Viewed integration.test.ts:1-77
Viewed fern-customizations.test.ts:1-100
Viewed fern-customizations.test.ts:101-171
Viewed sdk-ci.yml:1-49
Viewed sdk-publish.yml:1-100
Viewed sdk-publish.yml:101-190
Viewed pyproject.toml:1-38
Viewed README.md:1-149
Listed directory dataset
Viewed evaluation_basic.xml:1-80
Viewed dataset_parser.py:1-78
Viewed agent_loop.py:1-120
Listed directory tests
Listed directory result
Listed directory 20251112
Viewed Latest.md:1-60
Viewed improvement_suggestions.md:1-60
Viewed README.md:1-72
Listed directory langgraph-deepagents-integration
Viewed main.py:1-50
Viewed sandbox_backend.py:1-100
Viewed main.py:1-100
Viewed main.py:1-38
Viewed main.py:1-100
Viewed main.py:1-57
Viewed main.py:1-64
Viewed main.py:1-45
Viewed main.py:1-100
Viewed main.py:1-64
Viewed main.py:1-90
Viewed main.py:1-52

# Comprehensive Architecture & Codebase Analysis: AIO Sandbox

## 1. Executive Summary & Context Alignment

This investigation synthesizes the architecture, codebase, and runtime capabilities of the **AIO Sandbox** (`sandbox`) and evaluates how it underpins the autonomous agent architecture outlined in [context.md](file:///home/maimoon-amin/Antigravity%20code/enterprise_os/Context%20Research/context.md), [research findings.md](file:///home/maimoon-amin/Antigravity%20code/enterprise_os/Context%20Research/research%20findings.md), and [task plan,md](file:///home/maimoon-amin/Antigravity%20code/enterprise_os/Context%20Research/task%20plan%2Cmd).

```
+---------------------------------------------------------------------------------------------------+
|                        AUTONOMOUS MARKETING & E-COMMERCE AGENTIC WORKFLOW                         |
| (Perception & Audit -> Strategic Reasoning -> HitL Governance -> Execution -> Learning Flywheel)  |
+---------------------------------------------------------------------------------------------------+
                                                  |
                      SDK Abstraction Layer (Python / JS / Go / Fern Engine)
                                                  v
+---------------------------------------------------------------------------------------------------+
|                            AIO SANDBOX RUNTIME (aio-sandbox Docker)                              |
|                                                                                                   |
|  +--------------------+  +--------------------+  +--------------------+  +---------------------+  |
|  | BROWSER AUTOMATION |  | SHELL & PERSISTENCE|  | CODE & COMPUTATION |  | MCP & DEV TOOLING   |  |
|  | - CDP Port 9222    |  | - Bash Sessions    |  | - Jupyter (8888)   |  | - MCP Hub (8079)    |  |
|  | - VNC / noVNC 6080 |  | - Terminal WS      |  | - Node.js Sessions |  | - Code-Server (8200)|  |
|  +--------------------+  +--------------------+  +--------------------+  +---------------------+  |
|                                                                                                   |
|  +---------------------------------------------------------------------------------------------+  |
|  | UNIFIED SECURE CONTAINER ENVIRONMENT: Shared File System (/home/gem) & Egress Proxy (8118)  |  |
|  +---------------------------------------------------------------------------------------------+  |
+---------------------------------------------------------------------------------------------------+
```

The AIO Sandbox solves the fragmentation found in conventional multi-agent environments—where browser automation, shell execution, file manipulation, and code evaluation occur in disparate, disconnected containers. By providing a **unified runtime and shared filesystem (`/home/gem`)** encapsulated inside a single Docker container, agents can download assets via headless Chromium, inspect and manipulate them with shell/Python scripts, and publish them via MCP connectors without boundary-crossing file transfers.

---

## 2. In-Depth SDK Architecture Analysis (`sdk/`)

The SDK directory contains the client libraries through which AI agents and host orchestrators interact with the sandbox environment.

### 2.1 The Fern Code Generation Engine (`sdk/fern/`) & Clarification on "F#"

* **Fern Generator Configuration**:
  The directory [sdk/fern](file:///home/maimoon-amin/Antigravity%20code/enterprise_os/sandbox/sdk/fern) contains [fern.config.json](file:///home/maimoon-amin/Antigravity%20code/enterprise_os/sandbox/sdk/fern/fern.config.json) and [generators.yml](file:///home/maimoon-amin/Antigravity%20code/enterprise_os/sandbox/sdk/fern/generators.yml). Fern is a declarative compiler and API code generation toolchain that ingests an OpenAPI specification and generates typed client SDKs across multiple languages.
* **Clarification on "F#"**:
  The reference to **F#** arises from a phonetic or typographical conflation with **Fern** (`fern`). **There are no F# code files in the codebase.** The configured generators in [generators.yml](file:///home/maimoon-amin/Antigravity%20code/enterprise_os/sandbox/sdk/fern/generators.yml) are:
  1. `fernapi/fern-python-sdk` (v4.28.0) $\rightarrow$ generates Python package `agent_sandbox` into `../python/agent_sandbox`
  2. `fernapi/fern-typescript-sdk` (v3.28.4) $\rightarrow$ generates TypeScript/JavaScript package into `../js/src`
  3. `fernapi/fern-go-sdk` (v1.12.4) $\rightarrow$ targets `github.com/agent-infra/sandbox-sdk-go`

### 2.2 Python SDK (`sdk/python/agent_sandbox`)

* **Package & Packaging**: Defined in [pyproject.toml](file:///home/maimoon-amin/Antigravity%20code/enterprise_os/sandbox/sdk/python/pyproject.toml) as `agent-sandbox` (v0.0.31), authored by ByteDance engineers, targeting Python $\ge$ 3.8.
* **Core Dependencies**: `httpx[socks]>=0.23.0,<1`, `pydantic>=1.9.0,<3`, `volcengine-python-sdk>=4.0.17`.
* **Client Architecture**:
  The primary entry point is [Sandbox](file:///home/maimoon-amin/Antigravity%20code/enterprise_os/sandbox/sdk/python/agent_sandbox/client.py#L33-L105) (and `AsyncSandbox`). It initializes a `SyncClientWrapper` / `AsyncClientWrapper` backed by `httpx.Client` with configurable timeout (default 60s), headers, and optional socks proxy support.
* **Fern Protection & Cloud Extensions**:
  Via `.fernignore`, custom extensions in [sdk/python/agent_sandbox/providers](file:///home/maimoon-amin/Antigravity%20code/enterprise_os/sandbox/sdk/python/agent_sandbox/providers) are protected from being overwritten by Fern regeneration. This includes [volcengine.py](file:///home/maimoon-amin/Antigravity%20code/enterprise_os/sandbox/sdk/python/agent_sandbox/providers/volcengine.py) and [sign.py](file:///home/maimoon-amin/Antigravity%20code/enterprise_os/sandbox/sdk/python/agent_sandbox/providers/sign.py), implementing Volcengine VEFAAS serverless sandbox lifecycle operations (create, readiness check, domain resolution, and deletion) using AWS v4-style HMAC-SHA256 signature schemes.

### 2.3 JavaScript / TypeScript SDK (`sdk/js/`)

* **Package & Packaging**: Configured in [package.json](file:///home/maimoon-amin/Antigravity%20code/enterprise_os/sandbox/sdk/js/package.json) as `@agent-infra/sandbox`. Built using modern ByteDance toolchain: `rslib` ([rslib.config.ts](file:///home/maimoon-amin/Antigravity%20code/enterprise_os/sandbox/sdk/js/rslib.config.ts)) producing dual CommonJS (`dist/cjs`) and ECMAScript Modules (`dist/esm`).
* **Client Architecture**:
  Exported from [src/Client.ts](file:///home/maimoon-amin/Antigravity%20code/enterprise_os/sandbox/sdk/js/src/Client.ts) as `SandboxClient` (and aliased as `Sandbox`). It provides lazy getter initializations for all sub-services.
* **Quality Assurance & Fern Integrity**:
  The test suite in [sdk/js/__test__](file:///home/maimoon-amin/Antigravity%20code/enterprise_os/sandbox/sdk/js/__test__) includes [fern-customizations.test.ts](file:///home/maimoon-amin/Antigravity%20code/enterprise_os/sandbox/sdk/js/__test__/fern-customizations.test.ts), which ensures that code regenerated by Fern does not erase custom patches—such as `BodyInit` imports in `core/fetcher/`, `core.isFailedResponse` pattern checking, and protected provider files specified in `.fernignore`.

### 2.4 Go SDK (`sdk/go/`)

* Documented in [sdk/go/README.md](file:///home/maimoon-amin/Antigravity%20code/enterprise_os/sandbox/sdk/go/README.md), pointing to external repository `https://github.com/agent-infra/sandbox-sdk-go`.
* Managed via Fern's `sdk-go` generator targeting Go module path `github.com/agent-infra/sandbox-sdk-go`.

### 2.5 SDK Functional Subsystem Parity Matrix

Both the Python and JavaScript SDKs expose 1:1 service parity across 20 distinct sandbox subsystems:

| Subsystem | Python Accessor | JS Accessor | Operational Purpose |
| :--- | :--- | :--- | :--- |
| **Sandbox Core** | `client.sandbox` | `client.sandbox` | Query sandbox context, home directory (`/home/gem`), and lifecycle |
| **Shell** | `client.shell` | `client.shell` | Persistent terminal sessions, interactive command execution, grep |
| **Bash** | `client.bash` | `client.bash` | Synchronous one-off bash script execution with stdout/stderr capture |
| **File** | `client.file` | `client.file` | High-level file CRUD, binary/base64 encode, directory glob, regex search |
| **Jupyter** | `client.jupyter` | `client.jupyter` | Stateful IPython kernel execution (Python 3.12), cell outputs |
| **Node.js** | `client.nodejs` | `client.nodejs` | Stateful JavaScript execution runtime sessions |
| **MCP** | `client.mcp` | `client.mcp` | Query and call Model Context Protocol tools registered on MCP hub |
| **Browser Core** | `client.browser` | `client.browser` | High-level browser control, screenshot streaming, CDP metadata |
| **Browser Page** | `client.browser_page`| `client.browserPage`| Direct page actions (navigate, get markdown, click elements, fill) |
| **Browser Tabs** | `client.browser_tabs`| `client.browserTabs`| Multi-tab lifecycle (create tab, switch tab, list tabs, close tab) |
| **Browser State**| `client.browser_state`|`client.browserState`| Page load state, DOM readiness, scroll position |
| **Browser Cookies**|`client.browser_cookies`|`client.browserCookies`| Session cookie inspection, session storage injection |
| **Browser Network**|`client.browser_network`|`client.browserNetwork`| Network request inspection, HAR export, third-party tag audit |
| **Browser Captcha**|`client.browser_captcha`|`client.browserCaptcha`| Captcha detection and automated solver waiting hooks |
| **Code** | `client.code` | `client.code` | Polyglot code execution dispatch |
| **Util** | `client.util` | `client.util` | Utility transforms (e.g., HTML to Markdown conversion via Markitdown) |
| **Skills** | `client.skills` | `client.skills` | Modular skill definition and execution (Claude Skills standard) |
| **Proxy** | `client.proxy` | `client.proxy` | Egress network diagnosis, bypass routes, upstream verification |
| **Display** | `client.display` | `client.display` | Virtual X11 display controls, resolution adjustment, screen recording |
| **Auth** | `client.auth` | `client.auth` | Token authentication validation and access control |

---

## 3. Docker & Containerization Architecture (`docker/`, `docker-compose.yaml`)

The deployment architecture is centered on a single container running multiple cooperating daemons.

### 3.1 Container Lineage & CI/CD Pipeline

* **Repository State**: The directory [docker/](file:///home/maimoon-amin/Antigravity%20code/enterprise_os/sandbox/docker) contains `.gitkeep`. Rather than building the complex container image from scratch on every commit, the project uses an automated mirroring pipeline defined in [.github/workflows/push-to-ghcr.yml](file:///home/maimoon-amin/Antigravity%20code/enterprise_os/sandbox/.github/workflows/push-to-ghcr.yml).
* **Source Base Image**: `enterprise-public-cn-beijing.cr.volces.com/vefaas-public/all-in-one-sandbox:${VERSION}` (hosted by ByteDance Volcengine).
* **Destination Registry**: Mirrored via Docker Buildx imagetools into GitHub Container Registry: `ghcr.io/agent-infra/sandbox:latest` and tagged release versions.

### 3.2 Container Runtime Topology & Service Port Mappings

Inspecting [docker-compose.yaml](file:///home/maimoon-amin/Antigravity%20code/enterprise_os/sandbox/docker-compose.yaml) reveals the internal service orchestration:

```
HOST (127.0.0.1:8080)
         |
         v
[CONTAINER: aio-sandbox]
         |
         +--> 8080 (PUBLIC_PORT / Unified Gateway Reverse Proxy)
                 |
                 +--> 8081: AUTH_BACKEND_PORT (API Key & Bearer Token Validator)
                 +--> 8091: SANDBOX_SRV_PORT (Core REST API Server)
                 +--> 8079: MCP_HUB_PORT (Model Context Protocol Hub)
                 |        |--> 8100: MCP_SERVER_BROWSER
                 |        |--> 8101: MCP_SERVER_MARKITDOWN
                 |        |--> 8102: MCP_SERVER_CHROME_DEVTOOLS
                 +--> 6080: WEBSOCKET_PROXY_PORT (noVNC HTML5 Web Client)
                 |        `--> 5900: VNC_SERVER_PORT (x11vnc GUI Desktop)
                 +--> 9222: BROWSER_REMOTE_DEBUGGING_PORT (Chrome CDP Interface)
                 +--> 8888: JUPYTER_LAB_PORT (Python Kernel Runtime)
                 +--> 8200: CODE_SERVER_PORT (Browser VSCode IDE)
                 +--> 8088: GEM_SERVER_PORT (Workspace Daemon)
                 `--> 8118: TINYPROXY_PORT (Outbound Network Egress Controller)
```

### 3.3 Security, Isolation, & Resource Governance

* **Privilege & Seccomp**: Configured with `no-new-privileges:true` and `security_opt: [seccomp:unconfined]`. The compose file notes that hardened production environments should mount `./docker/seccomp-profile.json`.
* **Resource Quotas**:
  * `shm_size: "2gb"`: Explicitly allocated shared memory to prevent Chromium headless rendering crashes.
  * `mem_limit: "8g"`, `cpus: "4"`, `pids_limit: 1024` to prevent fork-bomb attacks.
  * `tmpfs`: Mounted on `/tmp` (`size=1024m,noexec,nosuid`) and `/run` (`size=256m,noexec,nosuid`).
* **Egress Network Filtering**:
  * `EGRESS_NETWORK_POLICY: DENY_ALL`
  * Outbound traffic is routed through Tinyproxy (`PROXY_SERVER: http://127.0.0.1:8118`).
  * `EGRESS_ALLOWLIST`: Enforces domain allowlists (e.g. `*.google.com`, `*.meta.com`, `*.tiktok.com`, `*.linkedin.com`).
  * `DNS_OVER_HTTPS_TEMPLATES`: Enforces encrypted DNS resolution via Cloudflare (`https://cloudflare-dns.com/dns-query{?dns}`) to prevent DNS poisoning.
* **Authentication Matrix**:
  * Supports `SANDBOX_API_KEY` via `X-AIO-API-Key` header, `Authorization: Bearer <key>`, or `?api_key=` URL parameter.
  * Supports `JWT_PUBLIC_KEY` for enterprise single-sign-on.

---

## 4. Evaluation Framework Architecture (`evaluation/`)

The evaluation framework in [evaluation/](file:///home/maimoon-amin/Antigravity%20code/enterprise_os/sandbox/evaluation) provides an automated, rigorous benchmark suite inspired by Anthropic's *"Writing Tools for Agents"*.

### 4.1 Orchestration & Agent Loop Engine

* **Entry Point**: [evaluation/main.py](file:///home/maimoon-amin/Antigravity%20code/enterprise_os/sandbox/evaluation/main.py) manages CLI arguments, concurrent evaluation batches (`MAX_CONCURRENT_TASKS`), MCP session connections, and markdown report generation.
* **Agent Loop Abstraction ([evaluation/agent_loop.py](file:///home/maimoon-amin/Antigravity%20code/enterprise_os/sandbox/evaluation/agent_loop.py))**:
  * `BaseAgentLoop`: Abstract base class enforcing the execution interface `run(prompt, tools) -> Tuple[str, Dict[str, Any]]`.
  * `AzureOpenAIAgentLoop`: Implements multi-turn tool-calling loops with Azure OpenAI endpoints.
  * `OpenAIAgentLoop`: Implements OpenAI and OpenAI-compatible API loops (such as MiniMax).
  * System Prompt Enforcement: Agents are constrained by `DEFAULT_SYSTEM_PROMPT` to emit structured reasoning tags:
    * `<summary>`: Trace of tools used, step-by-step logic.
    * `<feedback>`: Critique of tool signatures, parameter clarity, and failures.
    * `<response>`: Final concise answer for automated scoring.

### 4.2 Dataset Architecture ([evaluation/dataset/](file:///home/maimoon-amin/Antigravity%20code/enterprise_os/sandbox/evaluation/dataset))

The dataset parser ([dataset_parser.py](file:///home/maimoon-amin/Antigravity%20code/enterprise_os/sandbox/evaluation/dataset_parser.py)) parses XML benchmark definitions into executable task suites. Each task includes category metadata, complexity, prompt, and expected response:

```xml
<task category="file" complexity="simple">
    <description>Test file_operations write capability</description>
    <prompt>Create a file at /tmp/test_eval.txt with content "Hello MCP". Then read it back and return the content.</prompt>
    <response>Hello MCP</response>
</task>
```

#### Evaluation Categories:
1. `evaluation_ping.xml`: Basic connectivity and MCP handshake.
2. `evaluation_basic.xml`: Single-tool baseline tests (file ops, arithmetic code execution, shell commands).
3. `evaluation_browser.xml`: Core browser navigation, DOM inspection, link extraction, form input, tab creation.
4. `evaluation_browser_advanced.xml`: Complex browser interaction (click by selector or index, keyboard keypress, hover tooltips, multi-select, scroll by offset).
5. `evaluation_code_advanced.xml`: Complex algorithm execution, async code, structured exception handling.
6. `evaluation_collaboration.xml`: Cross-tool workflows (e.g. creating an HTML file with file tools, opening it in browser, executing JavaScript, and validating output via shell).
7. `evaluation_editor.xml`: Text editor mutations (view, str_replace, insert, undo_edit).
8. `evaluation_packages.xml`: Environment inspection and package manager detection (Python pip/uv, Node.js npm).
9. `evaluation_util.xml`: Markdown parsing and conversion utilities.
10. `evaluation_workflow.xml`: Multi-step real-world agent scenarios.
11. `evaluation_nextjs.xml`: Full application scaffolding, dependency installation, and server startup.

### 4.3 Historical Benchmark Telemetry & Empirical Findings

The directory [evaluation/result/20251112/](file:///home/maimoon-amin/Antigravity%20code/enterprise_os/sandbox/evaluation/result/20251112) contains real execution reports:
* **[Latest.md](file:///home/maimoon-amin/Antigravity%20code/enterprise_os/sandbox/evaluation/result/20251112/Latest.md)**: Records tool invocation latency, success rates ($\ge 98\%$), tool step sequences, and failure reasons.
* **[improvement_suggestions.md](file:///home/maimoon-amin/Antigravity%20code/enterprise_os/sandbox/evaluation/result/20251112/improvement_suggestions.md)**: Documents practical edge cases and developer feedback uncovered during LLM testing:
  1. *`undo_edit` File Creation Defect*: When an agent creates a new file and subsequently calls `undo_edit`, the file remained on disk rather than being deleted.
  2. *Output Predictability in `execute_code`*: Some code execution calls required explicit `print()` while others evaluated the last expression, occasionally confusing the model.
  3. *Overlap between `str_replace_editor` and `file_operations`*: Dual ways of creating files confused smaller LLMs; the report recommends strict tool boundary delineation.
  4. *`browser_evaluate` JavaScript Syntax Requirements*: LLMs frequently passed raw statements rather than self-executing expressions or arrow functions, highlighting the need for clearer schema prompts.

---

## 5. Example Ecosystem & Integration Patterns (`examples/`)

The [examples/](file:///home/maimoon-amin/Antigravity%20code/enterprise_os/sandbox/examples) directory provides 13 operational blueprints demonstrating how external AI agent frameworks interface with the sandbox.

```
                              AIO SANDBOX INTEGRATIONS
                                         |
     +-------------------+---------------+-------------------+
     |                   |                                   |
Agent Frameworks   Browser Automations                Cloud & Storage
     |                   |                                   |
  - LangGraph         - Playwright (CDP)                  - Volcengine VEFAAS
    DeepAgents        - browser-use                       - TOS Object Storage
  - AutoGen (AG2)     - OpenAI CUA GUI Actions              Stream Upload
  - OpenAI Tool Call
  - MiniMax Function
```

### 5.1 Agentic Framework Integrations

* **LangGraph DeepAgents ([examples/langgraph-deepagents-integration](file:///home/maimoon-amin/Antigravity%20code/enterprise_os/sandbox/examples/langgraph-deepagents-integration))**:
  * Implements `AIOSandboxBackend` conforming to the DeepAgents `BaseSandbox` interface.
  * Connects `Sandbox(base_url)` and creates a persistent shell session (`shell.create_session`) that maintains environment variables and directory state across multiple agent steps.
  * Delegates file operations directly to `client.file` and command execution to `client.shell.exec_command`.
* **AutoGen AG2 ([examples/ag2-integration](file:///home/maimoon-amin/Antigravity%20code/enterprise_os/sandbox/examples/ag2-integration))**:
  * Implements a collaborative multi-agent loop with `AssistantAgent` (Coder), `UserProxyAgent` (Reviewer), and `GroupChatManager`.
  * The Coder generates Python scripts; code execution is dispatched into the sandbox's stateful Jupyter kernel (`jupyter.execute_code`) or persistent shell session, ensuring zero arbitrary code execution on the host machine.
* **OpenAI & MiniMax Tool Calling ([examples/openai-integration](file:///home/maimoon-amin/Antigravity%20code/enterprise_os/sandbox/examples/openai-integration), [examples/minimax-integration](file:///home/maimoon-amin/Antigravity%20code/enterprise_os/sandbox/examples/minimax-integration))**:
  * Formats sandbox operations (`jupyter.execute_code`, `nodejs.execute_code`) as native OpenAI JSON function tools.

### 5.2 Browser & Visual Computer-Use Automations

* **Browser-Use CUA ([examples/browser-use-cua](file:///home/maimoon-amin/Antigravity%20code/enterprise_os/sandbox/examples/browser-use-cua))**:
  * Demonstrates Computer-Use Agent (CUA) integration.
  * Maps OpenAI `ComputerAction` objects (`click`, `move`, `typing`, `press`, `scroll`, `drag`) to the sandbox's typed action hierarchy (`Action_Click`, `Action_Typing`, `Action_MoveTo`, `Action_Scroll`, `Action_Press`).
  * Captures live screenshots via `sandbox.browser.screenshot()` and feeds base64 image frames back into the multimodal model.
* **Browser-Use ([examples/browser-use-integration](file:///home/maimoon-amin/Antigravity%20code/enterprise_os/sandbox/examples/browser-use-integration))**:
  * Retrieves Chrome DevTools Protocol URL via `sandbox.browser.get_info().data.cdp_url` and initializes a `BrowserSession` that drives web tasks autonomously.
* **Playwright over CDP ([examples/playwright-integration](file:///home/maimoon-amin/Antigravity%20code/enterprise_os/sandbox/examples/playwright-integration))**:
  * Directly binds Playwright's `chromium.connect_over_cdp(cdp_url)` to control the sandbox browser with high performance.
* **Site to Markdown ([examples/site-to-markdown](file:///home/maimoon-amin/Antigravity%20code/enterprise_os/sandbox/examples/site-to-markdown))**:
  * A full pipeline: Playwright downloads page HTML over CDP, Jupyter runs `markdownify` inside the container to embed screenshots and generate a markdown asset, and the file is saved in `/home/gem/site.md`.

### 5.3 Cloud Provider & Storage Integrations

* **Volcengine Serverless Sandboxes ([examples/volcengine-provider](file:///home/maimoon-amin/Antigravity%20code/enterprise_os/sandbox/examples/volcengine-provider))**:
  * Demonstrates dynamic provisioning of ephemeral sandbox containers in the cloud using `VolcengineProvider`: creating applications, waiting for gateway readiness, creating isolated sandbox instances, discovering public APIG domains, and deleting instances upon task completion.
* **Direct Object Storage Streaming ([examples/oss-upload](file:///home/maimoon-amin/Antigravity%20code/enterprise_os/sandbox/examples/oss-upload))**:
  * Demonstrates memory-efficient streaming of sandbox files to cloud storage (Volcengine TOS or AWS S3) using `client.file.download_file(path, chunk_size=64KB)` without caching the full file in host RAM.

---

## 6. Synthesis & Strategic Alignment with the Enterprise OS Plan

Relating this codebase back to the [task plan,md](file:///home/maimoon-amin/Antigravity%20code/enterprise_os/Context%20Research/task%20plan%2Cmd) and [research findings.md](file:///home/maimoon-amin/Antigravity%20code/enterprise_os/Context%20Research/research%20findings.md):

1. **TSK-01 (Runtime Provisioning)**:
   The `SandboxClient` from `agent-sandbox` directly initializes all modules (`browser`, `browser_page`, `browser_network`, `file`, `shell`, `code`, `mcp`, `skills`). The container's `docker-compose.yaml` provides the requisite egress isolation and resource bounding.
2. **TSK-02 & TSK-03 (State Machine, Persistent Shells, & Tools)**:
   The pattern established in [examples/langgraph-deepagents-integration/sandbox_backend.py](file:///home/maimoon-amin/Antigravity%20code/enterprise_os/sandbox/examples/langgraph-deepagents-integration/sandbox_backend.py) (implementing a persistent shell session with UUID, working directory `/home/gem`, and direct API delegation) serves as the exact template for connecting the LangGraph cyclic reasoning core to the sandbox.
3. **TSK-04 (Asset & CRO Friction Audit)**:
   The combination of `client.browser_page` (extracting DOM, Core Web Vitals, and Markdown) and `client.browser_network` (inspecting network requests for Google Analytics 4 tags, Meta Pixels, and HAR files) provides everything required to execute automated Baymard heuristic audits.
4. **TSK-06 & TSK-08 (Content Repurposing & Funnel Telemetry)**:
   The sandbox's built-in Jupyter kernel and Python environment allow running data analytics scripts, evaluating conversion rates, calculating Net Contribution and CLV/CAC ratios, and converting multi-format assets within an isolated environment.

### Conclusion

The `sandbox` repository is an enterprise-grade agent execution platform developed by ByteDance engineers, featuring a centralized multi-service container (`aio-sandbox`), Fern-generated typed SDKs with 1:1 functional parity across Python and TypeScript, an Anthropic-inspired evaluation benchmark suite, and comprehensive integration patterns across modern agent frameworks.