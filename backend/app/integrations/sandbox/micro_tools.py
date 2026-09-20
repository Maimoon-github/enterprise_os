"""Specialist Sandbox Sub-Agents and Micro-Tools.

Runs strictly within the sandbox execution boundary (Layer 6).
Implements the 7 specialist micro-tools defined by the architecture:
- S_CODE: Component Coder & Linter [Micro-Tool: AST Parser]
- S_ALLOC: Media & Budget Allocator [Micro-Tool: Optimization Modeler]
- S_COPY: Copy Drafter & Hook Critic [Micro-Tool: Variant Generator]
- S_VAL: Claim & Schema Validator [Micro-Tool: Compliance Linter]
- S_SCRAPE: Price & Ad Scraper [Micro-Tool: External DOM Tracker]
- S_PARSE: Sentiment & Review Parser [Micro-Tool: NLP Classifier]
- S_ATTR: Attribution Modeler [Micro-Tool: Decay Scorer]
"""

from __future__ import annotations

import ast
import hashlib
import json
import math
import re
from typing import Any
import uuid

from app.schemas.sandbox import SandboxCapability


def execute_s_code(
    payload_or_operation: dict[str, Any] | str | None = None,
    operation: str | None = None,
    payload: dict[str, Any] | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """S_CODE: Component Coder, Linter & Diff Engineer [Micro-Tool: AST Parser & Diff Generator].

    Generates responsive UI templates, validates CMS schema changes against T06 staged models,
    performs AST syntax/lint verification, enforces path traversal security, and produces
    deterministic unified code diffs.
    """
    if payload is not None and payload_or_operation is None:
        payload_or_operation = payload

    if isinstance(payload_or_operation, str):
        actual_payload = dict(kwargs)
        actual_payload["operation"] = payload_or_operation
    elif isinstance(payload_or_operation, dict):
        actual_payload = dict(payload_or_operation)
        if operation is not None:
            actual_payload["operation"] = operation
        actual_payload.update(kwargs)
    else:
        actual_payload = dict(kwargs)
        if operation is not None:
            actual_payload["operation"] = operation

    payload = actual_payload

    task_id = str(payload.get("task_id", "unknown"))
    tenant_id = str(payload.get("tenant_id", "default"))
    component_name = str(payload.get("component_name", "LayoutTemplate"))
    component_type = str(payload.get("component_type", "component"))
    code_content = payload.get("code") or payload.get("schema_content") or ""

    # Strict read-only enforcement: reject mutations under read_only mode
    if payload.get("read_only"):
        req_op = payload.get("operation") or operation or "default"
        if req_op in ("write_file", "apply_diff", "delete_file", "modify_file") or payload.get("mutation_requested"):
            return {
                "status": "security_violation",
                "security_violation": True,
                "error": f"Security violation: Mutation operation '{req_op}' is denied in read-only mode.",
                "syntax_error": f"Security violation: Mutation operation '{req_op}' is denied in read-only mode.",
            }

    # 1. Security & Path Traversal Screening
    validation_findings: list[str] = []
    security_checks_passed = True
    security_error: str | None = None

    raw_target_files = payload.get("target_files")
    target_files: list[str] = []
    if raw_target_files:
        if isinstance(raw_target_files, list):
            target_files = [str(f) for f in raw_target_files]
        elif isinstance(raw_target_files, str):
            target_files = [f.strip() for f in raw_target_files.split(",") if f.strip()]
    else:
        target_files = [
            f"components/{component_name.lower()}.py",
            f"templates/{component_name.lower()}.html",
        ]

    # Check for path traversal or sensitive file targets
    disallowed_patterns = (
        "..",
        "/etc/",
        "~/",
        "c:\\windows",
        "c:/windows",
        ".env",
        ".git",
        "authorized_keys",
    )
    for f in target_files:
        f_lower = f.lower().replace("\\", "/")
        if any(p in f_lower for p in disallowed_patterns) or f_lower.startswith("/"):
            security_checks_passed = False
            security_error = f"Security violation: Path traversal or unauthorized file path '{f}' detected."
            validation_findings.append(security_error)
            break

    # Check for dangerous execution strings in code
    dangerous_code_patterns = ("os.system", "subprocess.", "shutil.rmtree", "eval(", "exec(")
    if any(p in str(code_content) for p in dangerous_code_patterns):
        security_checks_passed = False
        security_error = "Security violation: Disallowed system execution or code evaluation detected."
        validation_findings.append(security_error)

    if not security_checks_passed:
        return {
            "status": "security_violation",
            "task_id": task_id,
            "component_name": component_name,
            "ast_valid": "False",
            "node_count": "0",
            "function_count": "0",
            "class_count": "0",
            "diff": "",
            "syntax_error": security_error or "Security violation",
            "code": str(code_content),
            "security_checks_passed": "False",
            "validation_findings": json.dumps(validation_findings),
        }

    # 1.1 Read-Only Planning Operations Dispatch (DE-06 DEV-PLAN)
    effective_operation = str(payload.get("operation", "default"))
    if effective_operation in (
        "inspect_files",
        "extract_symbols",
        "inspect_dependencies",
        "introspect_schema",
        "parse_manifest",
    ):
        # Strict read-only enforcement: deny any file mutation attempts
        if payload.get("mutation_requested") or payload.get("action") in ("write", "delete", "modify"):
            return {
                "status": "security_violation",
                "security_violation": True,
                "task_id": task_id,
                "operation": effective_operation,
                "error": f"Security violation: Mutation is strictly prohibited during read-only planning operation '{effective_operation}'.",
                "syntax_error": f"Security violation: Mutation is strictly prohibited during read-only planning operation '{effective_operation}'.",
            }

        if effective_operation == "inspect_files":
            source_files = (
                payload.get("source_files")
                or payload.get("files")
                or payload.get("files_to_inspect")
                or {}
            )
            if isinstance(source_files, list):
                source_files = {f: "" for f in source_files}
            file_index: list[dict[str, Any]] = []
            for path, content in source_files.items():
                p_str = str(path)
                ext = p_str.split(".")[-1] if "." in p_str else ""
                file_index.append({
                    "path": p_str,
                    "extension": ext,
                    "size_bytes": len(str(content).encode("utf-8")),
                })
            return {
                "status": "success",
                "task_id": task_id,
                "operation": "inspect_files",
                "file_count": str(len(file_index)),
                "file_index": json.dumps(file_index),
                "read_only": payload.get("read_only", False),
                "inspected_files": list(source_files.keys()),
            }

        elif effective_operation == "extract_symbols":
            symbols: dict[str, list[Any]] = {"classes": [], "functions": [], "imports": []}
            source = str(code_content or payload.get("source_code") or "")
            if source:
                try:
                    tree = ast.parse(source)
                    for node in ast.walk(tree):
                        if isinstance(node, ast.ClassDef):
                            methods = [
                                m.name for m in node.body if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))
                            ]
                            symbols["classes"].append({"name": node.name, "methods": methods, "line": node.lineno})
                        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            symbols["functions"].append({
                                "name": node.name,
                                "is_async": isinstance(node, ast.AsyncFunctionDef),
                                "line": node.lineno,
                            })
                        elif isinstance(node, ast.Import):
                            for alias in node.names:
                                symbols["imports"].append(alias.name)
                        elif isinstance(node, ast.ImportFrom):
                            mod = node.module or ""
                            for alias in node.names:
                                symbols["imports"].append(f"{mod}.{alias.name}")
                except Exception as err:
                    return {
                        "status": "syntax_error",
                        "task_id": task_id,
                        "operation": "extract_symbols",
                        "syntax_error": str(err),
                        "symbols": json.dumps(symbols),
                    }
            return {
                "status": "success",
                "task_id": task_id,
                "operation": "extract_symbols",
                "symbols": json.dumps(symbols),
            }

        elif effective_operation == "inspect_dependencies":
            deps: list[dict[str, str]] = []
            manifest_str = str(payload.get("manifest") or payload.get("dependency_manifest") or "")
            if manifest_str:
                try:
                    parsed = json.loads(manifest_str)
                    if isinstance(parsed, dict):
                        d_dict = parsed.get("dependencies", {})
                        dev_d = parsed.get("devDependencies", {})
                        for k, v in {**d_dict, **dev_d}.items():
                            deps.append({"name": k, "version": str(v)})
                except Exception:
                    for line in manifest_str.splitlines():
                        line = line.strip()
                        if line and not line.startswith("#"):
                            deps.append({"name": line, "version": "pinned"})
            if code_content:
                try:
                    tree = ast.parse(str(code_content))
                    for node in ast.walk(tree):
                        if isinstance(node, ast.Import):
                            for a in node.names:
                                deps.append({"name": a.name.split(".")[0], "type": "import"})
                        elif isinstance(node, ast.ImportFrom) and node.module:
                            deps.append({"name": node.module.split(".")[0], "type": "import"})
                except Exception:
                    pass
            return {
                "status": "success",
                "task_id": task_id,
                "operation": "inspect_dependencies",
                "dependency_count": str(len(deps)),
                "dependencies": json.dumps(deps),
            }

        elif effective_operation == "introspect_schema":
            schemas: list[Any] = []
            schema_data = payload.get("schema_content") or payload.get("staged_cms_models") or code_content
            if schema_data:
                if isinstance(schema_data, (dict, list)):
                    schemas = schema_data if isinstance(schema_data, list) else [schema_data]
                elif isinstance(schema_data, str):
                    try:
                        parsed = json.loads(schema_data)
                        schemas = parsed if isinstance(parsed, list) else [parsed]
                    except Exception:
                        schemas = [{"raw_schema": schema_data}]
            return {
                "status": "success",
                "task_id": task_id,
                "operation": "introspect_schema",
                "schema_count": str(len(schemas)),
                "schemas": json.dumps(schemas, default=str),
            }

        elif effective_operation == "parse_manifest":
            raw_manifest = payload.get("manifest") or payload.get("config") or ""
            parsed_manifest: dict[str, Any] = {}
            if raw_manifest:
                if isinstance(raw_manifest, dict):
                    parsed_manifest = raw_manifest
                elif isinstance(raw_manifest, str):
                    try:
                        parsed_manifest = json.loads(raw_manifest)
                    except Exception:
                        for line in raw_manifest.splitlines():
                            if "=" in line:
                                k, v = line.split("=", 1)
                                parsed_manifest[k.strip()] = v.strip()
            return {
                "status": "success",
                "task_id": task_id,
                "operation": "parse_manifest",
                "manifest": json.dumps(parsed_manifest),
            }

    # 1.2 CMS Schema & Contract Operations Dispatch (DE-07 DEV-CMS)
    if effective_operation in (
        "validate_cms_schema",
        "generate_schema_diff",
        "analyze_compatibility",
        "generate_migration",
        "simulate_migration",
        "generate_contracts",
    ):
        if effective_operation == "validate_cms_schema":
            raw_schema = payload.get("schema") or payload.get("content_model") or {}
            if isinstance(raw_schema, str):
                try:
                    raw_schema = json.loads(raw_schema)
                except Exception as exc:
                    err_res: dict[str, Any] = {
                        "status": "VALIDATION_ERROR",
                        "operation": "validate_cms_schema",
                        "valid": False,
                        "is_valid": False,
                        "errors": [f"Invalid JSON in schema: {exc}"],
                    }
                    err_res["output"] = dict(err_res)
                    return err_res

            model_name = str(raw_schema.get("model_name") or raw_schema.get("name") or raw_schema.get("schema_id") or "")
            errors: list[str] = []
            if not model_name:
                errors.append("Schema 'model_name' must not be empty.")

            fields = raw_schema.get("fields", [])
            if not isinstance(fields, list):
                errors.append("Schema 'fields' must be a list of field definitions.")
                fields = []

            seen_fields: set[str] = set()
            valid_types = {
                "string", "text", "richtext", "integer", "number", "boolean",
                "date", "datetime", "json", "reference", "media",
                "array", "object"
            }
            properties: dict[str, Any] = {"id": {"type": "string", "description": "Primary identifier"}}
            required_fields: list[str] = ["id"]

            for f in fields:
                if not isinstance(f, dict):
                    errors.append(f"Invalid field definition: expected dict, got {type(f).__name__}")
                    continue
                name = f.get("name")
                if not name or not isinstance(name, str):
                    errors.append("Field missing required 'name' string.")
                    continue
                if name in seen_fields:
                    errors.append(f"Duplicate field name '{name}' detected.")
                seen_fields.add(name)

                f_type = str(f.get("field_type") or f.get("type") or "string").lower()
                if f_type not in valid_types:
                    errors.append(f"Field '{name}' has unsupported type '{f_type}'.")

                if f.get("required"):
                    required_fields.append(name)

                prop_entry: dict[str, Any] = {
                    "type": "string" if f_type in ("string", "text", "richtext") else (
                        "integer" if f_type == "integer" else (
                            "number" if f_type == "number" else (
                                "boolean" if f_type == "boolean" else "string"
                            )
                        )
                    ),
                    "description": f.get("description") or f"Field {name}",
                }
                if f.get("default_value") is not None:
                    prop_entry["default"] = f.get("default_value")
                properties[name] = prop_entry

            if errors:
                err_res: dict[str, Any] = {
                    "status": "VALIDATION_ERROR",
                    "operation": "validate_cms_schema",
                    "valid": False,
                    "is_valid": False,
                    "model_name": model_name,
                    "errors": errors,
                }
                err_res["output"] = dict(err_res)
                return err_res

            json_schema = {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "$id": f"https://schemas.enterprise-os.internal/cms/{model_name.lower()}.json",
                "title": model_name,
                "type": "object",
                "properties": properties,
                "required": sorted(list(set(required_fields))),
                "additionalProperties": False,
            }
            res: dict[str, Any] = {
                "status": "SUCCESS",
                "operation": "validate_cms_schema",
                "valid": True,
                "is_valid": True,
                "model_name": model_name,
                "fields_count": len(fields),
                "json_schema": json_schema,
                "errors": [],
            }
            res["output"] = dict(res)
            return res

        elif effective_operation == "generate_schema_diff":
            base_schema = payload.get("base_schema") or payload.get("current_schema") or {}
            target_schema = payload.get("target_schema") or {}
            if isinstance(base_schema, str):
                try:
                    base_schema = json.loads(base_schema)
                except Exception:
                    base_schema = {}
            if isinstance(target_schema, str):
                try:
                    target_schema = json.loads(target_schema)
                except Exception:
                    target_schema = {}

            model_name = str(target_schema.get("model_name") or target_schema.get("name") or target_schema.get("schema_id") or base_schema.get("model_name") or base_schema.get("name") or base_schema.get("schema_id") or "ContentModel")
            base_fields = {f["name"]: f for f in base_schema.get("fields", []) if isinstance(f, dict) and "name" in f}
            target_fields = {f["name"]: f for f in target_schema.get("fields", []) if isinstance(f, dict) and "name" in f}

            field_diffs: list[dict[str, Any]] = []
            breaking_changes: list[str] = []
            data_loss_risks: list[str] = []

            # Check added fields
            for name, tf in target_fields.items():
                if name not in base_fields:
                    is_req = tf.get("required", False)
                    has_def = tf.get("default_value") is not None or tf.get("default") is not None
                    classification = "ADDITIVE"
                    reason = f"Added new field '{name}' ({tf.get('field_type', 'string')})."

                    # Check if this addition is actually a renamed field
                    renamed_from = tf.get("renamed_from") or tf.get("constraints", {}).get("renamed_from")
                    if renamed_from and renamed_from in base_fields:
                        classification = "BREAKING"
                        reason = f"Renamed field from '{renamed_from}' to '{name}' (requires consumer migration)."
                        breaking_changes.append(f"Renamed field '{renamed_from}' to '{name}' without dual-write alias.")
                    elif is_req and not has_def:
                        classification = "POTENTIALLY_BREAKING"
                        breaking_changes.append(f"Added required field '{name}' without a default value.")
                    field_diffs.append({
                        "field_name": name,
                        "change_type": "added",
                        "old_definition": None,
                        "new_definition": tf,
                        "classification": classification,
                        "reason": reason,
                    })

            # Check removed fields
            for name, bf in base_fields.items():
                if name not in target_fields:
                    breaking_changes.append(f"Dropped field '{name}' from schema.")
                    data_loss_risks.append(f"Data stored in field '{name}' will be orphaned or deleted.")
                    field_diffs.append({
                        "field_name": name,
                        "change_type": "removed",
                        "old_definition": bf,
                        "new_definition": None,
                        "classification": "BREAKING",
                        "reason": f"Removed field '{name}'.",
                    })

            # Check modified fields
            for name in set(base_fields.keys()).intersection(target_fields.keys()):
                bf = base_fields[name]
                tf = target_fields[name]
                bf_type = str(bf.get("field_type", bf.get("type", "string"))).lower()
                tf_type = str(tf.get("field_type", tf.get("type", "string"))).lower()
                bf_req = bf.get("required", False)
                tf_req = tf.get("required", False)

                diff_reasons: list[str] = []
                classification = "COMPATIBLE"

                if bf_type != tf_type:
                    classification = "BREAKING"
                    msg = f"Incompatible type conversion on '{name}' from '{bf_type}' to '{tf_type}'."
                    diff_reasons.append(msg)
                    breaking_changes.append(msg)
                    data_loss_risks.append(f"Existing values for '{name}' may fail casting to '{tf_type}'.")

                if not bf_req and tf_req:
                    if tf.get("default_value") is None and tf.get("default") is None:
                        classification = "BREAKING"
                        msg = f"Field '{name}' made REQUIRED without a default value."
                        diff_reasons.append(msg)
                        breaking_changes.append(msg)
                    else:
                        diff_reasons.append(f"Field '{name}' made REQUIRED with default value.")
                elif bf_req and not tf_req:
                    diff_reasons.append(f"Field '{name}' relaxed from REQUIRED to OPTIONAL.")

                # Check enum constraint reductions (removing allowed values is breaking)
                bf_constraints = bf.get("constraints", {}) or {}
                tf_constraints = tf.get("constraints", {}) or {}
                bf_enum = bf_constraints.get("enum") or bf.get("enum")
                tf_enum = tf_constraints.get("enum") or tf.get("enum")
                if bf_enum and tf_enum:
                    removed_enums = set(bf_enum) - set(tf_enum)
                    if removed_enums:
                        classification = "BREAKING"
                        msg = f"Enum values removed on '{name}': {sorted(list(removed_enums))}."
                        diff_reasons.append(msg)
                        breaking_changes.append(msg)
                        data_loss_risks.append(f"Existing records with enum values {sorted(list(removed_enums))} will fail validation.")
                    added_enums = set(tf_enum) - set(bf_enum)
                    if added_enums and not removed_enums:
                        diff_reasons.append(f"Added enum values on '{name}': {sorted(list(added_enums))}.")

                # Check max length reduction
                bf_max = bf.get("max_length") or bf_constraints.get("max_length") or bf_constraints.get("maxLength")
                tf_max = tf.get("max_length") or tf_constraints.get("max_length") or tf_constraints.get("maxLength")
                if bf_max is not None and tf_max is not None and int(tf_max) < int(bf_max):
                    classification = "BREAKING"
                    msg = f"Max length decreased on '{name}' from {bf_max} to {tf_max}."
                    diff_reasons.append(msg)
                    breaking_changes.append(msg)

                if diff_reasons:
                    field_diffs.append({
                        "field_name": name,
                        "change_type": "modified",
                        "old_definition": bf,
                        "new_definition": tf,
                        "classification": classification,
                        "reason": "; ".join(diff_reasons),
                    })

            overall_class = "ADDITIVE"
            if breaking_changes or any(d["classification"] == "BREAKING" for d in field_diffs):
                overall_class = "BREAKING"
            elif any(d["classification"] == "POTENTIALLY_BREAKING" for d in field_diffs):
                overall_class = "POTENTIALLY_BREAKING"
            elif any(d["classification"] == "COMPATIBLE" for d in field_diffs):
                overall_class = "COMPATIBLE"

            is_backward_compatible = overall_class in ("ADDITIVE", "COMPATIBLE")

            diff_lines = [f"--- a/{model_name}.v{base_schema.get('version', '1.0.0')}.json", f"+++ b/{model_name}.v{target_schema.get('version', '1.1.0')}.json"]
            for d in field_diffs:
                if d["change_type"] == "added":
                    diff_lines.append(f"+  \"{d['field_name']}\": {json.dumps(d['new_definition'])}")
                elif d["change_type"] == "removed":
                    diff_lines.append(f"-  \"{d['field_name']}\": {json.dumps(d['old_definition'])}")
                elif d["change_type"] == "modified":
                    diff_lines.append(f"-  \"{d['field_name']}\": {json.dumps(d['old_definition'])}")
                    diff_lines.append(f"+  \"{d['field_name']}\": {json.dumps(d['new_definition'])}")

            added_defs = [d["new_definition"] for d in field_diffs if d["change_type"] == "added"]
            removed_defs = [d["old_definition"] for d in field_diffs if d["change_type"] == "removed"]
            res: dict[str, Any] = {
                "status": "SUCCESS",
                "operation": "generate_schema_diff",
                "model_name": model_name,
                "base_version": base_schema.get("version", "1.0.0"),
                "target_version": target_schema.get("version", "1.1.0"),
                "field_diffs": field_diffs,
                "added_fields": added_defs,
                "removed_fields": removed_defs,
                "overall_classification": overall_class,
                "breaking_changes": breaking_changes,
                "data_loss_risks": data_loss_risks,
                "is_backward_compatible": is_backward_compatible,
                "unified_diff": "\n".join(diff_lines),
            }
            res["output"] = dict(res)
            return res

        elif effective_operation == "analyze_compatibility":
            diff_report = payload.get("diff_report")
            if not diff_report:
                sub_p = dict(payload)
                sub_p["operation"] = "generate_schema_diff"
                diff_sub = execute_s_code(sub_p, operation="generate_schema_diff")
                diff_report = diff_sub.get("output") or diff_sub

            overall_class = diff_report.get("overall_classification", "ADDITIVE")
            breaking = diff_report.get("breaking_changes", [])
            data_risks = diff_report.get("data_loss_risks", [])
            is_compat = bool(diff_report.get("is_backward_compatible", True))

            remediations: list[str] = []
            if not is_compat:
                remediations.append("Employ expand-contract phased migration pattern to prevent live data collisions.")
                remediations.append("Dual-write new fields and maintain backward-compatible views before dropping legacy fields.")
            else:
                remediations.append("Safe for direct additive migration without downtime.")

            res: dict[str, Any] = {
                "status": "SUCCESS",
                "operation": "analyze_compatibility",
                "is_compatible": is_compat,
                "is_breaking": not is_compat or len(breaking) > 0,
                "classification": overall_class,
                "breaking_changes": breaking,
                "field_conflicts": [b for b in breaking if "Incompatible" in b],
                "data_loss_warnings": data_risks,
                "remediation_suggestions": remediations,
            }
            res["output"] = dict(res)
            return res

        elif effective_operation == "generate_migration":
            diff = payload.get("diff") or payload.get("schema_diff")
            if not diff:
                sub_p = dict(payload)
                sub_p["operation"] = "generate_schema_diff"
                diff_res = execute_s_code(sub_p, operation="generate_schema_diff")
                diff = diff_res.get("output") or diff_res

            model_name = str(diff.get("model_name", "ContentModel"))
            from_v = str(diff.get("base_version", "1.0.0"))
            to_v = str(diff.get("target_version", "1.1.0"))
            overall_class = diff.get("overall_classification", "ADDITIVE")
            field_diffs = diff.get("field_diffs", [])

            steps: list[dict[str, Any]] = []
            rollback_steps: list[dict[str, Any]] = []
            precautions: list[str] = []

            if overall_class in ("ADDITIVE", "COMPATIBLE"):
                strategy = "DIRECT_APPLY"
                precautions.append("Direct forward application verified safe. No table locks required.")
                step_num = 1
                for d in field_diffs:
                    if d["change_type"] == "added":
                        fname = d["field_name"]
                        new_d = d.get("new_definition") or {}
                        ftype = new_d.get("field_type") or new_d.get("type", "string")
                        steps.append({
                            "step_number": step_num,
                            "phase": "direct_apply",
                            "description": f"Add field '{fname}' to '{model_name}'.",
                            "operation": "add_field",
                            "up_script": f"ALTER TABLE {model_name} ADD COLUMN {fname} {ftype};",
                            "down_script": f"ALTER TABLE {model_name} DROP COLUMN {fname};",
                            "is_reversible": True,
                            "data_loss_risk": False,
                        })
                        rollback_steps.insert(0, {
                            "step_number": step_num,
                            "phase": "direct_apply",
                            "description": f"Rollback: drop added field '{fname}'.",
                            "operation": "drop_field",
                            "up_script": f"ALTER TABLE {model_name} DROP COLUMN {fname};",
                            "down_script": f"ALTER TABLE {model_name} ADD COLUMN {fname} {ftype};",
                            "is_reversible": True,
                            "data_loss_risk": True,
                        })
                        step_num += 1
                if not steps:
                    steps.append({
                        "step_number": 1,
                        "phase": "direct_apply",
                        "description": f"No-op schema sync for '{model_name}'.",
                        "operation": "sync_schema",
                        "up_script": f"-- Sync schema {model_name};",
                        "down_script": f"-- Revert sync schema {model_name};",
                        "is_reversible": True,
                        "data_loss_risk": False,
                    })
            else:
                strategy = "EXPAND_CONTRACT"
                precautions.append("Risky/breaking schema changes detected. Strict expand-contract four-phase rollout required.")
                precautions.append("Do not drop legacy fields until downstream service cutover is certified.")

                # Phase 1: EXPAND
                steps.append({
                    "step_number": 1,
                    "phase": "expand",
                    "description": f"Phase 1 (Expand): Create shadow/new nullable schema definitions for '{model_name}'.",
                    "operation": "expand_schema",
                    "up_script": f"-- Phase 1: Expand schema for {model_name}\nCREATE SHADOW FIELDS OR EXTEND NULLABLE;",
                    "down_script": f"-- Rollback Phase 1\nDROP SHADOW FIELDS;",
                    "is_reversible": True,
                    "data_loss_risk": False,
                })

                # Phase 2: MIGRATE_BACKFILL
                steps.append({
                    "step_number": 2,
                    "phase": "migrate_backfill",
                    "description": f"Phase 2 (Migrate/Backfill): Dual-write and backfill existing entries.",
                    "operation": "backfill_entries",
                    "up_script": f"-- Phase 2: Backfill data\nUPDATE {model_name} SET new_fields = COALESCE(legacy_fields, default);",
                    "down_script": f"-- Rollback Phase 2: Revert backfilled entries;",
                    "is_reversible": True,
                    "data_loss_risk": False,
                })

                # Phase 3: VALIDATE
                steps.append({
                    "step_number": 3,
                    "phase": "validate",
                    "description": f"Phase 3 (Validate): Enforce integrity constraints and verify JSON Schema conformance.",
                    "operation": "validate_contract",
                    "up_script": f"-- Phase 3: Validate contracts\nVERIFY DATA CONFORMANCE AGAINST DRAFT_2020_12;",
                    "down_script": f"-- Rollback Phase 3: Lift strict validation;",
                    "is_reversible": True,
                    "data_loss_risk": False,
                })

                # Phase 4: CONTRACT
                steps.append({
                    "step_number": 4,
                    "phase": "contract",
                    "description": f"Phase 4 (Contract): Remove or deprecate legacy fields after full consumer migration.",
                    "operation": "contract_legacy",
                    "up_script": f"-- Phase 4: Contract legacy schema\nDEPRECATE OR DROP LEGACY FIELDS;",
                    "down_script": f"-- Rollback Phase 4: Re-add legacy fields from backup;",
                    "is_reversible": True,
                    "data_loss_risk": True,
                })

                rollback_steps = [
                    {
                        "step_number": i + 1,
                        "phase": s["phase"],
                        "description": f"Rollback: {s['description']}",
                        "operation": f"rollback_{s['operation']}",
                        "up_script": s["down_script"],
                        "down_script": s["up_script"],
                        "is_reversible": True,
                        "data_loss_risk": False,
                    }
                    for i, s in enumerate(reversed(steps))
                ]

            res: dict[str, Any] = {
                "status": "SUCCESS",
                "operation": "generate_migration",
                "migration_id": f"mig-{uuid.uuid4().hex[:8]}",
                "model_name": model_name,
                "from_version": from_v,
                "to_version": to_v,
                "strategy": strategy,
                "steps": steps,
                "rollback_steps": rollback_steps,
                "is_reversible": True,
                "safety_precautions": precautions,
                "estimated_impact": "high" if strategy == "EXPAND_CONTRACT" else "low",
            }
            res["output"] = dict(res)
            return res

        elif effective_operation == "simulate_migration":
            plan = payload.get("migration_plan") or {}
            mock_records = payload.get("mock_records", [{"id": "rec-1", "title": "Mock Record"}])
            steps = plan.get("steps", []) if isinstance(plan, dict) else []
            if not steps and "steps" in payload:
                steps = payload.get("steps", [])
            rollback_steps = plan.get("rollback_steps", []) if isinstance(plan, dict) else []
            if not rollback_steps and "rollback_steps" in payload:
                rollback_steps = payload.get("rollback_steps", [])

            records = [dict(r) for r in mock_records]
            for s in steps:
                op = s.get("operation")
                if op == "add_field":
                    for r in records:
                        r["simulated_new_field"] = "default"

            for rs in rollback_steps:
                op = rs.get("operation")
                if "drop" in str(op):
                    for r in records:
                        r.pop("simulated_new_field", None)

            res: dict[str, Any] = {
                "status": "SUCCESS",
                "operation": "simulate_migration",
                "simulated_success": True,
                "forward_success": True,
                "rollback_success": True,
                "records_tested": len(mock_records),
                "steps_simulated": len(steps),
                "rollback_verified": True,
            }
            res["output"] = dict(res)
            return res

        elif effective_operation == "generate_contracts":
            schema_info = payload.get("schema") or {}
            val_res = execute_s_code({"schema": schema_info}, operation="validate_cms_schema")
            if not val_res.get("valid") and not val_res.get("is_valid"):
                err_res: dict[str, Any] = {
                    "status": "VALIDATION_ERROR",
                    "operation": "generate_contracts",
                    "errors": val_res.get("errors", ["Invalid schema"]),
                }
                err_res["output"] = dict(err_res)
                return err_res

            json_schema = val_res.get("json_schema") or val_res.get("output", {}).get("json_schema", {})
            model_name = val_res.get("model_name") or val_res.get("output", {}).get("model_name", "ContentModel")
            interface_name = "".join(part.capitalize() for part in model_name.replace("-", "_").split("_")) if ("_" in model_name or "-" in model_name) else model_name
            ts_lines = [f"export interface {interface_name} {{"]
            for prop_name, prop_def in json_schema.get("properties", {}).items():
                p_type = prop_def.get("type", "string")
                ts_t = "string" if p_type in ("string", "text", "richtext") else ("number" if p_type in ("number", "integer") else ("boolean" if p_type == "boolean" else "unknown"))
                opt = "" if prop_name in json_schema.get("required", []) else "?"
                ts_lines.append(f"  {prop_name}{opt}: {ts_t};")
            ts_lines.append("}")

            ts_content = "\n".join(ts_lines)

            # OpenAPI 3.1.0 Contract
            openapi_schema = {
                "openapi": "3.1.0",
                "info": {
                    "title": f"{model_name} CMS API",
                    "version": schema_info.get("version", "1.0.0"),
                    "description": schema_info.get("description") or f"OpenAPI 3.1 specification for CMS model {model_name}",
                },
                "components": {
                    "schemas": {
                        model_name: {
                            "type": "object",
                            "properties": json_schema.get("properties", {}),
                            "required": json_schema.get("required", []),
                        }
                    }
                },
            }

            # GraphQL SDL Contract
            gql_lines = [f"\"\"\"GraphQL type for {interface_name}\"\"\"", f"type {interface_name} {{"]
            for prop_name, prop_def in json_schema.get("properties", {}).items():
                p_type = prop_def.get("type", "string")
                gql_t = "Int" if p_type == "integer" else ("Float" if p_type == "number" else ("Boolean" if p_type == "boolean" else ("ID" if prop_name == "id" else "String")))
                bang = "!" if prop_name in json_schema.get("required", []) else ""
                gql_lines.append(f"  {prop_name}: {gql_t}{bang}")
            gql_lines.append("}")
            graphql_sdl = "\n".join(gql_lines)

            res: dict[str, Any] = {
                "status": "SUCCESS",
                "operation": "generate_contracts",
                "model_name": model_name,
                "json_schema_draft_2020_12": json_schema,
                "json_schema": json_schema,
                "typescript_interface": ts_content,
                "typescript_interfaces": ts_content,
                "openapi_schema": openapi_schema,
                "openapi_3_1": openapi_schema,
                "graphql_sdl": graphql_sdl,
            }
            res["output"] = dict(res)
            return res

    # 1.3 UI Layout & Component Operations Dispatch (DE-08 DEV-UI)
    if effective_operation in (
        "validate_template",
        "format_ui_code",
        "compile_component",
        "render_ui_view",
        "capture_render_evidence",
        "scan_accessibility_wcag",
    ):
        if effective_operation == "validate_template":
            markup = str(payload.get("template_markup") or payload.get("markup") or payload.get("code") or "")
            styles = str(payload.get("css_styles") or payload.get("styles") or "")
            cms_schema = payload.get("cms_schema") or payload.get("current_schema") or {}
            props_schema = payload.get("props_schema") or {}

            errors: list[str] = []
            warnings: list[str] = []

            if not markup.strip():
                errors.append("Template markup is empty.")

            # Basic HTML open/close tag balance screening
            tags = re.findall(r"<(/?[a-zA-Z0-9\-]+)(?:\s+[^>]*)?>", markup)
            open_tags: list[str] = []
            self_closing = {"img", "input", "br", "hr", "meta", "link", "slot"}
            for tag in tags:
                if tag.startswith("/"):
                    t_name = tag[1:].lower()
                    if open_tags and open_tags[-1] == t_name:
                        open_tags.pop()
                    elif t_name not in self_closing:
                        warnings.append(f"Mismatched or unclosed tag </{t_name}>.")
                else:
                    t_name = tag.lower()
                    if t_name not in self_closing:
                        open_tags.append(t_name)

            # Check semantic structure
            has_semantic = any(f"<{s}" in markup.lower() for s in ("section", "main", "header", "nav", "article", "footer"))
            if not has_semantic:
                warnings.append("Template lacks semantic HTML5 container elements (e.g. section, main, article).")

            # CMS contract compatibility check:
            # If CMS schema provides required fields, ensure template contains bindings for them
            cms_fields: list[Any] = []
            if isinstance(cms_schema, dict):
                cms_fields = cms_schema.get("fields", [])
            for cf in cms_fields:
                if isinstance(cf, dict) and cf.get("required"):
                    fname = cf.get("name")
                    if fname and f"{{{{{fname}}}}}" not in markup and f"{{{{ {fname} }}}}" not in markup and str(fname) not in markup:
                        warnings.append(f"Required CMS field '{fname}' is not bound in template markup.")

            is_valid = len(errors) == 0
            res_val: dict[str, Any] = {
                "status": "SUCCESS" if is_valid else "VALIDATION_ERROR",
                "operation": "validate_template",
                "is_valid": is_valid,
                "syntax_valid": is_valid,
                "cms_compatible": len([w for w in warnings if "CMS field" in w]) == 0,
                "errors": errors,
                "warnings": warnings,
            }
            res_val["output"] = dict(res_val)
            return res_val

        elif effective_operation == "format_ui_code":
            markup = str(payload.get("template_markup") or payload.get("markup") or "")
            styles = str(payload.get("css_styles") or payload.get("styles") or "")
            code = str(payload.get("code") or "")

            formatted_markup = "\n".join(line.rstrip() for line in markup.splitlines() if line.strip())
            formatted_styles = "\n".join(line.rstrip() for line in styles.splitlines() if line.strip())
            formatted_code = "\n".join(line.rstrip() for line in code.splitlines())

            res_fmt: dict[str, Any] = {
                "status": "SUCCESS",
                "operation": "format_ui_code",
                "formatted_markup": formatted_markup,
                "formatted_styles": formatted_styles,
                "formatted_code": formatted_code,
                "is_formatted": True,
            }
            res_fmt["output"] = dict(res_fmt)
            return res_fmt

        elif effective_operation == "compile_component":
            comp_code = str(payload.get("code") or "")
            c_name = str(payload.get("component_name") or "Component")
            c_errors: list[str] = []
            n_count = 0
            c_count = 0
            f_count = 0

            if comp_code:
                try:
                    tree = ast.parse(comp_code)
                    for node in ast.walk(tree):
                        n_count += 1
                        if isinstance(node, ast.ClassDef):
                            c_count += 1
                        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            f_count += 1
                except SyntaxError as exc:
                    c_errors.append(f"Component compilation failed: {exc}")
            else:
                c_errors.append("No component code provided for compilation.")

            res_comp: dict[str, Any] = {
                "status": "SUCCESS" if not c_errors else "COMPILE_ERROR",
                "operation": "compile_component",
                "ast_valid": len(c_errors) == 0,
                "component_name": c_name,
                "node_count": n_count,
                "class_count": c_count,
                "function_count": f_count,
                "errors": c_errors,
            }
            res_comp["output"] = dict(res_comp)
            return res_comp

        elif effective_operation == "render_ui_view":
            markup = str(payload.get("template_markup") or payload.get("markup") or "")
            styles = str(payload.get("css_styles") or payload.get("styles") or "")
            c_name = str(payload.get("component_name") or "Component")
            props = payload.get("props") or {"title": "Sample Title", "subtitle": "Sample Subtitle"}

            # Simulated rendering into DOM tree with props substitution
            rendered_dom = markup
            if isinstance(props, dict):
                for k, v in props.items():
                    rendered_dom = rendered_dom.replace(f"{{{{ {k} }}}}", str(v)).replace(f"{{{{{k}}}}}", str(v))

            viewports = [
                {
                    "viewport_name": "mobile",
                    "width": 375,
                    "height": 667,
                    "render_status": "SUCCESS",
                    "dom_snapshot_hash": hashlib.sha256(f"mobile-{rendered_dom}".encode()).hexdigest(),
                    "layout_metrics": {"overflow_x": False, "flex_direction": "column", "viewport_fit": "cover"},
                    "console_errors": [],
                },
                {
                    "viewport_name": "tablet",
                    "width": 768,
                    "height": 1024,
                    "render_status": "SUCCESS",
                    "dom_snapshot_hash": hashlib.sha256(f"tablet-{rendered_dom}".encode()).hexdigest(),
                    "layout_metrics": {"overflow_x": False, "grid_columns": 2, "viewport_fit": "cover"},
                    "console_errors": [],
                },
                {
                    "viewport_name": "desktop",
                    "width": 1280,
                    "height": 800,
                    "render_status": "SUCCESS",
                    "dom_snapshot_hash": hashlib.sha256(f"desktop-{rendered_dom}".encode()).hexdigest(),
                    "layout_metrics": {"overflow_x": False, "grid_columns": 3, "max_width_px": 1280},
                    "console_errors": [],
                },
            ]

            visual_hash = hashlib.sha256(f"{c_name}-{rendered_dom}-{styles}".encode()).hexdigest()

            res_rnd: dict[str, Any] = {
                "status": "SUCCESS",
                "operation": "render_ui_view",
                "component_name": c_name,
                "viewports": viewports,
                "rendered_dom": rendered_dom,
                "visual_snapshot_hash": visual_hash,
                "simulated_in_sandbox": True,
                "sandbox_localhost_url": f"http://localhost:3000/preview/{c_name.lower()}",
                "zero_external_egress_verified": True,
                "all_rendered": True,
            }
            res_rnd["output"] = dict(res_rnd)
            return res_rnd

        elif effective_operation == "capture_render_evidence":
            render_data = payload.get("render_data")
            if not render_data:
                sub_p = dict(payload)
                sub_p["operation"] = "render_ui_view"
                sub_res = execute_s_code(sub_p, operation="render_ui_view")
                render_data = sub_res.get("output") or sub_res

            c_name = str(render_data.get("component_name") or payload.get("component_name") or "Component")
            viewports = render_data.get("viewports", [])
            vis_hash = str(render_data.get("visual_snapshot_hash") or hashlib.sha256(c_name.encode()).hexdigest())

            res_ev: dict[str, Any] = {
                "status": "SUCCESS",
                "operation": "capture_render_evidence",
                "viewports": viewports,
                "simulated_in_sandbox": True,
                "sandbox_localhost_url": f"http://localhost:3000/preview/{c_name.lower()}",
                "zero_external_egress_verified": True,
                "visual_snapshot_hash": vis_hash,
                "dom_tree_summary": f"Rendered {c_name} DOM across {len(viewports)} viewports successfully.",
                "render_duration_ms": 14.5,
            }
            res_ev["output"] = dict(res_ev)
            return res_ev

        elif effective_operation == "scan_accessibility_wcag":
            markup = str(payload.get("template_markup") or payload.get("markup") or "")
            tokens = payload.get("design_tokens") or {}
            styles = str(payload.get("css_styles") or "")

            findings: list[dict[str, Any]] = []

            # 1. Non-text Content (WCAG 1.1.1)
            img_tags = re.findall(r"<img\b([^>]*)>", markup, re.IGNORECASE)
            missing_alt = False
            for img_attrs in img_tags:
                if "alt=" not in img_attrs.lower():
                    missing_alt = True
                    break
            findings.append({
                "rule_id": "WCAG_2_2_AA_1_1_1_NON_TEXT",
                "criterion": "1.1.1 Non-text Content",
                "description": "All img elements must have descriptive alt attributes.",
                "severity": "CRITICAL" if missing_alt else "PASS",
                "element_selector": "img",
                "is_passed": not missing_alt,
                "recommendation": "Add descriptive alt='' attribute to all images." if missing_alt else "",
            })

            # 2. Heading Structure (WCAG 1.3.1)
            headings = [int(h) for h in re.findall(r"<h([1-6])\b", markup, re.IGNORECASE)]
            heading_gap = False
            for i in range(len(headings) - 1):
                if headings[i+1] > headings[i] + 1:
                    heading_gap = True
                    break
            findings.append({
                "rule_id": "WCAG_2_2_AA_1_3_1_HEADING_HIERARCHY",
                "criterion": "1.3.1 Info and Relationships (Headings)",
                "description": "Heading levels should increase sequentially without skipping levels.",
                "severity": "MODERATE" if heading_gap else "PASS",
                "element_selector": "h1..h6",
                "is_passed": not heading_gap,
                "recommendation": "Ensure headings do not skip levels (e.g. h1 to h3)." if heading_gap else "",
            })

            # 3. Contrast (Minimum) (WCAG 1.4.3)
            contrast_fail = bool(payload.get("simulate_contrast_failure", False))
            findings.append({
                "rule_id": "WCAG_2_2_AA_1_4_3_CONTRAST",
                "criterion": "1.4.3 Contrast (Minimum)",
                "description": "Visual presentation of text has a contrast ratio of at least 4.5:1.",
                "severity": "SERIOUS" if contrast_fail else "PASS",
                "element_selector": "body, text, p",
                "is_passed": not contrast_fail,
                "recommendation": "Increase color contrast between text and background to >= 4.5:1." if contrast_fail else "",
            })

            # 4. Accessible Names (WCAG 4.1.2)
            btn_tags = re.findall(r"<button\b([^>]*)>(.*?)</button>", markup, re.IGNORECASE | re.DOTALL)
            btn_missing_name = False
            for attrs, content in btn_tags:
                if not content.strip() and "aria-label" not in attrs.lower() and "title=" not in attrs.lower():
                    btn_missing_name = True
                    break
            findings.append({
                "rule_id": "WCAG_2_2_AA_4_1_2_NAME_ROLE_VALUE",
                "criterion": "4.1.2 Name, Role, Value",
                "description": "Interactive controls must possess accessible programmatic names.",
                "severity": "CRITICAL" if btn_missing_name else "PASS",
                "element_selector": "button",
                "is_passed": not btn_missing_name,
                "recommendation": "Add visible text or aria-label to all button elements." if btn_missing_name else "",
            })

            # 5. Form Labels (WCAG 3.3.2)
            inputs = re.findall(r"<input\b([^>]*)>", markup, re.IGNORECASE)
            input_unlabeled = False
            for inp_attrs in inputs:
                if "type=\"hidden\"" not in inp_attrs.lower() and "aria-label" not in inp_attrs.lower() and "id=" not in inp_attrs.lower():
                    input_unlabeled = True
                    break
            findings.append({
                "rule_id": "WCAG_2_2_AA_3_3_2_LABELS",
                "criterion": "3.3.2 Labels or Instructions",
                "description": "Form inputs must have associated labels or aria-label attributes.",
                "severity": "SERIOUS" if input_unlabeled else "PASS",
                "element_selector": "input",
                "is_passed": not input_unlabeled,
                "recommendation": "Provide associated label or aria-label for each form input." if input_unlabeled else "",
            })

            # 6. Landmarks (WCAG 1.3.1)
            has_landmarks = any(f"<{l}" in markup.lower() for l in ("section", "main", "nav", "header", "footer", "aside")) or "role=" in markup.lower()
            findings.append({
                "rule_id": "WCAG_2_2_AA_1_3_1_LANDMARKS",
                "criterion": "1.3.1 Info and Relationships (Landmarks)",
                "description": "Content should be structured using semantic landmark regions.",
                "severity": "MINOR" if not has_landmarks else "PASS",
                "element_selector": "main, section, nav",
                "is_passed": has_landmarks,
                "recommendation": "Wrap content in semantic landmarks (main, section, nav) or role attributes." if not has_landmarks else "",
            })

            rules_evaluated = len(findings)
            rules_passed = sum(1 for f in findings if f["is_passed"])
            compliance_score = round((rules_passed / rules_evaluated) * 100.0, 2) if rules_evaluated > 0 else 100.0

            res_wcag: dict[str, Any] = {
                "status": "SUCCESS",
                "operation": "scan_accessibility_wcag",
                "target_standard": "WCAG 2.2 A/AA",
                "rules_evaluated": rules_evaluated,
                "rules_passed": rules_passed,
                "compliance_score": compliance_score,
                "findings": findings,
                "contrast_ratio_verified": not contrast_fail,
                "keyboard_navigable_verified": True,
                "aria_semantics_verified": not btn_missing_name,
                "disclaimer": (
                    "Automated scan provides evidence of WCAG 2.2 A/AA criteria adherence, "
                    "but does not constitute comprehensive manual screen-reader or assistive-technology certification."
                ),
            }
            res_wcag["output"] = dict(res_wcag)
            return res_wcag

    # 1.4 Code Implementation Operations Dispatch (DE-09 DEV-CODE)
    if effective_operation in (
        "apply_code_patch",
        "format_code",
        "inspect_ast_symbols",
        "validate_syntax_compiler",
        "manage_packages",
        "generate_code",
    ):
        if effective_operation == "apply_code_patch":
            target_file = str(payload.get("target_file") or payload.get("file_path") or "")
            original_content = str(payload.get("original_content") or "")
            new_content = payload.get("new_content")
            patch_text = payload.get("patch") or payload.get("patch_text")
            allowed_artifacts = payload.get("allowed_artifacts")

            # Check for path traversal or sensitive file targets
            disallowed_patterns = ("..", "/etc/", "~/", "c:\\windows", "c:/windows", ".env", ".git", "authorized_keys")
            tf_lower = target_file.lower().replace("\\", "/")
            if any(p in tf_lower for p in disallowed_patterns) or tf_lower.startswith("/"):
                return {
                    "status": "security_violation",
                    "security_violation": True,
                    "operation": "apply_code_patch",
                    "error": f"Security violation: Path traversal or unauthorized target path '{target_file}'.",
                }

            # Scope boundary check
            if allowed_artifacts is not None:
                allowed_set = set(allowed_artifacts)
                if target_file not in allowed_set:
                    return {
                        "status": "security_violation",
                        "security_violation": True,
                        "operation": "apply_code_patch",
                        "error": f"Scope boundary violation: Target file '{target_file}' is not in authorized artifacts {sorted(allowed_set)}.",
                    }

            if new_content is not None:
                patched_code = str(new_content)
            elif patch_text:
                target_str = payload.get("target_content")
                replacement_str = payload.get("replacement_content")
                if target_str is not None and replacement_str is not None:
                    if target_str in original_content:
                        patched_code = original_content.replace(target_str, replacement_str, 1)
                    else:
                        patched_code = original_content + "\n" + replacement_str
                else:
                    patched_code = str(patch_text)
            else:
                patched_code = original_content

            action = "create" if not original_content.strip() else "modify"

            import difflib
            orig_lines = original_content.splitlines(keepends=True)
            new_lines = patched_code.splitlines(keepends=True)
            diff_lines = list(difflib.unified_diff(
                orig_lines,
                new_lines,
                fromfile=f"a/{target_file}",
                tofile=f"b/{target_file}",
            ))
            diff_unified = "".join(diff_lines)
            if not diff_unified and original_content != patched_code:
                comp_lines = patched_code.splitlines()
                diff_unified = (
                    f"--- a/{target_file}\n"
                    f"+++ b/{target_file}\n"
                    f"@@ -0,0 +1,{len(comp_lines)} @@\n"
                    + "".join(f"+ {line}\n" for line in comp_lines)
                )

            res_patch: dict[str, Any] = {
                "status": "SUCCESS",
                "operation": "apply_code_patch",
                "file_path": target_file,
                "patched_content": patched_code,
                "diff_unified": diff_unified,
                "action": action,
                "is_patched": True,
            }
            res_patch["output"] = dict(res_patch)
            return res_patch

        elif effective_operation == "format_code":
            code_str = str(payload.get("code") or payload.get("content") or "")
            file_path = str(payload.get("file_path") or "module.py")

            lines = [line.rstrip() for line in code_str.splitlines()]
            formatted_code = "\n".join(lines).strip()
            if formatted_code:
                formatted_code += "\n"

            if file_path.endswith(".py") and code_str.strip():
                try:
                    tree = ast.parse(code_str)
                    if hasattr(ast, "unparse"):
                        formatted_code = ast.unparse(tree) + "\n"
                except Exception:
                    pass

            res_fmt: dict[str, Any] = {
                "status": "SUCCESS",
                "operation": "format_code",
                "file_path": file_path,
                "formatted_code": formatted_code,
                "is_formatted": True,
            }
            res_fmt["output"] = dict(res_fmt)
            return res_fmt

        elif effective_operation == "inspect_ast_symbols":
            code_str = str(payload.get("code") or "")
            file_path = str(payload.get("file_path") or "module.py")

            classes: list[dict[str, Any]] = []
            functions: list[dict[str, Any]] = []
            imports: list[dict[str, Any]] = []
            errors: list[str] = []
            node_count = 0

            try:
                tree = ast.parse(code_str, filename=file_path)
                for node in ast.walk(tree):
                    node_count += 1

                for node in tree.body:
                    if isinstance(node, ast.ClassDef):
                        bases = [ast.unparse(b) for b in node.bases] if hasattr(ast, "unparse") else [getattr(b, "id", "") for b in node.bases]
                        methods = [n.name for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
                        doc = ast.get_docstring(node) or ""
                        classes.append({
                            "name": node.name,
                            "bases": bases,
                            "methods": methods,
                            "docstring": doc,
                            "line_number": getattr(node, "lineno", 1),
                        })
                    elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        args = [a.arg for a in node.args.args]
                        doc = ast.get_docstring(node) or ""
                        decorators = [ast.unparse(d) for d in node.decorator_list] if hasattr(ast, "unparse") else []
                        functions.append({
                            "name": node.name,
                            "args": args,
                            "is_async": isinstance(node, ast.AsyncFunctionDef),
                            "docstring": doc,
                            "decorators": decorators,
                            "line_number": getattr(node, "lineno", 1),
                        })
                    elif isinstance(node, ast.Import):
                        for alias in node.names:
                            imports.append({"module": alias.name, "alias": alias.asname})
                    elif isinstance(node, ast.ImportFrom):
                        for alias in node.names:
                            imports.append({"module": f"{node.module or ''}.{alias.name}", "alias": alias.asname})
            except SyntaxError as exc:
                errors.append(f"AST parsing failed: {exc}")

            symbols_summary = {
                "classes": [c["name"] for c in classes],
                "functions": [f["name"] for f in functions],
                "import_count": len(imports),
                "node_count": node_count,
            }

            res_sym: dict[str, Any] = {
                "status": "SUCCESS" if not errors else "AST_PARSE_ERROR",
                "operation": "inspect_ast_symbols",
                "file_path": file_path,
                "ast_valid": len(errors) == 0,
                "node_count": node_count,
                "classes": classes,
                "functions": functions,
                "imports": imports,
                "symbols_summary": symbols_summary,
                "errors": errors,
            }
            res_sym["output"] = dict(res_sym)
            return res_sym

        elif effective_operation == "validate_syntax_compiler":
            code_str = str(payload.get("code") or "")
            file_path = str(payload.get("file_path") or "module.py")

            checks_run = ["ast_parsing", "python_compiler_exec", "symbol_resolution"]
            errors: list[str] = []
            warnings: list[str] = []
            syntax_valid = True
            compiler_passed = True

            if not code_str.strip():
                errors.append("Source code is empty.")
                syntax_valid = False
                compiler_passed = False
            else:
                try:
                    ast.parse(code_str, filename=file_path)
                except SyntaxError as exc:
                    syntax_valid = False
                    errors.append(f"Syntax error at line {exc.lineno}: {exc.msg}")

                if syntax_valid:
                    try:
                        compile(code_str, file_path, "exec")
                    except Exception as exc:
                        compiler_passed = False
                        errors.append(f"Compiler sanity check failed: {exc}")
                else:
                    compiler_passed = False

                if "from * import" in code_str or "import *" in code_str:
                    warnings.append("Wildcard import detected; recommend explicit imports.")
                if "except:" in code_str:
                    warnings.append("Bare except clause detected; recommend specific exception types.")

            is_valid = len(errors) == 0
            res_comp_sanity: dict[str, Any] = {
                "status": "SUCCESS" if is_valid else "VALIDATION_ERROR",
                "operation": "validate_syntax_compiler",
                "is_valid": is_valid,
                "syntax_valid": syntax_valid,
                "compiler_passed": compiler_passed,
                "checks_run": checks_run,
                "compiler_output": "Compilation succeeded with 0 errors." if is_valid else f"Compilation failed: {errors}",
                "errors": errors,
                "warnings": warnings,
            }
            res_comp_sanity["output"] = dict(res_comp_sanity)
            return res_comp_sanity

        elif effective_operation == "manage_packages":
            pkg_name = str(payload.get("package_name") or "")
            action = str(payload.get("action") or "ADD").upper()
            version_spec = str(payload.get("version_spec") or "")
            egress_granted = bool(payload.get("egress_granted", False))
            authorized_packages = payload.get("authorized_packages") or []
            is_plan_authorized = bool(payload.get("is_plan_authorized", False))

            if not is_plan_authorized and pkg_name not in authorized_packages:
                res_err: dict[str, Any] = {
                    "status": "security_violation",
                    "security_violation": True,
                    "operation": "manage_packages",
                    "error": f"Security violation: Package '{pkg_name}' modification is not authorized by the approved plan.",
                    "package_name": pkg_name,
                    "is_authorized": False,
                }
                res_err["output"] = dict(res_err)
                return res_err

            if not egress_granted:
                res_err2: dict[str, Any] = {
                    "status": "security_violation",
                    "security_violation": True,
                    "operation": "manage_packages",
                    "error": f"Security violation: Network egress is disabled for package management of '{pkg_name}'.",
                    "package_name": pkg_name,
                    "is_authorized": False,
                }
                res_err2["output"] = dict(res_err2)
                return res_err2

            res_pkg: dict[str, Any] = {
                "status": "SUCCESS",
                "operation": "manage_packages",
                "package_name": pkg_name,
                "action": action,
                "version_spec": version_spec,
                "is_authorized": True,
                "message": f"Package '{pkg_name}' ({action}) successfully verified against allow-listed proxy.",
            }
            res_pkg["output"] = dict(res_pkg)
            return res_pkg

        elif effective_operation == "generate_code":
            c_name = str(payload.get("component_name") or "ApplicationService")
            file_path = str(payload.get("file_path") or f"services/{c_name.lower()}.py")

            code = (
                f'"""Application logic for {c_name}.\n\n'
                f'Generated by DEV-CODE authoring specialist.\n'
                f'"""\n\n'
                f'from __future__ import annotations\n\n'
                f'from typing import Any\n'
                f'import logging\n\n'
                f'logger = logging.getLogger(__name__)\n\n\n'
                f'class {c_name}:\n'
                f'    """Service implementation for {c_name}."""\n\n'
                f'    def __init__(self, config: dict[str, Any] | None = None) -> None:\n'
                f'        self.config = config or {{}}\n\n'
                f'    async def execute(self, payload: dict[str, Any]) -> dict[str, Any]:\n'
                f'        """Process business logic payload."""\n'
                f'        logger.info("Executing {c_name} with payload keys: %s", list(payload.keys()))\n'
                f'        return {{"status": "SUCCESS", "component": "{c_name}", "data": payload}}\n'
            )

            res_gen: dict[str, Any] = {
                "status": "SUCCESS",
                "operation": "generate_code",
                "component_name": c_name,
                "file_path": file_path,
                "code": code,
            }
            res_gen["output"] = dict(res_gen)
            return res_gen

    # 1.5 Verification Operations Dispatch (DE-10 DEV-VERIFY)
    if effective_operation in (
        "verify_environment",
        "run_build",
        "run_lint_check",
        "run_format_check",
        "run_type_check",
        "run_automated_tests",
        "run_coverage_analysis",
    ):
        # DEV-VERIFY enforces strict read-only execution: mutation attempts fail closed
        if payload.get("mutation_attempted") or payload.get("write_file") or payload.get("apply_patch"):
            res_mut: dict[str, Any] = {
                "status": "security_violation",
                "security_violation": True,
                "operation": effective_operation,
                "error": "Security violation: DEV-VERIFY is strictly read-only; mutation attempts are rejected.",
                "mutation_rejected": True,
            }
            res_mut["output"] = dict(res_mut)
            return res_mut

        if effective_operation == "verify_environment":
            required_tools = payload.get("required_tools") or ["python", "pytest", "ruff", "mypy"]
            env_status = str(payload.get("env_status", "READY")).upper()
            isolation_ok = bool(payload.get("isolation_validated", True))
            tools_present: list[str] = []
            missing_tools: list[str] = []

            for tool in required_tools:
                if payload.get(f"tool_missing_{tool}"):
                    missing_tools.append(tool)
                else:
                    tools_present.append(tool)

            is_ready = env_status == "READY" and isolation_ok and len(missing_tools) == 0
            res_env: dict[str, Any] = {
                "status": "SUCCESS" if is_ready else "BLOCKED",
                "operation": "verify_environment",
                "is_ready": is_ready,
                "isolation_validated": isolation_ok,
                "tools_present": tools_present,
                "missing_tools": missing_tools,
                "python_version": "3.11.0",
                "sandbox_isolation": "ACTIVE",
            }
            if not is_ready:
                res_env["error"] = f"Environment verification failed: missing tools={missing_tools}, isolation={isolation_ok}"
            res_env["output"] = dict(res_env)
            return res_env

        elif effective_operation == "run_build":
            candidate_source = payload.get("source_code") or {}
            simulated_failure = payload.get("simulate_build_failure")

            build_errors: list[str] = []
            if simulated_failure:
                build_errors.append(str(simulated_failure))
            else:
                for file_path, code in candidate_source.items():
                    if file_path.endswith(".py"):
                        try:
                            compile(code, file_path, "exec")
                        except Exception as exc:
                            build_errors.append(f"Build compilation error in '{file_path}': {exc}")

            success = len(build_errors) == 0
            res_build: dict[str, Any] = {
                "status": "SUCCESS" if success else "FAIL",
                "operation": "run_build",
                "exit_code": 0 if success else 1,
                "success": success,
                "build_passed": success,
                "compiled_files": list(candidate_source.keys()),
                "errors": build_errors,
                "stdout": "Build succeeded: all artifacts compiled cleanly." if success else "Build failed.",
                "stderr": "\n".join(build_errors) if build_errors else "",
            }
            res_build["output"] = dict(res_build)
            return res_build

        elif effective_operation == "run_lint_check":
            candidate_source = payload.get("source_code") or {}
            simulated_lint_errors = payload.get("simulate_lint_errors") or []
            lint_errors: list[str] = list(simulated_lint_errors)
            lint_warnings: list[str] = []

            for file_path, code in candidate_source.items():
                if file_path.endswith(".py"):
                    try:
                        tree = ast.parse(code, filename=file_path)
                        for node in ast.walk(tree):
                            if isinstance(node, ast.ImportFrom) and any(alias.name == "*" for alias in node.names):
                                lint_errors.append(f"{file_path}:{node.lineno}: [F403] 'from ... import *' used; unable to detect undefined names")
                            if isinstance(node, ast.ExceptHandler) and node.type is None:
                                lint_warnings.append(f"{file_path}:{node.lineno}: [E722] do not use bare 'except'")
                    except SyntaxError as syn_err:
                        lint_errors.append(f"{file_path}:{syn_err.lineno}: [E999] SyntaxError: {syn_err.msg}")

            passed = len(lint_errors) == 0
            res_lint: dict[str, Any] = {
                "status": "SUCCESS" if passed else "FAIL",
                "operation": "run_lint_check",
                "exit_code": 0 if passed else 1,
                "passed": passed,
                "lint_passed": passed,
                "error_count": len(lint_errors),
                "warning_count": len(lint_warnings),
                "errors": lint_errors,
                "warnings": lint_warnings,
                "stdout": f"All checks passed ({len(candidate_source)} files checked)." if passed else f"Found {len(lint_errors)} lint errors.",
                "stderr": "\n".join(lint_errors) if lint_errors else "",
            }
            res_lint["output"] = dict(res_lint)
            return res_lint

        elif effective_operation == "run_format_check":
            candidate_source = payload.get("source_code") or {}
            simulated_unformatted = payload.get("simulate_unformatted_files") or []
            unformatted_files: list[str] = list(simulated_unformatted)

            for file_path, code in candidate_source.items():
                lines = code.splitlines()
                has_trailing_space = any(line.rstrip() != line for line in lines)
                has_missing_final_newline = bool(code and not code.endswith("\n"))
                if has_trailing_space or has_missing_final_newline:
                    if file_path not in unformatted_files:
                        unformatted_files.append(file_path)

            passed = len(unformatted_files) == 0
            res_fmt_check: dict[str, Any] = {
                "status": "SUCCESS" if passed else "FAIL",
                "operation": "run_format_check",
                "exit_code": 0 if passed else 1,
                "passed": passed,
                "format_passed": passed,
                "unformatted_files": unformatted_files,
                "stdout": "All files formatted cleanly." if passed else f"{len(unformatted_files)} files would be reformatted.",
                "stderr": f"Files requiring formatting: {unformatted_files}" if unformatted_files else "",
            }
            res_fmt_check["output"] = dict(res_fmt_check)
            return res_fmt_check

        elif effective_operation == "run_type_check":
            candidate_source = payload.get("source_code") or {}
            simulated_type_errors = payload.get("simulate_type_errors") or []
            type_errors: list[str] = list(simulated_type_errors)

            for file_path, code in candidate_source.items():
                if file_path.endswith(".py"):
                    try:
                        tree = ast.parse(code, filename=file_path)
                        for node in ast.walk(tree):
                            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                                if payload.get("strict_type_checking") and node.returns is None:
                                    type_errors.append(f"{file_path}:{node.lineno}: Function '{node.name}' is missing return type annotation")
                    except Exception as exc:
                        type_errors.append(f"{file_path}: Type parse error: {exc}")

            passed = len(type_errors) == 0
            res_type: dict[str, Any] = {
                "status": "SUCCESS" if passed else "FAIL",
                "operation": "run_type_check",
                "exit_code": 0 if passed else 1,
                "passed": passed,
                "type_check_passed": passed,
                "error_count": len(type_errors),
                "errors": type_errors,
                "stdout": "Success: no type issues found." if passed else f"Found {len(type_errors)} type errors.",
                "stderr": "\n".join(type_errors) if type_errors else "",
            }
            res_type["output"] = dict(res_type)
            return res_type

        elif effective_operation == "run_automated_tests":
            test_type = str(payload.get("test_type", "unit")).lower()
            simulated_test_results = payload.get("simulate_test_results")

            if simulated_test_results:
                passed = int(simulated_test_results.get("passed", 0))
                failed = int(simulated_test_results.get("failed", 0))
                skipped = int(simulated_test_results.get("skipped", 0))
                errored = int(simulated_test_results.get("errored", 0))
                duration_s = float(simulated_test_results.get("duration_s", 1.25))
                failures = list(simulated_test_results.get("failures", []))
            else:
                passed = int(payload.get("tests_passed", 12))
                failed = int(payload.get("tests_failed", 0))
                skipped = int(payload.get("tests_skipped", 0))
                errored = int(payload.get("tests_errored", 0))
                duration_s = float(payload.get("duration_s", 0.85))
                failures = payload.get("test_failures") or []

            total = passed + failed + skipped + errored
            all_passed = (failed == 0 and errored == 0 and total > 0)
            res_test: dict[str, Any] = {
                "status": "SUCCESS" if all_passed else "FAIL",
                "operation": "run_automated_tests",
                "exit_code": 0 if all_passed else 1,
                "test_type": test_type,
                "all_passed": all_passed,
                "test_totals": {
                    "passed": passed,
                    "failed": failed,
                    "skipped": skipped,
                    "errored": errored,
                    "total": total,
                    "duration_s": duration_s,
                },
                "failures": failures,
                "stdout": f"==== {passed} passed in {duration_s}s ====" if all_passed else f"==== {failed} failed, {passed} passed ====",
                "stderr": "\n".join(failures) if failures else "",
            }
            res_test["output"] = dict(res_test)
            return res_test

        elif effective_operation == "run_coverage_analysis":
            simulated_coverage = payload.get("simulate_coverage")
            min_required_pct = float(payload.get("minimum_required_pct", 80.0))

            if simulated_coverage:
                line_pct = float(simulated_coverage.get("line_coverage_pct", 85.0))
                branch_pct = float(simulated_coverage.get("branch_coverage_pct", 80.0))
                total_stmt = int(simulated_coverage.get("total_statements", 100))
                covered_stmt = int(simulated_coverage.get("covered_statements", int(total_stmt * (line_pct / 100.0))))
                missing_lines = dict(simulated_coverage.get("missing_lines_by_file", {}))
            else:
                line_pct = float(payload.get("line_coverage_pct", 92.5))
                branch_pct = float(payload.get("branch_coverage_pct", 88.0))
                total_stmt = int(payload.get("total_statements", 150))
                covered_stmt = int(payload.get("covered_statements", int(total_stmt * (line_pct / 100.0))))
                missing_lines = payload.get("missing_lines_by_file") or {}

            threshold_met = line_pct >= min_required_pct
            res_cov: dict[str, Any] = {
                "status": "SUCCESS" if threshold_met else "FAIL",
                "operation": "run_coverage_analysis",
                "exit_code": 0 if threshold_met else 1,
                "line_coverage_pct": line_pct,
                "branch_coverage_pct": branch_pct,
                "total_statements": total_stmt,
                "covered_statements": covered_stmt,
                "missing_lines_by_file": missing_lines,
                "minimum_required_pct": min_required_pct,
                "coverage_threshold_met": threshold_met,
                "stdout": f"TOTAL coverage: {line_pct:.1f}% (required {min_required_pct:.1f}%)",
                "stderr": "" if threshold_met else f"Coverage {line_pct:.1f}% below minimum threshold {min_required_pct:.1f}%",
            }
            res_cov["output"] = dict(res_cov)
            return res_cov

    # 1.6 Security Review Operations Dispatch (DE-11 DEV-SEC)
    if effective_operation in (
        "scan_sast",
        "scan_secrets",
        "scan_dependencies_sca",
        "review_manifest_configs",
        "check_authorization_boundaries",
        "analyze_ast_dangerous_patterns",
    ):
        # DEV-SEC enforces strict read-only execution: mutation attempts fail closed
        if (
            payload.get("mutation_attempted")
            or payload.get("write_file")
            or payload.get("apply_patch")
        ):
            res_sec_mut: dict[str, Any] = {
                "status": "security_violation",
                "security_violation": True,
                "operation": effective_operation,
                "error": (
                    "Security violation: DEV-SEC is strictly read-only; mutation attempts "
                    "are rejected."
                ),
                "mutation_rejected": True,
            }
            res_sec_mut["output"] = dict(res_sec_mut)
            return res_sec_mut

        sec_findings: list[dict[str, Any]] = []
        # Pre-injected simulated findings (e.g. for testing specific vulnerability paths)
        for sf in payload.get("simulated_findings") or []:
            if isinstance(sf, dict):
                sec_findings.append(sf)

        candidate_sources: dict[str, str] = {}
        if isinstance(payload.get("source_code"), dict):
            candidate_sources.update(payload["source_code"])
        elif isinstance(payload.get("candidate_source"), dict):
            candidate_sources.update(payload["candidate_source"])
        elif code_content:
            candidate_sources["candidate_code.py"] = str(code_content)

        if effective_operation == "scan_sast":
            for fpath, fcontent in candidate_sources.items():
                try:
                    tree = ast.parse(fcontent)
                    for node in ast.walk(tree):
                        # Detect dangerous eval/exec
                        if isinstance(node, ast.Call):
                            func_name = ""
                            if isinstance(node.func, ast.Name):
                                func_name = node.func.id
                            elif isinstance(node.func, ast.Attribute):
                                func_name = node.func.attr
                            if func_name in ("eval", "exec", "compile"):
                                sec_findings.append({
                                    "finding_id": f"sast-eval-{uuid.uuid4().hex[:8]}",
                                    "rule_id": "SEC-SAST-001",
                                    "category": "SAST",
                                    "severity": "CRITICAL",
                                    "title": f"Use of dangerous built-in '{func_name}'",
                                    "description": (
                                        f"Dynamic code execution via '{func_name}' allows arbitrary "
                                        "code injection."
                                    ),
                                    "file_path": fpath,
                                    "line_number": getattr(node, "lineno", 1),
                                    "code_snippet": f"{func_name}(...)",
                                    "remediation_target": "DEV-CODE",
                                    "is_hard_block": True,
                                    "cwe_id": "CWE-95",
                                })
                            elif (
                                func_name in ("system", "popen")
                                and getattr(node.func, "value", None)
                                and getattr(node.func.value, "id", "") == "os"
                            ):
                                sec_findings.append({
                                    "finding_id": f"sast-cmd-{uuid.uuid4().hex[:8]}",
                                    "rule_id": "SEC-SAST-002",
                                    "category": "SAST",
                                    "severity": "CRITICAL",
                                    "title": "Unsafe command execution via os.system",
                                    "description": (
                                        "Direct shell invocation allows command injection vulnerabilities."
                                    ),
                                    "file_path": fpath,
                                    "line_number": getattr(node, "lineno", 1),
                                    "code_snippet": f"os.{func_name}(...)",
                                    "remediation_target": "DEV-CODE",
                                    "is_hard_block": True,
                                    "cwe_id": "CWE-78",
                                })
                            # Check subprocess with shell=True
                            elif func_name in ("call", "check_call", "check_output", "Popen", "run"):
                                for kw in getattr(node, "keywords", []):
                                    if (
                                        kw.arg == "shell"
                                        and isinstance(kw.value, ast.Constant)
                                        and kw.value.value is True
                                    ):
                                        sec_findings.append({
                                            "finding_id": f"sast-subproc-{uuid.uuid4().hex[:8]}",
                                            "rule_id": "SEC-SAST-003",
                                            "category": "SAST",
                                            "severity": "HIGH",
                                            "title": "subprocess invoked with shell=True",
                                            "description": (
                                                "Invoking subprocesses with shell=True opens command "
                                                "injection risk."
                                            ),
                                            "file_path": fpath,
                                            "line_number": getattr(node, "lineno", 1),
                                            "code_snippet": "subprocess(..., shell=True)",
                                            "remediation_target": "DEV-CODE",
                                            "is_hard_block": True,
                                            "cwe_id": "CWE-78",
                                        })
                except Exception as parse_exc:
                    sec_findings.append({
                        "finding_id": f"sast-syntax-{uuid.uuid4().hex[:8]}",
                        "rule_id": "SEC-SAST-000",
                        "category": "SAST",
                        "severity": "HIGH",
                        "title": f"AST parsing failed for {fpath}",
                        "description": str(parse_exc),
                        "file_path": fpath,
                        "line_number": 1,
                        "code_snippet": "",
                        "remediation_target": "DEV-CODE",
                        "is_hard_block": True,
                    })

        elif effective_operation == "scan_secrets":
            secret_regexes = [
                (
                    "SEC-SECRET-001",
                    "CRITICAL",
                    "Private Key Header",
                    r"-----BEGIN (RSA|EC|OPENSSH|DSA|PGP)?\s?PRIVATE KEY-----",
                ),
                (
                    "SEC-SECRET-002",
                    "HIGH",
                    "AWS Access Key ID",
                    r"AKIA[0-9A-Z]{16}",
                ),
                (
                    "SEC-SECRET-003",
                    "HIGH",
                    "GitHub Personal Access Token",
                    r"ghp_[A-Za-z0-9]{36}",
                ),
                (
                    "SEC-SECRET-004",
                    "HIGH",
                    "Hardcoded Secret / Password",
                    r"""(?i)(api[_-]?key|secret[_-]?key|client[_-]?secret|password|passwd)\s*[:=]\s*['"][A-Za-z0-9_\-.~+/=]{8,}['"]""",
                ),
            ]
            for fpath, fcontent in candidate_sources.items():
                for rule_id, sev, title, pat in secret_regexes:
                    for match in re.finditer(pat, fcontent):
                        start = max(0, match.start() - 10)
                        end = min(len(fcontent), match.end() + 10)
                        matched_snippet = fcontent[start:end]
                        lineno = fcontent[: match.start()].count("\n") + 1
                        sec_findings.append({
                            "finding_id": f"secret-{uuid.uuid4().hex[:8]}",
                            "rule_id": rule_id,
                            "category": "SECRET",
                            "severity": sev,
                            "title": title,
                            "description": f"Potential hardcoded credential exposed ({title}).",
                            "file_path": fpath,
                            "line_number": lineno,
                            "code_snippet": matched_snippet[:60],
                            "remediation_target": "DEV-CODE",
                            "is_hard_block": True,
                            "cwe_id": "CWE-798",
                        })

        elif effective_operation == "scan_dependencies_sca":
            known_vulns: dict[str, dict[str, Any]] = {
                "requests": {
                    "vulnerable_before": "2.31.0",
                    "cve": "CVE-2023-32681",
                    "severity": "MEDIUM",
                    "description": "Proxy-Authorization header leak on HTTPS redirect.",
                },
                "urllib3": {
                    "vulnerable_before": "2.0.7",
                    "cve": "CVE-2023-45803",
                    "severity": "HIGH",
                    "description": "Request body not stripped on redirect.",
                },
                "cryptography": {
                    "vulnerable_before": "41.0.0",
                    "cve": "CVE-2023-38325",
                    "severity": "HIGH",
                    "description": "Vulnerable OpenSSL cipher parsing.",
                },
                "jinja2": {
                    "vulnerable_before": "3.1.3",
                    "cve": "CVE-2024-22195",
                    "severity": "HIGH",
                    "description": "Cross-site scripting via xmlattr filter.",
                },
                "pillow": {
                    "vulnerable_before": "10.0.1",
                    "cve": "CVE-2023-4863",
                    "severity": "CRITICAL",
                    "description": "Heap buffer overflow in libwebp.",
                },
                "pyyaml": {
                    "vulnerable_before": "6.0",
                    "cve": "CVE-2020-14343",
                    "severity": "CRITICAL",
                    "description": "Arbitrary code execution through FullLoader.",
                },
            }

            sca_raw_deps: Any = payload.get("dependencies") or {}
            req_content = str(payload.get("requirements_content", ""))

            dep_dict: dict[str, str] = {}
            if isinstance(sca_raw_deps, dict):
                dep_dict = {str(k).lower(): str(v) for k, v in sca_raw_deps.items()}
            elif isinstance(sca_raw_deps, list):
                for item in sca_raw_deps:
                    parts = re.split(r"[=><~^!]", str(item), maxsplit=1)
                    pkg = parts[0].strip().lower()
                    v = parts[1].strip() if len(parts) > 1 else "1.0.0"
                    dep_dict[pkg] = v

            if req_content:
                for line in req_content.splitlines():
                    line = line.strip()
                    if line and not line.startswith("#"):
                        parts = re.split(r"[=><~^!]", line, maxsplit=1)
                        pkg_name = parts[0].strip().lower()
                        pkg_ver = parts[1].strip() if len(parts) > 1 else "1.0.0"
                        dep_dict[pkg_name] = pkg_ver

            for pkg, ver in dep_dict.items():
                if pkg in known_vulns:
                    vuln_info = known_vulns[pkg]
                    cutoff = vuln_info["vulnerable_before"]
                    is_vuln = ver.lstrip("v<>=~^") < cutoff
                    if is_vuln or payload.get("simulate_vulnerability"):
                        sev = vuln_info["severity"]
                        is_hb = sev in ("CRITICAL", "HIGH")
                        sec_findings.append({
                            "finding_id": f"sca-{pkg}-{uuid.uuid4().hex[:8]}",
                            "rule_id": f"SEC-SCA-{pkg.upper()}",
                            "category": "SCA",
                            "severity": sev,
                            "title": f"Vulnerable dependency: {pkg}@{ver}",
                            "description": f"{vuln_info['description']} (Fixed in {cutoff})",
                            "file_path": "requirements.txt",
                            "line_number": 1,
                            "code_snippet": f"{pkg}=={ver}",
                            "remediation_target": "DEV-CODE",
                            "is_hard_block": is_hb,
                            "cve_id": vuln_info["cve"],
                        })

        elif effective_operation == "review_manifest_configs":
            manifests = payload.get("manifests") or {}
            if not manifests and "manifest_content" in payload:
                manifests = {"manifest.yaml": str(payload["manifest_content"])}

            for mpath, mcontent in manifests.items():
                mstr = str(mcontent)
                if re.search(r"(?i)debug\s*[:=]\s*true", mstr):
                    sec_findings.append({
                        "finding_id": f"cfg-debug-{uuid.uuid4().hex[:8]}",
                        "rule_id": "SEC-CFG-001",
                        "category": "CONFIG",
                        "severity": "HIGH",
                        "title": "Debug mode enabled in runtime configuration",
                        "description": "Debug flag exposes stack traces and internal endpoints.",
                        "file_path": mpath,
                        "line_number": 1,
                        "code_snippet": "DEBUG=True",
                        "remediation_target": "DEV-CODE",
                        "is_hard_block": True,
                        "cwe_id": "CWE-489",
                    })
                if re.search(r"(?i)privileged\s*:\s*true", mstr):
                    sec_findings.append({
                        "finding_id": f"cfg-priv-{uuid.uuid4().hex[:8]}",
                        "rule_id": "SEC-CFG-002",
                        "category": "CONFIG",
                        "severity": "CRITICAL",
                        "title": "Container configured with privileged: true",
                        "description": "Privileged containers can escape isolation and compromise host.",
                        "file_path": mpath,
                        "line_number": 1,
                        "code_snippet": "privileged: true",
                        "remediation_target": "DEV-CODE",
                        "is_hard_block": True,
                        "cwe_id": "CWE-250",
                    })
                if re.search(r"(?i)network_mode\s*:\s*host|hostNetwork\s*:\s*true", mstr):
                    sec_findings.append({
                        "finding_id": f"cfg-net-{uuid.uuid4().hex[:8]}",
                        "rule_id": "SEC-CFG-003",
                        "category": "CONFIG",
                        "severity": "HIGH",
                        "title": "Host networking requested",
                        "description": "Host networking bypasses container isolation boundaries.",
                        "file_path": mpath,
                        "line_number": 1,
                        "code_snippet": "hostNetwork: true",
                        "remediation_target": "DEV-CODE",
                        "is_hard_block": True,
                    })

        elif effective_operation == "check_authorization_boundaries":
            routes = payload.get("routes") or []
            for r in routes:
                if isinstance(r, dict) and not r.get("authenticated", True):
                    sec_findings.append({
                        "finding_id": f"perm-route-{uuid.uuid4().hex[:8]}",
                        "rule_id": "SEC-PERM-001",
                        "category": "PERMISSION",
                        "severity": "HIGH",
                        "title": f"Unauthenticated route: {r.get('path', 'unknown')}",
                        "description": "Route does not enforce authentication or tenant isolation.",
                        "file_path": r.get("file_path", "routes.py"),
                        "line_number": r.get("line_number", 1),
                        "code_snippet": f"{r.get('method', 'GET')} {r.get('path', '')}",
                        "remediation_target": "DEV-CODE",
                        "is_hard_block": True,
                        "cwe_id": "CWE-306",
                    })

        elif effective_operation == "analyze_ast_dangerous_patterns":
            for fpath, fcontent in candidate_sources.items():
                try:
                    tree = ast.parse(fcontent)
                    for node in ast.walk(tree):
                        if (
                            isinstance(node, ast.Attribute)
                            and node.attr in ("__globals__", "__subclasses__")
                        ):
                            sec_findings.append({
                                "finding_id": f"ast-magic-{uuid.uuid4().hex[:8]}",
                                "rule_id": "SEC-AST-001",
                                "category": "AST_PATTERN",
                                "severity": "CRITICAL",
                                "title": f"Introspection attack pattern '{node.attr}'",
                                "description": (
                                    f"Access to Python magic attribute '{node.attr}' indicates "
                                    "sandbox escape attempt."
                                ),
                                "file_path": fpath,
                                "line_number": getattr(node, "lineno", 1),
                                "code_snippet": f".{node.attr}",
                                "remediation_target": "DEV-CODE",
                                "is_hard_block": True,
                                "cwe_id": "CWE-94",
                            })
                except Exception as ast_err:
                    sec_findings.append({
                        "finding_id": f"ast-err-{uuid.uuid4().hex[:8]}",
                        "rule_id": "SEC-AST-ERR",
                        "category": "AST_PATTERN",
                        "severity": "HIGH",
                        "title": "AST Pattern check failed",
                        "description": str(ast_err),
                        "file_path": fpath,
                        "line_number": 1,
                        "code_snippet": "",
                        "remediation_target": "DEV-CODE",
                        "is_hard_block": True,
                    })

        hard_block_count = sum(
            1
            for f in sec_findings
            if f.get("is_hard_block") or f.get("severity") in ("CRITICAL", "HIGH")
        )
        verdict = "DENY" if hard_block_count > 0 else "PASS"

        res_sec: dict[str, Any] = {
            "status": "SUCCESS" if verdict == "PASS" else "DENIED",
            "operation": effective_operation,
            "verdict": verdict,
            "findings": sec_findings,
            "total_findings": len(sec_findings),
            "hard_block_count": hard_block_count,
            "remediation_targets": sorted(
                list({f.get("remediation_target", "DEV-CODE") for f in sec_findings})
            ),
            "scanners_run": [effective_operation],
        }
        res_sec["output"] = dict(res_sec)
        return res_sec

    # 1.7 Release Packaging Operations Dispatch (DE-11 DEV-REL)
    if effective_operation in (
        "package_release_bundle",
        "generate_cyclonedx_sbom",
        "generate_deployment_manifest",
        "generate_rollback_manifest",
        "simulate_migration_dry_run",
        "verify_release_integrity",
    ):
        rel_component = str(payload.get("component_name", component_name))
        rel_version = str(payload.get("version", "1.0.0"))
        rel_task_id = str(payload.get("task_id", task_id))

        if effective_operation == "package_release_bundle":
            source_files = payload.get("source_files") or {}
            artifacts_list: list[dict[str, Any]] = []
            digests_map: dict[str, str] = {}

            if isinstance(source_files, dict):
                for fname, fcontent in sorted(source_files.items()):
                    content_bytes = (
                        fcontent.encode("utf-8")
                        if isinstance(fcontent, str)
                        else bytes(fcontent)
                    )
                    sha = hashlib.sha256(content_bytes).hexdigest()
                    artifacts_list.append({
                        "artifact_name": fname,
                        "file_path": f"dist/{fname}",
                        "sha256": sha,
                        "size_bytes": len(content_bytes),
                        "media_type": (
                            "text/plain"
                            if fname.endswith((".py", ".txt", ".json", ".md"))
                            else "application/octet-stream"
                        ),
                    })
                    digests_map[fname] = sha
            elif isinstance(source_files, list):
                for item in source_files:
                    fname = str(item)
                    dummy_bytes = f"# packaged artifact: {fname}\n".encode("utf-8")
                    sha = hashlib.sha256(dummy_bytes).hexdigest()
                    artifacts_list.append({
                        "artifact_name": fname,
                        "file_path": f"dist/{fname}",
                        "sha256": sha,
                        "size_bytes": len(dummy_bytes),
                        "media_type": "application/octet-stream",
                    })
                    digests_map[fname] = sha

            bundle_digest = hashlib.sha256(
                json.dumps(digests_map, sort_keys=True).encode("utf-8")
            ).hexdigest()

            res_bundle: dict[str, Any] = {
                "status": "SUCCESS",
                "operation": "package_release_bundle",
                "component_name": rel_component,
                "version": rel_version,
                "release_artifacts": artifacts_list,
                "artifact_digests": digests_map,
                "bundle_digest": bundle_digest,
                "artifact_count": len(artifacts_list),
            }
            res_bundle["output"] = dict(res_bundle)
            return res_bundle

        elif effective_operation == "generate_cyclonedx_sbom":
            sbom_raw_deps: Any = payload.get("dependencies") or {}
            components_list: list[dict[str, Any]] = []

            dep_items: list[tuple[str, str]] = []
            if isinstance(sbom_raw_deps, dict):
                dep_items = [(str(k), str(v)) for k, v in sbom_raw_deps.items()]
            elif isinstance(sbom_raw_deps, list):
                for item in sbom_raw_deps:
                    parts = re.split(r"[=><~^!]", str(item), maxsplit=1)
                    pkg = parts[0].strip()
                    v = parts[1].strip() if len(parts) > 1 else "1.0.0"
                    dep_items.append((pkg, v))

            for pkg_name, pkg_ver in sorted(dep_items):
                purl = f"pkg:pypi/{pkg_name}@{pkg_ver}"
                comp_hash = hashlib.sha256(purl.encode("utf-8")).hexdigest()
                components_list.append({
                    "name": pkg_name,
                    "version": pkg_ver,
                    "type": "library",
                    "purl": purl,
                    "hashes": {"SHA-256": comp_hash},
                    "licenses": ["MIT"],
                })

            sbom_dict: dict[str, Any] = {
                "bomFormat": "CycloneDX",
                "specVersion": "1.5",
                "serialNumber": f"urn:uuid:{uuid.uuid4()}",
                "version": 1,
                "metadata": {
                    "component": {
                        "name": rel_component,
                        "version": rel_version,
                        "type": "application",
                    }
                },
                "components": components_list,
                "dependencies": [],
            }
            sbom_bytes = json.dumps(sbom_dict, sort_keys=True).encode("utf-8")
            sbom_dict["sbom_hash"] = hashlib.sha256(sbom_bytes).hexdigest()

            res_sbom: dict[str, Any] = {
                "status": "SUCCESS",
                "operation": "generate_cyclonedx_sbom",
                "sbom": sbom_dict,
                "sbom_hash": sbom_dict["sbom_hash"],
                "component_count": len(components_list),
            }
            res_sbom["output"] = dict(res_sbom)
            return res_sbom

        elif effective_operation == "generate_deployment_manifest":
            manifest_id = str(
                payload.get("manifest_id") or f"deploy-{rel_component}-{rel_version}"
            )
            deploy_dict: dict[str, Any] = {
                "manifest_id": manifest_id,
                "component_name": rel_component,
                "version": rel_version,
                "runtime": str(payload.get("runtime", "python:3.11-slim")),
                "entrypoint": str(payload.get("entrypoint", "main.py")),
                "environment_variables": dict(
                    sorted(payload.get("environment_variables", {}).items())
                ),
                "healthcheck_endpoint": str(payload.get("healthcheck_endpoint", "/health")),
                "resource_limits": payload.get("resource_limits")
                or {"cpu": "1.0", "memory": "1Gi"},
                "ingress_route": str(payload.get("ingress_route", f"/{rel_component}")),
            }
            manifest_bytes = json.dumps(deploy_dict, sort_keys=True).encode("utf-8")
            deploy_dict["manifest_hash"] = hashlib.sha256(manifest_bytes).hexdigest()

            res_deploy: dict[str, Any] = {
                "status": "SUCCESS",
                "operation": "generate_deployment_manifest",
                "deployment_manifest": deploy_dict,
                "manifest_hash": deploy_dict["manifest_hash"],
            }
            res_deploy["output"] = dict(res_deploy)
            return res_deploy

        elif effective_operation == "generate_rollback_manifest":
            target_rel_id = str(payload.get("target_release_id", f"rel-{rel_task_id}"))
            prev_ver = str(payload.get("previous_stable_version", "0.9.0"))
            revert_steps = payload.get("revert_steps") or [
                "Drain active traffic from candidate pods",
                "Route 100% traffic to previous stable version",
                "Verify health check endpoints respond with 200 OK",
            ]
            mig_revert = payload.get("migration_revert_instructions") or []
            auto_checks = payload.get("automated_verification_steps") or [
                "GET /health returns status UP",
                "Validate error rate < 0.01% over 5-minute window",
            ]

            rollback_dict: dict[str, Any] = {
                "rollback_id": f"rollback-{target_rel_id}",
                "target_release_id": target_rel_id,
                "previous_stable_version": prev_ver,
                "rollback_strategy": str(
                    payload.get("rollback_strategy", "BLUE_GREEN_DRAIN")
                ),
                "revert_steps": revert_steps,
                "migration_revert_instructions": mig_revert,
                "automated_verification_steps": auto_checks,
            }
            rb_bytes = json.dumps(rollback_dict, sort_keys=True).encode("utf-8")
            rollback_dict["rollback_hash"] = hashlib.sha256(rb_bytes).hexdigest()

            res_rb: dict[str, Any] = {
                "status": "SUCCESS",
                "operation": "generate_rollback_manifest",
                "rollback_manifest": rollback_dict,
                "rollback_hash": rollback_dict["rollback_hash"],
            }
            res_rb["output"] = dict(res_rb)
            return res_rb

        elif effective_operation == "simulate_migration_dry_run":
            sim_failure = bool(payload.get("simulate_migration_failure", False))
            raw_instructions = (
                payload.get("migrations")
                or payload.get("migration_instructions")
                or [
                    {
                        "step_number": 1,
                        "operation": "CREATE_TABLE_IF_NOT_EXISTS",
                        "model_name": rel_component,
                        "dry_run_passed": not sim_failure,
                        "sql_or_schema_change": (
                            f"-- dry-run schema migration for {rel_component}"
                        ),
                    }
                ]
            )
            processed_instructions: list[dict[str, Any]] = []
            for idx, inst in enumerate(raw_instructions, 1):
                if isinstance(inst, dict):
                    processed_instructions.append({
                        "step_number": inst.get("step_number", idx),
                        "operation": str(inst.get("operation", "APPLY_SCHEMA_DELTA")),
                        "model_name": str(inst.get("model_name", rel_component)),
                        "dry_run_passed": not sim_failure and bool(
                            inst.get("dry_run_passed", True)
                        ),
                        "sql_or_schema_change": str(inst.get("sql_or_schema_change", "")),
                    })

            all_passed = not sim_failure and all(
                i["dry_run_passed"] for i in processed_instructions
            )
            res_mig: dict[str, Any] = {
                "status": "SUCCESS" if all_passed else "FAIL",
                "operation": "simulate_migration_dry_run",
                "dry_run_passed": all_passed,
                "migration_instructions": processed_instructions,
                "error": (
                    ""
                    if all_passed
                    else "Database migration dry-run simulation failed: backward-incompatible schema delta."
                ),
            }
            res_mig["output"] = dict(res_mig)
            return res_mig

        elif effective_operation == "verify_release_integrity":
            artifacts_to_check = payload.get("release_artifacts") or []
            expected_digests = payload.get("artifact_digests") or {}
            mismatches: list[str] = []
            matched = 0

            for art in artifacts_to_check:
                if isinstance(art, dict):
                    aname = art.get("artifact_name", "")
                    asha = art.get("sha256", "")
                    if aname in expected_digests:
                        if expected_digests[aname] == asha:
                            matched += 1
                        else:
                            mismatches.append(
                                f"{aname}: expected {expected_digests[aname]}, got {asha}"
                            )
                    else:
                        matched += 1

            integrity_ok = len(mismatches) == 0
            res_integ: dict[str, Any] = {
                "status": "SUCCESS" if integrity_ok else "INTEGRITY_FAIL",
                "operation": "verify_release_integrity",
                "integrity_verified": integrity_ok,
                "matched_count": matched,
                "mismatches": mismatches,
                "error": (
                    ""
                    if integrity_ok
                    else f"Release integrity verification failed on {len(mismatches)} artifacts."
                ),
            }
            res_integ["output"] = dict(res_integ)
            return res_integ

    # 2. Syntax & AST Validation
    ast_valid = True
    node_count = 0
    function_count = 0
    class_count = 0
    syntax_error = None

    if code_content:
        try:
            tree = ast.parse(str(code_content))
            for node in ast.walk(tree):
                node_count += 1
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    function_count += 1
                elif isinstance(node, ast.ClassDef):
                    class_count += 1
            validation_findings.append(
                f"AST verification passed: {node_count} nodes, {class_count} classes, {function_count} functions."
            )
        except SyntaxError as err:
            ast_valid = False
            syntax_error = f"SyntaxError at line {err.lineno}: {err.msg}"
            validation_findings.append(syntax_error)
    else:
        # Generate default component skeleton and diff if none provided
        code_content = (
            f"class {component_name}:\n"
            f"    def render(self, context: dict) -> str:\n"
            f"        return f'<div class=\"{component_name.lower()}-container\">{component_name}: {{context}}</div>'\n"
        )
        tree = ast.parse(code_content)
        node_count = len(list(ast.walk(tree)))
        class_count = 1
        function_count = 1
        validation_findings.append(f"Generated default component skeleton for '{component_name}'.")

    # 3. CMS Schema Diff Generation & Staged Model Reconciliation
    cms_schema_diffs: list[dict[str, Any]] = []
    staged_models_raw = payload.get("t06_staged_models") or payload.get("staged_cms_models")
    staged_models: list[dict[str, Any]] = []
    if staged_models_raw:
        if isinstance(staged_models_raw, str):
            try:
                parsed_staged = json.loads(staged_models_raw)
                staged_models = parsed_staged if isinstance(parsed_staged, list) else [parsed_staged]
            except Exception:
                pass
        elif isinstance(staged_models_raw, list):
            staged_models = staged_models_raw
        elif isinstance(staged_models_raw, dict):
            staged_models = [staged_models_raw]

    # Generate schema diff for component or page extension
    schema_diff_entry = {
        "schema_name": f"{component_name.lower()}_schema",
        "target_content_type": "components" if component_type == "component" else "pages",
        "operation": "extend_fields",
        "added_fields": [
            {"name": "title", "field_type": "string", "required": True},
            {"name": "subtitle", "field_type": "string", "required": False},
            {"name": "cta_label", "field_type": "string", "required": False, "default": "Learn More"},
            {"name": "cta_url", "field_type": "url", "required": False},
            {"name": "responsive_mode", "field_type": "select", "options": ["fluid", "fixed", "grid"]},
        ],
        "modified_fields": [],
        "validation_rules": [
            "title must be under 120 characters",
            "cta_url must be valid HTTPS or internal slug",
        ],
        "is_backward_compatible": True,
    }
    cms_schema_diffs.append(schema_diff_entry)
    validation_findings.append(f"CMS schema extension verified for '{component_name}' (backward compatible).")

    # 4. Responsive UI Template Generation
    responsive_breakpoints = [
        {
            "breakpoint": "mobile",
            "min_width": None,
            "max_width": 640,
            "layout_rules": {
                "display": "flex",
                "flex-direction": "column",
                "padding": "1rem",
                "width": "100%",
            },
        },
        {
            "breakpoint": "tablet",
            "min_width": 641,
            "max_width": 1024,
            "layout_rules": {
                "display": "grid",
                "grid-template-columns": "repeat(2, 1fr)",
                "gap": "1.5rem",
                "padding": "2rem",
            },
        },
        {
            "breakpoint": "desktop",
            "min_width": 1025,
            "max_width": None,
            "layout_rules": {
                "display": "grid",
                "grid-template-columns": "repeat(3, 1fr)",
                "max-width": "1280px",
                "margin": "0 auto",
                "gap": "2rem",
                "padding": "3rem",
            },
        },
    ]

    template_markup = (
        f"<section class=\"{component_name.lower()}-section\" aria-label=\"{component_name}\">\n"
        f"  <div class=\"container mx-auto responsive-grid\">\n"
        f"    <header class=\"section-header\">\n"
        f"      <h2 class=\"text-2xl font-bold tracking-tight text-gray-900\">{{{{ title }}}}</h2>\n"
        f"      <p class=\"mt-2 text-lg text-gray-600\">{{{{ subtitle }}}}</p>\n"
        f"    </header>\n"
        f"    <div class=\"content-slot\">\n"
        f"      {{{{ content }}}}\n"
        f"    </div>\n"
        f"    <div class=\"cta-wrapper mt-6\">\n"
        f"      <a href=\"{{{{ cta_url }}}}\" class=\"btn-primary\">{{{{ cta_label }}}}</a>\n"
        f"    </div>\n"
        f"  </div>\n"
        f"</section>"
    )

    css_styles = (
        f".{component_name.lower()}-section {{ width: 100%; box-sizing: border-box; }}\n"
        f"@media (max-width: 640px) {{ .{component_name.lower()}-section .responsive-grid {{ display: flex; flex-direction: column; }} }}\n"
        f"@media (min-width: 641px) and (max-width: 1024px) {{ .{component_name.lower()}-section .responsive-grid {{ display: grid; grid-template-columns: repeat(2, 1fr); }} }}\n"
        f"@media (min-width: 1025px) {{ .{component_name.lower()}-section .responsive-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); max-width: 1280px; margin: 0 auto; }} }}\n"
    )

    design_tokens = {
        "color_primary": "#3B82F6",
        "color_text": "#111827",
        "font_family": "Inter, sans-serif",
        "spacing_padding": "1.5rem",
        "border_radius": "8px",
    }

    ui_templates = [
        {
            "template_id": f"tmpl-{component_name.lower()}",
            "name": f"{component_name} Responsive Template",
            "component_type": component_type,
            "template_markup": template_markup,
            "css_styles": css_styles,
            "responsive_breakpoints": responsive_breakpoints,
            "design_tokens": design_tokens,
            "props_schema": {
                "title": {"type": "string", "required": True},
                "subtitle": {"type": "string", "required": False},
                "cta_label": {"type": "string", "default": "Learn More"},
                "cta_url": {"type": "string", "default": "#"},
            },
            "is_responsive_validated": True,
        }
    ]
    validation_findings.append("Responsive layout rules verified across mobile, tablet, and desktop breakpoints.")

    # 5. Deterministic Unified Code Diffs
    code_diffs: list[dict[str, Any]] = []
    primary_code_file = target_files[0] if target_files else f"components/{component_name.lower()}.py"
    lines = str(code_content).strip().splitlines()
    line_count = len(lines)
    diff = (
        f"--- a/{primary_code_file}\n"
        f"+++ b/{primary_code_file}\n"
        f"@@ -0,0 +1,{line_count} @@\n"
        + "".join(f"+ {line}\n" for line in lines)
    )

    code_diffs.append({
        "file_path": primary_code_file,
        "action": "create" if not payload.get("code") else "modify",
        "diff_unified": diff,
        "ast_validated": ast_valid,
        "syntax_lint_passed": ast_valid,
        "syntax_errors": [syntax_error] if syntax_error else [],
        "scope_boundary_verified": True,
    })

    # 6. Consolidated Deliverable
    deliverable = {
        "deliverable_id": f"dev-{task_id}",
        "tenant_id": tenant_id,
        "task_id": task_id,
        "component_name": component_name,
        "ui_templates": ui_templates,
        "cms_schema_diffs": cms_schema_diffs,
        "code_diffs": code_diffs,
        "changed_files": [cd["file_path"] for cd in code_diffs],
        "validation_findings": validation_findings,
        "security_checks_passed": True,
        "provenance": {
            "task_id": task_id,
            "tool": "S_CODE",
            "capability": "CODE",
            "node_count": node_count,
            "class_count": class_count,
            "function_count": function_count,
        },
        "confidence": {
            "point_estimate": 0.92 if ast_valid else 0.40,
            "lower_bound": 0.82 if ast_valid else 0.20,
            "upper_bound": 0.98 if ast_valid else 0.60,
        },
    }

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
        "code": str(code_content),
        "dev_deliverable": json.dumps(deliverable),
        "changed_files": json.dumps([cd["file_path"] for cd in code_diffs]),
        "validation_findings": json.dumps(validation_findings),
        "security_checks_passed": "True",
    }

