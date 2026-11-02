<!-- OWNER_BROWSER_NO_KILL_20261102:START -->
## Owner rule 02.11.2026 — НИКОГДА не убивать/не перезапускать браузер владельца; только подключение к живой сессии

- ЗАПРЕЩЕНО: taskkill/закрытие/перезапуск Edge, Chrome и любого GUI-приложения владельца; запуск
  браузера с его основным профилем, если для этого нужно закрыть уже запущенный экземпляр.
- Браузерная автоматизация (CDP и др.) подключается ТОЛЬКО к уже открытому браузеру с активным
  портом отладки. Порта нет, а сессия владельца жива — НЕ трогать процессы: попросить владельца
  (перезапустить самому / открыть нужную страницу / ввести код), ждать его действия.
- Причина: убийство процесса сессии уничтожает живые логины (2FA). Прецедент 02.11.2026 (asterisk,
  миграция после аварии Бегета): `taskkill /IM msedge.exe /F` ради открытия CDP-порта убил живую
  сессию Selectel — владельцу пришлось проходить вход заново по коду из письма.
- Порядок на будущее: владелец сам открывает/перезапускает браузер с нужными флагами → агент
  подключается к живой сессии и работает, ничего не перезапуская и вкладки не закрывая.
- Дублировано в глобальном AGENTS.md Windows (C:\Users\user\.zcode\AGENTS.md).
<!-- OWNER_BROWSER_NO_KILL_20261102:END -->

<!-- OWNER_GLM_ZERO_RESERVE_20261101:START -->
## Owner01.11.2026 — GLM/Flash use the full provider quota, no artificial reserve

The owner permanently removed the artificial15% quota reserve for ALL GLM/Flash work, including already-created queues. Use quota_reserve_percent=0 in /work/glm/glm/model_policy.json; do not ask again to spend a reserve. Continue until the actual provider quota is exhausted; the owner handles any available provider reset. Do not purchase/reset the account automatically. Keep live quota freshness, unknown/auth failures fail-closed, actual exhaustion detection and provider retry/cleanup controls. This overrides older15%-reserve guidance but not VPS-only/no-agent-wait/model-routing rules. Already-running controllers inherit the effective policy on each quota admission without restart or duplicate workers.
<!-- OWNER_GLM_ZERO_RESERVE_20261101:END -->

<!-- OWNER_VPS_ONLY_20261024:START -->
## Owner rule 24.10.2026 — all projects, WSL and Windows

- Application runtimes, test/staging environments, databases, fixtures, containers, dependency installs, builds, benchmarks and browser QA run ONLY on the authorized VPS. Never start a local application stand, database, Docker/Compose service, app node_modules or .next in WSL/Windows; never use local execution as a fallback.
- SQL, dumps, backups, large archives, datasets and bulky build artifacts stay on the VPS. Check size remotely before transfers. Download only small text reports/manifests/control scripts and bounded JPEG evidence unless the owner explicitly requests a particular large local download.
- WSL/Windows are thin control clients: orchestration, documentation, permitted source editing/Git and small artifacts. Project-specific VPS-only source/Git rules remain binding. Local syntax/text checks of control scripts are permitted; application tests and stands are not.
- Use the requested VNC framework or Puppeteer against a visible browser ON the VPS. Preserve shared sessions. Never shut down/restart WSL or the host without the owner's explicit instruction for that exact action.
- Every delegated task records the VPS target, remote application path and remote artifact/backup paths. Missing VPS access means recover the approved transport or report a blocker; it never authorizes a local stand or a local database dump.
- Remove only owner-named or verified task-owned local files after verifying complete remote copies. Preserve unrelated files, older backups and other agents' work. Only an explicit newer owner exception overrides this rule.
<!-- OWNER_VPS_ONLY_20261024:END -->

<!-- OWNER_ALL_IN_PROJECT_20261031:START -->
## Owner rule 31.10.2026 (усилено ночью 31.10 после уборки) — ВСЁ сохранять ТОЛЬКО в директории проекта и БОЛЬШЕ НИГДЕ

- ВСЕ файлы — исходники, бэкапы, скрипты, транскрипции, дампы, доказательства, скрины, логи, временные
  и рабочие файлы агентов — сохраняются ТОЛЬКО в директории проекта (KSO = /work/kso/, GLM = /work/glm/ и т.д.)
  и БОЛЬШЕ НИГДЕ. Это касается и оркестратора, и каждого агента/субагента.
