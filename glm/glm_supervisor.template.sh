#!/usr/bin/env bash
# Supervise one headless GLM task: terminal report contract, retries, quota waits.
# Hang autorestart (2026-09-29): worker process может жить, стоя на оборванном
# модельном стриме (инцидент: оба воркера двух очередей молчали 2.5 ч). Сигналы
# активности — ЛЮБОЙ из трёх: CPU дерева воркера вырос / файлы в каталоге очереди
# или логе обновились / свежий rollout-exec файл сессии (ловится по fd процессов).
# Записи самого фреймворка (state/, orch/, logs/) активностью не считаются:
# иначе QUOTA-DEFER в логе оркестратора на каждом poll вечно сбрасывал бы таймер.
# Тишина дольше GLM_HANG_TIMEOUT_SECONDS → kill+respawn (в счёт MAX_RESPAWN).
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TASK="${TASK:?need TASK}"
PROJECT_DIR="${PROJECT_DIR:?need PROJECT_DIR}"
TASK_FILE="${TASK_FILE:?need TASK_FILE}"
REPORT="${REPORT:?need REPORT}"
LOG="${LOG:?need LOG}"
STATE_DIR="${STATE_DIR:?need STATE_DIR}"
PROVIDER_ID="${PROVIDER_ID:?need PROVIDER_ID}"
MODEL_ID="${MODEL_ID:?need MODEL_ID}"
MODE="${MODE:-build}"
CONTROLLER="${CONTROLLER:-manual}"
LAUNCHER="${LAUNCHER:-$ROOT/glm_agent_launcher.template.sh}"
GLM_BIN="${GLM_BIN:-glm}"
MAX_RESPAWN="${MAX_RESPAWN:-3}"
MAX_RUNTIME_SECONDS="${MAX_RUNTIME_SECONDS:-0}"
GLM_RUNTIME_LIMIT_ENABLED="${GLM_RUNTIME_LIMIT_ENABLED:-0}"
GLM_HANG_TIMEOUT_SECONDS="${GLM_HANG_TIMEOUT_SECONDS:-0}"   # opt-in only; no idle deadline by default
POLL="${POLL:-10}"
RATE_LIMIT_WAIT_SECONDS="${RATE_LIMIT_WAIT_SECONDS:-900}"
RATE_LIMIT_MAX_WAITS="${RATE_LIMIT_MAX_WAITS:-32}"
NOTIFY_CMD="${NOTIFY_CMD:-}"
# Provider recovery is enabled by default. Financial/UI side effects still need
# durable guards; a model retry is never permission to replay an operation.
GLM_TRANSIENT_RETRY_SAFE="${GLM_TRANSIENT_RETRY_SAFE:-1}"
GLM_TRANSIENT_MAX_RETRIES="${GLM_TRANSIENT_MAX_RETRIES:-0}" # 0: unlimited
GLM_TRANSIENT_RETRY_DELAY_SECONDS="${GLM_TRANSIENT_RETRY_DELAY_SECONDS:-10}"
GLM_TRANSIENT_RETRY_MAX_DELAY_SECONDS="${GLM_TRANSIENT_RETRY_MAX_DELAY_SECONDS:-60}"
# Shared stub-aware report classification (glm/report_status.py), identical for
# supervisor, queue and status display: a report that is only the
# "report placeholder — in progress" stub is NOT a terminal report.
REPORT_STATUS_HELPER="${REPORT_STATUS_HELPER:-$ROOT/report_status.py}"

STATUS_RE='^[[:space:]]*[*#`>[:space:]]*STATUS:[[:space:]]*(SUCCESS|FAIL|BLOCKED|PARTIAL)[*`[:space:]]*$'
RATE_LIMIT_RE='quota|usage cap|usage limit|rate.?limit|limit reached|too many requests|statusCode:[[:space:]]*429([^0-9]|$)|HTTP(/[0-9.]+)?[[:space:]:]+429([^0-9]|$)|insufficient_quota|resets? at|resetAt'
AUTH_RE='sign in|not authenticated|authentication|unauthorized|coding_plan_required|select a model before continuing|model creation failed'
TRANSIENT_RE='statusCode:[[:space:]]*(500|502|503|504)|HTTP[^[:alnum:]]*(500|502|503|504)|Bad Gateway|Service Unavailable|Gateway Timeout|ECONNRESET|ETIMEDOUT|socket hang up|error=http_response_incomplete'

