<!-- OWNER_VPS_ONLY_20261024:START -->
## Owner rule 24.10.2026 — all projects, WSL and Windows

- Application runtimes, test/staging environments, databases, fixtures, containers, dependency installs, builds, benchmarks and browser QA run ONLY on the authorized VPS. Never start a local application stand, database, Docker/Compose service, app node_modules or .next in WSL/Windows; never use local execution as a fallback.
- SQL, dumps, backups, large archives, datasets and bulky build artifacts stay on the VPS. Check size remotely before transfers. Download only small text reports/manifests/control scripts and bounded JPEG evidence unless the owner explicitly requests a particular large local download.
- WSL/Windows are thin control clients: orchestration, documentation, permitted source editing/Git and small artifacts. Project-specific VPS-only source/Git rules remain binding. Local syntax/text checks of control scripts are permitted; application tests and stands are not.
- Use the requested VNC framework or Puppeteer against a visible browser ON the VPS. Preserve shared sessions. Never shut down/restart WSL or the host without the owner's explicit instruction for that exact action.
- Every delegated task records the VPS target, remote application path and remote artifact/backup paths. Missing VPS access means recover the approved transport or report a blocker; it never authorizes a local stand or a local database dump.
- Remove only owner-named or verified task-owned local files after verifying complete remote copies. Preserve unrelated files, older backups and other agents' work. Only an explicit newer owner exception overrides this rule.
<!-- OWNER_VPS_ONLY_20261024:END -->

# Codex-supervised GLM workflow

This framework supports two controller modes. **Default: launch-only.** Prepare
the task, launch GLM, verify once that the actual worker and requested model
started (a queue-created message alone is insufficient), then return control to
the user. If startup is not yet known, wait only for the initial start/failure
signal; do not launch duplicates. If startup fails, report the failure rather
than claiming success.

## Default cadence: delegate and wait for the report

The owner's standing preference is to save Codex tokens by letting GLM do the
assigned work. Prepare a bounded task, verify actual model execution once, then
return control and leave GLM running independently. A gate, broker, queued task,
or selected model configuration alone is not startup evidence.

After startup, do not duplicate GLM's investigation or implementation in Codex
or native subagents. Prefer a lightweight completion notification over repeated
LLM polling. Return to task-level work when a completed report is available and
its review is already authorized, or when the user makes a new request. A status
question authorizes one compact check; it does not authorize another monitoring,
correction, or parallel implementation loop.

Requests to "finish", "fix", or "solve the problem" define the outcome; they do
not by themselves request continuous Codex supervision. Even in supervised mode,
wait for the report before reviewing or correcting work unless the user
explicitly requests continuous monitoring. Operational supervisors, quota
admission, isolation, and credential/process cleanup remain active throughout.
Report availability does not expand review, integration, or deployment authority.

In launch-only mode, after a verified start, do not keep polling status, read the result, review
patches, run QA, issue corrections, or launch follow-up tasks without a new user
request. GLM continues its already assigned bounded task independently. Do not
stop the worker when returning control. Its operational supervisor, quota controls, and exact credential/process
cleanup guards remain active;
these are infrastructure responsibilities, not ongoing Codex supervision.

Use **supervised** mode only when the user explicitly requests Codex monitoring
or independent review/correction through acceptance. Merely assigning GLM the
complete outcome does not select this mode. The controller workflow
and correction loop below apply only in that mode. In launch-only mode a worker
result remains an unreviewed candidate: no automatic acceptance, integration,
deployment, or claim that the application task is complete.

The reusable policy is [`glm/codex_supervised_policy.md`](../glm/codex_supervised_policy.md)
and the task template is [`glm/task.codex-supervised.template.md`](../glm/task.codex-supervised.template.md).
Application safety and model routing apply in both modes.

## Trust and execution boundary

`controller=codex`, a Git worktree, and `Mode: yolo` do **not** provide an OS
sandbox. They record ownership, separate Git state, and allow unattended tool
use; they do not restrict filesystem, network, process, or credential access.

Before granting tools, Codex must record evidence that the worker is inside an
appropriate machine-enforced boundary, including the boundary type and the
paths, network access, processes, and credentials it restricts. If that
isolation cannot be verified, use proposal-only execution with no tools. Never
launch that proposal through a tool-capable worker surface. Never give a worker
production or deployment credentials.

Application-specific rules override this generic workflow. For Darkhaven, all
source, Git operations, and tests remain on the VPS through its canonical
gateway. Do not create or run a local application stand.

An optional Linux process boundary may be provided by
`glm/landlock_exec.py`. It requires explicit allowed paths and Landlock ABI 6
or newer, and it fails closed when its requirements are not met. Codex must
probe the host and test the actual worker command through the wrapper before
recording it as isolation evidence. The wrapper is not installed or supported
on every host, is not the default process sandbox, and does not authorize
network access or remote production credentials.

## Role and input routing

