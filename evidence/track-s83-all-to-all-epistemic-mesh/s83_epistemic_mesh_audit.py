#!/usr/bin/env python3
"""CI-discovery `*_audit.py` CLI entrypoint for the K_8 epistemic mesh bundle."""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys

_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

import s83_epistemic_mesh_oracle as _oracle  # noqa: E402
import verify_s83_epistemic_mesh as _verifier  # noqa: E402


def _has_lean_binary() -> bool:
    try:
        _verifier.resolve_lean_binary()
        return True
    except _oracle.S83Error:
        return False


def _check_without_lean_binary(cert_path: Path, emit_json: bool) -> int:
    """Full deterministic pure-Q replay + R10+ static Lean gate + SHA pin check."""
    res = _verifier.check_certificate_file(cert_path, full_replay=False)
    lean_raw = _verifier.read_regular_bytes_capped(_THIS_DIR / "AllToAllEpistemicMesh.lean", "lean_source", max_bytes=1024 * 1024)
    tc_raw = _verifier.read_regular_bytes_capped(_THIS_DIR / "lean-toolchain", "lean_toolchain", max_bytes=4096)
    lk_raw = _verifier.read_regular_bytes_capped(_THIS_DIR / "lakefile.toml", "lakefile", max_bytes=65536)
    try:
        lean_src = lean_raw.decode("utf-8", "strict")
        tc_str = tc_raw.decode("utf-8", "strict").strip()
    except UnicodeDecodeError as exc:
        raise _oracle.S83Error("INVALID_UTF8", "artifact UTF-8 decode failed") from exc
    _verifier.static_gate_lean4_source(lean_src)
    _oracle.require_ok(tc_str == _oracle.EXPECTED_LEAN_TOOLCHAIN, "TOOLCHAIN_MISMATCH", tc_str)
    rebuilt = _oracle.build_certificate(
        lean_source_sha256=_oracle.sha256_hex(lean_raw),
        toolchain_sha256=_oracle.sha256_hex(tc_raw),
        lakefile_sha256=_oracle.sha256_hex(lk_raw),
    )
    rebuilt_raw = _oracle.canonical_json_bytes(rebuilt)
    disk_raw = _verifier.read_regular_bytes_capped(cert_path, "certificate", max_bytes=_verifier.MAX_JSON_BYTES)
    _oracle.require_ok(rebuilt_raw == disk_raw, "FULL_REPLAY_MISMATCH", "deterministic replay byte mismatch")
    if emit_json:
        res["static_lean_gate_passed"] = True
        res["deterministic_replay_passed"] = True
        res["lean_live"] = "skipped_no_binary"
        sys.stdout.write(_oracle.canonical_json_bytes(res).decode("ascii"))
    else:
        sys.stdout.write(f"OK {res['certificate_sha256']}\n")
    return 0


def main(argv: list[str] | tuple[str, ...] | None = None) -> int:
    if _has_lean_binary() or os.environ.get("ALETHEIA_REQUIRE_LEAN") == "1":
        return _verifier.main(argv)
    try:
        raw_argv = list(sys.argv[1:]) if argv is None else list(argv)
        opts = _verifier._parse_cli_args(raw_argv)
        mode = opts["mode"]
        if mode in ("default", "check"):
            cert_path = _THIS_DIR / "s83_epistemic_mesh_certificate.json" if mode == "default" else Path(opts["target"])
            return _check_without_lean_binary(cert_path, opts["json"])
    except _oracle.S83Error as exc:
        err_obj = {"error": True, "code": exc.code, "detail": exc.detail}
        sys.stderr.write(json.dumps(err_obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n")
        return 2
    return _verifier.main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
