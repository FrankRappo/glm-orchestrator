# Совместная работа с GLM/ZCode

Этот каталог предназначен для контролируемого делегирования задач агенту
GLM/ZCode из WSL. Контролёром запуска может быть Codex, GLM или пользователь.
Исполняемый фреймворк расположен в `/work/glm/common` и
`/work/glm/glm`; этот отдельный Git-репозиторий содержит исходники,
тесты и документацию. Runtime-данные и рабочие области исключены из Git.

GitHub-репозиторий: `https://github.com/FrankRappo/glm-orchestrator`.
Публичная историческая feature-ветка старого фреймворка
не используется для обновления GLM.

## Текущая конфигурация

- Среда: WSL2, Ubuntu 24.04.
- Windows-приложение: ZCode 3.14.1.
- Встроенный CLI: `zcode` 0.16.9.
- Команда в WSL: `glm`.
- Native-обёртка: `/usr/local/bin/glm-linux`.
- Windows fallback: `/usr/local/bin/glm-win`.
- Ссылка в `PATH`: `/usr/local/bin/glm` → `bin/glm` (чат без аргументов,
  остальные команды передаются штатному `glm-linux`).
- Runtime GLM: Linux Electron/Node 24.14.0 из официального ZCode 3.14.1.
- Терминальный мультиплексор: tmux 3.4.

Проверенные базовые команды:

```bash
glm --version
glm doctor --json --no-color
orchestrate limits
orchestrate usage --project /work/<project>
orchestrate doctor
```

`orchestrate limits` напрямую читает авторизованные квоты Max Coding Plan:
5-часовые и недельные credits, процент использованного и оставшегося,
время сброса и официальный MCP-пул. `orchestrate limits --json` возвращает
`remaining_percent` для каждого лимита.

`glm` является нативным Linux-процессом внутри WSL и работает с обычными
Linux-путями `/work/...`. Сейчас весь WSL-трафик защищён профилем
VPN over SSH, поэтому runtime использует текущий WSL VPN exit. tmux на
маршрутизацию не влияет.

Проверка маршрута в текущий момент:

```bash
# Публичный IP нативного runtime, которым запускается GLM
runuser -u "$(getent passwd 1000 | cut -d: -f1)" -- \
  env ELECTRON_RUN_AS_NODE=1 /opt/ZCode/zcode -e \
  'fetch("https://api.ipify.org").then(r=>r.text()).then(console.log)'

# Публичный IP обычного процесса WSL
curl -4 https://api.ipify.org
```

Не следует фиксировать IP в настройках: VPN и правила sing-box могут изменить
маршрут. Перед задачами, чувствительными к региону или IP, проверка выполняется
повторно.

## Каталоги

```text
/work/glm/
├── common/         # dispatcher, квоты и token ledger
├── glm/            # controller, worker, supervisor и model policy
├── docs/           # подробный runbook
├── tests/          # unit и fake integration tests
├── bin/            # стабильные entrypoints
├── tasks/          # runtime: подготовленные задания (gitignored)
├── logs/           # runtime: журналы запусков (gitignored)
├── limits/         # runtime: снимки квот (gitignored)
├── worktrees/      # runtime: изолированные git worktree (gitignored)
└── artifacts/      # runtime: отчёты и патчи (gitignored)
```

## Основные команды

Для интерактивного разговора без очереди задач см.
[`INTERACTIVE_START.txt`](INTERACTIVE_START.txt). В текущей установке
`glm tui` не работает из-за отсутствующего `@zcode/tui`, поэтому доступен
`bin/glm-chat` — многоходовый терминальный диалог через headless GLM.
Для короткой команды из любого каталога ссылка должна указывать на
диспетчер `bin/glm`:

```bash
sudo ln -sfn /work/glm/bin/glm /usr/local/bin/glm
cd /work/my-project && glm
glm chat --project /work/my-project
# Полный доступ к инструментам без подтверждений — только явно:
glm chat --project /work/my-project --mode yolo
```

GLM сам пишет задачи и управляет очередью:

```bash
orchestrate start --project /work/<project> --controller glm \
  --goal /work/<project>/GOAL.md --quota-policy enforce
```

Codex пишет задачи, GLM исполняет:

```bash
orchestrate start --project /work/<project> --controller codex \
  --quota-policy enforce
```

Статус и лимиты:

```bash
orchestrate status --project /work/<project>
orchestrate limits
orchestrate doctor --live
```

### Запуск из Windows

Фреймворк остаётся Linux-процессом, но команды можно вводить в Windows
PowerShell/Windows Terminal через `wsl.exe`:

Замените `YOUR_WSL_USER` на имя вашего обычного пользователя WSL.