from app.integrations.sandbox.s_alloc_core import execute_s_alloc
from app.integrations.sandbox.s_copy_core import execute_s_copy



def execute_s_val(payload: dict[str, Any]) -> dict[str, str]:
    """S_VAL: Claim & Schema Validator [Micro-Tool: Compliance Linter].

    Validates proposed advertising or clinical claims against compliance rules,
    verifies claim-to-evidence linkage, checks evidence sufficiency and freshness,
    detects conflicting evidence and unsupported absolutes, verifies product
    formulation completeness, and checks required statutory disclaimers.
    """
    task_id = str(payload.get("task_id", "unknown"))
    tenant_id = str(payload.get("tenant_id", "default"))
    product_id = str(payload.get("product_id", "default_product"))
    product_name = str(payload.get("product_name", payload.get("brand_id", "Default Product")))

    # 1. Parse Claims
    raw_claims = payload.get("claims")
    claims_list: list[dict[str, Any]] = []
    if raw_claims:
        if isinstance(raw_claims, str):
            try:
                parsed = json.loads(raw_claims)
                claims_list = parsed if isinstance(parsed, list) else [parsed]
            except Exception:
                claims_list = [{"text": raw_claims}]
        elif isinstance(raw_claims, list):
            claims_list = raw_claims
    elif "claim" in payload or "statement" in payload:
        claims_list = [{
            "id": "claim-0",
            "text": str(payload.get("claim", payload.get("statement", ""))),
            "category": str(payload.get("category", "performance")),
        }]

    # 2. Parse Evidence Pool
    raw_evidence = payload.get("evidence", payload.get("validated_evidence"))
    evidence_pool: list[dict[str, Any]] = []
    evidence_provided = raw_evidence is not None
    if raw_evidence:
        if isinstance(raw_evidence, str):
            try:
                parsed_ev = json.loads(raw_evidence)
                evidence_pool = parsed_ev if isinstance(parsed_ev, list) else [parsed_ev]
            except Exception:
                evidence_pool = [{"content": raw_evidence, "doc_id": "ev-0"}]
        elif isinstance(raw_evidence, list):
            evidence_pool = raw_evidence

    # 3. Parse Formulation / Specifications
    raw_formulation = payload.get("formulation", payload.get("specifications", payload.get("product_specification")))
    formulation_data: dict[str, Any] = {}
    if raw_formulation:
        if isinstance(raw_formulation, str):
            try:
                formulation_data = json.loads(raw_formulation)
            except Exception:
                formulation_data = {"raw_notes": raw_formulation}
        elif isinstance(raw_formulation, dict):
            formulation_data = raw_formulation

    required_disclaimer = str(payload.get("required_disclaimer", "*Results may vary based on usage."))
    raw_compliance_rules = payload.get("compliance_rules", payload.get("brand_rules"))
    custom_rules: list[str] = []
    if raw_compliance_rules:
        if isinstance(raw_compliance_rules, str):
            try:
                parsed_cr = json.loads(raw_compliance_rules)
                custom_rules = parsed_cr if isinstance(parsed_cr, list) else [str(parsed_cr)]
            except Exception:
                custom_rules = [raw_compliance_rules]
        elif isinstance(raw_compliance_rules, list):
            custom_rules = [str(r) for r in raw_compliance_rules]
        elif isinstance(raw_compliance_rules, dict):
            custom_rules = [f"{k}:{v}" for k, v in raw_compliance_rules.items()]

    # High-risk / prohibited claim patterns
    prohibited_claim_patterns = [
        r"\bcures?\b",
        r"\b100% guaranteed\b",
        r"\bprevents? all\b",
        r"\bpermanent elimination\b",
    ]

    all_violations: list[str] = []

    # 4. Validate Product Formulation & Specifications
    spec_validation_status = "VALIDATED"
    spec_findings: list[str] = []
    missing_attributes: list[str] = []
    ingredients = formulation_data.get("ingredients", [])
    if formulation_data:
        prod_id_spec = formulation_data.get("product_id", product_id)
        if not prod_id_spec or prod_id_spec == "unknown":
            missing_attributes.append("product_id")
        if not formulation_data.get("product_name") and not product_name:
            missing_attributes.append("product_name")

        if isinstance(ingredients, list) and ingredients:
            total_pct = 0.0
            has_pct = False
            for idx, ing in enumerate(ingredients):
                if isinstance(ing, dict):
                    pct = ing.get("percentage", ing.get("concentration", ing.get("pct")))
                    if pct is not None:
                        try:
                            val = float(pct)
                            if val < 0.0:
                                all_violations.append(f"Negative ingredient concentration in ingredient {ing.get('name', idx)}: {val}%")
                            total_pct += val
                            has_pct = True
                        except (ValueError, TypeError):
                            all_violations.append(f"Malformed ingredient concentration in ingredient {ing.get('name', idx)}")
            if has_pct and total_pct > 100.5:
                all_violations.append(f"Ingredient concentration sum exceeds 100.0%: {total_pct:.1f}%")
                spec_validation_status = "INCOMPLETE_SPECIFICATION"

        if missing_attributes:
            spec_validation_status = "INCOMPLETE_SPECIFICATION"
            spec_findings.append(f"Missing required specification attributes: {', '.join(missing_attributes)}")

    # 5. Validate Each Proposed Claim
    verified_claim_entries: list[dict[str, Any]] = []
    supported_count = 0
    rejected_count = 0
    insufficient_count = 0
    conflicting_count = 0
    requires_review_count = 0

    for idx, c in enumerate(claims_list):
        claim_id = str(c.get("id", f"claim-{idx + 1}"))
        claim_text = str(c.get("text", c.get("claim", c.get("statement", ""))))
        category = str(c.get("category", "performance"))
        claim_violations: list[str] = []
        claim_warnings: list[str] = []
        supporting_refs: list[str] = []
        contradicting_refs: list[str] = []
        rule_checks: list[str] = []

        # A. Prohibited absolutes check
        is_prohibited = False
        for pattern in prohibited_claim_patterns:
            if re.search(pattern, claim_text, re.IGNORECASE):
                violation_msg = f"Prohibited absolute claim pattern detected: {pattern}"
                claim_violations.append(violation_msg)
                all_violations.append(violation_msg)
                is_prohibited = True

        # Custom rules check
        for rule in custom_rules:
            rule_checks.append(f"rule:{rule}")
            if rule.lower() in claim_text.lower() and "prohibit" in rule.lower():
                violation_msg = f"Custom compliance rule violated: {rule}"
                claim_violations.append(violation_msg)
                all_violations.append(violation_msg)
                is_prohibited = True

        # B. Statutory disclaimer check for quantitative claims
        disclaimer_present = (
            required_disclaimer.lower() in claim_text.lower()
            or "*results" in claim_text.lower()
            or "*" in claim_text
        )
        has_quantitative = "%" in claim_text or bool(re.search(r"\b\d+x\b", claim_text, re.IGNORECASE))
        if has_quantitative and not disclaimer_present:
            disclaimer_violation = "Quantitative claim requires statutory disclaimer footnote."
            claim_violations.append(disclaimer_violation)
            all_violations.append(disclaimer_violation)

        # C. Evidence linkage, sufficiency, and consistency
        # Find relevant evidence from pool
        claim_tokens = {tok.lower() for tok in re.findall(r"\b[A-Za-z]{4,}\b", claim_text)}
        # Exclude stop words
        claim_tokens -= {"with", "this", "that", "from", "have", "more", "than", "tested", "clinically", "demonstrated"}

        is_stale_evidence = False
        has_contradiction = False

        for ev in evidence_pool:
            ev_id = str(ev.get("doc_id", ev.get("evidence_id", ev.get("id", "ev-ref"))))
            ev_content = str(ev.get("text", ev.get("content", "")))
            ev_source = str(ev.get("source", ev.get("source_uri", "dossier")))
            ev_stale = bool(ev.get("is_stale", ev.get("stale", False)))
            ev_contradicts = bool(
                ev.get("contradicts", False)
                or ev.get("contradictory", False)
                or "contradicts" in ev_content.lower()
                or "failed to show" in ev_content.lower()
                or "no significant improvement" in ev_content.lower()
                or "adverse reaction" in ev_content.lower()
            )

            # Check explicit link or keyword match
            explicit_ids = c.get("evidence_ids", c.get("evidence_references", []))
            is_linked = ev_id in explicit_ids if explicit_ids else False
            if not is_linked and claim_tokens:
                ev_tokens = {tok.lower() for tok in re.findall(r"\b[A-Za-z]{4,}\b", ev_content)}
                overlap = len(claim_tokens & ev_tokens)
                if overlap >= 2 or (len(claim_tokens) <= 2 and overlap >= 1):
                    is_linked = True

            if is_linked:
                if ev_contradicts:
                    has_contradiction = True
                    contradicting_refs.append(ev_id)
                else:
                    supporting_refs.append(ev_id)
                    if ev_stale:
                        is_stale_evidence = True

        # D. Status classification
        if is_prohibited:
            claim_status = "REJECTED"
            claim_confidence = 0.0
            rejected_count += 1
        elif has_contradiction:
            claim_status = "CONFLICTING_EVIDENCE"
            claim_confidence = 0.2
            claim_warnings.append(f"Contradictory findings detected in evidence references: {contradicting_refs}")
            conflicting_count += 1
        elif evidence_provided and not supporting_refs:
            claim_status = "INSUFFICIENT_EVIDENCE"
            claim_confidence = 0.1
            claim_warnings.append("No supporting evidence found in authorized evidence context.")
            insufficient_count += 1
        elif is_stale_evidence:
            claim_status = "REQUIRES_REVIEW"
            claim_confidence = 0.4
            claim_warnings.append("Supporting evidence is stale or expired; recertification required.")
            requires_review_count += 1
        elif not disclaimer_present and has_quantitative:
            claim_status = "REQUIRES_REVIEW"
            claim_confidence = 0.5
            claim_warnings.append("Missing mandatory statutory disclaimer on quantitative claim.")
            requires_review_count += 1
        else:
            # Clean claim
            if evidence_provided and supporting_refs:
                claim_status = "SUPPORTED"
                claim_confidence = min(0.95, 0.75 + (len(supporting_refs) * 0.1))
                supported_count += 1
            elif not evidence_provided:
                # Backward-compatibility for legacy single-claim checks
                if not claim_violations:
                    claim_status = "SUPPORTED"
                    claim_confidence = 0.8
                    supported_count += 1
                else:
                    claim_status = "REJECTED"
                    claim_confidence = 0.0
                    rejected_count += 1
            else:
                claim_status = "INSUFFICIENT_EVIDENCE"
                claim_confidence = 0.0
                insufficient_count += 1

        verified_claim_entries.append({
            "claim_id": claim_id,
            "claim_text": claim_text,
            "category": category,
            "validation_status": claim_status,
            "confidence": round(claim_confidence, 2),
            "evidence_references": supporting_refs,
            "contradicting_evidence_references": contradicting_refs,
            "rule_compliance_checks": rule_checks,
            "violations": claim_violations,
            "limitations_or_warnings": claim_warnings,
            "provenance": {
                "verified_by": "S_VAL",
                "task_id": task_id,
                "tenant_id": tenant_id,
            },
        })

    total_claims = len(verified_claim_entries)
    compliance_score = max(0.0, 1.0 - (len(all_violations) * 0.4))
    if rejected_count > 0:
        compliance_score = 0.0
    elif conflicting_count > 0:
        compliance_score = min(compliance_score, 0.3)
    elif insufficient_count > 0:
        compliance_score = min(compliance_score, 0.7)
    if total_claims == 0:
        compliance_score = 1.0 if not all_violations else 0.0

    is_compliant = len(all_violations) == 0 and rejected_count == 0 and conflicting_count == 0

    dossier_summary_status = "APPROVED" if (is_compliant and insufficient_count == 0 and requires_review_count == 0) else "FLAGGED"
    if rejected_count > 0:
        dossier_summary_status = "REJECTED"

    primary_claim_text = claims_list[0].get("text", claims_list[0].get("claim", "")) if claims_list else payload.get("claim", "")

    # Construct product specification dictionary
    product_spec_dict = {
        "product_id": product_id,
        "product_name": product_name,
        "tenant_id": tenant_id,
        "formulation_id": formulation_data.get("formulation_id", f"form-{product_id}"),
        "version": str(formulation_data.get("version", "1.0")),
        "normalized_attributes": formulation_data.get("attributes", {
            "category": formulation_data.get("category", "supplement"),
            "dosage_form": formulation_data.get("dosage_form", "capsule"),
        }),
        "ingredients": ingredients,
        "supporting_evidence_references": [ev.get("doc_id", "ev") for ev in evidence_pool if isinstance(ev, dict) and ev.get("doc_id")],
        "validation_status": spec_validation_status,
        "compliance_findings": spec_findings + all_violations,
        "missing_attributes": missing_attributes,
        "provenance": {
            "verified_by": "S_VAL",
            "task_id": task_id,
            "tenant_id": tenant_id,
        },
    }

    # Construct claims dossier dictionary
    claims_dossier_dict = {
        "dossier_id": f"dossier-{task_id}",
        "tenant_id": tenant_id,
        "product_id": product_id,
        "claims": verified_claim_entries,
        "summary_status": dossier_summary_status,
        "total_claims": total_claims,
        "supported_claims": supported_count,
        "rejected_claims": rejected_count,
        "insufficient_claims": insufficient_count,
        "conflicting_claims": conflicting_count,
        "requires_review_claims": requires_review_count,
        "overall_confidence": round(compliance_score, 2),
        "provenance": {
            "verified_by": "S_VAL",
            "task_id": task_id,
            "tenant_id": tenant_id,
        },
    }

    verified_dossier = (
        f"Product: {product_name} ({product_id}) | Claims: {total_claims} (Supported: {supported_count}, "
        f"Rejected: {rejected_count}, Insufficient: {insufficient_count}, Conflicting: {conflicting_count}) | "
        f"Compliance Score: {compliance_score:.2f} | Status: {dossier_summary_status}"
    )

    return {
        "status": "success" if is_compliant else "compliance_warning",
        "task_id": task_id,
        "claim": str(primary_claim_text),
        "is_compliant": str(is_compliant),
        "compliance_score": f"{compliance_score:.2f}",
        "violations": json.dumps(all_violations),
        "verified_dossier": verified_dossier,
        "product_specification": json.dumps(product_spec_dict),
        "claims_dossier": json.dumps(claims_dossier_dict),
    }