Model routing is invariant across complexity and controller type. `Input: text`
requires GLM-5.3. `Input: image`, `Input: vnc`, or `Interface: vnc` requires
GLM-5.3-Flash. `Model: auto` and `inherit` resolve from that input route; an
explicit incompatible model is rejected before launch rather than silently
changed. Older models remain unsupported.

Provide permitted screenshot paths or the capture target. Record the actual
model ID, whether the image was opened, and which files were inspected. If the
image tool cannot render pixels, report that gap rather than claiming a visual
check from an upload receipt or URL.

Keep visual interpretation bounded to visual evidence. A screenshot
finding does not replace Codex's independent source and final-diff review, and
a screenshot verdict alone does not prove functional behavior. Codex still
runs the applicable trusted behavioral checks before acceptance.

## VNC / RustDesk input before KSO tasks

Seeing a live image does not prove that mouse or keyboard input reaches the cash
machine. Before delegating GUI work, the controller checks input permissions and
records a visible, nonfinancial response on the remote screen. Viewer tooltips,
opening a local menu, `windowactivate`, and an input command returning code0 are
not that proof. An inert click on an empty canvas cannot establish keyboard focus.

The verified KSO1 incident on 24.10.2026 had two relevant settings: both the
service and cashier-user `RustDesk2.toml` contained `enable-keyboard = 'N'`, and
the Linux viewer used Map mode. Ctrl+Shift+Q did nothing. The keyboard-mode menu
was absent while remote input was denied; that was not evidence of a missing
feature in the client build.

The successful recovery was:

1. The controller backed up the actual service and user configs, then enabled
   input in the already-authorized service window using the installed RustDesk
   CLI (`rustdesk.exe --option enable-keyboard Y`). It verified the resulting
   configuration; the command's exit alone was insufficient.
2. The controller reconnected its own viewer session. In this incident it also
   restarted only the RustDesk service to reload permissions; Electron and 1C
   process IDs remained unchanged. A service restart is a conditional recovery
   step, not a mandatory action on every launch. No WSL/host reboot is involved.
3. The keyboard icon became available in the session toolbar. The controller
   selected **Legacy** instead of **Map** in this Linux viewer, clicked inside
   the remote canvas and sent **Ctrl+Shift+Q once**. A fresh screenshot showed
   the 1C window underneath: kiosk minimization was actually verified.

After that, the KSO operator procedure uses Win+D or the visible remote Windows
Show Desktop strip to hide 1C. Win/Super may be intercepted locally; choose
coordinates from a fresh image. Ctrl+Shift+Q is a toggle: another press can bring
the kiosk back. Do not transfer old native-screen coordinates into a scaled viewer.

The task's controls must allow the relevant RustDesk toolbar and remote taskbar,
including hover and ordinary navigation. A blanket top/bottom pixel cutoff had
prevented the earlier worker from applying the documented recovery. Keep exact
cash/viewer identity, actual Flash selection, fresh-frame and no-replay checks;
do not allow another peer, a local shell, or unrelated host controls.

Workers receive the controller's permission/input evidence. They do not receive
production credentials or change remote permissions themselves. If a shortcut
has no visible effect, stop repeating it and report the transport obstruction.
Provider 502 errors are a separate issue: retries cannot enable remote input.

This incident verified kiosk minimization only. The owner then requested a stop;
shift 251 remained open and no settlement, Z report or shift closure was started
as part of the input repair. Evidence is retained locally under
`/work/kso/backups/kso1_rmk_close_diag_20261022/manual_vnc_20261024/`.

## Launch and credential lifetime

Always keep the operational supervisor around the model process. Temporary
provider/network failures recover by default with 10/20/40/60-second backoff
(60-second ceiling), without an elapsed-time cutoff. The recovery budget is
separate from `Max-Respawn` / `No-Respawn` for ordinary worker failures. Each
attempt keeps its response artifact. A retry keeps the same task and evidence;
financial/UI operations require durable guards and read-only reconciliation
before any repeat. An unknown outcome must not be retried as an operation.
Authentication/configuration failures, quota policy, and terminal task reports
keep their existing handling. `GLM_TRANSIENT_MAX_RETRIES` can explicitly set a
positive recovery cap; its default zero permits continued provider recovery.

Keep the controller task originals, checks, queue state, logs, model configuration,
and directory parents protected from worker writes. A root controller must not
write predictable files beneath worker-replaceable directories or follow worker
symlinks. Pre-create an exact worker-writable report when the queue needs one.

Use a distinct unprivileged account or equivalent isolation so that unmediated
metadata operations cannot modify other projects owned by the usual login user.
Landlock alone does not prevent those operations. Verify actual denial of project
secrets and host/session controls before the first model turn.

Any temporary model-provider authentication needs an independent controller
cleanup guard outside the worker process group. Arm it before launch. On queue
exit, explicit manual stop, or crash, stop and verify the dedicated workload, including
detached descendants, before removing its temporary profile. A worker wrapper's
`finally` block alone does not survive SIGTERM/SIGKILL. Prefer a dedicated cgroup
where available; a single-task UID guard must check actual UID/PID/starttime and
verify that no active processes remain. Test abnormal termination explicitly.
Never revoke the shared provider login as cleanup of a temporary task profile.

