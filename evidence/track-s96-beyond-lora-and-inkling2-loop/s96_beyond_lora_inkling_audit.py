#!/usr/bin/env python3
"""CI-discovery `*_audit.py` CLI entrypoint for the Track S96 Beyond-LoRA & Inkling-2-Mini bundle."""
from __future__ import annotations

from pathlib import Path
import sys

_THIS_DIR = str(Path(__file__).resolve().parent)
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

import verify_s96_beyond_lora_inkling as _verifier  # noqa: E402


def main(argv: list[str] | tuple[str, ...] | None = None) -> int:
    return _verifier.main(list(argv) if argv is not None else None)


if __name__ == "__main__":
    raise SystemExit(main())
