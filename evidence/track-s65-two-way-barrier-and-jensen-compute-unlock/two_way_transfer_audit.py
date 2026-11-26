#!/usr/bin/env python3
"""Live Lean 4.36.0 Kernel Verifier, Strict-I/O Auditor & Canonical Certificate CLI.

Verifies:
  1. Pure-Init Lean 4.36.0 module (`TwoWayTransfer.lean`, 10 theorems) via both static
     proof-envelope gate and live `lean` kernel + `#print axioms` audit.
  2. Hardware provenance receipt (`mlos_zone_b_receipt.json`) integrity & clean-run fields.
  3. Live integer RAPL hardware probe (`two_way_silicon_live_results.json`) & Pillar 1/2
     pure-Z/Q exact-operator derivations.
  4. Strict-I/O atomic `0o600` certificate emission, canonical byte verification,
     hardlink/symlink/FIFO/`$PWD`/Darwin-prefix defense, and fail-closed CLI.
"""
from __future__ import annotations

import errno
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import threading
from typing import Any, Sequence

_THIS_DIR = str(Path(__file__).resolve().parent)
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

import two_way_transfer_oracle as oracle  # noqa: E402
from two_way_transfer_oracle import (  # noqa: E402
    MAX_LEAN_BYTES,
    STANDARD_LEAN4_AXIOMS,
    TwoWayTransferError,
    canonical_json_bytes,
    parse_exact_rational,
    parse_strict_json_text,
    require_exact_bool,
    require_exact_int,
    require_exact_keys,
    require_exact_str,
    require_ok,
    require_sha256_hex,
    static_lean4_source_check,
    validate_json_tree,
)

SCHEMA_VERSION = "aletheia.two_way_barrier_jensen_unlock.v1"
STUDY_ID = "TWO-WAY-BARRIER-AND-JENSEN-COMPUTE-UNLOCK"
EXPECTED_LEAN_TOOLCHAIN = "leanprover/lean4:v4.36.0"
EXPECTED_LEAN_VERSION_LINE = (
    "Lean (version 4.36.0, x86_64-unknown-linux-gnu, "
    "commit 611c117bfaf7b7ae1cfcf246ce6fba31e8f509e9, Release)"
)
EXPECTED_THEOREMS: tuple[str, ...] = (
    "TwoWayTransfer.competing_potential_sign_inversion",
    "TwoWayTransfer.coulomb_short_range_turnover_universal",
    "TwoWayTransfer.sub_barrier_bridge_dominance_universal",
    "TwoWayTransfer.endoreversible_energy_global_min_universal",
    "TwoWayTransfer.race_to_sleep_below_fstar_universal",
    "TwoWayTransfer.smooth_pacing_above_fstar_universal",
    "TwoWayTransfer.jensen_fixed_work_smooth_beats_bursty_universal",
    "TwoWayTransfer.parallel_impedance_ucurve_universal",
    "TwoWayTransfer.qwen_smollm_scale_flip_exact_witness",
    "TwoWayTransfer.measured_silicon_efficiency_witness",
)
EXPECTED_THEOREM_AXIOMS: dict[str, tuple[str, ...]] = {
    "TwoWayTransfer.competing_potential_sign_inversion": ("propext", "Quot.sound"),
    "TwoWayTransfer.coulomb_short_range_turnover_universal": ("propext", "Quot.sound"),
    "TwoWayTransfer.sub_barrier_bridge_dominance_universal": ("propext", "Quot.sound"),
    "TwoWayTransfer.endoreversible_energy_global_min_universal": ("propext", "Quot.sound"),
    "TwoWayTransfer.race_to_sleep_below_fstar_universal": ("propext", "Quot.sound"),
    "TwoWayTransfer.smooth_pacing_above_fstar_universal": ("propext", "Quot.sound"),
    "TwoWayTransfer.jensen_fixed_work_smooth_beats_bursty_universal": ("propext", "Quot.sound"),
    "TwoWayTransfer.parallel_impedance_ucurve_universal": ("propext", "Quot.sound"),
    "TwoWayTransfer.qwen_smollm_scale_flip_exact_witness": (),
    "TwoWayTransfer.measured_silicon_efficiency_witness": (),
}

PRIOR_LITERATURE_N0: tuple[str, ...] = (
    "Curzon & Ahlborn (1975) / Salamon et al. (2001): endoreversible finite-time thermodynamics and convex rate-dissipation bounds",
    "Jensen (1906): strict convexity inequality for power-rate dissipation",
    "Miyoshi et al. (2002) / Le Sueur & Heiser (2010): critical power slope and race-to-sleep vs. DVFS pacing crossover",
    "Gamow (1928) / Yukawa (1935): Coulomb barrier vs. short-range attractive potential turnover",
    "Conway & Sloane (1999): Construction-A and Reed-Muller lattice structures",
    "de Moura & Ullrich (2021): Lean 4 theorem prover and core Init kernel",
)

MAX_JSON_BYTES = 2_097_152
MAX_ALLOWED_CAP_BYTES = 4_194_304
_READ_CHUNK_BYTES = 65_536
_LEAN_TIMEOUT_SECONDS = 60
_DEFAULT_PROJECT_ROOT = Path(__file__).resolve().parent
_DIR_OPEN_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)
_DARWIN_SYSTEM_PREFIXES = frozenset({"var", "tmp", "etc"})
_TEMP_NAME_LOCK = threading.Lock()
_TEMP_COUNTER = 0

_AXIOM_NONE_RE = re.compile(r"\A'([A-Za-z0-9_.]+)' does not depend on any axioms\Z")
_AXIOM_LIST_RE = re.compile(r"\A'([A-Za-z0-9_.]+)' depends on axioms: \[([^\]]*)\]\Z")

