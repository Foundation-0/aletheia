#!/usr/bin/env python3
"""CI-discovery `*_audit.py` CLI entrypoint for the Track S84 K_16 higher-order epistemic mesh."""
from __future__ import annotations

from pathlib import Path
import sys

_THIS_DIR = str(Path(__file__).resolve().parent)
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

import verify_s84_higher_order_k16 as _verifier  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    return _verifier.main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