mkdir -p "$STATE_DIR" "$(dirname "$REPORT")" "$(dirname "$LOG")"
SLOG="$LOG.supervisor"
exec >> "$SLOG" 2>&1

log(){ echo "[$(date '+%F %T')] $*"; }
notify(){ [[ -n "$NOTIFY_CMD" ]] && $NOTIFY_CMD "$*" >/dev/null 2>&1 || true; }

report_verdict(){
  # SUCCESS|FAIL|BLOCKED|PARTIAL (terminal) | UNFINISHED (placeholder stub) |
  # NONE (no STATUS line) | empty (unreadable/unsafe report inode).
  [[ -f "$1" ]] || { printf 'NONE\n'; return 0; }
  python3 "$REPORT_STATUS_HELPER" classify "$1" 2>/dev/null || true
}

report_status(){
  # Terminal statuses only; an UNFINISHED stub behaves like no report at all.
  local verdict
  verdict="$(report_verdict "$REPORT")"
  case "$verdict" in
    SUCCESS|FAIL|BLOCKED|PARTIAL) printf '%s\n' "$verdict" ;;
  esac
  return 0
}

write_blocked_report(){
  local reason="$1"
  [[ -n "$(report_status)" ]] && return 0
  # Isolated workers may write only the pre-created report inode, not siblings
  # in its controller-owned directory. Keep incomplete evidence in STATE_DIR.
  python3 - "$REPORT" "$STATE_DIR" "$TASK" "$reason" "$LOG" "$SLOG" <<'PYREPORT'
import os, stat, sys, tempfile
path, state, task, reason, log, slog = sys.argv[1:]
fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
with os.fdopen(fd, 'r+b') as report:
    info = os.fstat(report.fileno())
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise RuntimeError('unsafe report inode')
    if info.st_size:
        prefix = os.path.basename(path)+'.incomplete.'
        try:
            previous, _ = tempfile.mkstemp(prefix=prefix, dir=os.path.dirname(path))
        except PermissionError:
            previous, _ = tempfile.mkstemp(prefix=prefix, dir=state)
        with os.fdopen(previous, 'wb') as backup:
            while chunk := report.read(65536):
                backup.write(chunk)
    text = f'# {task} blocked\n\n{reason}\n\nSee `{log}` and `{slog}` for evidence.\n\nSTATUS: BLOCKED\n'
    report.seek(0)
    report.truncate()
    report.write(text.encode('utf-8'))
    report.flush()
    os.fsync(report.fileno())
PYREPORT
}

terminate_tree(){
  local pid="$1"
  kill -TERM -- "-$pid" 2>/dev/null || kill -TERM "$pid" 2>/dev/null || true
  sleep 3
  kill -KILL -- "-$pid" 2>/dev/null || kill -KILL "$pid" 2>/dev/null || true
}

