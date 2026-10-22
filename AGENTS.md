# GLM Orchestrator Repository

- Execute clear local edit/test/verify work autonomously.
- For Codex-supervised GLM work, follow [`docs/CODEX_SUPERVISED.md`](docs/CODEX_SUPERVISED.md) and inject the `CODEX_SUPERVISED_V1` policy; worker success is only a candidate result until Codex independently accepts it.
- Default GLM controller mode is launch-only: prepare the task, launch it, verify once that the actual worker/model started, then return control. Do not keep polling, reviewing, fixing, or starting follow-up tasks unless the user explicitly requests supervised mode. Keep operational supervisor and exact cleanup guards active.
- GLM tasks run without wall-clock or inactivity limits by default. Never enable a runtime deadline, idle-kill timer, or time-based credential cleanup guard unless the user explicitly requests that limit. Cleanup follows workload exit or manual stop; it must not cut off active work by elapsed time.
- Preserve all running WSL sessions. Never run `wsl --shutdown`, `wsl --terminate`, restart/stop WslService or LxssManager, kill WSL/vmmem host processes, or reboot/shutdown the host unless the owner explicitly requests that exact disruptive action. Routine troubleshooting, setup, updates, or another project's task do not authorize it. Prepare any required changes and report that activation needs an owner-scheduled restart; do not interrupt shared sessions. Added after the owner confirmed GLM caused the 2026-10-15 WSL shutdown incident.
- Keep runtime data under ignored `tasks/`, `logs/`, `limits/`, `worktrees/`, `projects/`, and `artifacts/` paths.
- Never commit ZCode credentials, OAuth tokens, generated provider files, task logs, or customer data.
- Run `bash tests/run_glm_tests.sh`, `orchestrate doctor --live`, and live quota admission before claiming runtime changes complete.
- Keep `common/zcode_coding_plan_quota.mjs` output credential-free; credentials may only be decrypted in memory for official Z.ai/ZCode endpoints.
- Preserve fail-closed quota admission and the single-controller lock contract.
