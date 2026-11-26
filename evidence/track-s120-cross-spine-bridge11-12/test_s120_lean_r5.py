#!/usr/bin/env python3
"""CI-discovered R4/R5 entry point delegating to lean/verify_s120_lean_r5.py.

Ensures Foundation-0/aletheia's evidence-tracks workflow (`evidence/*/test_*.py`)
runs all static R13b, SHA-256, exact integer/Z[sqrt(5)] oracle, and live Lean 4.36.0
proof checks (#49-#50) across all three isolated R4 modes (-I -B, -I -O -B, -I -B -W error).
Zero bare asserts, zero external dependencies.
"""

from __future__ import annotations

from pathlib import Path
import sys

_LEAN_DIR = str((Path(__file__).resolve().parent / "lean").resolve())
if _LEAN_DIR not in sys.path:
    sys.path.insert(0, _LEAN_DIR)

import verify_s120_lean_r5 as _lean_r5


def main(argv: list[str] | None = None) -> int:
    return _lean_r5.main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