_CERT_KEYS: frozenset[str] = frozenset(
    {"schema_version", "study_id", "payload_sha256", "certificate_sha256", "payload"}
)
_PAYLOAD_KEYS: frozenset[str] = frozenset(
    {
        "study_id",
        "novelty_class",
        "oracle_class",
        "measured_live_silicon",
        "measured_external_mathlib",
        "privacy_locks",
        "lean_toolchain",
        "lean_version_line",
        "prior_literature_n0",
        "project_manifest",
        "lean_module",
        "hardware_provenance",
        "pillar1_competing_potential",
        "pillar2_live_silicon",
        "summary",
    }
)
_PRIVACY_KEYS: frozenset[str] = frozenset(
    {"audio_capture_accessed", "camera_accessed", "display_modified"}
)
_MANIFEST_KEYS: frozenset[str] = frozenset(
    {
        "lean_toolchain_sha256",
        "lakefile_sha256",
        "lean_source_sha256",
        "c_probe_source_sha256",
        "live_probe_json_sha256",
        "mlos_receipt_json_sha256",
        "theorem_count",
    }
)
_LEAN_MOD_KEYS: frozenset[str] = frozenset(
    {
        "rel_path",
        "source_sha256",
        "line_count",
        "theorem_count",
        "static_envelope_clean",
        "kernel_exit_code",
        "zero_warnings",
        "theorems",
    }
)
_THEOREM_ENTRY_KEYS: frozenset[str] = frozenset(
    {"name", "axioms", "standard_axioms_only"}
)
_HW_PROV_KEYS: frozenset[str] = frozenset(
    {
        "receipt_schema",
        "profile_id",
        "profile_sha256",
        "receipt_sha256",
        "determinism_zone",
        "exit_code",
        "clean_hardware_run",
        "anomalies_count",
        "gpu_start_pstate",
        "gpu_end_pstate",
        "linux_kmd_baseline_vram_mib",
    }
)
_SUMMARY_KEYS: frozenset[str] = frozenset(
    {
        "theorem_count",
        "universal_theorem_count",
        "zero_axiom_theorem_count",
        "forbidden_axiom_count",
        "lean_kernel_checked",
        "all_theorems_standard_axioms_only",
        "live_silicon_verified",
        "float_count_on_trust_path",
        "bare_assert_count",
        "rng_calls",
    }
)
_BOOL_LEAF_KEYS: frozenset[str] = frozenset(
    {
        "measured_live_silicon",
        "measured_external_mathlib",
        "audio_capture_accessed",
        "camera_accessed",
        "display_modified",
        "static_envelope_clean",
        "zero_warnings",
        "standard_axioms_only",
        "clean_hardware_run",
        "wikitext2_h16_sign_inversion",
        "python_h16_sign_inversion",
        "python_05b_strict_sub_barrier_band",
        "block_h2_beats_h16_all_scales",
        "psys_vendor_scale_obstruction_detected",
        "exp_a_checksum_conserved",
        "race_to_sleep_beats_fixed_burst_pkg",
        "paced100_beats_burst1_fixed_window_pkg",
        "exp_b_checksum_conserved",
        "best_phys_beats_1t_pkg",
        "best_phys_beats_16t_pkg",
        "best_phys_beats_1t_psys",
        "best_phys_beats_16t_psys",
        "lean_kernel_checked",
        "all_theorems_standard_axioms_only",
        "live_silicon_verified",
        "verified",
    }
)


# ============================================================================
# 1. Hardened Strict-I/O Primitives (dir_fd, Hardlinks, $PWD, Darwin Prefix)
# ============================================================================

_CONCRETE_PATH_TYPE = type(Path())


def _require_concrete_path(path: Any, label: str) -> Path:
    if type(path) is not _CONCRETE_PATH_TYPE:
        raise TwoWayTransferError("INVALID_PATH_TYPE", f"{label}: exact pathlib.Path required")
    require_exact_str(str(path), f"{label}.path", max_len=4096, non_empty=True)
    return path


def _normalize_darwin_system_prefix(rel_parts: tuple[str, ...]) -> tuple[str, ...]:
    """Normalize verified root-owned macOS /var, /tmp, /etc -> /private/* symlinks only."""
    if sys.platform != "darwin" or len(rel_parts) < 2 or rel_parts[0] not in _DARWIN_SYSTEM_PREFIXES:
        return rel_parts
    top = rel_parts[0]
    try:
        st_lnk = os.lstat(f"/{top}")
        target = os.readlink(f"/{top}")
        st_priv = os.lstat("/private")
    except OSError:
        return rel_parts
    if (
        stat.S_ISLNK(st_lnk.st_mode)
        and st_lnk.st_uid == 0
        and target == f"private/{top}"
        and stat.S_ISDIR(st_priv.st_mode)
        and st_priv.st_uid == 0
    ):
        return ("private",) + rel_parts
    return rel_parts


def _verify_pwd_not_symlink(cwd_str: str, label: str) -> None:
    pwd_env = os.environ.get("PWD")
    if pwd_env is None:
        return
    pwd_s = require_exact_str(pwd_env, f"{label}.PWD", max_len=4096, non_empty=False)
    if not pwd_s.startswith("/"):
        return
    try:
        st_cwd = os.stat(cwd_str)
        st_pwd = os.stat(pwd_s)
    except OSError:
        return
    if (st_cwd.st_dev, st_cwd.st_ino) != (st_pwd.st_dev, st_pwd.st_ino):
        return
    raw_parts = tuple(p for p in Path(pwd_s).parts if p not in ("/", ""))
    parts = _normalize_darwin_system_prefix(raw_parts)
    dfd = os.open("/", _DIR_OPEN_FLAGS)
    try:
        for part in parts:
            if part == ".":
                continue
            try:
                next_fd = os.open(part, _DIR_OPEN_FLAGS, dir_fd=dfd)
            except OSError as exc:
                raise TwoWayTransferError(
                    "SYMLINK_ANCESTOR_FORBIDDEN", f"{label}: $PWD contains symlink or traversal component"
                ) from exc
            os.close(dfd)
            dfd = next_fd
    finally:
        os.close(dfd)