Tasks run without wall-clock or inactivity deadlines by default. Never enable
a runtime/idle limit or an independent cleanup timer that kills an active worker
unless the user explicitly requests that limit. A cleanup guard waits for actual
workload exit/manual stop, without a maximum duration. Provider quota admission
and actual authentication/configuration errors still apply.


Cleanup receipts must distinguish observed deletion/process absence from claims
about unrelated profile integrity. Claim unchanged shared files only with actual
before/after evidence; otherwise record integrity as not measured.

## Controller workflow (explicit supervised mode only)

1. Codex fixes the scope, architecture, acceptance gates, regression
   invariants, trusted checks, allowed paths, and forbidden actions. Existing
   tests and acceptance gates are controller-owned and a worker may not weaken,
   skip, delete, or rewrite them to obtain a pass.
2. Codex creates a task from the supervised template, records the baseline
   commit, selects either a verified isolated tool boundary or proposal-only
   mode, selects the model from the task's input role, and injects the policy
   block marked `CODEX_SUPERVISED_V1`.
3. GLM explores the allowed area, implements the bounded change, runs focused
   checks, and fixes failures within scope. It must stop rather than invent
   business policy or infer authorization for side effects.
4. GLM returns a compact report: baseline SHA; final SHA when available; exact
   changed files and final diff summary; requirement-to-evidence mapping; exact
   commands with exit codes; and known gaps. It should not paste logs, prompts,
   source context, or repeated reasoning. `STATUS: SUCCESS` is a candidate
   result, never acceptance, integration, or deployment.
5. Codex independently reads the final diff and critical affected code against
   the recorded baseline. Codex checks scope, architecture, security-sensitive
   behavior, regressions, and every requirement rather than accepting the
   worker's summary.
6. Codex reviews each proposed verification command or script before executing
   it, then runs the trusted acceptance checks independently. Worker-created or
   worker-modified verification code is evidence to inspect, not automatically
   trusted validation.
7. Codex alone decides acceptance and integration. Codex owns all deployment,
   production access, credential use, and post-deployment validation.

## Controller continuity and correction loop (explicit supervised mode only)

The Codex controller that starts a supervised task remains responsible for the
same active task until its declared scope and mandatory acceptance are complete.
Launch, planning completion, a worker-stage exit, and `STATUS: SUCCESS` are
intermediate lifecycle events, not final handoffs.

At launch, retain stable pointers to the controller task, worker session or
attempt, baseline, and report path. Await the completed report from that same
attempt, preferably through a lightweight completion notification. Poll through
Codex only when the user explicitly requests continuous monitoring; a standalone
status request permits one compact check. Do not start a duplicate worker merely
because the first attempt is quiet or still running. Retrieve full logs only to
diagnose a concrete failure or missing evidence. An inexpensive external monitor
may wait and notify the controller,
but it cannot accept or certify the result, create correction scope, or silently
acquire broader filesystem, network, credential, deployment, or production
authority.

When an attempt reports `STATUS: SUCCESS`, Codex performs the independent diff
review and trusted acceptance checks above. If that review finds a defect or
missing evidence, Codex creates a bounded correction task linked to the original
task. The correction task records the exact findings, required tests, current
baseline, allowed paths, and unchanged acceptance gates. Codex then waits for
that correction, reviews it, and repeats only the checks needed to establish the
affected acceptance claims. Do not turn the correction loop into repeated
unbounded full-suite runs or new process bureaucracy.

A retry continues the same failed attempt only when the runner's retry contract
can safely resume or repeat it with the same scope and inputs. A correction task
is a new, explicitly linked attempt created after Codex has reviewed an output
and identified concrete changes. Preserve the raw failure status, exit evidence,
and report from every failed attempt. Before retrying, determine whether the
failed command may have produced side effects; never blindly repeat a
non-idempotent or externally visible action.

The controller stops only when the scoped requirements and mandatory acceptance
are complete, the user explicitly stops the work, or a concrete need for
authority or information remains after all safe in-scope work is exhausted.
Ending a planning phase, worker process, monitoring stage, or correction attempt
does not satisfy that stop condition.

## Token-efficiency target

Save Codex tokens by giving GLM the bounded implementation loop and returning
only structured evidence. Prefer precise paths, one baseline SHA, targeted
reads, focused edit/test cycles, and a final compact diff summary. In supervised mode, Codex still reads the complete final diff and validates
critical behavior. In launch-only mode those checks wait for a separate request.

Claims such as `2-3x` or `10x` savings are measurement targets, not promises.
Measure comparable tasks with the same acceptance gates and report Codex input,
output, and cached tokens plus GLM usage, elapsed time, rework, and acceptance
outcome. Reject savings claims that omit failed attempts or reduce validation.
