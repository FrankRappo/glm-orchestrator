# Codex-supervised GLM workflow

This framework supports two controller modes. **Default: launch-only.** Prepare
the task, launch GLM, verify once that the actual worker and requested model
started (a queue-created message alone is insufficient), then return control to
the user. If startup is not yet known, wait only for the initial start/failure
signal; do not launch duplicates. If startup fails, report the failure rather
than claiming success.

After a verified start, do not keep polling status, read the result, review
patches, run QA, issue corrections, or launch follow-up tasks without a new user
request. GLM continues its already assigned bounded task independently. Do not
stop the worker when returning control. Its operational supervisor, timeout,
quota controls, and exact credential/process cleanup guards remain active;
these are infrastructure responsibilities, not ongoing Codex supervision.

Use **supervised** mode only when the user explicitly requests monitoring,
review/correction, or completion of the entire work. The controller workflow
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

Model routing is project-configurable and must be explicit in each supervised
task. For this workspace, source exploration, implementation, testing, fixes,
and source review use `Model: GLM-5.3` with `Input: text`. Screenshot and image
interpretation use `Model: GLM-5.3-Flash` with `Input: image`; GLM-5.3 is not
used for those inputs.

Keep visual interpretation bounded to visual evidence. A Flash screenshot
finding does not replace Codex's independent source and final-diff review, and
a screenshot verdict alone does not prove functional behavior. Codex still
runs the applicable trusted behavioral checks before acceptance.

## Launch and credential lifetime

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
exit, timeout, hang, or crash, stop and verify the dedicated workload, including
detached descendants, before removing its temporary profile. A worker wrapper's
`finally` block alone does not survive SIGTERM/SIGKILL. Prefer a dedicated cgroup
where available; a single-task UID guard must check actual UID/PID/starttime and
verify that no active processes remain. Test abnormal termination explicitly.
Never revoke the shared provider login as cleanup of a temporary task profile.

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
attempt, baseline, and report path. Await or poll that same attempt at a bounded
interval. Do not start a duplicate worker merely because the first attempt is
quiet or still running. During progress checks, read compact status and report
updates; retrieve full logs only to diagnose a concrete failure or missing
evidence. An inexpensive external monitor may wait and notify the controller,
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