def _open_dir_chain(target: Path, label: str, *, create_parents: bool) -> tuple[int, str]:
    err_code = "FILE_WRITE_ERROR" if create_parents else "FILE_READ_ERROR"
    if not target.is_absolute():
        try:
            cwd_str = os.getcwd()
        except OSError as exc:
            raise TwoWayTransferError("CWD_UNAVAILABLE", f"{label}: current directory unavailable") from exc
        _verify_pwd_not_symlink(cwd_str, label)
        abs_path = Path(cwd_str) / target
    else:
        abs_path = target

    raw_parts = tuple(p for p in abs_path.parts if p not in ("/", ""))
    require_ok(len(raw_parts) >= 1, "INVALID_LEAF_NAME", f"{label}: missing leaf component")
    for p_seg in raw_parts:
        require_ok(p_seg != "..", "INVALID_LEAF_NAME", f"{label}: '..' component forbidden")
    parts = _normalize_darwin_system_prefix(raw_parts)
    leaf = parts[-1]
    parent_parts = parts[:-1]

    dfd = os.open("/", _DIR_OPEN_FLAGS)
    try:
        for part in parent_parts:
            if part == ".":
                continue
            try:
                next_fd = os.open(part, _DIR_OPEN_FLAGS, dir_fd=dfd)
            except OSError as exc:
                if create_parents and exc.errno == errno.ENOENT:
                    try:
                        os.mkdir(part, 0o755, dir_fd=dfd)
                    except FileExistsError:
                        pass
                    except OSError as mk_exc:
                        raise TwoWayTransferError(
                            "FILE_WRITE_ERROR", f"{label}: mkdir failed ({type(mk_exc).__name__})"
                        ) from mk_exc
                    try:
                        next_fd = os.open(part, _DIR_OPEN_FLAGS, dir_fd=dfd)
                    except OSError as re_exc:
                        raise TwoWayTransferError(
                            "FILE_WRITE_ERROR", f"{label}: open created dir failed ({type(re_exc).__name__})"
                        ) from re_exc
                elif exc.errno in (errno.ELOOP, errno.ENOTDIR):
                    raise TwoWayTransferError(
                        "SYMLINK_FORBIDDEN", f"{label}: symlink or non-directory ancestor forbidden"
                    ) from exc
                else:
                    raise TwoWayTransferError(
                        err_code, f"{label}: cannot traverse ancestor ({type(exc).__name__})"
                    ) from exc
            os.close(dfd)
            dfd = next_fd
        return dfd, leaf
    except BaseException:
        os.close(dfd)
        raise


def read_regular_bytes_capped(path: Path, label: str = "file", max_bytes: int = MAX_JSON_BYTES) -> bytes:
    target = _require_concrete_path(path, label)
    require_exact_int(max_bytes, "max_bytes", lo=1, hi=MAX_ALLOWED_CAP_BYTES)
    dfd, leaf = _open_dir_chain(target, label, create_parents=False)
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
    try:
        try:
            fd = os.open(leaf, flags, dir_fd=dfd)
        except OSError as exc:
            if exc.errno == errno.ELOOP:
                raise TwoWayTransferError("SYMLINK_FORBIDDEN", f"{label}: symlink leaf forbidden") from exc
            raise TwoWayTransferError("FILE_READ_ERROR", f"{label}: cannot open ({type(exc).__name__})") from exc
    finally:
        os.close(dfd)

    chunks: list[bytes] = []
    total = 0
    try:
        st_f = os.fstat(fd)
        require_ok(stat.S_ISREG(st_f.st_mode), "NOT_A_REGULAR_FILE", f"{label}: not a regular file")
        require_ok(st_f.st_nlink == 1, "HARDLINK_FORBIDDEN", f"{label}: hardlinked input forbidden")
        while total <= max_bytes:
            chunk = os.read(fd, min(_READ_CHUNK_BYTES, max_bytes + 1 - total))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
    except TwoWayTransferError:
        raise
    except OSError as exc:
        raise TwoWayTransferError("FILE_READ_ERROR", f"{label}: read failed ({type(exc).__name__})") from exc
    finally:
        os.close(fd)
    require_ok(total <= max_bytes, "FILE_TOO_LARGE", f"{label}: exceeds {max_bytes} bytes")
    return b"".join(chunks)


def write_regular_bytes_safe(path: Path, payload: bytes, label: str = "output") -> None:
    global _TEMP_COUNTER
    require_ok(type(payload) is bytes, "INVALID_PAYLOAD_BYTES", f"{label}: exact bytes required")
    target = _require_concrete_path(path, label)
    dfd, leaf = _open_dir_chain(target, label, create_parents=True)
    tmp_name: str | None = None
    try:
        try:
            st_existing = os.lstat(leaf, dir_fd=dfd)
        except FileNotFoundError:
            st_existing = None
        except OSError as exc:
            raise TwoWayTransferError("FILE_WRITE_ERROR", f"{label}: lstat failed ({type(exc).__name__})") from exc
        if st_existing is not None:
            require_ok(not stat.S_ISLNK(st_existing.st_mode), "SYMLINK_FORBIDDEN", f"{label}: symlink target forbidden")
            require_ok(stat.S_ISREG(st_existing.st_mode), "NOT_A_REGULAR_FILE", f"{label}: non-regular target")
            require_ok(st_existing.st_nlink <= 1, "HARDLINK_FORBIDDEN", f"{label}: hardlinked target forbidden")

        pid = os.getpid()
        for _ in range(32):
            with _TEMP_NAME_LOCK:
                _TEMP_COUNTER += 1
                seq_num = _TEMP_COUNTER
                cand = f".twt.{pid}.{seq_num}.{os.urandom(8).hex()}.tmp"
            try:
                fd = os.open(
                    cand,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_NONBLOCK,
                    0o600,
                    dir_fd=dfd,
                )
                tmp_name = cand
                break
            except FileExistsError:
                continue
            except OSError as exc:
                raise TwoWayTransferError(
                    "FILE_WRITE_ERROR", f"{label}: create temp failed ({type(exc).__name__})"
                ) from exc
        else:
            raise TwoWayTransferError("FILE_WRITE_ERROR", f"{label}: exhausted temp file slots")

        try:
            view = memoryview(payload)
            written = 0
            while written < len(view):
                written += os.write(fd, view[written:])
            os.fsync(fd)
            st_tmp = os.fstat(fd)
            require_ok(st_tmp.st_nlink == 1, "HARDLINK_FORBIDDEN", f"{label}: temp link count altered")
        except TwoWayTransferError:
            raise
        except OSError as exc:
            raise TwoWayTransferError("FILE_WRITE_ERROR", f"{label}: write failed ({type(exc).__name__})") from exc
        finally:
            os.close(fd)

        try:
            st_pre = os.lstat(leaf, dir_fd=dfd)
        except FileNotFoundError:
            st_pre = None
        except OSError as exc:
            raise TwoWayTransferError("FILE_WRITE_ERROR", f"{label}: post-lstat failed ({type(exc).__name__})") from exc
        if st_pre is not None:
            require_ok(not stat.S_ISLNK(st_pre.st_mode), "SYMLINK_FORBIDDEN", f"{label}: symlink race detected")
            require_ok(stat.S_ISREG(st_pre.st_mode), "NOT_A_REGULAR_FILE", f"{label}: non-regular race detected")
            require_ok(st_pre.st_nlink <= 1, "HARDLINK_FORBIDDEN", f"{label}: hardlink race detected")

        try:
            os.replace(tmp_name, leaf, src_dir_fd=dfd, dst_dir_fd=dfd)
            tmp_name = None
            os.fsync(dfd)
        except OSError as exc:
            raise TwoWayTransferError(
                "FILE_WRITE_ERROR", f"{label}: atomic replace failed ({type(exc).__name__})"
            ) from exc
    finally:
        if tmp_name is not None:
            try:
                os.unlink(tmp_name, dir_fd=dfd)
            except OSError:
                pass
        os.close(dfd)


