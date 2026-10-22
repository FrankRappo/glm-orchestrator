# Логи сессий ZCode/GLM: где лежат и как отличить интерактивную от оркестратора

Дата: 28.09.2026 (после кейса «искали интерактивную сессию, а нашли оркестратора»).

## Где что лежит

| Что | Путь | Особенности |
|---|---|---|
| Полный model I/O (запросы+ответы модели, reasoning, tool calls) | `/root/.zcode/cli/rollout/model-io-sess_<uuid>.jsonl` | Ротация: по факту остаются только последние ~3 файла, старые автоматически удаляются. Живой оркестратор видно по растущему размеру/mtime. |
| Полные транскрипты ВСЕХ сессий (включая удалённые из rollout) | `/root/.zcode/cli/db/db.sqlite`, таблицы `session`, `message`, `part` | Главный источник истории. `session`: id, title, directory, time_created (ms epoch), parent_id. `message.data` / `part.data` — JSON с текстом. |
| Результаты tool calls (артефакты) | `/root/.zcode/cli/artifacts/sess_<uuid>/` | `call_...-tool-result-....json` |
| stdout tool calls (bash) | `/root/.zcode/cli/exec/sess_<uuid>/` | `call_...-stdout.log` |
| Очередь/таски оркестратора | `/work/glm/tasks/<task_dir>/` (`TZ.md`, `reports/report_TXX_*.md`) | Отчёты = прогресс задач; живой статус — `orchestrate status --project <task_dir>` |
| Проектные session-логи (shop) | `/work/shop/session_log_YYYYMMDD.md` | Хронология глазами агента |

## Как отличить интерактивную сессию от оркестратора

Признаки (проверять по `db.sqlite`, таблица `session`):

1. **`title`** — самое надёжное:
   - воркеры оркестратора начинаются с `You are an autonomous GLM coding worker controlled by the...`;
   - интерактивная — обычный текст первого сообщения пользователя (например `Git results and new session log`).
2. **`directory`** (cwd):
   - воркеры — `/work/glm/tasks/<task_dir>`;
   - интерактивная — `/root`, `/work/...` без `/tasks/`;
   - служебные runtime-заглушки — `/tmp/tmp.*` (title `Do not use tools. Reply with exactly GLM_RUNTIME_OK.`) — это НЕ сессии работы, пропустить.
3. **В model-io jsonl**: заголовок `x-zcode-session-type` и `querySource`; tmux-имя воркера вида `glm_<hash>_TXX_<slug>_sup` прямо называет задачу.
4. **Хронология**: интерактивная сессия-родитель создаётся непосредственно перед цепочкой воркеров (пример: `sess_7cfe9233` 23:08–00:13 в `/root` запустила очередь в 00:12; дальше подряд шли воркеры в `/work/glm/tasks/...`).

## Готовые рецепты

Список сессий за сутки (кто интерактивный, кто воркер):

```bash
python3 - <<'EOF'
import sqlite3, datetime
db = sqlite3.connect('file:/root/.zcode/cli/db/db.sqlite?mode=ro', uri=True)
cut = int(datetime.datetime(2026,9,28,0,0,tzinfo=datetime.timezone.utc).timestamp()*1000)
for sid,pid,title,d,tc,tu in db.execute(
    "SELECT id,parent_id,title,directory,time_created,time_updated "
    "FROM session WHERE time_created>=? ORDER BY time_created", (cut,)):
    ts = datetime.datetime.fromtimestamp(tc/1000).strftime('%d.%m %H:%M')
    kind = 'WORKER' if title.startswith('You are an autonomous') else (
           'STUB' if 'GLM_RUNTIME_OK' in (title or '') else 'INTERACTIVE')
    print(f"{ts} {kind:11} {d:50} {sid[:14]} :: {str(title)[:60]}")
EOF
```

Последние сообщения конкретной сессии (даже если rollout-файл удалён):

```bash
python3 - <<'EOF'
import sqlite3, json
sid = 'sess_XXXXXXXX'  # неполный id не подойдёт — взять из списка выше
db = sqlite3.connect('file:/root/.zcode/cli/db/db.sqlite?mode=ro', uri=True)
full = db.execute("SELECT id FROM session WHERE id LIKE ?", (sid+'%',)).fetchone()[0]
for mid, data in db.execute("SELECT id,data FROM message WHERE session_id=? ORDER BY sequence", (full,)):
    role = json.loads(data).get('role')
    for (pdata,) in db.execute("SELECT data FROM part WHERE message_id=?", (mid,)):
        p = json.loads(pdata)
        t = p.get('text','')
        if t.strip() and not t.startswith('<'):
            print(f"--- {role} ---\n{t[:800]}")
EOF
```

Живой хвост оркестратора (если ещё работает):

```bash
ls -lt /root/.zcode/cli/rollout/ | head        # чей файл растёт — тот и живой
tmux ls                                         # воркеры вида glm_<hash>_TXX_*_sup
```

Разбор одной записи jsonl: интересное лежит в `response.text` (ответ модели),
`response.toolCalls` (вызовы инструментов с input), `request.body.messages` (история),
`response.reasoningText` (размышления); поля верхнего уровня — `completedAt`,
`durationMs`, `usage`.
