# GLM Orchestrator Repository

- Execute clear local edit/test/verify work autonomously.
- Keep runtime data under ignored `tasks/`, `logs/`, `limits/`, `worktrees/`, and `artifacts/` paths.
- Never commit ZCode credentials, OAuth tokens, generated provider files, task logs, or customer data.
- Run `bash tests/run_glm_tests.sh`, `orchestrate doctor --live`, and live quota admission before claiming runtime changes complete.
- Keep `common/zcode_coding_plan_quota.mjs` output credential-free; credentials may only be decrypted in memory for official Z.ai/ZCode endpoints.
- Preserve fail-closed quota admission and the single-controller lock contract.
