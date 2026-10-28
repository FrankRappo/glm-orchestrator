<!-- OWNER_VPS_ONLY_20261024:START -->
## Owner rule 24.10.2026 — all projects, WSL and Windows

- Application runtimes, test/staging environments, databases, fixtures, containers, dependency installs, builds, benchmarks and browser QA run ONLY on the authorized VPS. Never start a local application stand, database, Docker/Compose service, app node_modules or .next in WSL/Windows; never use local execution as a fallback.
- SQL, dumps, backups, large archives, datasets and bulky build artifacts stay on the VPS. Check size remotely before transfers. Download only small text reports/manifests/control scripts and bounded JPEG evidence unless the owner explicitly requests a particular large local download.
- WSL/Windows are thin control clients: orchestration, documentation, permitted source editing/Git and small artifacts. Project-specific VPS-only source/Git rules remain binding. Local syntax/text checks of control scripts are permitted; application tests and stands are not.
- Use the requested VNC framework or Puppeteer against a visible browser ON the VPS. Preserve shared sessions. Never shut down/restart WSL or the host without the owner's explicit instruction for that exact action.
- Every delegated task records the VPS target, remote application path and remote artifact/backup paths. Missing VPS access means recover the approved transport or report a blocker; it never authorizes a local stand or a local database dump.
- Remove only owner-named or verified task-owned local files after verifying complete remote copies. Preserve unrelated files, older backups and other agents' work. Only an explicit newer owner exception overrides this rule.
<!-- OWNER_VPS_ONLY_20261024:END -->

# GLM Orchestrator Repository

- Execute clear local edit/test/verify work autonomously.
- Route all text/code tasks to GLM-5.3 and every screenshot/VNC task to GLM-5.3-Flash, at every complexity and for every controller. `Input: image`, `Input: vnc`, or `Interface: vnc` require Flash; an explicit GLM-5.3 request for those tasks must fail before launch. Do not claim a model saw an image merely because Read uploaded one. The 23.10.2026 end-to-end test on ZCode 3.16.3 showed GLM-5.3 received only a CDN upload receipt, while GLM-5.3-Flash correctly read an unseen random visual code, colors and shapes. Record the actual model ID and image inspected. Configured model selections must include a valid reasoning level; otherwise the CLI can silently fall back to the first model. Evidence: `artifacts/zcode_3_16_3_20261023/vision_comparison_verified.json`.
- For the owner's KSO GUI tasks, GLM must itself view fresh VNC/RustDesk screenshots and choose click coordinates through `/work/vnc_work_v2-vm121-review`. Do not substitute UIAutomation, hidden desktop-item enumeration, DOM/name-based button discovery, PowerShell mouse scripts or direct financial calls for that visual flow. Use the installed ordinary UI; when asked only to close the current shift, do not open another shift for a test. Verify the visible result after each action; provider recovery does not authorize replaying a financial gesture blindly.
- Before a KSO RustDesk GUI task, the controller must verify remote input permissions and a visible nonfinancial response. On 24.10.2026, `enable-keyboard = 'N'` on the cash machine blocked control and hid the keyboard-mode menu. The verified recovery was: back up configs, enable input in the authorized service window, reconnect (restart only RustDesk if needed), choose Legacy in this Linux viewer, focus the remote canvas, then press Ctrl+Shift+Q once and verify that 1C is visible. Map had not delivered the combination in this case. Do not diagnose a missing menu as an unsupported client version, accept code0/local tooltips as remote-input proof, or repeat inert shortcuts indefinitely. Permit the session toolbar and remote taskbar needed for this procedure while keeping the exact target/model/fresh-frame checks. See `docs/CODEX_SUPERVISED.md#vnc--rustdesk-input-before-kso-tasks`. Workers must report denied permissions to the controller rather than changing production configuration themselves.
- For Codex-supervised GLM work, follow [`docs/CODEX_SUPERVISED.md`](docs/CODEX_SUPERVISED.md) and inject the `CODEX_SUPERVISED_V1` policy; worker success is only a candidate result until Codex independently accepts it.
- Default GLM controller mode is launch-only: prepare the task, launch it, verify once that the actual worker/model started, then return control. Do not keep polling, reviewing, fixing, or starting follow-up tasks unless the user explicitly requests supervised mode. Keep operational supervisor and exact cleanup guards active.
- Owner preference: **delegate, verify startup once, wait for the report**. After verified startup, let GLM perform the assigned work independently; do not duplicate its investigation or implementation in Codex or native subagents. Resume task-level review when the completed report is available and review is already authorized, or on a new user request. Use a lightweight completion notification instead of repeated LLM status checks. A request to “finish” or “fix” an assigned GLM task does not by itself request continuous Codex supervision. A status question permits one concise status check, not a new monitoring or correction loop. Continuous supervision requires an explicit request. This cadence also applies to supervised work unless the user asks for continuous monitoring.
- Report startup honestly: a prepared task, gate, broker, queued session, or configured model is not a started GLM worker. Confirm the actual requested model has begun executing before saying it is working. Leave running workers and their operational/cleanup guards active when returning control.
- GLM tasks run without wall-clock or inactivity limits by default. Never enable a runtime deadline, idle-kill timer, or time-based credential cleanup guard unless the user explicitly requests that limit. Cleanup follows workload exit or manual stop; it must not cut off active work by elapsed time.
- Preserve all running WSL sessions. Never run `wsl --shutdown`, `wsl --terminate`, restart/stop WslService or LxssManager, kill WSL/vmmem host processes, or reboot/shutdown the host unless the owner explicitly requests that exact disruptive action. Routine troubleshooting, setup, updates, or another project's task do not authorize it. Prepare any required changes and report that activation needs an owner-scheduled restart; do not interrupt shared sessions. Added after the owner confirmed GLM caused the 2026-10-15 WSL shutdown incident.
- Keep runtime data under ignored `tasks/`, `logs/`, `limits/`, `worktrees/`, `projects/`, and `artifacts/` paths.
- Never commit ZCode credentials, OAuth tokens, generated provider files, task logs, or customer data.
- Run `bash tests/run_glm_tests.sh`, `orchestrate doctor --live`, and live quota admission before claiming runtime changes complete.
- Keep `common/zcode_coding_plan_quota.mjs` output credential-free; credentials may only be decrypted in memory for official Z.ai/ZCode endpoints.
- Preserve fail-closed quota admission and the single-controller lock contract.
- Always launch model work under the operational supervisor with automatic recovery for temporary provider/network errors (500/502/503/504, connection reset/timeout). Preserve each attempt, back off between retries, and retain the same task scope and artifacts. `No-Respawn` limits ordinary worker failures; it does not disable temporary provider recovery. Never replay financial or GUI side effects blindly: use durable operation guards and verify actual state before a retry. Authentication/configuration errors and genuine terminal reports require their existing handling.


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
