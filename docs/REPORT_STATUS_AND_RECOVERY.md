# Report status classification and transient recovery

Shared contract implemented by `glm/report_status.py` and used identically by
`glm/glm_supervisor.template.sh` (worker supervision), `glm/glm_orchestrator.template.sh`
(queue) and `common/orchestrate.template.sh` (`orchestrate status` display).

## Classification

`python3 glm/report_status.py classify <report>` prints one verdict:

| verdict | meaning |
| --- | --- |
| `SUCCESS` / `FAIL` / `BLOCKED` / `PARTIAL` | terminal report (exit 0) |
| `UNFINISHED` | in-progress placeholder stub, **not** terminal (exit 1) |
| `NONE` | no report file or no STATUS line (exit 1) |
| classifier error | unsafe/unreadable inode, missing helper, or unknown oversized tail (exit 2, no verdict) |

Rules, in order:

1. The last STATUS line in the file wins (`SUCCESS|FAIL|BLOCKED|PARTIAL`,
   same line grammar the templates always used).
2. `SUCCESS`/`FAIL`/`BLOCKED` are always terminal, even if the report also
   contains a placeholder heading.
3. `PARTIAL` is terminal **except** for the clear unfinished case: the report
   contains a `report placeholder — in progress` marker (dash/colon/paren
   variants) and has no meaningful body — nothing besides whitespace, generic
   section headings, report-title headings, rules and the STATUS line. A
   descriptive heading that states a finding is meaningful. That exact stub
   (`# T14 report placeholder — in progress` + `STATUS: PARTIAL`, 58 bytes) is
   the 2026-10-24 incident; it is treated like a missing report.
4. Bare legacy `STATUS:` markers without the placeholder marker stay terminal,
   and a finished report that merely mentions "placeholder" or "in progress"
   inside a substantive body stays terminal.
5. An oversized report cannot be proved to be a placeholder-only stub when
   its earlier body was omitted. Its final `PARTIAL` remains terminal. If the
   bounded cut lands mid-line, the incomplete first line is excluded; a STATUS
   suffix from that line cannot become false terminal evidence.

The helper uses nonblocking `O_NOFOLLOW`, then requires a regular single-link
inode. FIFOs, directories, and symlinked/hardlinked leaves are refused before
any blocking read or classification (exit 2, no verdict). Reports over 1 MiB
are read through a bounded 1 MiB terminal tail. The last STATUS in that tail is
preserved even when an older status lies in the prefix; if the tail has no
STATUS after excluding a mid-line fragment, the helper fails closed rather
than returning NONE.

## Recovery and evidence

When a worker attempt ends:

1. A terminal report keeps its existing terminal priority — no retry, never
   replaying possibly-completed financial/GUI work. Authentication errors and
   quota (429) waits are also unchanged.
2. A classifier error is unknown completion: supervisor and queue stop without
   launching/retrying a worker, writing BLOCKED, or creating `ALL_DONE`, and
   the original unsafe/unknown report is left untouched. Status displays the
   classifier diagnostic and `CLASSIFIER ERROR`.
3. If the report is the unfinished stub, the supervisor preserves a per-attempt
   evidence copy at `state/glm/<task>.attempt-<n>.stub.md` before any later
   attempt or blocked-report write replaces the content. The report file itself
   keeps its inode/owner/mode; only the worker writes to it.
4. Only then do the provider-failure classifiers run. A retryable HTTP
   500/502/503/504, connection reset/timeout together with the stub (or with no
   report) triggers automatic recovery with backoff — even when
   `MAX_RESPAWN=0` / `No-Respawn: true`, which limits ordinary failures only.
   The current attempt's log offset, auth-before-quota-before-transient
   ordering and quota wait caps are unchanged.
5. A stub with exit code 0 is not a completion: without a transient failure it
   is an ordinary failure and the supervisor writes the usual blocked report
   (backing up the stub as `*.incomplete.*` evidence).

## Queue and status behavior

* The queue does not skip a task, log it finished, or create `ALL_DONE` while
  its report is only the stub; the task stays pending and is relaunched.
* `orchestrate status` shows `NO FINAL REPORT — in-progress placeholder stub`
  for such reports instead of a terminal `STATUS: PARTIAL`.

Worker guidance is in the launcher preamble: progress notes are not terminal
reports; a STATUS line belongs in the report only when it is genuinely finished.
