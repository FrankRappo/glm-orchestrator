# Задача `<task-id>`

> Общий шаблон для ручной подготовки. Для автоматической очереди используйте
> [`glm/task.template.md`](glm/task.template.md): там обязательные заголовки
> модели/сложности, имя отчёта и финальный `STATUS`.

## Цель

Одно проверяемое предложение с ожидаемым результатом.

## Репозиторий и рабочая область

- Репозиторий: `<absolute-path>`
- Worktree: `/work/glm/worktrees/<task-id>`
- Ветка: `glm/<task-id>`

## Разрешённая область изменений

- `<file-or-directory>`

## Запрещено

- Не изменять файлы вне указанной области.
- Не удалять и не перезаписывать пользовательские изменения.
- Не добавлять зависимости без явной необходимости в задаче.
- Не выполнять публикацию, deploy, force-push или destructive-команды.

## Требования

1. `<requirement>`
2. `<requirement>`

## Критерии приёмки

- [ ] `<observable-result>`
- [ ] `<observable-result>`

## Проверки

```bash
<targeted-test-command>
<lint-command>
<typecheck-or-build-command>
```

## Формат ответа GLM

Верни:

1. краткое описание реализации;
2. список изменённых файлов;
3. выполненные команды проверки и их результаты;
4. оставшиеся риски и ограничения.


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
