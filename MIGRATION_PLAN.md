# Migration plan: standalone GLM orchestrator repository

Status: **complete and verified**. The standalone remote is
`https://github.com/FrankRappo/glm-orchestrator`.

1. Preserve existing runtime directories and ignore them from Git.
2. Copy the tested GLM/common source, tests, and runbook from `/work/settings`.
3. Replace hard-coded `/work/settings` paths with `/work/glm` paths.
4. Initialize a standalone Git repository owned by a regular WSL user and commit the baseline.
5. Repoint `/usr/local/bin/orchestrate` and restart the quota watcher from this repository.
6. Run unit, fake integration, live quota, live model, token-usage, and VPN gates.
7. Remove the migrated GLM source from `/work/settings`, update its layout docs, and commit the deletion.

Stop condition: all commands resolve under `/work/glm`, live gates pass, both repositories are clean,
and no active process references the legacy source locations.

Verification (2026-09-21): fake integration tests, GLM live doctor,
authenticated Max quota admission, Windows-to-WSL entrypoints, token usage
fallback, Codex regression tests, and fail-closed VPN check passed. System
entrypoints and the quota watcher resolve only under `/work/glm`.
