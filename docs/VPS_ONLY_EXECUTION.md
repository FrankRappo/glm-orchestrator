# VPS-only execution and backup storage

## Owner rule 24.10.2026 — all projects, WSL and Windows

- Application runtimes, test/staging environments, databases, fixtures, containers, dependency installs, builds, benchmarks and browser QA run ONLY on the authorized VPS. Never start a local application stand, database, Docker/Compose service, app node_modules or .next in WSL/Windows; never use local execution as a fallback.
- SQL, dumps, backups, large archives, datasets and bulky build artifacts stay on the VPS. Check size remotely before transfers. Download only small text reports/manifests/control scripts and bounded JPEG evidence unless the owner explicitly requests a particular large local download.
- WSL/Windows are thin control clients: orchestration, documentation, permitted source editing/Git and small artifacts. Project-specific VPS-only source/Git rules remain binding. Local syntax/text checks of control scripts are permitted; application tests and stands are not.
- Use the requested VNC framework or Puppeteer against a visible browser ON the VPS. Preserve shared sessions. Never shut down/restart WSL or the host without the owner's explicit instruction for that exact action.
- Every delegated task records the VPS target, remote application path and remote artifact/backup paths. Missing VPS access means recover the approved transport or report a blocker; it never authorizes a local stand or a local database dump.
- Remove only owner-named or verified task-owned local files after verifying complete remote copies. Preserve unrelated files, older backups and other agents' work. Only an explicit newer owner exception overrides this rule.

The shared launcher preamble applies this policy to every controller. Global ZCode and Codex AGENTS.md files in WSL/Windows and the owner memory notes mirror it. This policy needs no provider/token/settings/SQLite changes.
