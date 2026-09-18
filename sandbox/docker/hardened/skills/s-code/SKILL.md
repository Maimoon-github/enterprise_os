---
name: s-code
description: Component coding, static analysis, linting, and structural validation micro-tool for W_DEV.
---

# S_CODE: Component Coder & Linter

Authorized Worker: `W_DEV` (Development)
Permitted Operations: `parse_ast`, `lint`, `generate_diff`, `execute_code`, `validate_syntax`, `apply_code_patch`, `format_code`, `inspect_ast_symbols`, `validate_syntax_compiler`, `manage_packages`, `generate_code`
Core Tool: AST parser / code linter / code patcher / compiler sanity checker

## Execution Contract
- Accepts source code, patch content, schema content, and component specifications.
- Enforces syntactic and structural checks using Python AST structural analysis and native compilation sanity checking.
- Applies scoped file patches within plan-authorized boundaries.
- Formats code according to repository-native conventions.
- Emits unified diff, complexity node counts, symbol maps, and compilation sanity evidence.
- Strictly isolated: No external network access permitted (`network_policy: disabled`); package management allowed only when explicitly authorized by plan with proxy egress.
