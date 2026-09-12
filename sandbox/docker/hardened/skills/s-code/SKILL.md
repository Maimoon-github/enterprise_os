---
name: s-code
description: Component coding, static analysis, linting, and structural validation micro-tool for W_DEV.
---

# S_CODE: Component Coder & Linter

Authorized Worker: `W_DEV` (Development)
Permitted Operations: `parse_ast`, `lint`, `generate_diff`, `execute_code`, `validate_syntax`
Core Tool: AST parser / code linter

## Execution Contract
- Accepts source code, schema content, and component name.
- Enforces syntactic and structural checks using Python AST.
- Emits unified diff, complexity node counts, and linting status.
- Strictly isolated: No external network access permitted (`network_policy: disabled`).
