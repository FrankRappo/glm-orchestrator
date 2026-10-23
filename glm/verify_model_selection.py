#!/usr/bin/env python3
"""Check actual CLI model telemetry before a controller enables UI input."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import stat


class ModelSelectionError(ValueError):
    pass


def verify(path: Path, expected: str) -> dict:
    fd = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
    with os.fdopen(fd, 'r', encoding='utf-8') as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > 64 * 1024 * 1024:
            raise ModelSelectionError('unsafe model telemetry file')
        records = []
        for line in stream:
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                # A currently appended last line is not evidence yet.
                continue
            if isinstance(row, dict) and row.get('type') == 'model_io' and row.get('querySource') == 'main_turn':
                records.append(row)
    if not records:
        raise ModelSelectionError('no completed main-model request; UI input must remain disabled')
    models = {r.get('model', {}).get('modelId') for r in records}
    if models != {expected}:
        raise ModelSelectionError(f'actual model differs from required {expected}; UI input must remain disabled')
    sessions = {r.get('sessionId') for r in records}
    if len(sessions) != 1 or not all(isinstance(s, str) and s.startswith('sess_') for s in sessions):
        raise ModelSelectionError('model telemetry has no single session identity')
    return {'verified': True, 'actualModel': expected, 'sessionId': next(iter(sessions)),
            'completedMainRequests': len(records)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('telemetry', type=Path)
    parser.add_argument('--expected', required=True, choices=['GLM-5.3', 'GLM-5.3-Flash'])
    args = parser.parse_args()
    try:
        proof = verify(args.telemetry, args.expected)
    except (OSError, ModelSelectionError) as exc:
        parser.exit(1, f'model selection not verified: {exc}\n')
    print(json.dumps(proof))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