# --- hang detection helpers -----------------------------------------------
# CPU дерева процессов (jiffies, utime+stime): зависший на стриме воркер не
# ест CPU вовсе; здоровый — ест сам или через детей (chromium/node/bash-инструменты).
tree_cpu_jiffies(){
  local root="$1" pid p stat_line rest ppid utime stime acc=0
  local -a queue=("$root")
  local -A seen=()
  while (( ${#queue[@]} )); do
    pid="${queue[0]}"; queue=("${queue[@]:1}")
    [[ -z "${seen[$pid]:-}" ]] || continue
    seen[$pid]=1
    stat_line="$(cat "/proc/$pid/stat" 2>/dev/null)" || continue
    rest="${stat_line##*) }"
    read -r _ ppid _ _ _ _ _ _ _ _ _ utime stime _ <<< "$rest"
    acc=$(( acc + utime + stime ))
    while read -r p; do queue+=("$p"); done < <(pgrep -P "$pid" 2>/dev/null)
  done
  echo "$acc"
}

# Свежий mtime rollout/exec файла сессии, если дерево воркера держит его открытым
# (CLI дозаписывает файл при каждом модельном вызове — между вызовами закрывает).
rollout_fd_mtime(){
  local pgid="$1" pid f target t best=0
  for pid in $(pgrep -g "$pgid" 2>/dev/null); do
    for f in /proc/$pid/fd/*; do
      target="$(readlink "$f" 2>/dev/null)" || continue
      case "$target" in
        */cli/rollout/model-io-sess_*|*/cli/exec/sess_*) ;;
        *) continue ;;
      esac
      t="$(stat -Lc %Y "$f" 2>/dev/null)" || continue
      (( t > best )) && best=$t
    done
  done
  echo "$best"
}

# Самый свежий файл под каталогом (артефакты долгих tool-вызовов: генерации,
# скриншоты, отчёты) — второй сигнал активности помимо модельных вызовов.
# state/, orch/ и logs/ (включая STATE_DIR и каталог LOG) исключаются: их пишут
# супервизор и оркестратор, а не воркер; LOG воркера проверяется отдельно.
newest_mtime_under(){
  local dir="$1" extra t
  local -a prune=()
  shift
  for extra in "$@"; do
    [[ -n "$extra" && -d "$extra" ]] && prune+=( -o -path "$extra" )
  done
  t="$(find "$dir" \( -path "$dir/state" -o -path "$dir/orch" "${prune[@]}" \) -prune \
        -o -type f -printf '%T@\n' 2>/dev/null | sort -rn | head -1)"
  echo "${t%%.*}"
}

rate_limited(){ tail -n 120 "$LOG" 2>/dev/null | grep -aiE "$RATE_LIMIT_RE" | tail -1; }
auth_blocked(){ tail -n 120 "$LOG" 2>/dev/null | grep -aiE "$AUTH_RE" | tail -1; }
attempt_log(){ tail -c "+$((attempt_log_offset + 1))" "$LOG" 2>/dev/null; }

attempt=0
rate_waits=0
transient_waits=0
ordinary_failures=0
while :; do
  attempt=$((attempt + 1))
  started=$(date +%s)
  printf '%s\n' "$started" > "$STATE_DIR/$TASK.started"
  : > "$STATE_DIR/$TASK.running"
  log "launch attempt=$attempt task=$TASK model=$MODEL_ID mode=$MODE"
  attempt_log_offset="$(stat -c %s "$LOG" 2>/dev/null || echo 0)"

  setsid env \
    PROJECT_DIR="$PROJECT_DIR" TASK="$TASK" TASK_FILE="$TASK_FILE" REPORT="$REPORT" \
    LOG="$LOG" STATE_DIR="$STATE_DIR" PROVIDER_ID="$PROVIDER_ID" MODEL_ID="$MODEL_ID" \
    MODE="$MODE" CONTROLLER="$CONTROLLER" GLM_BIN="$GLM_BIN" \
    USAGE_LEDGER="${USAGE_LEDGER:-$(dirname "$LOG")/glm_usage.jsonl}" \
    GLM_DISALLOWED_TOOLS="${GLM_DISALLOWED_TOOLS:-}" \
    GLM_SUPERVISOR_ATTEMPT="$attempt" \
    bash "$LAUNCHER" &
  pid=$!
  printf '%s\n' "$pid" > "$STATE_DIR/$TASK.pid"

  timed_out=0
  hang_killed=0
  last_active="$started"
  last_cpu=-1
  while kill -0 "$pid" 2>/dev/null; do
    now=$(date +%s)
    if [[ "$GLM_RUNTIME_LIMIT_ENABLED" == 1 ]] && (( MAX_RUNTIME_SECONDS > 0 && now - started >= MAX_RUNTIME_SECONDS )); then
      timed_out=1
      log "runtime limit ${MAX_RUNTIME_SECONDS}s reached; terminating pgid=$pid"
      terminate_tree "$pid"
      break
    fi
    if (( GLM_HANG_TIMEOUT_SECONDS > 0 )); then
      activity=0
      t="$(stat -c %Y "$LOG" 2>/dev/null || echo 0)"; (( t > activity )) && activity=$t
      t="$(newest_mtime_under "$PROJECT_DIR" "$STATE_DIR" "$(dirname "$LOG")")"; (( t > activity )) && activity=$t
      t="$(rollout_fd_mtime "$pid")"; (( t > activity )) && activity=$t
      cpu="$(tree_cpu_jiffies "$pid")"
      if (( last_cpu >= 0 && cpu > last_cpu )); then activity=$now; fi
      last_cpu="$cpu"
      (( activity > last_active )) && last_active=$activity
      if (( now - last_active >= GLM_HANG_TIMEOUT_SECONDS )); then
        hang_killed=1
        log "HANG: no activity $((now - last_active))s (cpu=${cpu}j) ≥ ${GLM_HANG_TIMEOUT_SECONDS}s; terminating pgid=$pid"
        notify "GLM task $TASK hung $((now - last_active))s+ without activity; restarting"
        terminate_tree "$pid"
        break
      fi
    fi
    sleep "$POLL"
  done
  wait "$pid" 2>/dev/null
  rc=$?
  # An exited CLI may leave tool/MCP descendants behind. Finish that exact
  # attempt's process group before another model can act on the same task.
  if kill -0 -- "-$pid" 2>/dev/null; then
    terminate_tree "$pid"
  fi
  rm -f "$STATE_DIR/$TASK.running" "$STATE_DIR/$TASK.pid"
  : > "$STATE_DIR/$TASK.finished"

  verdict="$(report_verdict "$REPORT")"
  case "$verdict" in
    SUCCESS|FAIL|BLOCKED|PARTIAL)
      log "terminal report task=$TASK status=$verdict rc=$rc"
      [[ "$verdict" == SUCCESS ]] && exit 0
      exit 1
      ;;
  esac
  if [[ "$verdict" == UNFINISHED ]]; then
    # Not a terminal report: preserve the stub per attempt before the retry
    # (or a blocked report) clears/replaces it. The report leaf itself keeps
    # its inode/owner/mode; only evidence copies land in STATE_DIR.
    stub_evidence="$STATE_DIR/$TASK.attempt-$attempt.stub.md"
    if cat -- "$REPORT" > "$stub_evidence.tmp" 2>/dev/null; then
      mv -f -- "$stub_evidence.tmp" "$stub_evidence"
      log "unfinished placeholder stub task=$TASK attempt=$attempt; treated as no report; evidence saved to $stub_evidence"
    else
      rm -f -- "$stub_evidence.tmp"
      log "unfinished placeholder stub task=$TASK attempt=$attempt; treated as no report; evidence copy failed"
    fi
  fi

  auth_line="$(attempt_log | grep -aiE "$AUTH_RE" | tail -1 || true)"
  if [[ -n "$auth_line" ]]; then
    log "credential/configuration blocker: $auth_line"
    write_blocked_report "GLM CLI is not authenticated or has no usable model: $auth_line"
    notify "GLM task $TASK blocked by authentication/model configuration"
    exit 2
  fi

  limit_line="$(attempt_log | grep -aiE "$RATE_LIMIT_RE" | tail -1 || true)"
  if [[ -n "$limit_line" ]]; then
    rate_waits=$((rate_waits + 1))
    if (( rate_waits > RATE_LIMIT_MAX_WAITS )); then
      write_blocked_report "GLM quota remained unavailable after $RATE_LIMIT_MAX_WAITS waits."
      log "quota wait cap reached"
      exit 2
    fi
    log "quota marker: $limit_line; wait ${RATE_LIMIT_WAIT_SECONDS}s ($rate_waits/$RATE_LIMIT_MAX_WAITS)"
    notify "GLM task $TASK waiting for quota reset"
    sleep "$RATE_LIMIT_WAIT_SECONDS"
    continue
  fi

  transient_line="$(attempt_log | grep -aiE "$TRANSIENT_RE" | tail -1 || true)"
  if [[ "$GLM_TRANSIENT_RETRY_SAFE" == 1 && -n "$transient_line" ]] && (( rc != 0 )); then
    transient_waits=$((transient_waits + 1))
    if (( GLM_TRANSIENT_MAX_RETRIES > 0 && transient_waits > GLM_TRANSIENT_MAX_RETRIES )); then
      write_blocked_report "Transient provider retry cap reached after $transient_waits failures."
      log "transient provider retry cap reached"
      exit 1
    fi
    exponent=$(( transient_waits - 1 )); (( exponent > 6 )) && exponent=6
    delay=$(( GLM_TRANSIENT_RETRY_DELAY_SECONDS * (1 << exponent) ))
    (( delay > GLM_TRANSIENT_RETRY_MAX_DELAY_SECONDS )) && delay=$GLM_TRANSIENT_RETRY_MAX_DELAY_SECONDS
    log "transient provider failure rc=$rc; retry=$transient_waits backoff=${delay}s; scope and task unchanged"
    sleep "$delay"
    continue
  fi

  ordinary_failures=$((ordinary_failures + 1))
  if (( ordinary_failures > MAX_RESPAWN )); then
    reason="GLM worker failed without a terminal report after $attempt attempts (last rc=$rc"
    [[ "$timed_out" == 1 ]] && reason+=", runtime timeout"
    [[ "$hang_killed" == 1 ]] && reason+=", hang timeout ${GLM_HANG_TIMEOUT_SECONDS}s"
    reason+=")."
    write_blocked_report "$reason"
    log "$reason"
    exit 1
  fi
  log "non-quota failure rc=$rc; retrying ($attempt/$MAX_RESPAWN)"
  sleep 5
done
