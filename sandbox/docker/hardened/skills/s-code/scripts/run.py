#!/usr/bin/env python3
"""S_CODE AST Parser & Linter Execution Script."""
import ast
import json
import sys

def run_s_code(payload: dict) -> dict:
    code_content = payload.get("code") or payload.get("schema_content") or ""
    task_id = payload.get("task_id", "unknown")
    component_name = payload.get("component_name", "LayoutTemplate")

    ast_valid = True
    node_count = 0
    function_count = 0
    class_count = 0
    syntax_error = None

    if code_content:
        try:
            tree = ast.parse(code_content)
            for node in ast.walk(tree):
                node_count += 1
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    function_count += 1
                elif isinstance(node, ast.ClassDef):
                    class_count += 1
        except SyntaxError as err:
            ast_valid = False
            syntax_error = f"SyntaxError at line {err.lineno}: {err.msg}"
    else:
        code_content = (
            f"class {component_name}:\n"
            f"    def render(self, context: dict) -> str:\n"
            f"        return f'<div>{component_name}: {{context}}</div>'\n"
        )
        tree = ast.parse(code_content)
        node_count = len(list(ast.walk(tree)))
        class_count = 1
        function_count = 1

    diff = (
        f"--- a/components/{component_name.lower()}.py\n"
        f"+++ b/components/{component_name.lower()}.py\n"
        f"@@ -0,0 +1,5 @@\n"
        + "".join(f"+ {line}\n" for line in code_content.strip().splitlines())
    )

    return {
        "status": "success" if ast_valid else "lint_failed",
        "task_id": task_id,
        "component_name": component_name,
        "ast_valid": str(ast_valid),
        "node_count": str(node_count),
        "function_count": str(function_count),
        "class_count": str(class_count),
        "diff": diff,
        "syntax_error": syntax_error or "",
        "code": code_content,
    }

if __name__ == "__main__":
    raw_input = sys.stdin.read()
    data = json.loads(raw_input) if raw_input.strip() else {}
    result = run_s_code(data)
    sys.stdout.write(json.dumps(result))
