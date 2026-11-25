#!/usr/bin/env python3
"""CI-discovery `*_audit.py` CLI entrypoint for the Track S105 Dual Chow Matroid Tomography bundle."""
from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Sequence

_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

import verify_s105_dual_chow_matroid as _verifier  # noqa: E402


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if "--verify-lean" in args:
        as_json = "--json" in args
        target = _THIS_DIR / "DualChowMatroidTomography.lean"
        for i, a in enumerate(args):
            if a == "--verify-lean" and i + 1 < len(args) and not args[i + 1].startswith("-"):
                target = Path(args[i + 1])
                break
        res = _verifier.verify_lean4_file_live(target)
        if as_json:
            sys.stdout.write(json.dumps(res, sort_keys=True) + "\n")
        else:
            sys.stdout.write(f"LEAN_OK theorems={res['theorems_verified']} sha256={res['lean_source_sha256']}\n")
        return 0
    return _verifier.main(args)


if __name__ == "__main__":
    raise SystemExit(main())
