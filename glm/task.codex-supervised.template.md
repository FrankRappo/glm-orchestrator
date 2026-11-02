<!-- OWNER_VPS_ONLY_20261024:START -->
## Owner rule 24.10.2026 — all projects, WSL and Windows

- Application runtimes, test/staging environments, databases, fixtures, containers, dependency installs, builds, benchmarks and browser QA run ONLY on the authorized VPS. Never start a local application stand, database, Docker/Compose service, app node_modules or .next in WSL/Windows; never use local execution as a fallback.
- SQL, dumps, backups, large archives, datasets and bulky build artifacts stay on the VPS. Check size remotely before transfers. Download only small text reports/manifests/control scripts and bounded JPEG evidence unless the owner explicitly requests a particular large local download.
- WSL/Windows are thin control clients: orchestration, documentation, permitted source editing/Git and small artifacts. Project-specific VPS-only source/Git rules remain binding. Local syntax/text checks of control scripts are permitted; application tests and stands are not.
- Use the requested VNC framework or Puppeteer against a visible browser ON the VPS. Preserve shared sessions. Never shut down/restart WSL or the host without the owner's explicit instruction for that exact action.
- Every delegated task records the VPS target, remote application path and remote artifact/backup paths. Missing VPS access means recover the approved transport or report a blocker; it never authorizes a local stand or a local database dump.
- Remove only owner-named or verified task-owned local files after verifying complete remote copies. Preserve unrelated files, older backups and other agents' work. Only an explicit newer owner exception overrides this rule.
<!-- OWNER_VPS_ONLY_20261024:END -->

<!-- OWNER_NO_AGENT_WAIT_20261030:START -->
## Owner rule 30.10.2026 — do not wait for agents by default

- DEFAULT: DO NOT WAIT FOR AGENTS. Waiting for an agent to finish requires an explicit instruction from the owner. This applies to every project, model, provider, native subagent and orchestrator in WSL and Windows.
- After delegation, perform at most one brief startup check and return control immediately. If actual model startup is not yet confirmed, say so honestly and return control; do not extend startup verification into an idle waiting loop.
- Do not keep a turn open, sleep, repeatedly poll logs/status, use wait_agent, or repeatedly await an exec/session/report just to wait for agent completion unless the owner expressly asks to wait.
- Requests to implement, finish, fix, supervise, review, accept, achieve high quality, or use multiple agents DO NOT authorize waiting. Supervised mode and responsibility for later acceptance do not authorize waiting either.
- Only an explicit request such as "wait", "wait until the agent finishes", "жди", or "дождись завершения" authorizes waiting for that specific run. A later "do not wait" immediately revokes that authorization. Do not carry waiting permission into other runs or projects.
- A status question authorizes one compact status check and a concise answer, not a monitoring or waiting loop. Perform already-authorized review when a completed report is actually available or on a new owner request; never wait for an unavailable report by default.
- Leave agents and their operational supervisors/recovery/quota/cleanup guards running independently. A lightweight asynchronous completion notification is allowed; an idle LLM/controller waiting loop is not. Stopping a wait does not mean stopping the worker.
- Preserve task, attempt, baseline and report pointers so later acceptance can resume without a duplicate worker. A launched worker or SUCCESS report is not proof of application completion or acceptance.

This newer owner rule supersedes older instructions to "delegate and wait", "await the report", or keep a supervised turn alive until completion. Other safety, VPS-only, scope and acceptance rules remain in force.
<!-- OWNER_NO_AGENT_WAIT_20261030:END -->

# T<NN> — <short task name>

Complexity: medium
Model: GLM-5.3
Input: text
Mode: yolo
Resource-Lock: none
No-Respawn: false
Max-Respawn: 3

Temporary provider/network errors recover automatically under the operational
supervisor, separately from the ordinary respawn budget. Preserve checkpoints
and verify actual side effects before any operation is repeated.
Max-Runtime-Seconds: 0
Policy: CODEX_SUPERVISED_V1
Controller-Mode: launch-only
Wait-For-Completion: false

Use `Model: GLM-5.3` with `Input: text` for source exploration,
implementation, tests, fixes, and review. Use `Model: GLM-5.3-Flash` with
`Input: image`, `Input: vnc`, or `Interface: vnc` for screenshot/VNC work.
These routes are mandatory at every complexity. Provide image paths or the
permitted capture target, and record the actual model ID, which images were
opened, and any unavailable tool capability.

## Controller lifecycle

- Controller mode: `launch-only` (default) or `supervised` (explicit user request).
- Controller task ID: `<stable-task-id>`
- Worker session/attempt ID: `<attempt-id-or-pending>`
- Startup evidence: `<actual worker/model start, or startup failure>`
- Report path: `reports/report_T<NN>.md`
- VNC input evidence (for KSO GUI): `<controller-verified remote permissions,
  keyboard mode, fresh screenshot and visible nonfinancial response; code0/local
  tooltips are insufficient; required session-toolbar controls are available>`
- Default cadence: delegate, perform one brief startup check, return control immediately.
- Waiting: disabled by default, including supervised mode. Enable only with the exact explicit owner request recorded; task completion/review wording is insufficient.
- Completion notification: `<lightweight report-ready signal, if available>`
- Parent attempt/report: `<if explicitly assigned a correction>`

Launch-only: prepare, launch, verify the actual worker/model started once, then
return control. Do not continue polling, reviewing results, running QA, issuing
corrections, or launching follow-ups. Leave the worker and its operational
supervisor/quota/cleanup guards running. The result is unreviewed until
the user requests review. Do not claim application completion.

Do not duplicate GLM's assigned investigation or implementation in Codex or
native subagents after startup. A prepared gate, broker, queued session, or model
configuration is not actual model execution. A status question permits one
compact check, not a new polling/correction loop. A request to finish or fix the
assigned GLM task does not by itself request continuous Codex supervision.

Supervised (only when explicitly requested): retain the same attempt and return
control after one brief startup check. Independently review an actually completed
report, issue bounded linked corrections with exact findings/tests/baseline, and
retain responsibility for scoped acceptance across turns. Supervised mode does
not authorize waiting. Wait-For-Completion may be true only for a direct owner
request to wait for this run; record the owner's exact request. A lightweight
asynchronous completion notification is permitted. Preserve raw failures and
never blindly repeat side effects.

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
behavioral check that proves the related function. A visual verdict does
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


<!-- OWNER_STAND_MEMORY_UNCAPPED_20261029 -->
## Owner rule29.10.2026 — no artificial stand/build memory cap

By explicit owner instruction, future authorized VPS test/build jobs run without
controller-imposed RAM or swap ceilings. Do not copy legacy MemoryMax=2G,
MemoryHigh, MemorySwapMax=0, Docker --memory/--memory-swap, ulimit memory limits,
or artificial Node --max-old-space-size clamps into new stand/build jobs.
Use infinity for systemd task memory properties where necessary to override
controller defaults. Preserve VPS-only execution, distinct UID, strict filesystem
and network isolation, CPU scheduling, supervision and cleanup. This instruction
applies to task-owned tests/builds; existing production service limits are a
separate scope and remain governed by their own release policy.
