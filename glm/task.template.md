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
