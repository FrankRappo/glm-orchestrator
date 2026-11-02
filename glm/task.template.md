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
Model: auto
<!-- All complexities and inputs use GLM-5.3; auto resolves to GLM-5.3. -->
Input: text
Mode: yolo
Resource-Lock: none
No-Respawn: false
Max-Respawn: 3
Max-Runtime-Seconds: 0

## Objective

State one observable outcome.

## Read first

- `<path>`

## Scope

- Allowed: `<paths>`
- Forbidden: unrelated files, destructive git commands, push, deploy.

## Work

1. `<step>`
2. `<step>`

## Acceptance gates

- [ ] `<testable result>`
- [ ] Targeted tests pass.

## Verification commands

```bash
<targeted-test>
<lint-or-typecheck>
```

## Required report

Write `reports/report_T<NN>.md`. Its final line must be exactly one of:

```text
STATUS: SUCCESS
STATUS: FAIL
STATUS: BLOCKED
STATUS: PARTIAL
```


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