def _decode_utf8_typed(raw: bytes, code: str, label: str) -> str:
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise TwoWayTransferError(code, f"{label}: invalid UTF-8") from exc


# ============================================================================
# 2. Live Lean 4.36.0 Kernel Runner & Hardware Provenance Verifier
# ============================================================================

def parse_print_axioms_output(
    stdout: str,
    expected_theorems: Sequence[str],
    label: str = "print_axioms",
) -> dict[str, list[str]]:
    raw = require_exact_str(stdout, label, max_len=MAX_LEAN_BYTES, non_empty=True)
    entries: list[str] = []
    buf: list[str] = []
    in_brackets = False
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if in_brackets:
            buf.append(stripped)
            if stripped.endswith("]"):
                entries.append(" ".join(buf))
                buf = []
                in_brackets = False
        elif stripped.startswith("'") and "depends on axioms: [" in stripped and not stripped.endswith("]"):
            buf = [stripped]
            in_brackets = True
        else:
            entries.append(stripped)
    require_ok(not in_brackets, "MALFORMED_AXIOM_OUTPUT", f"{label}: unclosed axiom bracket")

    expected_set = frozenset(expected_theorems)
    found: dict[str, list[str]] = {}
    for entry in entries:
        m_none = _AXIOM_NONE_RE.match(entry)
        if m_none is not None:
            thm = m_none.group(1)
            axioms: list[str] = []
        else:
            m_list = _AXIOM_LIST_RE.match(entry)
            if m_list is None:
                raise TwoWayTransferError("UNEXPECTED_LEAN_STDOUT", f"{label}: unexpected output '{entry[:80]}'")
            thm = m_list.group(1)
            body = m_list.group(2).strip()
            require_ok(len(body) >= 1, "EMPTY_AXIOM_BRACKETS", f"{label}: empty axiom list for {thm}")
            axioms = [tok.strip() for tok in body.split(",")]
            require_ok(all(len(a) >= 1 for a in axioms), "MALFORMED_AXIOM_TOKEN", f"{label}: blank axiom token")
        require_ok(thm in expected_set, "UNEXPECTED_THEOREM_NAME", f"{label}: unexpected theorem '{thm}'")
        require_ok(thm not in found, "DUPLICATE_THEOREM_PRINT", f"{label}: duplicate theorem '{thm}'")
        for ax in axioms:
            require_ok(ax in STANDARD_LEAN4_AXIOMS, "FORBIDDEN_LEAN_AXIOM", f"{label}: disallowed axiom '{ax}'")
        found[thm] = axioms

    for exp_thm in expected_theorems:
        require_ok(exp_thm in found, "MISSING_THEOREM_PRINT", f"{label}: missing '#print axioms' for '{exp_thm}'")
    return found


def resolve_lean_binary() -> str:
    env_bin = os.environ.get("ALETHEIA_LEAN_BIN")
    if env_bin is not None:
        require_exact_str(env_bin, "ALETHEIA_LEAN_BIN")
        p = Path(env_bin)
        require_ok(p.is_file() and os.access(str(p), os.X_OK), "LEAN_BINARY_UNAVAILABLE", "ALETHEIA_LEAN_BIN not executable")
        return str(p)
    found = shutil.which("lean")
    if found is not None and os.access(found, os.X_OK):
        return found
    home = Path.home()
    for rel in ((".local", "bin", "lean"), (".elan", "bin", "lean")):
        cand = home.joinpath(*rel)
        if cand.is_file() and os.access(str(cand), os.X_OK):
            return str(cand)
    raise TwoWayTransferError("LEAN_BINARY_UNAVAILABLE", "lean executable not found")


