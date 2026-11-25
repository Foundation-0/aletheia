#!/usr/bin/env python3
"""CI-discovery `*_audit.py` CLI entrypoint for the Track S88 Aletheia Mesh CLI bundle."""
from __future__ import annotations

from pathlib import Path
import sys

_THIS_DIR = str(Path(__file__).resolve().parent)
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

import verify_aletheia_mesh as _verifier  # noqa: E402


def main(argv: list[str] | tuple[str, ...] | None = None) -> int:
    return _verifier.main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
