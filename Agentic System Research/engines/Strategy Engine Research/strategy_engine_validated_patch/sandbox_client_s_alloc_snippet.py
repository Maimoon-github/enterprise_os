# Proposed S_ALLOC branch inside SandboxClient._execute_specialist.
# Exact SDK method names should remain consistent with the repository's pinned agent-sandbox SDK.

elif mandate.capability == SandboxCapability.ALLOC:
    if not (
        hasattr(remote_client, "file")
        and hasattr(remote_client.file, "write_file")
        and hasattr(remote_client, "shell")
        and hasattr(remote_client.shell, "exec_command")
    ):
        raise SandboxInvocationError(
            "Configured AIO sandbox does not expose required file/shell interfaces for S_ALLOC."
        )

    input_path = f"/workspace/{mandate.execution_id}.json"
    output_path = f"/workspace/{mandate.execution_id}.out.json"
    remote_client.file.write_file(
        file=input_path,
        content=json.dumps(mandate.payload, ensure_ascii=False),
    )
    command = (
        "python /home/gem/skills/s-alloc/scripts/run.py "
        f"< {input_path} > {output_path}"
    )
    response = remote_client.shell.exec_command(command=command)
    exit_code = getattr(response, "exit_code", 0)
    if exit_code not in (0, None):
        raise SandboxInvocationError(
            f"S_ALLOC remote execution failed with exit code {exit_code}."
        )
    output = remote_client.file.read_file(file=output_path)
    content = getattr(getattr(output, "data", output), "content", "")
    parsed = json.loads(content)
    if not isinstance(parsed, dict):
        raise SandboxInvocationError("S_ALLOC returned a non-object payload.")
    return parsed

# IMPORTANT:
# - Do not interpolate user-controlled payload values into the shell command.
# - Input/output filenames derive only from generated execution_id.
# - If a remote sandbox is configured, exceptions should propagate/fail closed.
# - Local dispatch_micro_tool fallback remains only for no-endpoint test/development mode.
