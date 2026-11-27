#!/usr/bin/env python3
"""CI-discovery `*_audit.py` entrypoint for the Track S166 CS-27..CS-29 & EXP-Q46b bundle."""
from __future__ import annotations

from pathlib import Path
import sys
from typing import Sequence

_THIS_DIR = str(Path(__file__).resolve().parent)
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

import verify_s166_cs27_cs29 as _verifier  # noqa: E402


def main(argv: Sequence[str] | None = None) -> int:
    return _verifier.main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
