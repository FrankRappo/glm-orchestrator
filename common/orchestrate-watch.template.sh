#!/usr/bin/env bash
# orchestrate-watch — держит очередь проекта GLM работающей без человека.
#
# Что делает (цикл каждые WATCH_INTERVAL_SECONDS):
#   1. есть ли в tasks/ таски без терминального STATUS в reports/ — если нет,
#      пишет сводку и сам завершается (работа закончена);
#   2. оркестратор (bin/orchestrate status) RUNNING — просто ждёт;
#   3. встал (квота исчерпана, воркер умер, idle-exit) — смотрит квоту
#      five_hour: хватает (>= WATCH_MIN_QUOTA_PERCENT) → перезапускает
#      orchestrate start; мала → ждёт сброса окна (5ч, катящееся);
#   4. анти-шторм: не больше WATCH_MAX_RESTARTS перезапусков за жизнь.
#
# Использование:
#   bin/orchestrate-watch --project /work/glm/tasks/<проект> [tmux]
# Параметры (env):
#   WATCH_INTERVAL_SECONDS=600   период проверки
#   WATCH_MAX_RESTARTS=8         потолок перезапусков
#   WATCH_MIN_QUOTA_PERCENT=15   порог квоты для перезапуска
#   WATCH_CONTROLLER=manual      контролёр очереди
#   WATCH_MAX_PARALLEL=1         параллель воркеров
#   WATCH_START_ARGS=""          доп. аргументы orchestrate start
#   WATCH_ONCE=0                 1 = один проход и выход (тест/проверка)
#   WATCH_LOG=<project>/logs/orchestrate-watch.log
#
# Запуск на ночь (образец):
#   tmux new-session -d -s glm_watch_<проект> \
#     'bin/orchestrate-watch --project /work/glm/tasks/<проект>'
set -uo pipefail

ROOT="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/.." && pwd)"
ORCH="$ROOT/bin/orchestrate"

PROJECT=""
while [ $# -gt 0 ]; do
  case "$1" in
    --project) PROJECT="${2:?--project требует путь}"; shift 2;;
    -h|--help) grep '^#' "$0" | sed 's/^# \{0,1\}//'; exit 0;;
    *) echo "неизвестный аргумент: $1 (см. --help)" >&2; exit 2;;
  esac
done
[ -n "$PROJECT" ] || { echo "обязателен --project DIR" >&2; exit 2; }
[ -x "$ORCH" ] || { echo "не найден $ORCH" >&2; exit 2; }

INTERVAL="${WATCH_INTERVAL_SECONDS:-600}"
MAX_RESTARTS="${WATCH_MAX_RESTARTS:-8}"
MIN_QUOTA="${WATCH_MIN_QUOTA_PERCENT:-15}"
CONTROLLER="${WATCH_CONTROLLER:-manual}"
MAX_PARALLEL="${WATCH_MAX_PARALLEL:-1}"
START_ARGS="${WATCH_START_ARGS:-}"
ONCE="${WATCH_ONCE:-0}"
LOG="${WATCH_LOG:-$PROJECT/logs/orchestrate-watch.log}"

mkdir -p "$(dirname "$LOG")"
RESTARTS=0
say() { echo "$(date '+%F %T') $*" >> "$LOG"; }

# квота five_hour: «<remaining_percent> <status>» или «-1 err»
quota_read() {
  timeout 60 "$ORCH" limits --json 2>/dev/null | python3 -c '
import json, sys
try:
    d = json.load(sys.stdin)
    b = [x for x in d["buckets"] if x.get("name") == "five_hour"][0]
    print(b["remaining_percent"], b["status"])
except Exception:
    print(-1, "err")'
}

# незакрытые таски: tasks/T*.md без "^STATUS:" в reports/report_<ID>.md
pending_tasks() {
  local t id r
  for t in "$PROJECT"/tasks/T*.md; do
    [ -f "$t" ] || continue
    id="$(basename "$t" | grep -oE '^T[0-9]+' || true)"
    [ -n "$id" ] || continue
    r="$PROJECT/reports/report_${id}.md"
    if [ ! -f "$r" ] || ! grep -q '^STATUS:' "$r"; then
      echo "$id"
    fi
  done
}

orch_running() {
  "$ORCH" status --project "$PROJECT" 2>/dev/null | grep -q 'RUNNING'
}

say "=== orchestrate-watch запущен (pid $$), project=$PROJECT ==="
while :; do
  if [ -z "$(pending_tasks)" ]; then
    say "все таски закрыты — сводка:"
    for r in "$PROJECT"/reports/report_T*.md; do
      [ -f "$r" ] && say "  $(basename "$r"): $(grep -m1 '^STATUS:' "$r" || echo 'нет STATUS')"
    done
    say "=== orchestrate-watch завершён ==="
    exit 0
  fi
  if ! orch_running; then
    if [ "$RESTARTS" -ge "$MAX_RESTARTS" ]; then
      say "СТОП: исчерпан лимит перезапусков ($MAX_RESTARTS) — очередь не трогаю до человека"
      exit 1
    fi
    read -r REM ST <<< "$(quota_read)"
    if [ "$REM" = "-1" ]; then
      say "квота не прочиталась — жду следующий цикл"
    elif awk "BEGIN{exit !($REM >= $MIN_QUOTA)}"; then
      RESTARTS=$((RESTARTS + 1))
      say "оркестратор не RUNNING, квота ${ST}/${REM}% — перезапуск #$RESTARTS"
      QUOTA_RESERVE_PERCENT="${QUOTA_RESERVE_PERCENT:-0}" "$ORCH" start \
        --project "$PROJECT" --controller "$CONTROLLER" \
        --max-parallel "$MAX_PARALLEL" --quota-policy enforce \
        $START_ARGS >> "$LOG" 2>&1
      say "перезапуск #$RESTARTS выполнен"
    else
      say "оркестратор не RUNNING, квота мала (${ST}/${REM}% < ${MIN_QUOTA}%) — жду сброса окна"
    fi
  fi
  [ "$ONCE" = "1" ] && { say "WATCH_ONCE=1 — выхожу после одного прохода"; exit 0; }
  sleep "$INTERVAL"
done