```powershell
wsl.exe -d Ubuntu-24.04 -u YOUR_WSL_USER -- orchestrate limits
wsl.exe -d Ubuntu-24.04 -u YOUR_WSL_USER -- orchestrate usage --project /work/project

wsl.exe -d Ubuntu-24.04 -u YOUR_WSL_USER -- orchestrate start `
  --project /work/project `
  --controller glm `
  --goal /work/project/GOAL.md
```

Даже при таком запуске `glm`, tmux и инструменты работают внутри WSL и идут
через WSL VPN. В аргументах используются пути `/work/...`, а не UNC-пути.
`glm-win` сохранён только как диагностический Windows fallback.

## Модель работы

### 1. Постановка задачи

Пользователь передаёт одну или несколько задач. Для каждой задачи Codex
определяет:

- ожидаемый результат;
- разрешённые файлы и компоненты;
- ограничения и запрещённые действия;
- критерии приёмки;
- команды проверки.

Задание сохраняется в `<project>/tasks/T<NN>_<slug>.md` по шаблону
`/work/glm/glm/task.template.md`.

### 2. Подготовка рабочей области

Перед делегированием Codex:

1. проверяет `git status` и сохраняет пользовательские изменения;
2. запускает базовые тесты, если они доступны;
3. создаёт отдельную ветку и git worktree для независимой задачи;
4. не назначает двум агентам одновременную запись в один worktree.

Рекомендуемая схема:

```bash
git -C /path/to/repo worktree add \
  /work/glm/worktrees/<task-id> -b glm/<task-id>
```

### 3. Передача задачи GLM

Штатный путь — через dispatcher. Автономные headless workers используют
`yolo`, поскольку интерактивные `build`/`edit` требуют permission client.

```bash
orchestrate start --project /work/<project> --controller codex \
  --quota-policy enforce
```

Для продолжения сессии применяются штатные параметры:

```bash
glm --cwd "$TREE" --continue
glm --cwd "$TREE" --resume <session-id>
```

### 4. Работа через tmux

Каждая длительная задача получает отдельную именованную сессию:

```bash
orchestrate start --project /work/<project> --controller glm \
  --goal /work/<project>/GOAL.md --quota-policy enforce
```

Наблюдение и получение результата:

```bash
orchestrate status --project /work/<project>
orchestrate attach --project /work/<project>
orchestrate usage --project /work/<project>
```

tmux используется как средство запуска, наблюдения и восстановления терминала.
Он не делает GLM встроенным Codex-subagent: интеграция осуществляется через
CLI, файлы, git и проверяемые результаты.

### 5. Проверка Codex

Результат GLM не принимается автоматически. Codex обязан:

1. изучить diff и проверить соблюдение области задачи;
2. исключить потерю пользовательских изменений;
3. запустить целевые тесты;
4. затем выполнить доступные lint, typecheck, build и статический анализ;
5. исправить найденные проблемы либо вернуть GLM конкретное повторное задание;
6. интегрировать ветку только после успешной проверки.

### 6. Отчёт пользователю

Финальный отчёт содержит:

- выполненные задачи;
- изменённые файлы;
- результаты тестов и проверок;
- оставшиеся риски или непроверенные области;
- сведения о ветках/worktree, если они ещё нужны.

## Правила безопасности

- Не передавать API-ключи, токены, пароли и содержимое credential-файлов в
  prompt или журналы.
- Не выполнять destructive-команды, force-push, публикацию и production
  deploy без явного задания.
- Не обходить тесты ради формального завершения.
- Не позволять параллельным исполнителям менять одни и те же файлы.
- Не считать текстовый ответ GLM доказательством: доказательством служат diff,
  тесты и воспроизводимые команды.
- Для внешнего доступа учитывать, что Windows GLM и нативный WSL могут иметь
  разные публичные IP.

## Текущие ограничения

На 2026-09-24 проверено:

| Возможность | Статус |
| --- | --- |
| `glm --version` | работает |
| `glm doctor --json` | работает |
| запуск команды внутри tmux | работает |
| интерактивный `glm tui` | в текущей установке отсутствует `@zcode/tui`; используйте `bin/glm-chat` |
| headless model prompt | авторизован, `orchestrate doctor --live` проходит |
| GLM-5.3 / Flash / 5.2 / 5-Turbo | live-проверка проходит |
| 5h / weekly / MCP quota | читаются из authenticated API |
| token ledger | работает через `orchestrate usage` |

TUI оркестратору не требуется: рабочий путь использует штатный headless
`--prompt`. Тот же headless-путь использует `bin/glm-chat` для диалога.
Нельзя запускать реальную задачу, пока `orchestrate doctor --live`
не завершится успешно.
