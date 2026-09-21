# Public release checklist

Status: **complete**. Public `main` contains only reviewed, generic source.
The earlier machine-specific history is retained in a separate private archive,
not in this public repository.

1. Keep the existing local tests and live doctor as regression gates.
2. Remove machine-specific usernames and VPN endpoint IPs from tracked source and documentation.
3. Scan every tracked file for credentials, private identity markers, and runtime artifacts.
4. Replace the short private Git history with one reviewed public snapshot.
5. Push that snapshot, change GitHub visibility, and verify anonymous read access.

The runtime must still resolve the WSL user and preserve the authenticated Max
quota, single-controller lock, and fail-closed admission behavior.

Verification: anonymous repository and README reads succeed; old private
commits are unavailable anonymously; unit/integration tests and live GLM
doctor pass; the active quota watcher still runs from `/work/glm`.