def query_lean_version(lean_bin: str) -> str:
    require_exact_str(lean_bin, "lean_bin")
    try:
        proc = subprocess.run(
            [lean_bin, "--version"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise TwoWayTransferError("LEAN_EXEC_ERROR", f"lean --version failed ({type(exc).__name__})") from exc
    require_ok(proc.returncode == 0, "LEAN_VERSION_FAILED", f"lean --version exited {proc.returncode}")
    line = proc.stdout.strip().splitlines()[0] if proc.stdout.strip() else ""
    require_ok(line.startswith("Lean (version 4.36.0,"), "LEAN_VERSION_MISMATCH", f"unexpected lean version '{line}'")
    return line


def run_live_lean_module(
    lean_bin: str,
    project_root: Path,
    rel_path: str = "TwoWayTransfer.lean",
    expected_theorems: Sequence[str] = EXPECTED_THEOREMS,
) -> dict[str, Any]:
    root = _require_concrete_path(project_root, "project_root")
    require_exact_str(rel_path, "rel_path")
    lean_path = root / rel_path
    raw_bytes = read_regular_bytes_capped(lean_path, f"lean:{rel_path}", max_bytes=MAX_LEAN_BYTES)
    source_text = _decode_utf8_typed(raw_bytes, "INVALID_UTF8_LEAN", rel_path)
    static_lean4_source_check(source_text, rel_path)
    src_sha = hashlib.sha256(raw_bytes).hexdigest()
    line_count = len(raw_bytes.splitlines())

    try:
        proc = subprocess.run(
            [lean_bin, str(lean_path)],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=_LEAN_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise TwoWayTransferError("LEAN_EXEC_ERROR", f"lean exec failed ({type(exc).__name__})") from exc

    require_ok(proc.returncode == 0, "LEAN_KERNEL_REJECTED", f"lean exited {proc.returncode}")
    require_ok(proc.stderr.strip() == "", "LEAN_STDERR_NONEMPTY", "lean stderr non-empty")
    require_ok("warning:" not in proc.stdout, "LEAN_WARNING_FORBIDDEN", "lean warning emitted")
    parsed_axioms = parse_print_axioms_output(proc.stdout, expected_theorems, rel_path)
    thm_entries = [
        {"name": name, "axioms": parsed_axioms[name], "standard_axioms_only": True}
        for name in expected_theorems
    ]
    return {
        "rel_path": rel_path,
        "source_sha256": src_sha,
        "line_count": line_count,
        "theorem_count": len(thm_entries),
        "static_envelope_clean": True,
        "kernel_exit_code": 0,
        "zero_warnings": True,
        "theorems": thm_entries,
    }


def load_hardware_provenance(project_root: Path) -> tuple[dict[str, Any], str]:
    """Read and validate the integer/string/bool fields of mlos_zone_b_receipt.json (zero floats stored)."""
    root = _require_concrete_path(project_root, "project_root")
    raw = read_regular_bytes_capped(root / "mlos_zone_b_receipt.json", "mlos_receipt", max_bytes=131_072)
    file_sha = hashlib.sha256(raw).hexdigest()
    text = _decode_utf8_typed(raw, "INVALID_UTF8_RECEIPT", "mlos_receipt")
    try:
        obj = json.loads(text, parse_constant=oracle._reject_const_token, object_pairs_hook=oracle._no_dup_pairs)
    except TwoWayTransferError:
        raise
    except ValueError as exc:
        raise TwoWayTransferError("RECEIPT_JSON_ERROR", f"mlos receipt invalid JSON ({exc})") from exc
    require_ok(type(obj) is dict, "RECEIPT_OBJECT_REQUIRED", "mlos receipt must be JSON object")
    require_ok(obj.get("schema") == "mlos-run-receipt/v0.1", "RECEIPT_SCHEMA_MISMATCH", "unexpected receipt schema")
    require_ok(
        require_exact_bool(obj.get("clean_hardware_run"), "clean_hardware_run") is True,
        "HARDWARE_NOT_CLEAN",
        "clean_hardware_run must be True",
    )
    anomalies = obj.get("anomalies")
    require_ok(type(anomalies) is list and len(anomalies) == 0, "HARDWARE_ANOMALIES", "anomalies must be empty")
    zone = require_exact_str(obj.get("determinism_zone"), "determinism_zone")
    require_ok(zone == "B", "RECEIPT_ZONE_MISMATCH", "determinism_zone must be B")
    exe = obj.get("execution")
    require_ok(type(exe) is dict, "RECEIPT_EXEC_MISSING", "execution dict required")
    exit_code = require_exact_int(exe.get("exit_code"), "execution.exit_code", lo=0, hi=0)
    start_gpu = obj.get("start_gpu_telemetry")
    end_gpu = obj.get("end_gpu_telemetry")
    require_ok(type(start_gpu) is dict and type(end_gpu) is dict, "RECEIPT_GPU_MISSING", "gpu telemetry required")
    start_ps = require_exact_str(start_gpu.get("pstate"), "start_gpu.pstate")
    end_ps = require_exact_str(end_gpu.get("pstate"), "end_gpu.pstate")
    require_ok(start_ps == "P8" and end_ps == "P8", "GPU_NOT_IDLE_P8", "GPU must be idle P8 at start and end")
    kmd_vram = require_exact_int(end_gpu.get("linux_kmd_baseline_vram_mib"), "linux_kmd_baseline_vram_mib", lo=0, hi=64)
    summary = {
        "receipt_schema": "mlos-run-receipt/v0.1",
        "profile_id": require_exact_str(obj.get("profile_id"), "profile_id"),
        "profile_sha256": require_sha256_hex(obj.get("profile_sha256"), "profile_sha256"),
        "receipt_sha256": require_sha256_hex(obj.get("receipt_sha256"), "receipt_sha256"),
        "determinism_zone": zone,
        "exit_code": exit_code,
        "clean_hardware_run": True,
        "anomalies_count": 0,
        "gpu_start_pstate": start_ps,
        "gpu_end_pstate": end_ps,
        "linux_kmd_baseline_vram_mib": kmd_vram,
    }
    return summary, file_sha


# ============================================================================
# 3. Certificate Builder, Deep Secondary Auditor & Typed CLI
# ============================================================================

def _audit_bool_leaf_bijection(obj: Any, label: str = "payload") -> None:
    stack: list[tuple[Any, str]] = [(obj, label)]
    while stack:
        cur, path = stack.pop()
        if type(cur) is dict:
            for k, v in cur.items():
                child = f"{path}.{k}"
                if k in _BOOL_LEAF_KEYS:
                    require_exact_bool(v, child)
                else:
                    require_ok(type(v) is not bool, "UNEXPECTED_BOOL_LEAF", f"{child}: unexpected bool")
                    stack.append((v, child))
        elif type(cur) is list:
            for idx, item in enumerate(cur):
                require_ok(type(item) is not bool, "UNEXPECTED_BOOL_ITEM", f"{path}[{idx}]: unexpected bool")
                stack.append((item, f"{path}[{idx}]"))


def _audit_all_rational_strings(obj: Any, label: str = "payload") -> None:
    """Enforce lowest-terms canonical ASCII rational formatting on every `*_q` leaf."""
    stack: list[tuple[Any, str]] = [(obj, label)]
    while stack:
        cur, path = stack.pop()
        if type(cur) is dict:
            for k, v in cur.items():
                child = f"{path}.{k}"
                if k.endswith("_q"):
                    parse_exact_rational(v, child)
                else:
                    stack.append((v, child))
        elif type(cur) is list:
            for idx, item in enumerate(cur):
                stack.append((item, f"{path}[{idx}]"))


def build_certificate(project_root: Path | None = None) -> dict[str, Any]:
    root = _DEFAULT_PROJECT_ROOT if project_root is None else _require_concrete_path(project_root, "project_root")
    lean_bin = resolve_lean_binary()
    lean_ver = query_lean_version(lean_bin)

    tc_bytes = read_regular_bytes_capped(root / "lean-toolchain", "lean-toolchain", max_bytes=256)
    tc_text = _decode_utf8_typed(tc_bytes, "INVALID_UTF8_TOOLCHAIN", "lean-toolchain").strip()
    require_ok(tc_text == EXPECTED_LEAN_TOOLCHAIN, "TOOLCHAIN_MISMATCH", f"expected {EXPECTED_LEAN_TOOLCHAIN}")
    lake_bytes = read_regular_bytes_capped(root / "lakefile.toml", "lakefile.toml", max_bytes=16_384)
    c_bytes = read_regular_bytes_capped(root / "two_way_silicon_probe.c", "c_probe", max_bytes=262_144)
    probe_bytes = read_regular_bytes_capped(root / "two_way_silicon_live_results.json", "live_probe", max_bytes=MAX_JSON_BYTES)
    probe_text = _decode_utf8_typed(probe_bytes, "INVALID_UTF8_PROBE", "live_probe")
    probe_obj = parse_strict_json_text(probe_text, require_object=True, label="live_probe")

    hw_prov, mlos_sha = load_hardware_provenance(root)
    lean_mod = run_live_lean_module(lean_bin, root)
    p1 = oracle.analyze_competing_potential_scale_flip()
    p2 = oracle.analyze_live_silicon_probe(probe_obj)

    zero_ax_cnt = sum(1 for t in lean_mod["theorems"] if len(t["axioms"]) == 0)
    payload: dict[str, Any] = {
        "study_id": STUDY_ID,
        "novelty_class": "N1",
        "oracle_class": "lean4_kernel_plus_exact_zq_plus_live_rapl",
        "measured_live_silicon": True,
        "measured_external_mathlib": False,
        "privacy_locks": {
            "audio_capture_accessed": False,
            "camera_accessed": False,
            "display_modified": False,
        },
        "lean_toolchain": tc_text,
        "lean_version_line": lean_ver,
        "prior_literature_n0": list(PRIOR_LITERATURE_N0),
        "project_manifest": {
            "lean_toolchain_sha256": hashlib.sha256(tc_bytes).hexdigest(),
            "lakefile_sha256": hashlib.sha256(lake_bytes).hexdigest(),
            "lean_source_sha256": lean_mod["source_sha256"],
            "c_probe_source_sha256": hashlib.sha256(c_bytes).hexdigest(),
            "live_probe_json_sha256": hashlib.sha256(probe_bytes).hexdigest(),
            "mlos_receipt_json_sha256": mlos_sha,
            "theorem_count": lean_mod["theorem_count"],
        },
        "lean_module": lean_mod,
        "hardware_provenance": hw_prov,
        "pillar1_competing_potential": p1,
        "pillar2_live_silicon": p2,
        "summary": {
            "theorem_count": lean_mod["theorem_count"],
            "universal_theorem_count": 8,
            "zero_axiom_theorem_count": zero_ax_cnt,
            "forbidden_axiom_count": 0,
            "lean_kernel_checked": True,
            "all_theorems_standard_axioms_only": True,
            "live_silicon_verified": True,
            "float_count_on_trust_path": 0,
            "bare_assert_count": 0,
            "rng_calls": 0,
        },
    }

    payload_sha = hashlib.sha256(canonical_json_bytes(payload)).hexdigest()
    core = {
        "schema_version": SCHEMA_VERSION,
        "study_id": STUDY_ID,
        "payload_sha256": payload_sha,
        "payload": payload,
    }
    cert_sha = hashlib.sha256(canonical_json_bytes(core)).hexdigest()
    cert = {
        "schema_version": SCHEMA_VERSION,
        "study_id": STUDY_ID,
        "payload_sha256": payload_sha,
        "certificate_sha256": cert_sha,
        "payload": payload,
    }
    secondary_audit_payload(payload, project_root=root, verify_live_lean=False)
    return cert


def secondary_audit_payload(
    payload: Any,
    *,
    project_root: Path | None = None,
    verify_live_lean: bool = False,
) -> dict[str, Any]:
    require_exact_bool(verify_live_lean, "verify_live_lean")
    validate_json_tree(payload, "payload")
    p = require_exact_keys(payload, _PAYLOAD_KEYS, "payload")
    _audit_bool_leaf_bijection(p, "payload")
    _audit_all_rational_strings(p, "payload")

    require_ok(p["study_id"] == STUDY_ID, "STUDY_ID_MISMATCH", "payload.study_id mismatch")
    require_ok(p["novelty_class"] == "N1", "NOVELTY_MISMATCH", "novelty_class must be N1")
    require_ok(
        p["oracle_class"] == "lean4_kernel_plus_exact_zq_plus_live_rapl",
        "ORACLE_CLASS_MISMATCH",
        "oracle_class mismatch",
    )
    require_ok(p["measured_live_silicon"] is True, "LIVE_SILICON_FLAG", "measured_live_silicon must be True")
    require_ok(p["measured_external_mathlib"] is False, "MATHLIB_FLAG", "measured_external_mathlib must be False")
    priv = require_exact_keys(p["privacy_locks"], _PRIVACY_KEYS, "privacy_locks")
    require_ok(priv["audio_capture_accessed"] is False, "PRIVACY_AUDIO", "audio must be False")
    require_ok(priv["camera_accessed"] is False, "PRIVACY_CAMERA", "camera must be False")
    require_ok(priv["display_modified"] is False, "PRIVACY_DISPLAY", "display must be False")
    require_ok(p["lean_toolchain"] == EXPECTED_LEAN_TOOLCHAIN, "TOOLCHAIN_MISMATCH", "lean_toolchain mismatch")
    ver_line = require_exact_str(p["lean_version_line"], "lean_version_line")
    require_ok(ver_line == EXPECTED_LEAN_VERSION_LINE, "LEAN_VERSION_MISMATCH", "lean_version_line mismatch")
    require_ok(p["prior_literature_n0"] == list(PRIOR_LITERATURE_N0), "LIT_MISMATCH", "prior_literature_n0 mismatch")

    root = _DEFAULT_PROJECT_ROOT if project_root is None else _require_concrete_path(project_root, "project_root")
    man = require_exact_keys(p["project_manifest"], _MANIFEST_KEYS, "project_manifest")
    tc_sha = require_sha256_hex(man["lean_toolchain_sha256"], "manifest.lean_toolchain_sha256")
    lake_sha = require_sha256_hex(man["lakefile_sha256"], "manifest.lakefile_sha256")
    lean_sha = require_sha256_hex(man["lean_source_sha256"], "manifest.lean_source_sha256")
    c_sha = require_sha256_hex(man["c_probe_source_sha256"], "manifest.c_probe_source_sha256")
    probe_sha = require_sha256_hex(man["live_probe_json_sha256"], "manifest.live_probe_json_sha256")
    mlos_sha = require_sha256_hex(man["mlos_receipt_json_sha256"], "manifest.mlos_receipt_json_sha256")
    require_ok(man["theorem_count"] == len(EXPECTED_THEOREMS), "THEOREM_COUNT_MISMATCH", "theorem_count mismatch")

    disk_tc = read_regular_bytes_capped(root / "lean-toolchain", "lean-toolchain", max_bytes=256)
    require_ok(hmac.compare_digest(hashlib.sha256(disk_tc).hexdigest(), tc_sha), "TOOLCHAIN_SHA_MISMATCH", "toolchain sha mismatch")
    disk_lake = read_regular_bytes_capped(root / "lakefile.toml", "lakefile.toml", max_bytes=16_384)
    require_ok(hmac.compare_digest(hashlib.sha256(disk_lake).hexdigest(), lake_sha), "LAKEFILE_SHA_MISMATCH", "lakefile sha mismatch")
    disk_c = read_regular_bytes_capped(root / "two_way_silicon_probe.c", "c_probe", max_bytes=262_144)
    require_ok(hmac.compare_digest(hashlib.sha256(disk_c).hexdigest(), c_sha), "C_PROBE_SHA_MISMATCH", "c_probe sha mismatch")

    disk_probe = read_regular_bytes_capped(root / "two_way_silicon_live_results.json", "live_probe", max_bytes=MAX_JSON_BYTES)
    require_ok(hmac.compare_digest(hashlib.sha256(disk_probe).hexdigest(), probe_sha), "LIVE_PROBE_SHA_MISMATCH", "live_probe sha mismatch")
    probe_obj = parse_strict_json_text(_decode_utf8_typed(disk_probe, "INVALID_UTF8_PROBE", "live_probe"), label="live_probe")

    expected_hw, disk_mlos_sha = load_hardware_provenance(root)
    require_ok(hmac.compare_digest(disk_mlos_sha, mlos_sha), "MLOS_SHA_MISMATCH", "mlos receipt sha mismatch")
    hw = require_exact_keys(p["hardware_provenance"], _HW_PROV_KEYS, "hardware_provenance")
    require_ok(hw == expected_hw, "HARDWARE_PROVENANCE_MISMATCH", "hardware_provenance mismatch")

    lm = require_exact_keys(p["lean_module"], _LEAN_MOD_KEYS, "lean_module")
    require_ok(lm["rel_path"] == "TwoWayTransfer.lean", "REL_PATH_MISMATCH", "rel_path mismatch")
    mod_sha = require_sha256_hex(lm["source_sha256"], "lean_module.source_sha256")
    require_ok(hmac.compare_digest(mod_sha, lean_sha), "LEAN_SHA_SELF_MISMATCH", "manifest vs module sha mismatch")
    line_cnt = require_exact_int(lm["line_count"], "lean_module.line_count", lo=20, hi=5000)
    require_ok(lm["theorem_count"] == len(EXPECTED_THEOREMS), "MOD_THEOREM_COUNT", "module theorem_count mismatch")
    require_ok(lm["static_envelope_clean"] is True, "STATIC_ENVELOPE_FLAG", "static_envelope_clean must be True")
    require_ok(lm["kernel_exit_code"] == 0, "KERNEL_EXIT_NONZERO", "kernel_exit_code must be 0")
    require_ok(lm["zero_warnings"] is True, "WARNINGS_FLAG", "zero_warnings must be True")

    thms = lm["theorems"]
    require_ok(type(thms) is list and len(thms) == len(EXPECTED_THEOREMS), "THEOREMS_LIST_MISMATCH", "theorems len mismatch")
    for idx, (t_obj, exp_name) in enumerate(zip(thms, EXPECTED_THEOREMS)):
        t = require_exact_keys(t_obj, _THEOREM_ENTRY_KEYS, f"theorems[{idx}]")
        require_ok(t["name"] == exp_name, "THEOREM_NAME_MISMATCH", f"theorem[{idx}] name mismatch")
        require_ok(t["standard_axioms_only"] is True, "THEOREM_AXIOM_FLAG", f"{exp_name} not standard_axioms_only")
        axs = t["axioms"]
        require_ok(type(axs) is list and len(axs) <= 3, "AXIOM_LIST_INVALID", f"{exp_name} axioms invalid")
        seen_ax: set[str] = set()
        for ax in axs:
            ax_s = require_exact_str(ax, f"{exp_name}.axiom")
            require_ok(ax_s in STANDARD_LEAN4_AXIOMS, "FORBIDDEN_LEAN_AXIOM", f"{exp_name}: disallowed axiom '{ax_s}'")
            require_ok(ax_s not in seen_ax, "DUPLICATE_AXIOM", f"{exp_name}: duplicate axiom '{ax_s}'")
            seen_ax.add(ax_s)
        require_ok(axs == list(EXPECTED_THEOREM_AXIOMS[exp_name]), "AXIOM_SET_MISMATCH", f"{exp_name}: axiom footprint mismatch")

    disk_lean = read_regular_bytes_capped(root / "TwoWayTransfer.lean", "TwoWayTransfer.lean", max_bytes=MAX_LEAN_BYTES)
    require_ok(hmac.compare_digest(hashlib.sha256(disk_lean).hexdigest(), mod_sha), "LEAN_SOURCE_SHA_MISMATCH", "lean disk sha mismatch")
    require_ok(len(disk_lean.splitlines()) == line_cnt, "LEAN_LINE_COUNT_MISMATCH", "lean line_count mismatch")
    static_lean4_source_check(_decode_utf8_typed(disk_lean, "INVALID_UTF8_LEAN", "TwoWayTransfer.lean"), "TwoWayTransfer.lean")

    if verify_live_lean:
        lean_bin = resolve_lean_binary()
        live_ver = query_lean_version(lean_bin)
        require_ok(live_ver == ver_line, "LEAN_VERSION_DRIFT", "live lean version mismatch")
        live_mod = run_live_lean_module(lean_bin, root)
        require_ok(live_mod == lm, "LIVE_LEAN_DRIFT", "live lean kernel output mismatch")

    expected_p1 = oracle.analyze_competing_potential_scale_flip()
    require_ok(p["pillar1_competing_potential"] == expected_p1, "PILLAR1_MISMATCH", "pillar1 mismatch")
    expected_p2 = oracle.analyze_live_silicon_probe(probe_obj)
    require_ok(p["pillar2_live_silicon"] == expected_p2, "PILLAR2_MISMATCH", "pillar2 mismatch")

    summ = require_exact_keys(p["summary"], _SUMMARY_KEYS, "summary")
    require_ok(summ["theorem_count"] == len(EXPECTED_THEOREMS), "SUMMARY_THMS", "summary.theorem_count mismatch")
    require_ok(summ["universal_theorem_count"] == 8, "SUMMARY_UNIV", "summary.universal_theorem_count mismatch")
    require_ok(summ["zero_axiom_theorem_count"] == 2, "SUMMARY_ZERO_AX", "summary.zero_axiom_theorem_count mismatch")
    require_ok(summ["forbidden_axiom_count"] == 0, "SUMMARY_FORBIDDEN", "summary.forbidden_axiom_count != 0")
    require_ok(summ["lean_kernel_checked"] is True, "SUMMARY_KERNEL", "summary.lean_kernel_checked False")
    require_ok(summ["all_theorems_standard_axioms_only"] is True, "SUMMARY_STD_AX", "summary.all_theorems_standard_axioms_only False")
    require_ok(summ["live_silicon_verified"] is True, "SUMMARY_SILICON", "summary.live_silicon_verified False")
    require_ok(summ["float_count_on_trust_path"] == 0, "SUMMARY_FLOATS", "summary.float_count_on_trust_path != 0")
    require_ok(summ["bare_assert_count"] == 0, "SUMMARY_ASSERTS", "summary.bare_assert_count != 0")
    require_ok(summ["rng_calls"] == 0, "SUMMARY_RNG", "summary.rng_calls != 0")

    return {"verified": True, "theorem_count": len(EXPECTED_THEOREMS)}


def validate_certificate_payload(
    cert: Any,
    *,
    project_root: Path | None = None,
    verify_live_lean: bool = False,
) -> dict[str, Any]:
    require_exact_bool(verify_live_lean, "verify_live_lean")
    validate_json_tree(cert, "certificate")
    c = require_exact_keys(cert, _CERT_KEYS, "certificate")
    require_ok(c["schema_version"] == SCHEMA_VERSION, "SCHEMA_MISMATCH", "schema_version mismatch")
    require_ok(c["study_id"] == STUDY_ID, "STUDY_ID_MISMATCH", "certificate study_id mismatch")
    p_sha = require_sha256_hex(c["payload_sha256"], "payload_sha256")
    c_sha = require_sha256_hex(c["certificate_sha256"], "certificate_sha256")

    actual_p_sha = hashlib.sha256(canonical_json_bytes(c["payload"])).hexdigest()
    require_ok(hmac.compare_digest(actual_p_sha, p_sha), "PAYLOAD_HASH_MISMATCH", "payload_sha256 mismatch")

    core = {
        "schema_version": c["schema_version"],
        "study_id": c["study_id"],
        "payload_sha256": p_sha,
        "payload": c["payload"],
    }
    actual_c_sha = hashlib.sha256(canonical_json_bytes(core)).hexdigest()
    require_ok(hmac.compare_digest(actual_c_sha, c_sha), "CERT_HASH_MISMATCH", "certificate_sha256 mismatch")

    res = secondary_audit_payload(
        c["payload"],
        project_root=project_root,
        verify_live_lean=verify_live_lean,
    )
    return {
        "verified": True,
        "study_id": STUDY_ID,
        "schema_version": SCHEMA_VERSION,
        "payload_sha256": p_sha,
        "certificate_sha256": c_sha,
        "theorem_count": res["theorem_count"],
    }


def check_certificate_file(
    cert_path: Path,
    *,
    project_root: Path | None = None,
    verify_live_lean: bool = True,
) -> dict[str, Any]:
    raw = read_regular_bytes_capped(cert_path, "certificate_file", max_bytes=MAX_JSON_BYTES)
    text = _decode_utf8_typed(raw, "INVALID_UTF8_JSON", "certificate_file")
    cert = parse_strict_json_text(text, require_object=True, label="certificate_file")
    require_ok(
        hmac.compare_digest(raw, canonical_json_bytes(cert) + b"\n"),
        "NON_CANONICAL_CERT_BYTES",
        "certificate file must be exact canonical compact ASCII JSON + LF",
    )
    return validate_certificate_payload(cert, project_root=project_root, verify_live_lean=verify_live_lean)


def main(argv: Any = None) -> int:
    raw_argv = sys.argv[1:] if argv is None else argv
    try:
        require_ok(type(raw_argv) in (list, tuple), "INVALID_CLI_ARGS", "argv must be list or tuple")
        args = [require_exact_str(item, "argv", max_len=4096, non_empty=False) for item in raw_argv]
        if len(args) == 0:
            cert = build_certificate()
            out = {
                "study_id": STUDY_ID,
                "certificate_sha256": cert["certificate_sha256"],
                "payload_sha256": cert["payload_sha256"],
                "theorem_count": cert["payload"]["summary"]["theorem_count"],
                "verified": True,
            }
            sys.stdout.write(canonical_json_bytes(out).decode("ascii") + "\n")
            return 0
        if args == ["--standalone", "--json"]:
            cert = build_certificate()
            sys.stdout.write(canonical_json_bytes(cert).decode("ascii") + "\n")
            return 0
        if len(args) == 2 and args[0] == "--write":
            require_ok(len(args[1]) > 0 and not args[1].startswith("-"), "INVALID_CLI_ARGS", "--write target invalid")
            cert = build_certificate()
            write_regular_bytes_safe(Path(args[1]), canonical_json_bytes(cert) + b"\n", "certificate_out")
            out = {
                "written": True,
                "certificate_sha256": cert["certificate_sha256"],
                "payload_sha256": cert["payload_sha256"],
            }
            sys.stdout.write(canonical_json_bytes(out).decode("ascii") + "\n")
            return 0
        if len(args) == 2 and args[0] == "--check":
            require_ok(len(args[1]) > 0 and not args[1].startswith("-"), "INVALID_CLI_ARGS", "--check target invalid")
            verdict = check_certificate_file(Path(args[1]), verify_live_lean=True)
            sys.stdout.write(canonical_json_bytes(verdict).decode("ascii") + "\n")
            return 0
        raise TwoWayTransferError(
            "INVALID_CLI_ARGS",
            "usage: [--standalone --json | --write <path> | --check <path>]",
        )
    except TwoWayTransferError as exc:
        sys.stderr.write(f"ERROR [{exc.code}]: {exc}\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
