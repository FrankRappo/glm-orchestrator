#!/usr/bin/env python3
"""Shared terminal-report classification for supervisor, queue and status.

Incident (2026-10-24, T14): a worker left exactly the in-progress stub

    # T14 report placeholder — in progress

    STATUS: PARTIAL

after a retryable HTTP 502. Every parser treated that PARTIAL as terminal
before the provider-failure classifiers ran, so recovery never happened.

Contract (docs/REPORT_STATUS_AND_RECOVERY.md):
  SUCCESS/FAIL/BLOCKED  always terminal, with or without a placeholder note.
  PARTIAL               terminal unless the report is ONLY the in-progress
                        placeholder stub (placeholder-in-progress marker,
                        no meaningful body, last status PARTIAL).
  no STATUS line        not a terminal report.

A finished report that mentions "placeholder" or "in progress" inside a
substantive body stays terminal. Bare legacy ``STATUS:`` markers without the
placeholder marker stay terminal. Reports are opened nonblocking with
O_NOFOLLOW and must be regular single-link inodes; FIFOs and linked leaves are
refused rather than classified. Oversized reports retain terminal evidence
from a bounded tail or fail closed when that tail has no STATUS. Their
PARTIAL verdict remains terminal because omitted bytes prevent proving the
"only a stub" condition. A tail cut mid-line drops that incomplete first line
so a suffix cannot masquerade as complete STATUS evidence.
"""

from __future__ import annotations

import argparse
import os
import re
import stat
import sys

MAX_BYTES = 1 << 20  # bound oversized-report scans to the terminal tail

STATUS_RE = re.compile(
    r"^\s*[*#`>\s]*STATUS:\s*(SUCCESS|FAIL|BLOCKED|PARTIAL)[*`\s]*$")
PLACEHOLDER_RE = re.compile(
    r"\breport\s+placeholder\b[^\n]{0,120}?[\u2014\u2013\-:(]\s*\(?\bin\s+progress\)?\s*[.!…]{0,3}\s*$",
    re.IGNORECASE)
HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s+(.*?)\s*#*\s*$")
GENERIC_HEADINGS = {
    "blockers",
    "dependencies",
    "evidence",
    "findings",
    "issues",
    "next",
    "next steps",
    "notes",
    "open issues",
    "progress",
    "remaining",
    "remaining work",
    "report",
    "result",
    "results",
    "status",
    "summary",
    "todo",
    "todos",
    "verification",
}


def _meaningful_body(lines: list[str]) -> bool:
    """True when any line carries content beyond a clear skeleton.

    Headings are preserved as findings when they describe actual outcomes.
    Only generic section labels and report-title forms are treated as
    skeleton structure; this avoids discarding a real heading-only PARTIAL.
    """
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if STATUS_RE.match(stripped):
            continue
        heading = HEADING_RE.match(stripped)
        if heading:
            if PLACEHOLDER_RE.search(stripped):
                continue
            label = re.sub(r"[*_`]", "", heading.group(1))
            label = label.strip(" \t:.-").lower()
            label = re.sub(r"\s+", " ", label)
            if not label or label in GENERIC_HEADINGS:
                continue
            if re.fullmatch(r"(?:t\d+\s+)?(?:completion\s+)?report(?:\s+for\s+t\d+)?",
                            label):
                continue
            return True
        if stripped.startswith("#"):
            continue
        if set(stripped) <= set("-=*_~ |"):
            continue
        return True
    return False


def classify_text(text: str, *, complete: bool = True) -> str:
    """Return SUCCESS|FAIL|BLOCKED|PARTIAL (terminal), UNFINISHED or NONE.

    ``complete`` is false for an oversized report read through a bounded tail.
    Its omitted prefix means the helper cannot prove a placeholder-only stub.
    """
    lines = text.splitlines()
    statuses = [match.group(1) for match in map(STATUS_RE.match, lines) if match]
    if not statuses:
        return "NONE"
    status = statuses[-1]  # last STATUS line wins, like the old grep|tail -1
    if status != "PARTIAL":
        return status
    if (complete and any(PLACEHOLDER_RE.search(line) for line in lines)
            and not _meaningful_body(lines)):
        return "UNFINISHED"
    return "PARTIAL"


def read_report(path: str) -> tuple[str, bool] | None:
    """Read a safe report leaf and whether it was bounded.

    A missing file is simply no report (empty text -> NONE); None means an
    unsafe/unreadable inode or an oversized tail with no terminal evidence.
    O_NONBLOCK ensures a FIFO is inspected and rejected rather than opened
    indefinitely. Oversized files are scanned through a bounded tail; a
    terminal STATUS there wins over any earlier status, while an unknown tail
    is a classifier failure rather than NONE. If the byte cut lands mid-line,
    that partial first line is discarded before classification.
    """
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except FileNotFoundError:
        return "", False
    except OSError as exc:
        print(f"report_status: refusing unsafe/unreadable report {path}: {exc}",
              file=sys.stderr)
        return None
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            print(f"report_status: refusing non-regular or shared inode: {path}",
                  file=sys.stderr)
            return None
        bounded = info.st_size > MAX_BYTES
        with os.fdopen(fd, "rb", closefd=False) as handle:
            if bounded:
                handle.seek(info.st_size - MAX_BYTES - 1)
                boundary = handle.read(1)
                data = handle.read(MAX_BYTES)
                if boundary != b"\n":
                    newline = data.find(b"\n")
                    data = data[newline + 1:] if newline >= 0 else b""
            else:
                data = handle.read(MAX_BYTES)
    finally:
        os.close(fd)
    text = data.decode("utf-8", errors="replace")
    if bounded and not any(
            STATUS_RE.match(line) for line in text.splitlines()):
        print(f"report_status: oversized report has no terminal STATUS in "
              f"its bounded tail, refusing unknown completion: {path}",
              file=sys.stderr)
        return None
    return text, bounded


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("mode", choices=("classify",))
    parser.add_argument("path", help="report file to classify")
    args = parser.parse_args(argv)

    report = read_report(args.path)
    if report is None:
        return 2
    text, bounded = report
    verdict = classify_text(text, complete=not bounded)
    if verdict == "NONE":
        print("NONE")
        return 1
    print(verdict)
    return 0 if verdict in ("SUCCESS", "FAIL", "BLOCKED", "PARTIAL") else 1


if __name__ == "__main__":
    raise SystemExit(main())
