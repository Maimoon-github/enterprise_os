---
name: s-alloc
description: Execute deterministic media allocation, observational funnel estimation, and budget-preserving roadmap calculations inside the Enterprise OS S_ALLOC sandbox capability.
---

# S_ALLOC execution contract

This is a container micro-tool manifest, not a ChatGPT personal skill.

- Permit caller `W_STRAT` with an IE/PAB-authorized grant and capability `S_ALLOC`.
- Execute only `/opt/skills/s-alloc/scripts/run.py` with the image's pinned Python
  interpreter. Pass one `SandboxMandate` JSON object over stdin. Do not accept
  commands, user code, shell fragments, import paths, URLs or output paths.
- Use an immutable image pinned by SHA-256 with the shared strategy schema and
  Pydantic 2.13.5. Include no database, RAG, CMS, SDK or provider credentials.
- Launch a fresh Kata or Firecracker micro-VM. Apply `DENY_ALL`, an isolated
  network namespace, seccomp, no-new-privileges, all capabilities dropped,
  non-root execution, read-only root, no host mounts, private tmpfs scratch,
  256 MiB RAM, 32 PIDs, bounded CPU and the mandate timeout before starting.
- Disable swap, cross-run caches, core dumps and shared memory with peer tasks.
- Allow at most 512 KiB input and 256 KiB complete returned result. Intercept
  exit status, bounded stderr, syscall/security events and resource telemetry
  in the trusted controller. Persist traces through the existing audit owner.
- Enforce `(execution_id, mandate_hash)` idempotency in the controller. Return
  the original signed output/attestation on replay; reject changed bytes.
- Destroy the VM and its tmpfs before signing the execution attestation; confirm
  fresh-instance identity, teardown, network, filesystem, seccomp and RAM policy.
- Cryptographically sign output hash, mandate hash, policy hash, pinned image
  digest, instance ID, execution ID and trace hash with the controller key.
  No inside-container self-report is a security attestation.

The solver fits nonnegative saturation coefficients to supplied same-duration
observations, enumerates feasible budget grid points, applies ROAS/CPA
constraints, returns a Pareto subset, and bootstraps conditional uncertainty.
`search_limit` and `infeasible` return no spend plan. All successful plans remain
proposals requiring IE/HITL approval. Textual brand rules are preserved for human
review; machine-enforceable limits must arrive as `narrowed_spend` from IE.

The manifest declares requirements; the existing sandbox controller must enforce
them. The Python script and ordinary Docker containers alone do not establish a
micro-VM, kernel isolation or an immutable ledger.
