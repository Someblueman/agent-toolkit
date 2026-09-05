#!/usr/bin/env python3
"""stdin: Codex lifecycle JSON; stdout: Codex hook JSON. --help prints usage."""

import importlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "tools/quality"), str(Path(__file__).resolve().parent)]
main = importlib.import_module("quality_hook").main

if "--help" in sys.argv:
    print(__doc__)
else:
    print(json.dumps(main(sys.stdin)))
