#!/usr/bin/env python3
"""CI-discovery `*_audit.py` CLI entrypoint for Track S106 Hypersphere & Denominator-pi bundle."""
from __future__ import annotations

from pathlib import Path
import sys

_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

import s106_sphere_denom_pi_oracle as _oracle  # noqa: E402
import verify_s106_sphere_denom_pi as _verifier  # noqa: E402


def main(argv: list[str] | tuple[str, ...] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if "--verify-lean" in args:
        as_json = "--json" in args
        clean_args = [a for a in args if a not in ("--verify-lean", "--json")]
        if clean_args:
            target = Path(clean_args[0])
        else:
            target = _THIS_DIR / _oracle.LEAN_SOURCE_NAME
        try:
            res = _verifier.verify_lean4_file_live(target)
            if as_json:
                sys.stdout.write(_oracle.canonical_json_bytes(res).decode("ascii") + "\n")
            else:
                sys.stdout.write(f"OK {_oracle.LEAN_MODULE} theorems={res['theorems_verified']}\n")
            return 0
        except _verifier.S106Error as exc:
            sys.stderr.write(f"FAIL verify-lean: {exc.code} {exc.detail}\n")
            return 2
    return _verifier.main(args)


if __name__ == "__main__":
    raise SystemExit(main())
