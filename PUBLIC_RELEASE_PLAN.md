# Public release checklist

1. Keep the existing local tests and live doctor as regression gates.
2. Remove machine-specific usernames and VPN endpoint IPs from tracked source and documentation.
3. Scan every tracked file for credentials, private identity markers, and runtime artifacts.
4. Replace the short private Git history with one reviewed public snapshot.
5. Push that snapshot, change GitHub visibility, and verify anonymous read access.

The runtime must still resolve the WSL user and preserve the authenticated Max
quota, single-controller lock, and fail-closed admission behavior.
