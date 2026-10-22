# T<NN> — <short task name>

Complexity: medium
Model: GLM-5.3
Input: text
Mode: yolo
Resource-Lock: none
No-Respawn: false
Max-Respawn: 3
Max-Runtime-Seconds: 0
Policy: CODEX_SUPERVISED_V1
Controller-Mode: launch-only

Use `Model: GLM-5.3` with `Input: text` for source exploration,
implementation, testing, fixes, and source review. For screenshot or image
interpretation, use a separate task with `Model: GLM-5.3-Flash` and
`Input: image`; do not route image input to GLM-5.3. Model routing may be
overridden by application-specific rules.

## Controller lifecycle

- Controller mode: `launch-only` (default) or `supervised` (explicit user request).
- Controller task ID: `<stable-task-id>`
- Worker session/attempt ID: `<attempt-id-or-pending>`
- Startup evidence: `<actual worker/model start, or startup failure>`
- Report path: `reports/report_T<NN>.md`
- Parent attempt/report: `<if explicitly assigned a correction>`

Launch-only: prepare, launch, verify the actual worker/model started once, then
return control. Do not continue polling, reviewing results, running QA, issuing
corrections, or launching follow-ups. Leave the worker and its operational
supervisor/quota/cleanup guards running. The result is unreviewed until
the user requests review. Do not claim application completion.

Supervised (only when explicitly requested): await the same attempt without
duplicate launches, independently review the result, issue bounded linked
corrections with exact findings/tests/baseline, and continue through the scoped
acceptance. Preserve raw failures and never blindly repeat side effects.

## Objective

State one observable outcome without adding unstated business policy.

## Baseline and repository

- Repository: `<absolute-path>`
- Baseline commit: `<full-sha>`
- Working tree/worktree: `<absolute-path>`
- Application-specific rules: `<path-or-none>`

Application-specific rules override the generic supervised policy. Darkhaven
source, Git operations, and tests must remain on its VPS through the canonical
gateway; no local application stand may be created or run.

## Execution boundary

- Execution mode: `<isolated-tools | proposal-only-no-tools>`
- Machine-enforced boundary: `<container/vm/sandbox or none>`
- Isolation evidence: `<command/output or attestation proving restrictions>`
- Filesystem access: `<restricted paths>`
- Network access: `<restricted destinations or none>`
- Available credentials: `<non-production credentials or none>`
- Optional process wrapper: `<glm/landlock_exec.py or none>`
- Wrapper probe for actual command: `<command and successful result or none>`

`controller=codex`, a worktree, and `Mode: yolo` are not OS isolation. If the
machine-enforced boundary cannot be verified, select `proposal-only-no-tools`.
Do not submit proposal-only work through the current tool-capable worker
launcher. If `glm/landlock_exec.py` is selected, give it explicit allowed
paths, require Landlock ABI 6 or newer, and probe the actual worker command. It
fails closed, is not universally installed, is not the default sandbox, and
does not grant network authorization. Production, deployment, and remote
production credentials are always forbidden.

## Scope

- Allowed paths:
  - `<path>`
- Forbidden paths:
  - `<path>`
- Forbidden actions:
  - deploy, publish, push, merge, or modify production
  - request, read, or use production/deployment credentials
  - destructive Git or filesystem operations
  - weaken, skip, delete, replace, or rewrite existing tests/acceptance gates
  - infer side-effect authorization or invent business policy

## Requirements

1. `<requirement>`
2. `<requirement>`

## Regression invariants

- `<behavior that must remain unchanged>`
- Preserve all unrelated and pre-existing changes.

For a visual task, record what the screenshot can establish and the trusted
behavioral check that proves the related function. A Flash visual verdict does
not replace Codex's independent source or final-diff review.

## Trusted checks

These checks and acceptance criteria are controller-owned. The worker may run
them but may not change them. Codex reviews any script or command before running
it as independent acceptance.

```bash
<targeted-test>
<lint-typecheck-or-build>
```

## Independent acceptance (only when review/supervision is requested)

- [ ] Codex reads the complete final diff from the baseline commit.
- [ ] Codex inspects critical behavior and maps every requirement to evidence.
- [ ] Codex reviews verification commands/scripts before executing them.
- [ ] Codex independently runs the trusted checks and records their exits.
- [ ] Every review finding is closed by a bounded linked correction or recorded
      as an explicit unresolved blocker.
- [ ] Codex, and only Codex, decides integration or deployment.

Worker `STATUS: SUCCESS` means candidate completion only.

In launch-only mode the controller stops after verified startup; the checks
above remain pending a separate user request. Only explicit supervised mode
continues through review/correction and acceptance. Neither mode authorizes
production writes or broader credentials for the worker.

## Required compact report

Write `reports/report_T<NN>.md` with:

- baseline SHA and final SHA if available;
- controller task ID, attempt ID, attempt kind, parent attempt/report if any,
  and report path;
- exact changed files and final diff summary;
- requirement-to-evidence mapping;
- exact commands and exit codes;
- known gaps.

Do not paste logs, prompts, source context, or repeated reasoning. End with
exactly one of:

```text
STATUS: SUCCESS
STATUS: FAIL
STATUS: BLOCKED
STATUS: PARTIAL
```

No wall-clock or inactivity deadline by default. Runtime/idle limits and guards
that terminate active work by elapsed time require an explicit user request.
Cleanup waits for workload exit or manual stop, without a maximum duration.
