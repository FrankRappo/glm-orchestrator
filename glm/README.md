<!-- OWNER_GLM_ZERO_RESERVE_20261101:START -->
## Owner01.11.2026 — GLM/Flash use the full provider quota, no artificial reserve

The owner permanently removed the artificial15% quota reserve for ALL GLM/Flash work, including already-created queues. Use quota_reserve_percent=0 in /work/glm/glm/model_policy.json; do not ask again to spend a reserve. Continue until the actual provider quota is exhausted; the owner handles any available provider reset. Do not purchase/reset the account automatically. Keep live quota freshness, unknown/auth failures fail-closed, actual exhaustion detection and provider retry/cleanup controls. This overrides older15%-reserve guidance but not VPS-only/no-agent-wait/model-routing rules. Already-running controllers inherit the effective policy on each quota admission without restart or duplicate workers.
<!-- OWNER_GLM_ZERO_RESERVE_20261101:END -->

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

# GLM/ZCode orchestration backend

This backend runs headless GLM workers under tmux. It has no Claude runtime
dependency. Codex, GLM itself, or a human can own the queue; ownership is
recorded and protected by one controller lock.

## Components

- `glm-linux-wrapper.template.sh` — native Linux CLI wrapper for the official
  ZCode `.deb`; root launches are dropped to the configured regular user.
- `glm_controller.template.sh` — asks GLM to decompose one goal into `T*.md`
  task files, then starts the queue.
- `glm_orchestrator.template.sh` — dynamic task discovery, bounded parallelism,
  resource locks, model routing, quota admission, terminal reports.
- `glm_supervisor.template.sh` — retries, runtime deadline, quota waits,
  authentication/configuration quarantine.
- `glm_agent_launcher.template.sh` — isolated model selection and one headless
  `glm --prompt` call.
- `task_metadata.py` and `model_policy.json` — validated per-task routing.
- `glm_runtime_doctor.template.sh` — static and optional live model check.

Use the common entrypoint rather than calling these scripts directly:

```bash
bash /work/glm/common/orchestrate.template.sh doctor --live
bash /work/glm/common/orchestrate.template.sh limits
bash /work/glm/common/orchestrate.template.sh limits --json
bash /work/glm/common/orchestrate.template.sh usage --project /work/myproject
```

The same commands can be entered from Windows through WSL:

```powershell
wsl.exe -d Ubuntu-24.04 -u agentuser -- orchestrate limits
wsl.exe -d Ubuntu-24.04 -u agentuser -- orchestrate usage --project /work/myproject
```

Always pass Linux paths (`/work/...`), not `\\wsl.localhost\...`, to the
orchestrator.

If the live doctor asks for authentication, complete the standalone CLI OAuth
once. Desktop login and CLI login can be separate:

```bash
glm login
```

Run the Linux CLI as a regular user so OAuth and plugin state live under that
user's `~/.zcode`. For a native Linux/WSL installation use
`GLM_PATH_STYLE=native` (the default). Only Windows-interoperability wrappers
should set `GLM_PATH_STYLE=windows`.

The default provider is `account:zai-individual-coding-plan`, which uses the
connected personal Lite/Pro/Max plan. The orchestrator never reads or copies the
credential file into task prompts or logs. The quota helper decrypts credentials
only in memory to query the official quota endpoints and emits normalized usage
without secrets.

`orchestrate limits` shows both `used` and `remaining_pct` for every quota bucket,
including the shared five-hour and weekly Coding Plan pools, alongside the raw
remaining/limit values. `limits --json` includes `remaining_percent` (or `null`
when the limit is zero). Remaining percent is computed from the provider's
remaining amount, so it can differ slightly from `100 - used_percent` when the
provider rounds its used-percent figure.

## GLM controls the run

```bash
cat > /work/myproject/GOAL.md <<'EOF'
Implement the requested feature, add regression tests, and verify the build.
EOF

bash /work/glm/common/orchestrate.template.sh start \
  --project /work/myproject \
  --controller glm \
  --goal /work/myproject/GOAL.md \
  --max-parallel 2 \
  --quota-policy enforce
```

GLM first creates bounded `tasks/T*.md` files, then the same queue starts GLM
workers for them.

## Codex controls the run

Codex writes the tasks from `task.template.md`, then starts the queue with its
ownership recorded:

```bash
bash /work/glm/common/orchestrate.template.sh start \
  --project /work/myproject \
  --controller codex \
  --max-parallel 2 \
  --quota-policy enforce
```

`controller=codex` does not launch another Codex process. It means the current
Codex session owns planning, task authoring, steering, review, and integration;
GLM sessions execute the task files.

## Task routing

Supported headers:

```text
Complexity: low | medium | high | critical
Model: auto | GLM-5.3
Input: text | image
Mode: build | edit | plan | yolo
Resource-Lock: none | <name>
No-Respawn: true | false
Max-Respawn: 3
Max-Runtime-Seconds: 0
```

`0` means no runtime deadline. The supervisor leaves runtime limits disabled by default,
even if an older task specifies a positive value. To enforce a task deadline, set
`GLM_RUNTIME_LIMIT_ENABLED=1` when starting `orchestrate` and give the task a
positive `Max-Runtime-Seconds` value.

Autonomous headless tasks should use `Mode: yolo`. ZCode's `build` and `edit`
modes expect an interactive permission client; the launcher maps them to
`yolo` by default (`GLM_HEADLESS_AUTO_APPROVE=1`) so unattended workers do not
stall on `No permission client configured`.

Default policy:

| Complexity | Model |
| --- | --- |
| low | GLM-5.3 |
| medium | GLM-5.3 |
| high | GLM-5.3 |
| critical | GLM-5.3 |

Critical work still requires independent review by the owning Codex session or
another explicitly chosen reviewer. Model price alone is not a verification
strategy.

Every task uses GLM-5.3, including `auto`/`inherit`, all complexities, and
both `Input: text` and `Input: image`. Other task models are rejected by the
workspace policy. The planner and live doctor also validate their selected
model against that policy; an override cannot silently select Flash.

GLM-5.3 can inspect permitted screenshots itself through available image tools.
Provide the screenshot paths or allowed capture target and report which images
were actually opened. No separate Flash task is needed. Screenshot evidence
does not replace the applicable behavioral tests.

The planner and workers also default to token-conscious execution: targeted
file reads, concise evidence, focused tests during edits, and required broad
validation at the end. This does not relax acceptance or verification.
Complexity describes task scope; it no longer selects a cheaper model. Check
the actual provider and quota snapshot before claiming savings.

## Runtime status

```bash
bash /work/glm/common/orchestrate.template.sh status --project /work/myproject
bash /work/glm/common/orchestrate.template.sh attach --project /work/myproject
bash /work/glm/common/orchestrate.template.sh stop --project /work/myproject
```

The queue uses exact tmux names and a `flock` controller lock. A second Codex,
GLM, or manual controller cannot silently take ownership of the same state
directory.