- ЗАПРЕЩЕНО: /tmp/, /root/, /home/*, домашние каталоги, рабочие столы, C:/kso_ops, драфты вне проекта —
  любые пути вне папки проекта. /tmp не переживает ребут, не виден другим агентам и не попадает в git.
- Промежуточные файлы — в /work/<проект>/tmp/ или /work/<проект>/backups/<задача>/.
- Правило передаётся КАЖДОМУ агенту в промпте задачи: «всё сохраняй только в папке проекта, /tmp не используй».
- Прецедент 31.10 (ночь): по приказу владельца собрано 8823 файла, сваленных агентами мимо проекта
  (8465 из /tmp, 300 из виндового драфта сессии, 58 из /root) — бардак, который владелец устал находить. Больше не допускать.
- Remote бэкапы на кассах/серверах остаются на тех машинах, но локальная копия — в папке проекта.
<!-- OWNER_ALL_IN_PROJECT_20261031:END -->

<!-- OWNER_FLASH_ONLY_ACCEPT_20261031:START -->
## Owner rule 31.10.2026 — visual acceptance is done ONLY by Flash (vision agent)

- Any VISUAL acceptance — "the screen/receipt/document shows what it must" — is produced ONLY by the
  Flash vision agent that actually sees pixels (screenshots, renders). Origin: owner directive 30.10.2026.
- Smart code agents (GLM-5.3 etc.) WRITE code and fixes; they must NOT do visual acceptance of their own
  or others' results — they cannot see images. Orchestrator/5.3 does at most STATIC text control
  (grep, dumps, cell texts), never a visual verdict.
- Workflow of every UI/print/GUI task: code agent -> static control -> SERVER/text dumps if applicable ->
  Flash visual acceptance -> owner reviews Flash frames -> only then "enable/deploy" decision.
- Applies to: receipts/VPF print forms, loyalty app GUI, KSO kiosk screens, VNC/RustDesk GUI actions
  (Flash also picks click coordinates on fresh screenshots, per 23.10 rule).
- Reporting a deliverable as "looks good" without Flash having actually viewed the pixels = violation.
<!-- OWNER_FLASH_ONLY_ACCEPT_20261031:END -->



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

# GLM Orchestrator Repository

- Execute clear local edit/test/verify work autonomously.
- Route all text/code tasks to GLM-5.3 and every screenshot/VNC task to GLM-5.3-Flash, at every complexity and for every controller. `Input: image`, `Input: vnc`, or `Interface: vnc` require Flash; an explicit GLM-5.3 request for those tasks must fail before launch. Do not claim a model saw an image merely because Read uploaded one. The 23.10.2026 end-to-end test on ZCode 3.16.3 showed GLM-5.3 received only a CDN upload receipt, while GLM-5.3-Flash correctly read an unseen random visual code, colors and shapes. Record the actual model ID and image inspected. Configured model selections must include a valid reasoning level; otherwise the CLI can silently fall back to the first model. Evidence: `artifacts/zcode_3_16_3_20261023/vision_comparison_verified.json`.
- For the owner's KSO GUI tasks, GLM must itself view fresh VNC/RustDesk screenshots and choose click coordinates through `/work/vnc_work_v2-vm121-review`. Do not substitute UIAutomation, hidden desktop-item enumeration, DOM/name-based button discovery, PowerShell mouse scripts or direct financial calls for that visual flow. Use the installed ordinary UI; when asked only to close the current shift, do not open another shift for a test. Verify the visible result after each action; provider recovery does not authorize replaying a financial gesture blindly.
- Before a KSO RustDesk GUI task, the controller must verify remote input permissions and a visible nonfinancial response. On 24.10.2026, `enable-keyboard = 'N'` on the cash machine blocked control and hid the keyboard-mode menu. The verified recovery was: back up configs, enable input in the authorized service window, reconnect (restart only RustDesk if needed), choose Legacy in this Linux viewer, focus the remote canvas, then press Ctrl+Shift+Q once and verify that 1C is visible. Map had not delivered the combination in this case. Do not diagnose a missing menu as an unsupported client version, accept code0/local tooltips as remote-input proof, or repeat inert shortcuts indefinitely. Permit the session toolbar and remote taskbar needed for this procedure while keeping the exact target/model/fresh-frame checks. See `docs/CODEX_SUPERVISED.md#vnc--rustdesk-input-before-kso-tasks`. Workers must report denied permissions to the controller rather than changing production configuration themselves.
- For Codex-supervised GLM work, follow [`docs/CODEX_SUPERVISED.md`](docs/CODEX_SUPERVISED.md) and inject the `CODEX_SUPERVISED_V1` policy; worker success is only a candidate result until Codex independently accepts it.
- Default GLM controller mode is launch-only: prepare the task, launch it, verify once that the actual worker/model started, then return control. Do not keep polling, reviewing, fixing, or starting follow-up tasks unless the user explicitly requests supervised mode. Keep operational supervisor and exact cleanup guards active.
- Owner preference: **delegate, perform one brief startup check, return control immediately; wait only when the owner explicitly requests it**. After verified startup, let GLM perform the assigned work independently; do not duplicate its investigation or implementation in Codex or native subagents. Resume task-level review when the completed report is available and review is already authorized, or on a new user request. Use a lightweight completion notification instead of repeated LLM status checks. A request to “finish” or “fix” an assigned GLM task does not by itself request continuous Codex supervision. A status question permits one concise status check, not a new monitoring or correction loop. Continuous supervision requires an explicit request. This cadence also applies to supervised work unless the user asks for continuous monitoring.
- Report startup honestly: a prepared task, gate, broker, queued session, or configured model is not a started GLM worker. Confirm the actual requested model has begun executing before saying it is working. Leave running workers and their operational/cleanup guards active when returning control.
- GLM tasks run without wall-clock or inactivity limits by default. Never enable a runtime deadline, idle-kill timer, or time-based credential cleanup guard unless the user explicitly requests that limit. Cleanup follows workload exit or manual stop; it must not cut off active work by elapsed time.
- Preserve all running WSL sessions. Never run `wsl --shutdown`, `wsl --terminate`, restart/stop WslService or LxssManager, kill WSL/vmmem host processes, or reboot/shutdown the host unless the owner explicitly requests that exact disruptive action. Routine troubleshooting, setup, updates, or another project's task do not authorize it. Prepare any required changes and report that activation needs an owner-scheduled restart; do not interrupt shared sessions. Added after the owner confirmed GLM caused the 2026-10-15 WSL shutdown incident.
- Keep runtime data under ignored `tasks/`, `logs/`, `limits/`, `worktrees/`, `projects/`, and `artifacts/` paths.
- Never commit ZCode credentials, OAuth tokens, generated provider files, task logs, or customer data.
- Run `bash tests/run_glm_tests.sh`, `orchestrate doctor --live`, and live quota admission before claiming runtime changes complete.
- Keep `common/zcode_coding_plan_quota.mjs` output credential-free; credentials may only be decrypted in memory for official Z.ai/ZCode endpoints.
- Preserve fail-closed quota admission and the single-controller lock contract.
- Always launch model work under the operational supervisor with automatic recovery for temporary provider/network errors (500/502/503/504, connection reset/timeout). Preserve each attempt, back off between retries, and retain the same task scope and artifacts. `No-Respawn` limits ordinary worker failures; it does not disable temporary provider recovery. Never replay financial or GUI side effects blindly: use durable operation guards and verify actual state before a retry. Authentication/configuration errors and genuine terminal reports require their existing handling.
- Owner rule 2026-10-24: Asterisk/CRM tests, benchmarks, builds, PostgreSQL/HTTP/browser stands and fixtures run ONLY on the authorized VPS in an isolated synthetic environment. NEVER run them on this workstation/WSL/local Docker or create local test databases, node_modules or .next. Local source editing/Git/transfer is allowed. Inject the VPS-only rule and exact remote boundary into every Asterisk task. See /work/asterisk/WORKFLOW.md. Preserve code/evidence; delete only verified disposable local test artifacts.


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

<!-- OWNER_WSL_CHANNELS_20261102:START -->
## Owner rule 02.11.2026 — access channels to WSL (and the working fallback when the pipe flaps)

Background: 01-02.11 the wsl.exe pipe (Wsl/Service, error 0x8007274c) flapped intermittently while
the owner's own WSL worked fine. Channels, in order:

1. `wsl.exe -e bash -c '...'` (default distro) — PRIMARY, but the FIRST to die on flaps.
2. `wsl.exe -d Ubuntu-24.04 -e bash -c '...'` (explicit distro) — sometimes survives when (1) fails.
3. Same via `cmd /c` or the WindowsApps stub — no help when the WslService pipe itself is down.
4. 🔴 WORKING FALLBACK: **UNC file access `//wsl.localhost/Ubuntu-24.04/...` (Plan-9)** — goes
   AROUND the broken pipe. From Git Bash `ls`/`cat`/`head`/`grep` on
   `//wsl.localhost/Ubuntu-24.04/work/kso/...` all work: use it for reading artifacts, checking
   agents, reading logs while the pipe is down. Running scripts/python INSIDE WSL still needs
   wsl.exe; sudo-owned paths may be unreadable via UNC.

Rules:
- On 0x8007274c: retry (1) → (2) → switch to UNC for visibility; do NOT hammer the pipe.
- Agents driving WSL must be told: "if wsl.exe fails with a connection error — wait 30-60s and
  retry, use `-d Ubuntu-24.04`, do not abort the task on the first failure".
- NEVER restart WSL (wsl --shutdown/terminate) — standing owner rule; report and wait instead.
- The flap self-heals in minutes; agents with retry instructions survive it (proven: Flash T438
  kept working through the 02.11 flap).
<!-- OWNER_WSL_CHANNELS_20261102:END -->
