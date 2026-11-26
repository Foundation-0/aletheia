#!/usr/bin/env python3
"""CI-discovery `*_audit.py` CLI entrypoint for Track S110 Geosphere Weft Conservation bundle."""
from __future__ import annotations

from pathlib import Path
import sys
from typing import Sequence

_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

import s110_geosphere_weft_oracle as _oracle  # noqa: E402
import verify_s110_geosphere_weft_conservation as _verifier  # noqa: E402


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if "--standalone" in args:
        cert = _oracle.build_certificate()
        sys.stdout.write(_oracle.canonical_json_bytes(cert).decode("utf-8") + "\n")
        return 0
    if "--verify-pins" in args:
        non_flags = [a for a in args if not a.startswith("--")]
        if not non_flags:
            for parent in _THIS_DIR.parents:
                sample = parent / "notes/sphere_pi_forces_2026_11_25/PREREG_S110_GEOSPHERE_PLANETARY_ARCHITECTURE.md"
                if sample.is_file():
                    flags = [a for a in args if a != "--verify-pins"]
                    return _verifier.main(["--verify-pins", str(parent)] + flags)
    return _verifier.main(args)


if __name__ == "__main__":
    raise SystemExit(main())