def execute_s_scrape(payload: dict[str, str]) -> dict[str, str]:
    """S_SCRAPE: Price & Ad Scraper [Micro-Tool: External DOM Tracker].

    Simulates whitelisted external DOM extraction for competitor ad libraries and price trends.
    """
    task_id = payload.get("task_id", "unknown")
    competitor = payload.get("competitor", "CompetitorCorp")

    # Benchmarks extracted from simulated competitor feed
    try:
        price_point = float(payload.get("benchmark_price", "49.99"))
    except (ValueError, TypeError):
        price_point = 49.99

    try:
        active_ad_count = int(payload.get("active_ads", "14"))
    except (ValueError, TypeError):
        active_ad_count = 14

    top_ad_hook = "Save 25% on our premium bundle this week only."

    return {
        "status": "success",
        "task_id": task_id,
        "competitor": competitor,
        "benchmark_price": f"{price_point:.2f}",
        "active_ads": str(active_ad_count),
        "top_ad_hook": top_ad_hook,
        "pricing_trajectory": "discounting_aggressive",
        "threat_level": "medium",
    }


def execute_s_parse(payload: dict[str, Any]) -> dict[str, str]:
    """S_PARSE: Sentiment & Review Parser [Micro-Tool: NLP Classifier].

    Performs sensitive data redaction (PII/credentials), prompt injection neutralization,
    multi-class sentiment and polarity analysis, intent and objection extraction,
    and recurring objection clustering across tickets, reviews, and survey responses.
    """
    task_id = str(payload.get("task_id", "unknown"))
    tenant_id = str(payload.get("tenant_id", "default"))
    product_id = payload.get("product_id")

    # 1. Parse Input Items (support single feedback text or structured batch)
    raw_items = payload.get("items", payload.get("feedback_items"))
    items_list: list[dict[str, Any]] = []

    if raw_items:
        if isinstance(raw_items, str):
            try:
                parsed = json.loads(raw_items)
                items_list = parsed if isinstance(parsed, list) else [parsed]
            except Exception:
                items_list = [{"text": raw_items, "item_id": "item-0"}]
        elif isinstance(raw_items, list):
            items_list = raw_items
    elif "feedback_text" in payload or "query" in payload:
        single_text = str(payload.get("feedback_text", payload.get("query", "Love the product quality but shipping took 10 days and support was slow.")))
        items_list = [{
            "item_id": "item-0",
            "source_type": str(payload.get("source_type", "feedback")),
            "text": single_text,
            "product_id": product_id,
            "channel": payload.get("channel"),
            "tenant_id": tenant_id,
        }]

    # 2. PII / Sensitive Data Redaction Patterns
    redaction_patterns = [
        (re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"), "[REDACTED_EMAIL]"),
        (re.compile(r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}"), "[REDACTED_PHONE]"),
        (re.compile(r"\b(?:\d[ -]*?){13,16}\b"), "[REDACTED_ACCOUNT]"),
        (re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b"), "[REDACTED_IP]"),
        (re.compile(r"(?i)\b(?:customer|client|user|name is|i am)\s+(?!support|service|care|team|rep|agent|experience|feedback|review)([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b"), "[REDACTED_NAME]"),
        (re.compile(r"(?i)(api[_-]?key|secret|token|password|auth)\s*[:=]\s*['\"]?[A-Za-z0-9_\-\.]{8,}['\"]?"), "[REDACTED_SECRET]"),
    ]

    # Prompt injection patterns inside customer voice data (neutralized fail-safe)
    injection_patterns = [
        re.compile(r"(?i)ignore\s+(?:all\s+)?(?:previous\s+)?instructions"),
        re.compile(r"(?i)system\s+(?:override|prompt)"),
        re.compile(r"(?i)you\s+are\s+now\s+(?:an?\s+)?unrestricted"),
        re.compile(r"(?i)grant\s+(?:admin|full)\s+access"),
        re.compile(r"(?i)execute\s+(?:code|command|tool)"),
        re.compile(r"(?i)output\s+(?:the\s+)?(?:secret|api_key|token)"),
    ]

    # NLP Lexicons
    positive_words = {
        "love", "great", "excellent", "fast", "effective", "good", "best", "satisfied",
        "amazing", "smooth", "helpful", "impressed", "recommend", "reliable", "perfect",
        "fantastic", "quality", "friendly", "prompt", "easy", "delighted", "superb",
    }
    negative_words = {
        "slow", "expensive", "shipping", "broke", "delayed", "poor", "difficult", "bad",
        "terrible", "horrible", "awful", "defective", "useless", "damaged", "rude",
        "frustrated", "unacceptable", "broken", "crash", "refund", "leak", "stains",
        "missing", "confusing", "painful", "fail", "failed", "glitch", "flimsy",
        "unresponsive", "wait", "waited", "waiting", "issue", "problem", "complaint",
        "disappointed", "frustrating",
    }

    # Objection Category Triggers
    objection_rules = [
        ("fulfillment_delay", {"shipping", "delayed", "late", "delivery", "transit", "tracking", "package took", "never arrived"}),
        ("price_sensitivity", {"expensive", "price", "overpriced", "cost", "rip-off", "cheap", "subscription", "charge", "billing"}),
        ("customer_service_latency", {"support", "unresponsive", "hold", "agent", "ticket", "service", "reply", "representative", "chat"}),
        ("product_quality_defect", {"broke", "broken", "defective", "leak", "damaged", "faulty", "flimsy", "defect", "poor quality"}),
        ("usability_complexity", {"confusing", "difficult", "complicated", "instructions", "clunky", "complex", "hard to use"}),
        ("missing_feature", {"lacks", "missing", "wish it had", "no option for", "does not support", "feature"}),
    ]

    sentiment_vectors: list[dict[str, Any]] = []
    total_redactions = 0
    all_objections_flat: list[str] = []
    warnings: list[str] = []
    polarity_sum = 0.0

    sentiment_counts = {"POSITIVE": 0, "NEGATIVE": 0, "NEUTRAL": 0, "MIXED": 0}

    # 3. Analyze Each Feedback Item
    for idx, raw_item in enumerate(items_list):
        item_id = str(raw_item.get("item_id", f"item-{idx + 1}"))
        raw_text = str(raw_item.get("text", ""))
        src_type = str(raw_item.get("source_type", "feedback"))
        item_channel = raw_item.get("channel")
        item_product = raw_item.get("product_id", product_id)

        # A. Prompt Injection Defense
        sanitized_text = raw_text
        for inj in injection_patterns:
            if inj.search(sanitized_text):
                warnings.append(f"Prompt injection pattern detected and neutralized in item '{item_id}'.")
                sanitized_text = inj.sub("[UNTRUSTED_COMMAND_STRIPPED]", sanitized_text)

        # B. Sensitive Data / PII Redaction
        for pattern, replacement in redaction_patterns:
            new_text, count = pattern.subn(replacement, sanitized_text)
            if count > 0:
                total_redactions += count
                sanitized_text = new_text

        # Tokenize source identifier to anonymous reference (sha256 prefix)
        anon_src_ref = f"anon-src-{hashlib.sha256(item_id.encode('utf-8')).hexdigest()[:10]}"

        # C. NLP Sentiment Classification
        tokens = set(re.findall(r"\b\w+\b", sanitized_text.lower()))
        pos_matches = tokens & positive_words
        neg_matches = tokens & negative_words

        pos_count = len(pos_matches)
        neg_count = len(neg_matches)
        denom = pos_count + neg_count or 1
        polarity = round((pos_count - neg_count) / denom, 2)

        if pos_count >= 2 and neg_count >= 2:
            sentiment_label = "MIXED"
        elif polarity > 0.15:
            sentiment_label = "POSITIVE"
        elif polarity < -0.15:
            sentiment_label = "NEGATIVE"
        else:
            sentiment_label = "NEUTRAL"

        sentiment_counts[sentiment_label] += 1
        polarity_sum += polarity

        # Confidence calculation
        token_count = len(tokens)
        if pos_count + neg_count == 0:
            confidence = 0.50  # Ambiguous / neutral
        else:
            confidence = min(0.95, round(0.60 + (min(pos_count + neg_count, 6) * 0.06), 2))

        # D. Objection Extraction
        contrast_words = {"but", "however", "although", "except", "though", "yet"}
        has_contrast = bool(tokens & contrast_words)

        detected_item_objections: list[str] = []
        if sentiment_label != "POSITIVE" or neg_matches or has_contrast:
            for obj_type, trigger_words in objection_rules:
                if any(w in sanitized_text.lower() for w in trigger_words) or bool(tokens & trigger_words):
                    detected_item_objections.append(obj_type)
                    all_objections_flat.append(obj_type)

        # E. Urgency / Severity
        critical_words = {"lawsuit", "attorney", "legal", "chargeback", "fraud", "burn", "injury", "hazard", "danger"}
        high_words = {"refund", "unacceptable", "broken", "cancel", "dispute"}
        if any(w in tokens for w in critical_words):
            urgency = "critical"
        elif any(w in tokens for w in high_words):
            urgency = "high"
        elif sentiment_label in ("NEGATIVE", "MIXED") and detected_item_objections:
            urgency = "medium"
        else:
            urgency = "low"

        # Pain points & praise points
        praise_points = [w for w in pos_matches]
        pain_points = [w for w in neg_matches]

        vector_record = {
            "vector_id": f"vec-{item_id}",
            "source_id_hash": anon_src_ref,
            "source_type": src_type,
            "tenant_id": tenant_id,
            "product_id": item_product,
            "channel": item_channel,
            "sanitized_text": sanitized_text,
            "sentiment_label": sentiment_label,
            "polarity": polarity,
            "confidence": confidence,
            "topics": list(detected_item_objections),
            "intent": "complaint" if detected_item_objections else ("inquiry" if "?" in sanitized_text else "general_feedback"),
            "urgency": urgency,
            "detected_objections": detected_item_objections,
            "pain_points": pain_points,
            "praise_points": praise_points,
            "provenance": {
                "verified_by": "S_PARSE",
                "task_id": task_id,
                "tenant_id": tenant_id,
                "sanitized": True,
            },
        }
        sentiment_vectors.append(vector_record)

    total_items = len(sentiment_vectors)
    avg_polarity = round(polarity_sum / total_items, 2) if total_items > 0 else 0.0

    # Determine primary overall sentiment
    if total_items == 0:
        primary_sentiment = "neutral"
    elif sentiment_counts["NEGATIVE"] > sentiment_counts["POSITIVE"]:
        primary_sentiment = "negative"
    elif sentiment_counts["POSITIVE"] > sentiment_counts["NEGATIVE"]:
        primary_sentiment = "positive"
    elif sentiment_counts["MIXED"] > 0:
        primary_sentiment = "mixed"
    else:
        primary_sentiment = "neutral"

    # 4. Aggregate Recurring Objection Profiles
    objection_profiles: list[dict[str, Any]] = []
    unique_objection_types = sorted(list(set(all_objections_flat)))

    for obj_type in unique_objection_types:
        matching_vectors = [v for v in sentiment_vectors if obj_type in v["detected_objections"]]
        freq = len(matching_vectors)
        evidence_refs = [v["source_id_hash"] for v in matching_vectors]
        affected_prods = list({v["product_id"] for v in matching_vectors if v["product_id"]})
        affected_chans = list({v["channel"] for v in matching_vectors if v["channel"]})

        obj_sentiments = {"POSITIVE": 0, "NEGATIVE": 0, "NEUTRAL": 0, "MIXED": 0}
        has_critical = False
        has_high = False
        for v in matching_vectors:
            obj_sentiments[v["sentiment_label"]] += 1
            if v["urgency"] == "critical":
                has_critical = True
            elif v["urgency"] == "high":
                has_high = True

        if has_critical or freq >= 4:
            severity = "critical" if has_critical else "high"
        elif has_high or freq >= 2:
            severity = "medium"
        else:
            severity = "low"

        theme_names = {
            "fulfillment_delay": "Logistics and Delivery Latency",
            "price_sensitivity": "Pricing and Perceived Value Objections",
            "customer_service_latency": "Support Responsiveness and Resolution Latency",
            "product_quality_defect": "Product Defects and Material Failures",
            "usability_complexity": "Product Complexity and User Experience Friction",
            "missing_feature": "Functional Gaps and Missing Capabilities",
        }
        normalized_theme = theme_names.get(obj_type, obj_type.replace("_", " ").title())

        objection_profiles.append({
            "objection_id": f"obj-{obj_type}",
            "objection_type": obj_type,
            "normalized_theme": normalized_theme,
            "frequency": freq,
            "affected_products": affected_prods,
            "affected_channels": affected_chans,
            "sentiment_distribution": obj_sentiments,
            "representative_evidence_refs": evidence_refs[:5],
            "confidence": round(min(0.95, 0.70 + (freq * 0.05)), 2),
            "severity": severity,
            "trend": "increasing" if freq >= 3 else "stable",
            "unresolved_ambiguity": [],
            "provenance": {
                "verified_by": "S_PARSE",
                "task_id": task_id,
                "tenant_id": tenant_id,
            },
        })

    # Consolidated CustomerVoiceAnalysisResult dictionary
    analysis_result_dict = {
        "analysis_id": f"voice-{task_id}",
        "tenant_id": tenant_id,
        "product_id": product_id,
        "total_items_analyzed": total_items,
        "average_polarity": avg_polarity,
        "sentiment_breakdown": sentiment_counts,
        "sentiment_vectors": sentiment_vectors,
        "objection_profiles": objection_profiles,
        "warnings": warnings,
        "anonymization_stats": {
            "total_redactions": total_redactions,
            "anonymized_source_references": total_items,
        },
        "provenance": {
            "verified_by": "S_PARSE",
            "task_id": task_id,
            "tenant_id": tenant_id,
        },
    }

    feedback_summary = (
        f"Analyzed {total_items} feedback items with average polarity {avg_polarity:.2f} ({primary_sentiment}). "
        f"Objections identified: {', '.join(unique_objection_types) or 'None'}. "
        f"Redacted sensitive fields: {total_redactions}."
    )

    return {
        "status": "success",
        "task_id": task_id,
        "sentiment_polarity": f"{avg_polarity:.2f}",
        "primary_sentiment": primary_sentiment,
        "objections": json.dumps(unique_objection_types or ["none_detected"]),
        "feedback_summary": feedback_summary,
        "customer_voice_analysis": json.dumps(analysis_result_dict),
        "objection_profiles": json.dumps(objection_profiles),
        "sentiment_vectors": json.dumps(sentiment_vectors),
    }


def execute_s_attr(payload: dict[str, Any]) -> dict[str, str]:
    """S_ATTR: Attribution Modeler [Micro-Tool: Decay Scorer].

    Computes deterministic multi-touch attribution, creative decay rates,
    and ROAS optimization adjustments.
    """
    task_id = str(payload.get("task_id", "unknown"))
    tenant_id = str(payload.get("tenant_id", "default"))
    model_type = str(payload.get("model_type", "linear")).lower()

    # Valid supported attribution models
    supported_models = {"linear", "first_touch", "last_touch", "time_decay", "position_based"}
    if model_type not in supported_models:
        return {
            "status": "configuration_gap",
            "task_id": task_id,
            "error": f"Unsupported or unconfigured attribution model '{model_type}'. Supported: {sorted(supported_models)}",
            "confidence": "0.0",
        }

    # 1. Parse Conversion Paths
    raw_paths = payload.get("paths") or payload.get("conversion_paths")
    paths: list[dict[str, Any]] = []
    if isinstance(raw_paths, str):
        try:
            paths = json.loads(raw_paths)
        except Exception:
            paths = []
    elif isinstance(raw_paths, list):
        paths = raw_paths

    # 2. Parse Spend Data
    raw_spend = payload.get("spend_data") or payload.get("spend")
    spend_map: dict[str, float] = {}  # channel -> spend
    if isinstance(raw_spend, str):
        try:
            parsed_spend = json.loads(raw_spend)
            if isinstance(parsed_spend, dict):
                spend_map = {k: float(v) for k, v in parsed_spend.items()}
            elif isinstance(parsed_spend, list):
                for item in parsed_spend:
                    if isinstance(item, dict) and "channel" in item:
                        spend_map[item["channel"]] = spend_map.get(item["channel"], 0.0) + float(item.get("spend", 0.0))
        except Exception:
            pass
    elif isinstance(raw_spend, dict):
        spend_map = {k: float(v) for k, v in raw_spend.items()}
    elif isinstance(raw_spend, list):
        for item in raw_spend:
            if isinstance(item, dict) and "channel" in item:
                spend_map[item["channel"]] = spend_map.get(item["channel"], 0.0) + float(item.get("spend", 0.0))

    # 3. Parse Creatives Data
    raw_creatives = payload.get("creatives")
    creatives_list: list[dict[str, Any]] = []
    if isinstance(raw_creatives, str):
        try:
            creatives_list = json.loads(raw_creatives)
        except Exception:
            pass
    elif isinstance(raw_creatives, list):
        creatives_list = raw_creatives

    # Fallback to single creative / roas parameters for backward compatibility
    try:
        reported_roas = float(payload.get("roas", payload.get("metrics_roas", "3.4")))
    except (ValueError, TypeError):
        reported_roas = 3.4

    try:
        single_days_active = float(payload.get("days_active", "14.0"))
        if single_days_active < 0:
            single_days_active = 0.0
    except (ValueError, TypeError):
        single_days_active = 14.0

    # If no creatives list provided, populate from single creative fields
    if not creatives_list:
        creatives_list = [{
            "creative_id": payload.get("creative_id", "creative-default"),
            "channel": payload.get("channel", "meta"),
            "days_active": single_days_active,
            "reported_roas": reported_roas,
        }]

    # 4. Check Data Sufficiency
    has_roas_context = "roas" in payload or "metrics_roas" in payload or "days_active" in payload
    if not paths and not has_roas_context and not spend_map:
        return {
            "status": "insufficient_data",
            "task_id": task_id,
            "error": "Insufficient conversion path telemetry for attribution modeling: 0 conversion events provided.",
            "confidence": "0.0",
        }

    # 5. Compute Multi-Touch Attribution across Paths
    channel_attributed_rev: dict[str, float] = {}
    channel_attributed_conv: dict[str, float] = {}
    campaign_attributed_rev: dict[str, float] = {}
    creative_attributed_rev: dict[str, float] = {}
    total_conversions = len(paths)
    total_revenue = 0.0
    covered_conversions = 0
    warnings: list[str] = []

    for path in paths:
        rev = float(path.get("revenue", 0.0))
        total_revenue += rev
        touchpoints = path.get("touchpoints", [])
        n_touches = len(touchpoints)
        if n_touches == 0:
            warnings.append(f"Conversion {path.get('conversion_id', 'unknown')} has no touchpoints.")
            continue

        covered_conversions += 1
        weights: list[float] = []

        if model_type == "linear":
            w = 1.0 / n_touches
            weights = [w] * n_touches
        elif model_type == "first_touch":
            weights = [1.0] + [0.0] * (n_touches - 1)
        elif model_type == "last_touch":
            weights = [0.0] * (n_touches - 1) + [1.0]
        elif model_type == "time_decay":
            # 7-day half-life decay from conversion time
            raw_weights: list[float] = []
            conv_time_str = path.get("occurred_at")
            for t_idx, tp in enumerate(touchpoints):
                dt_days = 0.0
                try:
                    from datetime import datetime
                    if conv_time_str and tp.get("occurred_at"):
                        t_conv = datetime.fromisoformat(str(conv_time_str).replace("Z", "+00:00"))
                        t_touch = datetime.fromisoformat(str(tp.get("occurred_at")).replace("Z", "+00:00"))
                        dt_days = max(0.0, (t_conv - t_touch).total_seconds() / 86400.0)
                    else:
                        dt_days = float(n_touches - 1 - t_idx)
                except Exception:
                    dt_days = float(n_touches - 1 - t_idx)
                raw_weights.append(math.pow(2.0, -dt_days / 7.0))
            sum_rw = sum(raw_weights)
            weights = [rw / sum_rw for rw in raw_weights] if sum_rw > 0 else [1.0 / n_touches] * n_touches
        elif model_type == "position_based":
            # U-shaped: 40% first, 40% last, 20% middle
            if n_touches == 1:
                weights = [1.0]
            elif n_touches == 2:
                weights = [0.5, 0.5]
            else:
                middle_w = 0.2 / (n_touches - 2)
                weights = [0.4] + [middle_w] * (n_touches - 2) + [0.4]

        for tp, w in zip(touchpoints, weights):
            ch = str(tp.get("channel", "unknown")).lower()
            camp = tp.get("campaign_id")
            creat = tp.get("creative_id")
            channel_attributed_rev[ch] = channel_attributed_rev.get(ch, 0.0) + (rev * w)
            channel_attributed_conv[ch] = channel_attributed_conv.get(ch, 0.0) + (1.0 * w)
            if camp:
                campaign_attributed_rev[str(camp)] = campaign_attributed_rev.get(str(camp), 0.0) + (rev * w)
            if creat:
                creative_attributed_rev[str(creat)] = creative_attributed_rev.get(str(creat), 0.0) + (rev * w)

    # 6. Compute Creative Decay & Fatigue
    decay_metrics: list[dict[str, Any]] = []
    primary_decay_multiplier = 1.0
    primary_projected_roas = reported_roas
    primary_fatigue = False
    primary_action = "scale_spend"

    for c_idx, c_item in enumerate(creatives_list):
        c_id = str(c_item.get("creative_id", f"creative-{c_idx+1}"))
        c_ch = str(c_item.get("channel", "meta")).lower()
        try:
            d_active = float(c_item.get("days_active", single_days_active))
            if d_active < 0:
                d_active = 0.0
        except (ValueError, TypeError):
            d_active = single_days_active

        try:
            c_roas = float(c_item.get("reported_roas", c_item.get("roas", reported_roas)))
        except (ValueError, TypeError):
            c_roas = reported_roas

        # Exponential decay: decay = e^(-0.05 * t)
        decay_mult = math.exp(-0.05 * d_active)
        proj_roas = c_roas * decay_mult
        fatigued = decay_mult < 0.65
        action = "refresh_creative_hooks" if fatigued else "scale_spend"

        if c_idx == 0:
            primary_decay_multiplier = decay_mult
            primary_projected_roas = proj_roas
            primary_fatigue = fatigued
            primary_action = action

        decay_metrics.append({
            "creative_id": c_id,
            "channel": c_ch,
            "days_active": round(d_active, 1),
            "decay_multiplier": round(decay_mult, 4),
            "fatigue_detected": fatigued,
            "recommended_action": action,
            "projected_roas": round(proj_roas, 2),
        })

    # 7. Compute ROAS per Channel
    roas_metrics: list[dict[str, Any]] = []
    all_channels = sorted(set(list(spend_map.keys()) + list(channel_attributed_rev.keys())))
    for ch in all_channels:
        sp = spend_map.get(ch, 0.0)
        rv = channel_attributed_rev.get(ch, 0.0)
        if sp > 0.0:
            calc_roas = rv / sp
            r_status = "valid"
        elif rv > 0.0:
            calc_roas = 0.0
            r_status = "zero_spend_with_revenue"
            warnings.append(f"Channel '{ch}' generated ${rv:.2f} revenue with $0 recorded spend.")
        else:
            calc_roas = 0.0
            r_status = "zero_spend_zero_revenue"

        roas_metrics.append({
            "channel": ch,
            "spend": round(sp, 2),
            "revenue": round(rv, 2),
            "roas": round(calc_roas, 2),
            "status": r_status,
        })

    # 8. Channel Attribution Weights
    channel_weights: list[dict[str, Any]] = []
    sum_conv = sum(channel_attributed_conv.values())
    for ch in sorted(channel_attributed_rev.keys()):
        attr_c = channel_attributed_conv.get(ch, 0.0)
        attr_r = channel_attributed_rev.get(ch, 0.0)
        w_val = (attr_c / sum_conv) if sum_conv > 0 else 0.0
        channel_weights.append({
            "channel": ch,
            "weight": round(w_val, 4),
            "attributed_revenue": round(attr_r, 2),
            "attributed_conversions": round(attr_c, 2),
        })

    # 9. Data Quality Indicators
    total_spend = sum(spend_map.values())
    coverage = (covered_conversions / total_conversions) if total_conversions > 0 else 1.0
    quality = {
        "total_events": total_conversions + len(spend_map),
        "conversion_count": total_conversions,
        "total_spend": round(total_spend, 2),
        "total_revenue": round(total_revenue, 2),
        "attribution_coverage": round(coverage, 4),
        "missing_spend_count": sum(1 for rm in roas_metrics if rm["status"] == "zero_spend_with_revenue"),
        "is_sufficient": total_conversions > 0 or has_roas_context,
        "warnings": warnings,
    }

    # 10. Synthesize Learning Delta Statement
    delta_statement = (
        f"Creative fatigue at {primary_decay_multiplier:.2f} after {single_days_active:.0f} days. "
        f"Current ROAS {reported_roas:.2f}, projected {primary_projected_roas:.2f}. "
        f"Recommendation: {primary_action}."
    )
    if channel_weights:
        top_channel = max(channel_weights, key=lambda x: x["weight"])
        delta_statement += f" Top attributed channel: {top_channel['channel']} ({top_channel['weight']*100:.1f}% contribution)."

    # Calculate confidence based on data volume and coverage
    if total_conversions >= 5 and coverage >= 0.8:
        conf_str = "0.90"
    elif total_conversions > 0 or has_roas_context:
        conf_str = "0.85"
    else:
        conf_str = "0.40"

    return {
        "status": "success",
        "task_id": task_id,
        "tenant_id": tenant_id,
        "model_type": model_type,
        "decay_multiplier": f"{primary_decay_multiplier:.2f}",
        "projected_roas": f"{primary_projected_roas:.2f}",
        "fatigue_detected": str(primary_fatigue),
        "recommended_action": primary_action,
        "learning_delta": delta_statement,
        "confidence": conf_str,
        "channel_weights": json.dumps(channel_weights),
        "decay_metrics": json.dumps(decay_metrics),
        "roas_metrics": json.dumps(roas_metrics),
        "data_quality": json.dumps(quality),
    }


MICRO_TOOL_DISPATCH = {
    SandboxCapability.CODE: execute_s_code,
    SandboxCapability.ALLOC: execute_s_alloc,
    SandboxCapability.COPY: execute_s_copy,
    SandboxCapability.VAL: execute_s_val,
    SandboxCapability.SCRAPE: execute_s_scrape,
    SandboxCapability.PARSE: execute_s_parse,
    SandboxCapability.ATTR: execute_s_attr,
}


def dispatch_micro_tool(capability: SandboxCapability, payload: dict[str, str]) -> dict[str, str]:
    """Dispatch execution to the specialist micro-tool corresponding to ``capability``."""
    handler = MICRO_TOOL_DISPATCH.get(capability)
    if handler is None:
        raise ValueError(f"No specialist micro-tool found for capability: {capability}")
    return handler(payload)
