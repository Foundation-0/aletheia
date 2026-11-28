#!/usr/bin/env python3
"""Wave-11 Live RTX 3080 Zone-B Runner:
  - Probe A (EXP-Q25a / EXP-Q26b): Zero-Training `LoopCD-Hidden` + Palindromic Strang SU(2)
    Cayley Guidance on Converged `HoloSphere-V3` (`holosphere_v3_15m_flagship.pt`, 2.5832 BPB).
  - Probe B (EXP-Q25b / EXP-Q26a): Hazy Research *Plato's Key* x `Portal x/pi` `SphereMap`
    Quadrupole Procrustes Transfer + SVD Rank Curve + Dark-Memory Unlocking on Real Offline
    Base LLMs (`Qwen2.5-0.5B`, `Qwen2.5-1.5B`, `SmolLM2-360M`, strict `HF_HUB_OFFLINE=1`).

Pure-stdlib `--selftest-stdlib --json` runs cleanly under stock `/usr/bin/python3 -I` (verifying
PREREG SHA-256 pin, factual suite subject-disjointness >= 120 facts, and Zone-B bundle
provenance when present, without torch).
Zero bare asserts; strictly seeded RNG; zero host-path leaks; WEIGHTS = 0 inside expedition/.
"""

from __future__ import annotations

import argparse
import errno
import gc
import hashlib
import hmac
import json
import math
import os
from pathlib import Path
import random
import re
import stat
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional, Sequence, Tuple

SCHEMA_W11_LIVE = "aletheia.wave11.live_loopcd_platosphere.v1"
SCHEMA_W11_SELFTEST = "aletheia.wave11.live_loopcd_platosphere_selftest.v1"
PREREG_FILENAME = "PREREG_W11_LIVE_LOOPCD_PLATOSPHERE.md"
PINNED_PREREG_SHA256 = "b09baa4d6adab2b2883064b294b7e66656b135bca09ee672d50f60e14539ef05"
PINNED_PROFILE_ID = "ux582hs-rtx3080-8gb"
PINNED_PROFILE_SHA256 = "566c9192d38682a0ec4d652a63a3510aaefb9dc20ef91ae9bdc6d4abbbf5cbe2"
PINNED_COMMITTED_RESULTS_PAYLOAD_SHA256 = "8d3000e3b45a17b0b8b8a68289d9d1755d2bc5d55cfbc7e6a1e4444ebb07f891"
PINNED_COMMITTED_RESULTS_FILE_SHA256 = "70493bada84e449ce121b9437b409135c562b3eae434623a3c9a4f6f8d5a7b67"
PINNED_COMMITTED_RECEIPT_SHA256 = "7f31de378b1b067c1edce9f5cc12400b1649ae3e95e6291568d90ccab0889fb0"
EXPECTED_GPU_NAME = "NVIDIA GeForce RTX 3080 Laptop GPU"
EXPECTED_DETERMINISM_PINS: Dict[str, str] = {
    "CUBLAS_WORKSPACE_CONFIG": ":4096:8",
    "HF_HUB_OFFLINE": "1",
    "MKL_NUM_THREADS": "1",
    "NUMEXPR_NUM_THREADS": "1",
    "OMP_NUM_THREADS": "1",
    "OPENBLAS_NUM_THREADS": "1",
    "PYTHONHASHSEED": "0",
    "TORCH_USE_DETERMINISTIC_ALGORITHMS": "1",
    "TRANSFORMERS_OFFLINE": "1",
    "VECLIB_MAXIMUM_THREADS": "1",
}
REQUIRED_RESULTS_KEYS = frozenset(
    {
        "gpu_name",
        "payload_sha256",
        "prereg_filename",
        "prereg_sha256",
        "probe_a_loopcd_strang_holosphere_v3",
        "probe_b_platos_key_spheremap_procrustes",
        "schema",
        "wall_seconds",
    }
)
OPTIONAL_RESULTS_GIT_KEYS = frozenset({"git_head", "git_head_status"})
EXPECTED_RECEIPT_KEYS = frozenset(
    {
        "anomalies",
        "bound_prereg_file",
        "bound_prereg_sha256",
        "bound_profile_file",
        "bound_results_file",
        "bound_results_file_sha256",
        "bound_results_payload_sha256",
        "clean_hardware_run",
        "determinism_pins",
        "determinism_zone",
        "end_gpu_telemetry",
        "energy_power_status",
        "execution",
        "git_head",
        "git_head_status",
        "gpu_telemetry_available",
        "host",
        "profile_id",
        "profile_sha256",
        "receipt_sha256",
        "schema",
        "start_gpu_telemetry",
    }
)
EXPECTED_PROBE_B_MODELS = frozenset(
    {
        "HuggingFaceTB/SmolLM2-360M",
        "Qwen/Qwen2.5-0.5B",
        "Qwen/Qwen2.5-1.5B",
    }
)
EXPECTED_PROBE_B_PAIRS = frozenset(
    {
        "Qwen2.5-0.5B_to_Qwen2.5-1.5B",
        "Qwen2.5-1.5B_to_Qwen2.5-0.5B",
        "Qwen2.5-1.5B_to_SmolLM2-360M",
        "SmolLM2-360M_to_Qwen2.5-0.5B",
    }
)
_GIT_EXE_CANDIDATES = ("/usr/bin/git", "/bin/git", "/usr/local/bin/git")

VOCAB_SIZE = 260
BOS_ID = 256
MAX_ZONE_B_FILE_BYTES = 16 * 1024 * 1024
MAX_JSON_INT_DIGITS = 1024
MAX_JSON_DEPTH = 64
_HEX40_RE = re.compile(r"^[0-9a-f]{40}\Z")
_HEX64_RE = re.compile(r"^[0-9a-f]{64}\Z")
_GIT_LOCAL_ENV_VARS = frozenset(
    {
        "GIT_DIR",
        "GIT_WORK_TREE",
        "GIT_INDEX_FILE",
        "GIT_OBJECT_DIRECTORY",
        "GIT_ALTERNATE_OBJECT_DIRECTORIES",
        "GIT_COMMON_DIR",
        "GIT_CONFIG",
        "GIT_CONFIG_GLOBAL",
        "GIT_CONFIG_SYSTEM",
        "GIT_CONFIG_PARAMETERS",
        "GIT_CONFIG_COUNT",
    }
)


class Wave11ProbeError(RuntimeError):
    """Fail-closed exception for Wave-11 live GPU probes."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"[{code}] {message}")
        self.code = code
        self.message = message


def require_ok(cond: bool, code: str, message: str) -> None:
    if cond is not True:
        raise Wave11ProbeError(code, message)


def _canonical_json_bytes(obj: Any) -> bytes:
    return json.dumps(
        obj,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def _open_path_nofollow(path: Path, code: str, *, is_dir: bool) -> int:
    """Walk every path component from / using dir_fd + O_NOFOLLOW (TOCTOU-free)."""
    dir_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    leaf_flags = dir_flags if is_dir else (os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))
    if path.is_absolute():
        parts = path.parts[1:]
    else:
        cwd = Path(os.getcwd())
        parts = (*cwd.parts[1:], *path.parts)
    require_ok(len(parts) > 0, code, "Root path refused")
    cur_fd = -1
    try:
        cur_fd = os.open("/", os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        for comp in parts[:-1]:
            if comp == ".":
                continue
            next_fd = os.open(comp, dir_flags, dir_fd=cur_fd)
            try:
                os.close(cur_fd)
            except OSError:
                pass
            cur_fd = next_fd
        return os.open(parts[-1], leaf_flags, dir_fd=cur_fd)
    except OSError as exc:
        raise Wave11ProbeError(code, f"Unable to open path: {path.name}") from exc
    finally:
        if cur_fd >= 0:
            try:
                os.close(cur_fd)
            except OSError:
                pass


def _read_regular_file_bytes(
    path: Path,
    code: str,
    *,
    max_bytes: int = MAX_ZONE_B_FILE_BYTES,
    check_parents: Sequence[Path] = (),
) -> bytes:
    """Read a regular non-symlink file via dir_fd O_NOFOLLOW | O_NONBLOCK with strict byte cap."""
    for cp in check_parents:
        cp_fd = _open_path_nofollow(cp, code, is_dir=True)
        try:
            os.close(cp_fd)
        except OSError:
            pass
    fd = _open_path_nofollow(path, code, is_dir=False)
    try:
        try:
            st = os.fstat(fd)
            require_ok(stat.S_ISREG(st.st_mode), code, f"Non-regular file refused: {path.name}")
            chunks: List[bytes] = []
            remaining = max_bytes + 1
            while remaining > 0:
                chunk = os.read(fd, min(65536, remaining))
                if not chunk:
                    break
                chunks.append(chunk)
                remaining -= len(chunk)
        except OSError as exc:
            raise Wave11ProbeError(code, f"Unable to read regular file: {path.name}") from exc
        data = b"".join(chunks)
        require_ok(len(data) <= max_bytes, code, f"File exceeds byte cap: {path.name}")
        return data
    finally:
        try:
            os.close(fd)
        except OSError:
            pass


def _sha256_file(
    path: Path,
    *,
    code: str = "ZONEB_FILE_MISSING",
    check_parents: Sequence[Path] = (),
) -> str:
    return hashlib.sha256(_read_regular_file_bytes(path, code, check_parents=check_parents)).hexdigest()


def _expedition_root() -> Path:
    return Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------------
# 1. Deterministic Subject-Disjoint Factual Recall Suite (>= 120 Facts, 4 Relations)
# ---------------------------------------------------------------------------

# Format: (relation, subject, canonical_answer, accepted_prefixes, direct_template, paraphrase_template)
FACT_TEMPLATES: Dict[str, Tuple[str, str, str]] = {
    "capital": (
        "The capital of {subject} is",
        "What is the capital city of {subject}? Answer:",
        "The capital of France is Paris\nThe capital of Japan is Tokyo\nThe capital of Italy is Rome\nThe capital of {subject} is",
    ),
    "element": (
        "The chemical symbol for {subject} is",
        "In the periodic table, the symbol of {subject} is",
        "The chemical symbol for Oxygen is O\nThe chemical symbol for Carbon is C\nThe chemical symbol for Iron is Fe\nThe chemical symbol for {subject} is",
    ),
    "author": (
        "The author of {subject} is",
        "The novel {subject} was written by",
        "The author of Hamlet is William Shakespeare\nThe author of Odyssey is Homer\nThe author of Inferno is Dante\nThe author of {subject} is",
    ),
    "continent": (
        "The country of {subject} is located in the continent of",
        "Geographically, {subject} is a country in",
        "The country of Brazil is located in the continent of South America\nThe country of Egypt is located in the continent of Africa\nThe country of India is located in the continent of Asia\nThe country of {subject} is located in the continent of",
    ),
}

# 148 unique-subject facts across 4 relations (strictly disjoint subjects, none overlapping few-shot anchors!)
RAW_FACTS: Tuple[Tuple[str, str, str], ...] = (
    # --- Capitals (56 unique countries, excluding France/Japan/Italy used in 3-shot) ---
    ("capital", "Germany", "Berlin"),
    ("capital", "Spain", "Madrid"),
    ("capital", "Portugal", "Lisbon"),
    ("capital", "Greece", "Athens"),
    ("capital", "Poland", "Warsaw"),
    ("capital", "Austria", "Vienna"),
    ("capital", "Sweden", "Stockholm"),
    ("capital", "Norway", "Oslo"),
    ("capital", "Finland", "Helsinki"),
    ("capital", "Denmark", "Copenhagen"),
    ("capital", "Netherlands", "Amsterdam"),
    ("capital", "Belgium", "Brussels"),
    ("capital", "Switzerland", "Bern"),
    ("capital", "Ireland", "Dublin"),
    ("capital", "Hungary", "Budapest"),
    ("capital", "Romania", "Bucharest"),
    ("capital", "Bulgaria", "Sofia"),
    ("capital", "Croatia", "Zagreb"),
    ("capital", "Serbia", "Belgrade"),
    ("capital", "Ukraine", "Kyiv"),
    ("capital", "Russia", "Moscow"),
    ("capital", "Turkey", "Ankara"),
    ("capital", "China", "Beijing"),
    ("capital", "South Korea", "Seoul"),
    ("capital", "Thailand", "Bangkok"),
    ("capital", "Vietnam", "Hanoi"),
    ("capital", "Indonesia", "Jakarta"),
    ("capital", "Philippines", "Manila"),
    ("capital", "Malaysia", "Kuala Lumpur"),
    ("capital", "Pakistan", "Islamabad"),
    ("capital", "Iran", "Tehran"),
    ("capital", "Iraq", "Baghdad"),
    ("capital", "Saudi Arabia", "Riyadh"),
    ("capital", "Israel", "Jerusalem"),
    ("capital", "Jordan", "Amman"),
    ("capital", "Morocco", "Rabat"),
    ("capital", "Kenya", "Nairobi"),
    ("capital", "Nigeria", "Abuja"),
    ("capital", "Ethiopia", "Addis Ababa"),
    ("capital", "Ghana", "Accra"),
    ("capital", "Algeria", "Algiers"),
    ("capital", "Tunisia", "Tunis"),
    ("capital", "Canada", "Ottawa"),
    ("capital", "Mexico", "Mexico City"),
    ("capital", "Argentina", "Buenos Aires"),
    ("capital", "Chile", "Santiago"),
    ("capital", "Colombia", "Bogota"),
    ("capital", "Peru", "Lima"),
    ("capital", "Venezuela", "Caracas"),
    ("capital", "Cuba", "Havana"),
    ("capital", "Australia", "Canberra"),
    ("capital", "New Zealand", "Wellington"),
    ("capital", "Iceland", "Reykjavik"),
    ("capital", "Czech Republic", "Prague"),
    ("capital", "Slovakia", "Bratislava"),
    ("capital", "Bangladesh", "Dhaka"),
    # --- Chemical Elements (40 unique elements, excluding Oxygen/Carbon/Iron) ---
    ("element", "Hydrogen", "H"),
    ("element", "Helium", "He"),
    ("element", "Lithium", "Li"),
    ("element", "Nitrogen", "N"),
    ("element", "Sodium", "Na"),
    ("element", "Magnesium", "Mg"),
    ("element", "Aluminum", "Al"),
    ("element", "Silicon", "Si"),
    ("element", "Phosphorus", "P"),
    ("element", "Sulfur", "S"),
    ("element", "Chlorine", "Cl"),
    ("element", "Argon", "Ar"),
    ("element", "Potassium", "K"),
    ("element", "Calcium", "Ca"),
    ("element", "Titanium", "Ti"),
    ("element", "Chromium", "Cr"),
    ("element", "Manganese", "Mn"),
    ("element", "Cobalt", "Co"),
    ("element", "Nickel", "Ni"),
    ("element", "Copper", "Cu"),
    ("element", "Zinc", "Zn"),
    ("element", "Silver", "Ag"),
    ("element", "Tin", "Sn"),
    ("element", "Iodine", "I"),
    ("element", "Xenon", "Xe"),
    ("element", "Tungsten", "W"),
    ("element", "Platinum", "Pt"),
    ("element", "Gold", "Au"),
    ("element", "Mercury", "Hg"),
    ("element", "Lead", "Pb"),
    ("element", "Uranium", "U"),
    ("element", "Neon", "Ne"),
    ("element", "Fluorine", "F"),
    ("element", "Boron", "B"),
    ("element", "Beryllium", "Be"),
    ("element", "Bromine", "Br"),
    ("element", "Krypton", "Kr"),
    ("element", "Radium", "Ra"),
    ("element", "Plutonium", "Pu"),
    ("element", "Arsenic", "As"),
    # --- Authors (32 unique works, excluding Hamlet/Odyssey/Inferno) ---
    ("author", "Pride and Prejudice", "Jane Austen"),
    ("author", "Moby-Dick", "Herman Melville"),
    ("author", "Frankenstein", "Mary Shelley"),
    ("author", "Dracula", "Bram Stoker"),
    ("author", "The Great Gatsby", "F. Scott Fitzgerald"),
    ("author", "1984", "George Orwell"),
    ("author", "Animal Farm", "George Orwell"),
    ("author", "Brave New World", "Aldous Huxley"),
    ("author", "The Catcher in the Rye", "J. D. Salinger"),
    ("author", "To Kill a Mockingbird", "Harper Lee"),
    ("author", "War and Peace", "Leo Tolstoy"),
    ("author", "Anna Karenina", "Leo Tolstoy"),
    ("author", "Crime and Punishment", "Fyodor Dostoevsky"),
    ("author", "Don Quixote", "Miguel de Cervantes"),
    ("author", "The Hobbit", "J. R. R. Tolkien"),
    ("author", "Dune", "Frank Herbert"),
    ("author", "Fahrenheit 451", "Ray Bradbury"),
    ("author", "Jane Eyre", "Charlotte Bronte"),
    ("author", "Wuthering Heights", "Emily Bronte"),
    ("author", "Great Expectations", "Charles Dickens"),
    ("author", "Oliver Twist", "Charles Dickens"),
    ("author", "A Tale of Two Cities", "Charles Dickens"),
    ("author", "The Adventures of Huckleberry Finn", "Mark Twain"),
    ("author", "The Old Man and the Sea", "Ernest Hemingway"),
    ("author", "The Metamorphosis", "Franz Kafka"),
    ("author", "Les Miserables", "Victor Hugo"),
    ("author", "The Count of Monte Cristo", "Alexandre Dumas"),
    ("author", "The Stranger", "Albert Camus"),
    ("author", "One Hundred Years of Solitude", "Gabriel Garcia Marquez"),
    ("author", "The Picture of Dorian Gray", "Oscar Wilde"),
    ("author", "Alice's Adventures in Wonderland", "Lewis Carroll"),
    ("author", "Macbeth", "William Shakespeare"),
    # --- Continents (20 unique countries distinct from capitals where possible -> distinct fact keys!) ---
    ("continent", "Zimbabwe", "Africa"),
    ("continent", "Tanzania", "Africa"),
    ("continent", "Senegal", "Africa"),
    ("continent", "Cameroon", "Africa"),
    ("continent", "Uganda", "Africa"),
    ("continent", "Bolivia", "South America"),
    ("continent", "Ecuador", "South America"),
    ("continent", "Paraguay", "South America"),
    ("continent", "Uruguay", "South America"),
    ("continent", "Mongolia", "Asia"),
    ("continent", "Cambodia", "Asia"),
    ("continent", "Nepal", "Asia"),
    ("continent", "Myanmar", "Asia"),
    ("continent", "Kazakhstan", "Asia"),
    ("continent", "Estonia", "Europe"),
    ("continent", "Latvia", "Europe"),
    ("continent", "Lithuania", "Europe"),
    ("continent", "Slovenia", "Europe"),
    ("continent", "Luxembourg", "Europe"),
    ("continent", "Fiji", "Oceania"),
)


def _check_splits_disjoint(
    train_f: Sequence[Tuple[str, str, str]],
    val_f: Sequence[Tuple[str, str, str]],
    test_f: Sequence[Tuple[str, str, str]],
) -> None:
    """Fail-closed guard verifying train/val/test subject sets are pairwise disjoint."""
    tr_s = {s for _, s, _ in train_f}
    va_s = {s for _, s, _ in val_f}
    te_s = {s for _, s, _ in test_f}
    require_ok(len(tr_s & va_s) == 0 and len(tr_s & te_s) == 0 and len(va_s & te_s) == 0, "SPLIT_LEAK", "Subject overlap")


def build_subject_disjoint_fact_splits(
    seed: int = 20261125,
    facts: Sequence[Tuple[str, str, str]] = RAW_FACTS,
) -> Dict[str, Any]:
    """Verify unique subjects across all facts and construct deterministic 70/15/15 splits."""
    subjects = [s for _, s, _ in facts]
    require_ok(len(subjects) == len(set(subjects)), "DUP_SUBJECT", "Subjects must be globally unique")
    require_ok(len(facts) >= 120, "TOO_FEW_FACTS", f"Expected >= 120 facts, got {len(facts)}")

    rng = random.Random(seed)
    by_rel: Dict[str, List[Tuple[str, str, str]]] = {}
    for item in facts:
        by_rel.setdefault(item[0], []).append(item)

    train_f: List[Tuple[str, str, str]] = []
    val_f: List[Tuple[str, str, str]] = []
    test_f: List[Tuple[str, str, str]] = []
    for rel in sorted(by_rel):
        items = list(by_rel[rel])
        rng.shuffle(items)
        n = len(items)
        n_tr = int(round(0.70 * n))
        n_va = max(2, int(round(0.15 * n)))
        train_f.extend(items[:n_tr])
        val_f.extend(items[n_tr : n_tr + n_va])
        test_f.extend(items[n_tr + n_va :])

    _check_splits_disjoint(train_f, val_f, test_f)
    return {"train": train_f, "val": val_f, "test": test_f}


def _resolve_git_exe() -> Optional[str]:
    """Return an absolute system git binary without trusting mutable PATH entries."""
    for cand in _GIT_EXE_CANDIDATES:
        if os.path.isfile(cand) and os.access(cand, os.X_OK):
            return cand
    return None


def _clean_git_env() -> Dict[str, str]:
    return {k: v for k, v in os.environ.items() if k not in _GIT_LOCAL_ENV_VARS}


def _capture_git_head(repo_dir: Path) -> Tuple[Optional[str], str]:
    """Capture live 40-char lowercase hex git HEAD + clean/dirty status, or not_captured_at_run_time."""
    git_exe = _resolve_git_exe()
    if git_exe is None:
        return None, "not_captured_at_run_time"
    env = _clean_git_env()
    try:
        head_p = subprocess.run(
            [git_exe, "-C", str(repo_dir), "rev-parse", "--verify", "HEAD"],
            capture_output=True,
            timeout=5,
            env=env,
            check=False,
        )
        head_out = head_p.stdout.decode("utf-8", errors="strict")
    except (OSError, subprocess.TimeoutExpired, UnicodeDecodeError):
        return None, "not_captured_at_run_time"
    if head_p.returncode != 0:
        return None, "not_captured_at_run_time"
    sha = head_out.strip()
    if _HEX40_RE.fullmatch(sha) is None:
        return None, "not_captured_at_run_time"
    try:
        st_p = subprocess.run(
            [git_exe, "-C", str(repo_dir), "status", "--porcelain"],
            capture_output=True,
            timeout=5,
            env=env,
            check=False,
        )
        st_out = st_p.stdout.decode("utf-8", errors="strict")
    except (OSError, subprocess.TimeoutExpired, UnicodeDecodeError):
        return sha, "captured_dirty"
    if st_p.returncode != 0:
        return sha, "captured_dirty"
    return (sha, "captured") if st_out.strip() == "" else (sha, "captured_dirty")


def _verify_git_commit_exists(repo_dir: Path, sha: str) -> bool:
    """Verify that a claimed 40-hex git_head commit exists in the enclosing git repository."""
    git_exe = _resolve_git_exe()
    if git_exe is None:
        return False
    try:
        chk = subprocess.run(
            [git_exe, "-C", str(repo_dir), "cat-file", "-e", f"{sha}^{{commit}}"],
            capture_output=True,
            timeout=5,
            env=_clean_git_env(),
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return chk.returncode == 0


def build_zone_b_git_head_fields(git_head: Optional[str], *, dirty: bool = False) -> Dict[str, Any]:
    """Emit paired (git_head, git_head_status) receipt fields fail-closed."""
    if git_head is None:
        return {"git_head": None, "git_head_status": "not_captured_at_run_time"}
    require_ok(
        type(git_head) is str and _HEX40_RE.fullmatch(git_head) is not None,
        "INVALID_GIT_HEAD",
        "git_head must be None or a 40-char lowercase hex commit hash",
    )
    return {"git_head": git_head, "git_head_status": "captured_dirty" if dirty else "captured"}


def _check_json_depth(obj: Any, depth: int, code: str, name: str) -> None:
    """Reject excessively nested JSON structures fail-closed."""
    require_ok(depth <= MAX_JSON_DEPTH, code, f"JSON nesting exceeds {MAX_JSON_DEPTH} in {name}")
    if isinstance(obj, dict):
        for val in obj.values():
            _check_json_depth(val, depth + 1, code, name)
    elif isinstance(obj, list):
        for item in obj:
            _check_json_depth(item, depth + 1, code, name)


def _parse_json_dict_bytes(raw_bytes: bytes, name: str, code: str) -> Dict[str, Any]:
    """Strictly parse UTF-8 JSON bytes rejecting NaN/Inf, overflow floats, duplicate keys, oversized ints, and deep nesting."""

    def _reject_constant(token: str) -> Any:
        raise Wave11ProbeError(code, f"Non-finite JSON constant in {name}: {token!r}")

    def _parse_strict_float(token: str) -> float:
        val = float(token)
        require_ok(math.isfinite(val), code, f"Non-finite JSON float in {name}: {token!r}")
        return val

    def _reject_dup_keys(pairs: List[Tuple[str, Any]]) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        for k, v in pairs:
            require_ok(k not in out, code, f"Duplicate JSON key in {name}: {k!r}")
            out[k] = v
        return out

    def _parse_bounded_int(token: str) -> int:
        digits = token[1:] if token.startswith("-") else token
        require_ok(len(digits) <= MAX_JSON_INT_DIGITS, code, f"JSON integer exceeds {MAX_JSON_INT_DIGITS} digits in {name}")
        return int(token)

    try:
        raw = raw_bytes.decode("utf-8")
        obj = json.loads(
            raw,
            parse_constant=_reject_constant,
            parse_float=_parse_strict_float,
            parse_int=_parse_bounded_int,
            object_pairs_hook=_reject_dup_keys,
        )
        require_ok(isinstance(obj, dict), code, f"Expected JSON object in {name}")
        _check_json_depth(obj, 0, code, name)
    except (UnicodeDecodeError, ValueError, RecursionError) as exc:
        raise Wave11ProbeError(code, f"Invalid JSON in {name}") from exc
    return obj


def _load_json_dict(path: Path, code: str, *, check_parents: Sequence[Path] = ()) -> Dict[str, Any]:
    """Read and parse a UTF-8 regular JSON object file fail-closed."""
    raw_bytes = _read_regular_file_bytes(path, code, check_parents=check_parents)
    return _parse_json_dict_bytes(raw_bytes, path.name, code)


def _require_probe_a_files(ckpt_path: Path, eval_bin_path: Path) -> None:
    """Fail-closed check that Probe A flagship checkpoint and eval.bin exist on disk."""
    require_ok(ckpt_path.is_file() and eval_bin_path.is_file(), "PROBE_A_MISSING", "flagship ckpt or eval.bin missing")


def _require_wk_ref(w_k_ref: Any) -> Any:
    """Fail-closed check that mid-depth layer reference holonomy tensor was captured."""
    require_ok(w_k_ref is not None, "WK_REF_MISSING", "layer 2 w_su2 missing")
    return w_k_ref


def _require_cuda_available(cuda_available: bool) -> None:
    """Fail-closed check that CUDA is available before executing --run-gpu."""
    require_ok(bool(cuda_available), "CUDA_REQUIRED", "--run-gpu requires CUDA")


def _resolve_prereg_sha256() -> Tuple[str, str]:
    """Verify pinned PREREG SHA-256 directly on disk (fail-closed; no constant-SHA fallback)."""
    bundle_p = Path(__file__).resolve().parent.parent / "preregistrations" / PREREG_FILENAME
    legacy_p = _expedition_root() / "notes" / "portals_wave11_2026_11_25" / PREREG_FILENAME
    for prereg_p in (bundle_p, legacy_p):
        if prereg_p.is_symlink() or prereg_p.exists():
            actual = _sha256_file(prereg_p, code="PREREG_MISSING", check_parents=(prereg_p.parent,))
            require_ok(hmac.compare_digest(actual, PINNED_PREREG_SHA256), "PREREG_HASH_MISMATCH", f"Unexpected PREREG hash {actual}")
            return actual, "disk_verified"
    raise Wave11ProbeError("PREREG_MISSING", PREREG_FILENAME)


def _is_strict_num(val: Any) -> bool:
    if isinstance(val, bool) or not isinstance(val, (int, float)):
        return False
    try:
        return math.isfinite(float(val))
    except OverflowError:
        return False


def _verify_probe_a_and_b_contents(results_obj: Dict[str, Any]) -> None:
    """Recompute Probe A and Probe B summaries/verdicts from recorded raw grids/pairs fail-closed."""
    ws = results_obj.get("wall_seconds")
    require_ok(_is_strict_num(ws) and float(ws) > 0.0, "RESULTS_PROBES_INVALID", "invalid wall_seconds")

    pa = results_obj.get("probe_a_loopcd_strang_holosphere_v3")
    try:
        recomp_a = _summarize_probe_a_grids(
            pa["t2048_loopcd_grid"],
            pa["t8192_loopcd_grid"],
            pa["t8192_strang_cancellation_real_weights"],
            pa["t2048_live_su2_guidance_layer5"],
        )
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        raise Wave11ProbeError("RESULTS_PROBES_INVALID", "malformed probe_a grids") from exc
    require_ok(isinstance(pa, dict) and pa.get("summary") == recomp_a, "RESULTS_PROBES_INVALID", "probe_a summary does not match raw grids")

    pb = results_obj.get("probe_b_platos_key_spheremap_procrustes")
    require_ok(isinstance(pb, dict), "RESULTS_PROBES_INVALID", "missing probe_b_platos_key_spheremap_procrustes")
    mrs = pb.get("model_recall_summary")
    pairs = pb.get("pairs")
    pb_sum = pb.get("summary")
    require_ok(
        isinstance(mrs, dict)
        and frozenset(mrs.keys()) == EXPECTED_PROBE_B_MODELS
        and isinstance(pairs, dict)
        and frozenset(pairs.keys()) == EXPECTED_PROBE_B_PAIRS
        and isinstance(pb_sum, dict),
        "RESULTS_PROBES_INVALID",
        "malformed probe_b structure",
    )
    for m_info in mrs.values():
        require_ok(
            isinstance(m_info, dict) and type(m_info.get("total_facts")) is int and m_info.get("total_facts") == len(RAW_FACTS),
            "RESULTS_PROBES_INVALID",
            "probe_b model_recall_summary total_facts mismatch",
        )
    try:
        n_pairs = len(pairs)
        mean_frob = sum(float(p["test_transfer_accuracy"]["Frob_Procrustes"]) for p in pairs.values()) / n_pairs
        mean_ols = sum(float(p["test_transfer_accuracy"]["OLS_Procrustes"]) for p in pairs.values()) / n_pairs
        mean_sph = sum(float(p["test_transfer_accuracy"]["SphereMap_Quadrupole_Procrustes"]) for p in pairs.values()) / n_pairs
        mean_rand = sum(float(p["test_transfer_accuracy"]["Random_Orthogonal_Null"]) for p in pairs.values()) / n_pairs
        mean_shuf = sum(float(p["test_transfer_accuracy"]["Shuffled_Pair_Null"]) for p in pairs.values()) / n_pairs
        tot_dm = sum(int(p["dark_memory_recovery"]["n_dark_memories"]) for p in pairs.values())
        dm_frob = sum(float(p["dark_memory_recovery"]["Frob_Procrustes"]) * int(p["dark_memory_recovery"]["n_dark_memories"]) for p in pairs.values())
        dm_sph = sum(float(p["dark_memory_recovery"]["SphereMap_Quadrupole_Procrustes"]) * int(p["dark_memory_recovery"]["n_dark_memories"]) for p in pairs.values())
        dm_rand = sum(float(p["dark_memory_recovery"]["Random_Orthogonal_Null"]) * int(p["dark_memory_recovery"]["n_dark_memories"]) for p in pairs.values())
        dm_frob_rate = dm_frob / max(1, tot_dm)
        dm_sph_rate = dm_sph / max(1, tot_dm)
        dm_rand_rate = dm_rand / max(1, tot_dm)
        b1_pass, b2_pass = _eval_probe_b_gates(pairs, mean_frob, mean_ols, mean_sph, mean_rand, mean_shuf)
        b3_verdict = grade_probe_b_verdict(
            w11_b1_pass=b1_pass,
            mean_frob=mean_frob,
            mean_sph=mean_sph,
            mean_rand=mean_rand,
            mean_shuf=mean_shuf,
            tot_dm=tot_dm,
            dm_frob_rate=dm_frob_rate,
            dm_sph_rate=dm_sph_rate,
            dm_rand_rate=dm_rand_rate,
        )
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        raise Wave11ProbeError("RESULTS_PROBES_INVALID", "malformed probe_b pairs") from exc
    require_ok(
        pb_sum.get("gate_W11_B1_plato_replication_pass") is b1_pass
        and pb_sum.get("gate_W11_B2_ols_shrinkage_pass") is b2_pass
        and pb_sum.get("gate_W11_B3_spheremap_verdict") == b3_verdict
        and type(pb_sum.get("pooled_dark_memories_total")) is int
        and pb_sum.get("pooled_dark_memories_total") == tot_dm
        and _is_strict_num(pb_sum.get("mean_frob_procrustes"))
        and abs(float(pb_sum["mean_frob_procrustes"]) - mean_frob) <= 2e-4
        and _is_strict_num(pb_sum.get("mean_spheremap_quadrupole"))
        and abs(float(pb_sum["mean_spheremap_quadrupole"]) - mean_sph) <= 2e-4,
        "RESULTS_PROBES_INVALID",
        "probe_b summary or gate verdicts do not match recorded pair data",
    )


def verify_w11_zone_b_bundle(
    track_dir: Optional[Path] = None,
    *,
    expected_git_head: Optional[str] = None,
    verify_committed_pins: Optional[bool] = None,
) -> Dict[str, Any]:
    """Fail-closed verification of bound S121 Zone-B receipt, live results payload, probe verdicts, profile, and preregistration."""
    enforce_pins = (track_dir is None) if verify_committed_pins is None else bool(verify_committed_pins)
    tdir = track_dir if track_dir is not None else Path(__file__).parent
    prereg_dir = tdir.parent / "preregistrations"
    prereg_p = prereg_dir / PREREG_FILENAME
    results_p = tdir / "w11_live_loopcd_platosphere_results.json"
    receipt_p = tdir / "mlos_zone_b_w11_loopcd_platosphere.json"
    profile_p = tdir / "ux582hs-rtx3080-8gb.toml"

    prereg_sha = _sha256_file(prereg_p, code="ZONEB_PREREG_MISSING", check_parents=(tdir, prereg_dir))
    require_ok(hmac.compare_digest(prereg_sha, PINNED_PREREG_SHA256), "PREREG_HASH_MISMATCH", prereg_sha)

    results_raw = _read_regular_file_bytes(results_p, "ZONEB_FILE_MISSING", check_parents=(tdir,))
    receipt_raw = _read_regular_file_bytes(receipt_p, "ZONEB_FILE_MISSING", check_parents=(tdir,))
    profile_raw = _read_regular_file_bytes(profile_p, "ZONEB_FILE_MISSING", check_parents=(tdir,))
    results_file_sha = hashlib.sha256(results_raw).hexdigest()
    profile_sha = hashlib.sha256(profile_raw).hexdigest()

    results_obj = _parse_json_dict_bytes(results_raw, results_p.name, "RESULTS_JSON_INVALID")
    res_keys = frozenset(results_obj.keys())
    require_ok(
        REQUIRED_RESULTS_KEYS <= res_keys
        and res_keys <= (REQUIRED_RESULTS_KEYS | OPTIONAL_RESULTS_GIT_KEYS)
        and ("git_head" in res_keys) == ("git_head_status" in res_keys),
        "RESULTS_SCHEMA_INVALID",
        "unexpected or missing top-level keys in results JSON",
    )
    rec_payload_sha = results_obj.get("payload_sha256")
    require_ok(
        type(rec_payload_sha) is str and _HEX64_RE.fullmatch(rec_payload_sha) is not None,
        "RESULTS_SHA_MISSING",
        "missing or invalid lowercase hex payload_sha256",
    )
    results_body = {k: v for k, v in results_obj.items() if k != "payload_sha256"}
    exp_results_sha = hashlib.sha256(_canonical_json_bytes(results_body)).hexdigest()
    require_ok(hmac.compare_digest(rec_payload_sha, exp_results_sha), "RESULTS_SHA_MISMATCH", exp_results_sha)
    require_ok(
        results_obj.get("schema") == SCHEMA_W11_LIVE
        and results_obj.get("prereg_filename") == PREREG_FILENAME
        and results_obj.get("prereg_sha256") == PINNED_PREREG_SHA256
        and results_obj.get("gpu_name") == EXPECTED_GPU_NAME,
        "RESULTS_PREREG_MISMATCH",
        "results schema, prereg_sha256, or gpu_name mismatch",
    )
    _verify_probe_a_and_b_contents(results_obj)

    receipt_obj = _parse_json_dict_bytes(receipt_raw, receipt_p.name, "RECEIPT_JSON_INVALID")
    require_ok(
        frozenset(receipt_obj.keys()) == EXPECTED_RECEIPT_KEYS,
        "RECEIPT_SCHEMA_INVALID",
        "unexpected or missing top-level keys in Zone-B receipt JSON",
    )
    rec_sha = receipt_obj.get("receipt_sha256")
    require_ok(
        type(rec_sha) is str and _HEX64_RE.fullmatch(rec_sha) is not None,
        "RECEIPT_SHA_MISSING",
        "missing or invalid lowercase hex receipt_sha256",
    )
    receipt_body = {k: v for k, v in receipt_obj.items() if k != "receipt_sha256"}
    exp_rec_sha = hashlib.sha256(_canonical_json_bytes(receipt_body)).hexdigest()
    require_ok(hmac.compare_digest(rec_sha, exp_rec_sha), "RECEIPT_SHA_MISMATCH", exp_rec_sha)

    exe_obj = receipt_obj.get("execution")
    host_obj = receipt_obj.get("host")
    start_tel = receipt_obj.get("start_gpu_telemetry")
    end_tel = receipt_obj.get("end_gpu_telemetry")
    start_reasons = start_tel.get("clocks_event_reasons") if isinstance(start_tel, dict) else None
    end_reasons = end_tel.get("clocks_event_reasons") if isinstance(end_tel, dict) else None
    require_ok(
        receipt_obj.get("schema") == "mlos-run-receipt/v0.1"
        and receipt_obj.get("determinism_zone") == "B"
        and receipt_obj.get("clean_hardware_run") is True
        and receipt_obj.get("anomalies") == []
        and receipt_obj.get("determinism_pins") == EXPECTED_DETERMINISM_PINS
        and receipt_obj.get("gpu_telemetry_available") is True
        and isinstance(host_obj, dict)
        and host_obj.get("host_os") == "linux"
        and host_obj.get("cpu_isa") == "x86_64"
        and type(host_obj.get("os_release")) is str
        and len(host_obj["os_release"]) > 0
        and type(host_obj.get("python_version")) is str
        and len(host_obj["python_version"]) > 0
        and receipt_obj.get("profile_id") == PINNED_PROFILE_ID
        and hmac.compare_digest(profile_sha, PINNED_PROFILE_SHA256)
        and isinstance(exe_obj, dict)
        and type(exe_obj.get("exit_code")) is int
        and exe_obj.get("exit_code") == 0
        and isinstance(start_tel, dict)
        and isinstance(end_tel, dict)
        and start_tel.get("gpu_name") == EXPECTED_GPU_NAME
        and end_tel.get("gpu_name") == EXPECTED_GPU_NAME
        and start_tel.get("gpu_processes_queried") is True
        and end_tel.get("gpu_processes_queried") is True
        and isinstance(start_reasons, dict)
        and isinstance(end_reasons, dict)
        and start_reasons.get("thermal_throttled") is False
        and end_reasons.get("thermal_throttled") is False
        and start_reasons.get("slowdown_active") is False
        and end_reasons.get("slowdown_active") is False,
        "RECEIPT_HARDWARE_INVALID",
        "Zone-B receipt schema, determinism_pins, host, hardware, GPU identity, or clean-run invariants failed",
    )

    git_head = receipt_obj.get("git_head")
    git_head_status = receipt_obj.get("git_head_status")
    if git_head is None:
        git_head_ok = git_head_status == "not_captured_at_run_time"
    elif (
        type(git_head) is str
        and _HEX40_RE.fullmatch(git_head) is not None
        and git_head_status in ("captured", "captured_dirty")
    ):
        if expected_git_head is not None:
            git_head_ok = (
                type(expected_git_head) is str
                and _HEX40_RE.fullmatch(expected_git_head) is not None
                and hmac.compare_digest(git_head, expected_git_head)
            )
        else:
            git_head_ok = _verify_git_commit_exists(tdir, git_head)
    else:
        git_head_ok = False
    if "git_head" in results_obj:
        results_git_ok = (
            results_obj["git_head"] == git_head
            and results_obj["git_head_status"] == git_head_status
        )
    else:
        results_git_ok = git_head is None
    require_ok(
        receipt_obj.get("bound_results_file") == "w11_live_loopcd_platosphere_results.json"
        and receipt_obj.get("bound_results_payload_sha256") == rec_payload_sha
        and receipt_obj.get("bound_results_file_sha256") == results_file_sha
        and receipt_obj.get("bound_prereg_sha256") == PINNED_PREREG_SHA256
        and receipt_obj.get("bound_profile_file") == "ux582hs-rtx3080-8gb.toml"
        and receipt_obj.get("profile_sha256") == profile_sha
        and git_head_ok
        and results_git_ok
        and receipt_obj.get("energy_power_status") == "UNCONTROLLED_LAPTOP_TELEMETRY_NOT_AN_ENERGY_CLAIM",
        "RECEIPT_BINDING_MISMATCH",
        "Zone-B receipt binding fields do not match on-disk results/profile/prereg",
    )
    if enforce_pins:
        require_ok(
            hmac.compare_digest(rec_payload_sha, PINNED_COMMITTED_RESULTS_PAYLOAD_SHA256)
            and hmac.compare_digest(results_file_sha, PINNED_COMMITTED_RESULTS_FILE_SHA256)
            and hmac.compare_digest(rec_sha, PINNED_COMMITTED_RECEIPT_SHA256),
            "RECEIPT_PIN_MISMATCH",
            "Zone-B bundle hashes do not match pinned committed Wave-11 live run artifacts",
        )
    return {
        "passed": True,
        "git_head_status": git_head_status,
        "prereg_sha256": prereg_sha,
        "profile_sha256": profile_sha,
        "results_payload_sha256": rec_payload_sha,
        "results_file_sha256": results_file_sha,
        "receipt_sha256": rec_sha,
    }


def _eval_selftest_flags(
    n_facts: int,
    split_total: int,
    overlap_count: int,
    prereg_ok: bool,
    zb_present: bool,
    zb_verified: bool,
) -> Tuple[bool, bool]:
    subj_disjoint_ok = (n_facts >= 120 and split_total == n_facts and overlap_count == 0)
    all_ok = subj_disjoint_ok and prereg_ok and (zb_verified if zb_present else True)
    return subj_disjoint_ok, all_ok


def run_stdlib_selftest(*, allow_missing_zone_b: bool = False) -> Dict[str, Any]:
    """Pure-stdlib verification of PREREG lock, committed Zone-B bundle, & subject-disjoint 148-fact suite."""
    prereg_sha, prereg_src = _resolve_prereg_sha256()
    here = Path(__file__).parent
    zb_p = here / "mlos_zone_b_w11_loopcd_platosphere.json"
    zb_present = zb_p.is_symlink() or zb_p.exists()
    zb_verified = False
    if zb_present or not allow_missing_zone_b:
        zb = verify_w11_zone_b_bundle(here, verify_committed_pins=True)
        zb_verified = bool(zb["passed"])
        zb_present = True
    splits = build_subject_disjoint_fact_splits(20261125)
    tr_s = {s for _, s, _ in splits["train"]}
    va_s = {s for _, s, _ in splits["val"]}
    te_s = {s for _, s, _ in splits["test"]}
    overlap_count = len(tr_s & va_s) + len(tr_s & te_s) + len(va_s & te_s)
    subj_disjoint_ok, all_ok = _eval_selftest_flags(
        len(RAW_FACTS),
        sum(len(v) for v in splits.values()),
        overlap_count,
        hmac.compare_digest(prereg_sha, PINNED_PREREG_SHA256),
        zb_present,
        zb_verified,
    )
    payload: Dict[str, Any] = {
        "schema": SCHEMA_W11_SELFTEST,
        "prereg_filename": PREREG_FILENAME,
        "prereg_sha256": prereg_sha,
        "prereg_source": prereg_src,
        "zone_b_bundle_verified": zb_verified,
        "total_unique_facts": len(RAW_FACTS),
        "split_counts": {k: len(v) for k, v in splits.items()},
        "relations": sorted({r for r, _, _ in RAW_FACTS}),
        "subject_disjoint_pass": subj_disjoint_ok,
        "passed": all_ok,
    }
    payload["payload_sha256"] = hashlib.sha256(_canonical_json_bytes(payload)).hexdigest()
    return payload


# ---------------------------------------------------------------------------
# 2. Probe A: Live LoopCD-Hidden + Palindromic Strang SU(2) on HoloSphere-V3
# ---------------------------------------------------------------------------


def _summarize_probe_a_grids(
    grid_2048: Dict[str, Dict[str, Any]],
    grid_8192: Dict[str, Dict[str, Any]],
    strang_8192: Dict[str, Dict[str, Any]],
    su2_live_2048: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    """Pure-stdlib Probe A gate & summary reducer (extracted for direct R5/BoolOp coverage)."""
    base_l6_8192 = grid_8192["L6_k1_om0.0"]["bpb"]
    best_l6_8192_k, best_l6_8192_v = min(
        ((k, v) for k, v in grid_8192.items() if v["L_target"] == 6 and v["omega"] > 0.0),
        key=lambda kv: kv[1]["bpb"],
    )
    base_l4_8192 = grid_8192["L4_k1_om0.0"]["bpb"]
    best_l4_8192_k, best_l4_8192_v = min(
        ((k, v) for k, v in grid_8192.items() if v["L_target"] == 4 and v["omega"] > 0.0),
        key=lambda kv: kv[1]["bpb"],
    )
    base_l3_8192 = grid_8192["L3_k1_om0.0"]["bpb"]
    best_l3_8192_k, best_l3_8192_v = min(
        ((k, v) for k, v in grid_8192.items() if v["L_target"] == 3 and v["omega"] > 0.0),
        key=lambda kv: kv[1]["bpb"],
    )
    min_strang_ratio = min(v["left_over_right_err_ratio"] for v in strang_8192.values())

    base_su2 = su2_live_2048["unguided_om0.0"]["bpb"]
    best_su2_k, best_su2_v = min(
        ((k, v) for k, v in su2_live_2048.items() if k != "unguided_om0.0"),
        key=lambda kv: kv[1]["bpb"],
    )

    w11_a1_pass = min_strang_ratio >= 5.0
    l6_gain = best_l6_8192_v["bpb"] - base_l6_8192
    l4_gain = best_l4_8192_v["bpb"] - base_l4_8192
    l3_gain = best_l3_8192_v["bpb"] - base_l3_8192
    su2_gain = best_su2_v["bpb"] - base_su2

    base_l6_2048 = grid_2048["L6_k1_om0.0"]["bpb"]
    best_l6_2048_v = min((v for v in grid_2048.values() if v["L_target"] == 6 and v["omega"] > 0.0), key=lambda v: v["bpb"])
    l6_2048_gain = best_l6_2048_v["bpb"] - base_l6_2048

    any_top1_gain = (
        any(v["top1_acc"] > grid_8192[f"L{v['L_target']}_k1_om0.0"]["top1_acc"] for v in grid_8192.values() if v["omega"] > 0.0)
        or any(v["top1_acc"] > grid_2048[f"L{v['L_target']}_k1_om0.0"]["top1_acc"] for v in grid_2048.values() if v["omega"] > 0.0)
        or any(v["top1_acc"] > su2_live_2048["unguided_om0.0"]["top1_acc"] for k, v in su2_live_2048.items() if k != "unguided_om0.0")
    )
    any_bpb_gain = (l6_gain < 0.0) or (l6_2048_gain < 0.0) or (l4_gain < 0.0) or (l3_gain < 0.0) or (su2_gain < 0.0)

    w11_a2_verdict = grade_probe_a_verdict(
        w11_a1_pass=w11_a1_pass,
        l6_gain=l6_gain,
        l6_2048_gain=l6_2048_gain,
        l4_gain=l4_gain,
        l3_gain=l3_gain,
        su2_gain=su2_gain,
        any_bpb_gain=any_bpb_gain,
        any_top1_gain=any_top1_gain,
    )
    return {
        "base_L6_t8192_bpb": base_l6_8192,
        "best_guided_L6_t8192": {"config": best_l6_8192_k, **best_l6_8192_v, "delta_bpb": round(l6_gain, 6)},
        "base_L4_t8192_bpb": base_l4_8192,
        "best_guided_L4_t8192": {"config": best_l4_8192_k, **best_l4_8192_v, "delta_bpb": round(l4_gain, 6)},
        "base_L3_t8192_bpb": base_l3_8192,
        "best_guided_L3_t8192": {"config": best_l3_8192_k, **best_l3_8192_v, "delta_bpb": round(l3_gain, 6)},
        "base_su2_t2048_bpb": base_su2,
        "best_su2_t2048": {"config": best_su2_k, **best_su2_v, "delta_bpb": round(su2_gain, 6)},
        "min_strang_left_over_right_ratio_t8192": min_strang_ratio,
        "gate_W11_A1_strang_ge_5x": w11_a1_pass,
        "gate_W11_A2_verdict": w11_a2_verdict,
    }


def _run_probe_a_loopcd_and_strang(torch: Any, device: Any, ckpt_path: Path, eval_bin_path: Path) -> Dict[str, Any]:
    """Probe A (EXP-Q25a / EXP-Q26b) on converged holosphere_v3_15m_flagship.pt (read-only!)."""
    import torch.nn.functional as F  # type: ignore[import-not-found]

    exp = _expedition_root()
    v3_dir = exp / "track-s114-holosphere-geometry-silicon" / "v3_scaleup"
    e2e_dir = exp / "track-s117-holosphere-chunk32-bwd-and-h256" / "e2e_engine"
    s116_dir = exp / "track-s116-holosphere-persistent-megakernel"
    for p in (str(v3_dir), str(e2e_dir), str(s116_dir)):
        if p not in sys.path:
            sys.path.insert(0, p)

    import holosphere_v3_ablation as v3_ab  # type: ignore[import-not-found]
    import holosphere_v3_cuda_engine as v3_eng  # type: ignore[import-not-found]
    import run_holosphere_v3_flagship_train as fl_mod  # type: ignore[import-not-found]

    _require_probe_a_files(ckpt_path, eval_bin_path)
    ckpt = torch.load(str(ckpt_path), map_location="cpu", weights_only=True)
    _, s116_a16, s117_op = v3_ab._import_torch_stack()
    orig_sq = s116_a16.SiliquantA16BlockH4STE
    s116_a16.SiliquantA16BlockH4STE = v3_eng.FusedA16BlockH4STECuda  # type: ignore[assignment]
    try:
        comps = v3_ab._build_torch_components(torch, s116_a16, s117_op)
        model = comps["HoloSphereV3RowLM"](v3_ab.SCALE_SPECS["15M"], v3_ab.ROW_NAMES[3], seed=2026).to(device)
        model.load_state_dict(ckpt["state_dict"], strict=True)
        fl_mod._patch_row3_with_fused_cuda_engine(torch, model, comps, s116_a16, v3_ab, v3_eng)
    finally:
        s116_a16.SiliquantA16BlockH4STE = orig_sq  # type: ignore[assignment]
    model.eval()

    ev_raw = eval_bin_path.read_bytes()
    ev_2048 = fl_mod._build_bos_chunks(torch, ev_raw, seq_len=2049, max_chunks=16)
    ev_8192 = fl_mod._build_bos_chunks(torch, ev_raw, seq_len=8193, max_chunks=8)

    def _unit_norm(t: Any, eps: float = 1e-6) -> Any:
        return t * torch.rsqrt((t * t).sum(dim=-1, keepdim=True) + eps * eps)

    def _quat_mul(a: Any, b: Any) -> Any:
        return torch.stack((
            a[..., 0]*b[..., 0] - a[..., 1]*b[..., 1] - a[..., 2]*b[..., 2] - a[..., 3]*b[..., 3],
            a[..., 0]*b[..., 1] + a[..., 1]*b[..., 0] + a[..., 2]*b[..., 3] - a[..., 3]*b[..., 2],
            a[..., 0]*b[..., 2] - a[..., 1]*b[..., 3] + a[..., 2]*b[..., 0] + a[..., 3]*b[..., 1],
            a[..., 0]*b[..., 3] + a[..., 1]*b[..., 2] - a[..., 2]*b[..., 1] + a[..., 3]*b[..., 0],
        ), dim=-1)

    def _cayley(w: Any) -> Any:
        w2 = (w * w).sum(dim=-1, keepdim=True)
        inv = 1.0 / (1.0 + w2)
        return torch.cat(((1.0 - w2) * inv, 2.0 * w * inv), dim=-1)

    def _inv_cayley(q: Any) -> Any:
        return q[..., 1:] / (1.0 + q[..., :1]).clamp_min(1e-6)

    def _compose_cayley_vec(a: Any, b: Any) -> Any:
        na = (a * a).sum(dim=-1, keepdim=True)
        nb = (b * b).sum(dim=-1, keepdim=True)
        dot = (a * b).sum(dim=-1, keepdim=True)
        denom = (1.0 + na * nb - 2.0 * dot).clamp_min(1e-6)
        cr = torch.cross(a, b, dim=-1)
        return ((1.0 - nb) * a + (1.0 - na) * b + 2.0 * cr) / denom

    # Helper to evaluate LoopCD-Hidden across all (L_target, k, omega) in ONE cached layer-state pass!
    def _eval_loopcd_grid(chunks: Sequence[Any], tail_tokens: int, bsz: int) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        # Accumulate NLL & top-1 correct across (L_target in {6,4,3}, k, omega)
        omegas = (0.0, 0.1, 0.25, 0.5, 0.75, 1.0)
        configs: List[Tuple[int, int, float]] = []
        for k in (1, 2, 3):
            for om in omegas:
                configs.append((6, k, om))
        for lt in (4, 3):
            for k in (1, 2):
                for om in omegas:
                    configs.append((lt, k, om))

        nll_acc = {cfg: 0.0 for cfg in configs}
        top1_acc = {cfg: 0 for cfg in configs}
        total_toks = 0

        # Also accumulate Palindromic Strang BCH empirical cancellation stats on real w_su2 tensors!
        strang_stats: Dict[str, Dict[str, float]] = {}
        for k in (1, 2, 3):
            for om in (0.25, 0.5, 1.0):
                strang_stats[f"k{k}_om{om}"] = {"right_sq_sum": 0.0, "left_sq_sum": 0.0, "count": 0.0}

        with torch.no_grad():
            for i in range(0, len(chunks), bsz):
                batch = torch.stack(list(chunks[i : i + bsz]), dim=0).to(device)
                inp = batch[:, :-1]
                tgt = batch[:, 1:]
                seq_l = inp.shape[1]
                c_start = max(0, seq_l - tail_tokens)
                tgt_tail = tgt[:, c_start:]
                total_toks += int(tgt_tail.numel())

                with torch.amp.autocast("cuda", dtype=torch.bfloat16):
                    x = model.byte_conv(comps["h256_bent4_inject_zero_vram"](inp, model.d_model))
                    hs: List[Any] = [x[:, c_start:].float()]  # h_0..h_6 on tail
                    ws_layers: List[Any] = []
                    for blk in model.blocks:
                        x, aux = blk(x, gumbel_temp=0.0, step_seed=42)
                        hs.append(x[:, c_start:].float())
                        ws_layers.append(aux["w_su2"][:, c_start:].float())

                # Measure exact Strang BCH cancellation on real trained w_su2 vectors (layers k-1 vs 5)
                w5 = ws_layers[5]
                for k in (1, 2, 3):
                    wk = ws_layers[k - 1]
                    w_delta = _compose_cayley_vec(-wk, w5)
                    for om in (0.25, 0.5, 1.0):
                        w_lin = (1.0 + om) * w5 - om * wk
                        w_right = _compose_cayley_vec(w5, om * w_delta)
                        w_left = _compose_cayley_vec(om * w_delta, w5)
                        q_lin = _cayley(w_lin)
                        q_right = _cayley(w_right)
                        q_left = _cayley(w_left)
                        e_r = float(((q_lin - q_right).pow(2).sum(dim=-1)).sum().item())
                        e_l = float(((q_lin - q_left).pow(2).sum(dim=-1)).sum().item())
                        key = f"k{k}_om{om}"
                        strang_stats[key]["right_sq_sum"] += e_r
                        strang_stats[key]["left_sq_sum"] += e_l
                        strang_stats[key]["count"] += float(w5[..., 0].numel())

                # Evaluate all LoopCD-Hidden (L_target, k, omega) configs directly via lm_head!
                w_lm = v3_eng.FusedA16BlockH4STECuda.apply(model.lm_head.weight).float()
                l_sc = model.logit_scale.float()
                for cfg in configs:
                    lt, k, om = cfg
                    h_end = hs[lt]
                    h_early = hs[k]
                    h_guided = _unit_norm(h_end + om * (h_end - h_early)) if om > 0.0 else _unit_norm(h_end)
                    lg = F.linear(h_guided, w_lm) * l_sc
                    nll = F.cross_entropy(lg.reshape(-1, VOCAB_SIZE), tgt_tail.reshape(-1), reduction="sum")
                    nll_acc[cfg] += float(nll.item())
                    top1_acc[cfg] += int((lg.argmax(dim=-1) == tgt_tail).sum().item())

        grid_out: Dict[str, Any] = {}
        for cfg in configs:
            lt, k, om = cfg
            grid_out[f"L{lt}_k{k}_om{om}"] = {
                "L_target": lt,
                "k_early": k,
                "omega": om,
                "bpb": round((nll_acc[cfg] / float(total_toks)) / math.log(2.0), 6),
                "top1_acc": round(top1_acc[cfg] / float(total_toks), 6),
            }

        strang_out: Dict[str, Any] = {}
        for key, st in strang_stats.items():
            mean_r = st["right_sq_sum"] / max(1.0, st["count"])
            mean_l = st["left_sq_sum"] / max(1.0, st["count"])
            strang_out[key] = {
                "mean_sq_chordal_err_right": float(f"{mean_r:.4e}"),
                "mean_sq_chordal_err_left": float(f"{mean_l:.4e}"),
                "left_over_right_err_ratio": round(mean_l / max(1e-30, mean_r), 2),
            }
        return grid_out, strang_out

    # Also test LIVE SU(2) holonomy guidance inside layer 5 (right-ordered vs linear vs left-ordered) on ev_2048!
    def _eval_su2_guidance_live(chunks: Sequence[Any], tail_tokens: int, bsz: int) -> Dict[str, Any]:
        modes = ("unguided", "strang_linear", "exact_right_bch", "reversed_left_ctrl")
        omegas = (0.1, 0.25, 0.5, 0.75, 1.0)
        res_nll: Dict[str, float] = {"unguided_om0.0": 0.0}
        res_top1: Dict[str, int] = {"unguided_om0.0": 0}
        for m in modes[1:]:
            for om in omegas:
                res_nll[f"{m}_om{om}"] = 0.0
                res_top1[f"{m}_om{om}"] = 0
        total_toks = 0
        blk5 = model.blocks[5]
        w_lm = v3_eng.FusedA16BlockH4STECuda.apply(model.lm_head.weight).float()
        l_sc = model.logit_scale.float()

        with torch.no_grad():
            for i in range(0, len(chunks), bsz):
                batch = torch.stack(list(chunks[i : i + bsz]), dim=0).to(device)
                inp = batch[:, :-1]
                tgt = batch[:, 1:]
                seq_l = inp.shape[1]
                c_start = max(0, seq_l - tail_tokens)
                tgt_tail = tgt[:, c_start:]
                total_toks += int(tgt_tail.numel())

                with torch.amp.autocast("cuda", dtype=torch.bfloat16):
                    x = model.byte_conv(comps["h256_bent4_inject_zero_vram"](inp, model.d_model))
                    w_k_ref = None
                    for li in range(5):
                        x, aux_l = model.blocks[li](x, gumbel_temp=0.0, step_seed=42)
                        if li == 2:  # mid-depth layer k=3 reference holonomy
                            w_k_ref = aux_l["w_su2"].float()

                    # Compute layer-5 pre-SU2 state h_gen and baseline w5
                    h_gen, _ = blk5._feature_space_v_ring_stage1(x, gumbel_temp=0.0, step_seed=42)
                    raw_w5 = blk5.w_omega(h_gen).view(inp.shape[0], seq_l, model.d_model // 4, 3)
                    w5_base = comps["CayleyInverseFisherPrecond"].apply(
                        raw_w5 * blk5.omega_scale.view(1, 1, model.d_model // 4, 1), float(v3_ab.CAYLEY_W_MAX_NORM)
                    ).view(inp.shape[0], seq_l, model.n_heads, 8, 3).float()

                w_k_ref = _require_wk_ref(w_k_ref)
                w_delta = _compose_cayley_vec(-w_k_ref, w5_base)

                def _finish_blk5_and_score(w_use: Any, key_name: str) -> None:
                    with torch.amp.autocast("cuda", dtype=torch.bfloat16):
                        y_c, _, _ = v3_eng.holosphere_v3_chunk32_fused(
                            h_gen.float(), w_use.float(), blk5.w_q_fast.float(),
                            cayley_t=0.25, gamma=0.90, eta=0.15, eps=1e-6, project_boundary_tangent=1,
                        )
                        h_c = _unit_norm(blk5.w_cell_out(y_c.to(h_gen.dtype)))
                        xm = _unit_norm(h_gen + blk5.alpha_cell.abs() * (h_c - h_gen))
                        hm = _unit_norm(blk5.ffn(xm))
                        xo = _unit_norm(xm + blk5.alpha_mlp.abs() * (hm - xm))
                    lg = F.linear(_unit_norm(xo[:, c_start:].float()), w_lm) * l_sc
                    res_nll[key_name] += float(F.cross_entropy(lg.reshape(-1, VOCAB_SIZE), tgt_tail.reshape(-1), reduction="sum").item())
                    res_top1[key_name] += int((lg.argmax(dim=-1) == tgt_tail).sum().item())

                _finish_blk5_and_score(w5_base, "unguided_om0.0")
                for om in omegas:
                    _finish_blk5_and_score((1.0 + om) * w5_base - om * w_k_ref, f"strang_linear_om{om}")
                    _finish_blk5_and_score(_compose_cayley_vec(w5_base, om * w_delta), f"exact_right_bch_om{om}")
                    _finish_blk5_and_score(_compose_cayley_vec(om * w_delta, w5_base), f"reversed_left_ctrl_om{om}")

        return {
            k: {
                "bpb": round((res_nll[k] / float(total_toks)) / math.log(2.0), 6),
                "top1_acc": round(res_top1[k] / float(total_toks), 6),
            }
            for k in sorted(res_nll)
        }

    sys.stderr.write("[Probe A] Evaluating LoopCD-Hidden + Strang SU(2) on T=2048 & T=8192...\n")
    sys.stderr.flush()
    grid_2048, strang_2048 = _eval_loopcd_grid(ev_2048, tail_tokens=512, bsz=2)
    grid_8192, strang_8192 = _eval_loopcd_grid(ev_8192, tail_tokens=1024, bsz=2)
    su2_live_2048 = _eval_su2_guidance_live(ev_2048, tail_tokens=512, bsz=2)

    summary_a = _summarize_probe_a_grids(grid_2048, grid_8192, strang_8192, su2_live_2048)

    del model, ckpt
    gc.collect()
    torch.cuda.empty_cache()

    return {
        "t2048_loopcd_grid": grid_2048,
        "t8192_loopcd_grid": grid_8192,
        "t2048_strang_cancellation_real_weights": strang_2048,
        "t8192_strang_cancellation_real_weights": strang_8192,
        "t2048_live_su2_guidance_layer5": su2_live_2048,
        "summary": summary_a,
    }


# ---------------------------------------------------------------------------
# 3. Probe B: Plato's Key x Portal x/pi SphereMap Procrustes on Offline LLMs
# ---------------------------------------------------------------------------


def _resolve_offline_hf_snapshot(model_id: str) -> Path:
    hub_env = os.environ.get("HF_HUB_CACHE") or os.environ.get("HUGGINGFACE_HUB_CACHE")
    hub = Path(hub_env) if hub_env else Path(os.environ.get("HF_HOME", str(Path.home() / ".cache" / "huggingface"))) / "hub"
    key = "models--" + model_id.replace("/", "--")
    snaps = sorted((hub / key / "snapshots").glob("*"))
    require_ok(len(snaps) > 0, "OFFLINE_MODEL_MISSING", f"No cached snapshot for {model_id}")
    return snaps[-1]


_NEGATION_HEADS = frozenset({"not", "no", "never", "neither", "none", "unknown", "isn't", "wasn't", "aren't"})
_CLAUSE_SPLIT_RE = re.compile(r"[\n,;:!?()\"]")


def grade_probe_a_verdict(
    *,
    w11_a1_pass: bool,
    l6_gain: float,
    l6_2048_gain: float,
    l4_gain: float,
    l3_gain: float,
    su2_gain: float,
    any_bpb_gain: bool,
    any_top1_gain: bool,
) -> str:
    """Fail-closed Probe A gate grader (CONFIRMED strictly requires W11-A1 pass)."""
    if w11_a1_pass and (
        l6_gain <= -0.010 or l6_2048_gain <= -0.010 or l4_gain <= -0.050 or l3_gain <= -0.050 or su2_gain <= -0.010
    ):
        return "CONFIRMED"
    if w11_a1_pass and (any_bpb_gain or any_top1_gain):
        return "PARTIAL"
    return "FALSIFIED"


def grade_probe_b_verdict(
    *,
    w11_b1_pass: bool,
    mean_frob: float,
    mean_sph: float,
    mean_rand: float,
    mean_shuf: float,
    tot_dm: int,
    dm_frob_rate: float,
    dm_sph_rate: float,
    dm_rand_rate: float,
) -> str:
    """Fail-closed Probe B gate grader (B2 fix: NEVER emit CONFIRMED if W11-B1 fails!)."""
    diff_sph_frob = mean_sph - mean_frob
    dm_confirmed = tot_dm > 0 and dm_sph_rate > 0.18 and dm_sph_rate > dm_frob_rate and dm_sph_rate > dm_rand_rate
    if w11_b1_pass and (diff_sph_frob >= 0.03 or dm_confirmed):
        return "CONFIRMED"
    if not w11_b1_pass:
        if mean_frob > max(mean_rand, mean_shuf) and diff_sph_frob >= -0.02:
            return "PARTIAL_UNDERPOWERED"
        return "FALSIFIED"
    if diff_sph_frob >= -0.02:
        return "PARTIAL"
    return "FALSIFIED"


def _normalize_ans(s: str) -> str:
    clause = _CLAUSE_SPLIT_RE.split(s.strip())[0].strip().rstrip(".")
    return " ".join(clause.lower().replace(".", " ").split())


def _answer_matches(generated: str, canonical: str) -> bool:
    """Hardened B1 exact word-boundary / full-answer matcher (rejects prefix collisions & negations)."""
    raw_clause = _CLAUSE_SPLIT_RE.split(generated.strip())[0].strip()
    can_raw = canonical.strip()
    if not raw_clause or not can_raw:
        return False

    # 1. Chemical symbols (1-2 chars like "H", "He", "I", "As"): strict single-token case-sensitive match!
    # Eliminates "H"->"He", "N"->"Ne", "I think so"->"I", "as a result"->"As".
    if len(can_raw) <= 2:
        toks_raw = raw_clause.split()
        if len(toks_raw) != 1:
            return False
        tok0 = toks_raw[0].strip().rstrip(".")
        return tok0 == can_raw

    # 2. Multi-character answers (capitals, continents, authors): exact normalized word-boundary match.
    gen_n = _normalize_ans(raw_clause)
    can_n = _normalize_ans(can_raw)
    if not gen_n or not can_n:
        return False
    gen_toks = gen_n.split()
    can_toks = can_n.split()
    if gen_toks[0] in _NEGATION_HEADS:
        return False
    # Exact full canonical token sequence at start of answer
    if gen_toks[: len(can_toks)] == can_toks:
        return True
    # Multi-word author surname shortcut ONLY when answer begins directly with the surname (never "Not Shakespeare" / "J.K. Rowling")
    if len(can_toks) >= 2 and len(can_toks[-1]) >= 4 and gen_toks[0] == can_toks[-1]:
        return True
    # Explicit Kiev/Kyiv spelling alias (exact first token)
    if can_n == "kyiv" and gen_toks[0] == "kiev":
        return True
    return False


def make_swap_tuples(f_list: Sequence[Tuple[str, str, str]]) -> List[Tuple[str, str, str, str]]:
    """Deterministic within-relation swap pairings strictly enforcing tgt_subj != d_subj AND tgt_ans != d_ans."""
    by_r: Dict[str, List[Tuple[str, str, str]]] = {}
    for it in f_list:
        by_r.setdefault(it[0], []).append(it)
    out_t: List[Tuple[str, str, str, str]] = []
    for rel, items in sorted(by_r.items()):
        n_it = len(items)
        if n_it < 2:
            continue
        for idx, (_, d_subj, d_ans) in enumerate(items):
            d_ans_norm = _normalize_ans(d_ans)
            for step in range(1, n_it):
                _, tgt_subj, tgt_ans = items[(idx + step) % n_it]
                if tgt_subj != d_subj and _normalize_ans(tgt_ans) != d_ans_norm:
                    out_t.append((rel, d_subj, d_ans, tgt_subj))
                    break
    return out_t


def _locate_subject_last_token(tokenizer: Any, prompt: str, subject: str) -> Tuple[List[int], int]:
    """Find the exact token index of the last token of `subject` inside `prompt`."""
    idx = prompt.rfind(subject)
    require_ok(idx >= 0, "SUBJ_NOT_IN_PROMPT", f"{subject} not in {prompt}")
    prefix_incl = prompt[: idx + len(subject)]
    ids_full = tokenizer.encode(prompt, add_special_tokens=True)
    ids_pref = tokenizer.encode(prefix_incl, add_special_tokens=True)
    subj_pos = min(len(ids_full) - 1, max(0, len(ids_pref) - 1))
    return ids_full, subj_pos


def _greedy_decode_kv(
    torch: Any,
    model: Any,
    tok: Any,
    inp: Any,
    *,
    max_new_tokens: int = 5,
    first_out: Any = None,
) -> str:
    """Fast, 100% deterministic KV-cached greedy argmax decoder (zero GenerationConfig warnings)."""
    out = first_out if first_out is not None else model(input_ids=inp, use_cache=True)
    past = out.past_key_values
    nxt = out.logits[:, -1, :].argmax(dim=-1, keepdim=True)
    gen_ids: List[int] = [int(nxt.item())]
    eos_id = tok.eos_token_id
    for _ in range(max_new_tokens - 1):
        if eos_id is not None and gen_ids[-1] == int(eos_id):
            break
        out = model(input_ids=nxt, past_key_values=past, use_cache=True)
        past = out.past_key_values
        nxt = out.logits[:, -1, :].argmax(dim=-1, keepdim=True)
        gen_ids.append(int(nxt.item()))
    return str(tok.decode(gen_ids, skip_special_tokens=True))


def _extract_model_facts_and_keys(
    torch: Any,
    model_id: str,
    facts: Sequence[Tuple[str, str, str]],
    device: Any,
) -> Dict[str, Any]:
    """Load one offline LLM, evaluate direct/3-shot/paraphrase recall, and extract hidden states at subject token."""
    from transformers import AutoModelForCausalLM, AutoTokenizer  # type: ignore[import-not-found]

    snap = _resolve_offline_hf_snapshot(model_id)
    tok = AutoTokenizer.from_pretrained(str(snap), local_files_only=True)
    model = AutoModelForCausalLM.from_pretrained(
        str(snap), local_files_only=True, dtype=torch.bfloat16, attn_implementation="eager"
    ).to(device)
    model.eval()
    n_layers = int(model.config.num_hidden_layers)
    d_model = int(model.config.hidden_size)
    # Sample 6 evenly-spaced candidate layers across 15%..55% of depth (Plato's Key peak is 22%..38%!)
    cand_layers = sorted({
        max(1, min(n_layers - 1, int(round(frac * n_layers))))
        for frac in (0.15, 0.22, 0.28, 0.34, 0.42, 0.50)
    })

    direct_ok: Dict[str, bool] = {}
    dark_mem_ok: Dict[str, bool] = {}
    keys_by_layer: Dict[int, Dict[str, Any]] = {l: {} for l in cand_layers}
    direct_preds: Dict[str, str] = {}

    with torch.no_grad():
        for rel, subj, ans in facts:
            t_dir, t_para, t_3shot = FACT_TEMPLATES[rel]
            p_dir = t_dir.format(subject=subj)
            ids_full, subj_pos = _locate_subject_last_token(tok, p_dir, subj)
            inp = torch.tensor([ids_full], dtype=torch.long, device=device)

            out = model(input_ids=inp, output_hidden_states=True, use_cache=True)
            for l in cand_layers:
                # hidden_states[l] = residual stream output after transformer block (l-1), shape [1, T, D]
                keys_by_layer[l][subj] = out.hidden_states[l][0, subj_pos].detach().float().cpu()

            # Greedy decode up to 5 new tokens reusing prefill KV cache!
            gen_txt = _greedy_decode_kv(torch, model, tok, inp, max_new_tokens=5, first_out=out)
            ok_dir = _answer_matches(gen_txt, ans)
            direct_ok[subj] = ok_dir
            direct_preds[subj] = gen_txt.strip()[:32]

            # If direct recall missed, test dark-memory qualification (3-shot OR paraphrase!)
            if not ok_dir:
                ok_dm = False
                for p_alt in (t_3shot.format(subject=subj), t_para.format(subject=subj)):
                    alt_ids = torch.tensor([tok.encode(p_alt, add_special_tokens=True)], dtype=torch.long, device=device)
                    txt_alt = _greedy_decode_kv(torch, model, tok, alt_ids, max_new_tokens=5)
                    if _answer_matches(txt_alt, ans):
                        ok_dm = True
                        break
                dark_mem_ok[subj] = ok_dm
            else:
                dark_mem_ok[subj] = False

    del model
    gc.collect()
    torch.cuda.empty_cache()
    return {
        "model_id": model_id,
        "n_layers": n_layers,
        "d_model": d_model,
        "cand_layers": cand_layers,
        "direct_ok": direct_ok,
        "dark_mem_ok": dark_mem_ok,
        "direct_preds": direct_preds,
        "keys_by_layer": keys_by_layer,
    }


def _fit_procrustes_maps(
    torch: Any,
    za_tr: Any,  # [N, dA] float32
    zb_tr: Any,  # [N, dB] float32
    *,
    seed: int = 2026,
    svd_rank: Optional[int] = None,
) -> Dict[str, Any]:
    """Fit all 4 closed-form alignment maps + random/shuffled controls (strictly on train facts!)."""
    mu_a = za_tr.mean(dim=0)
    mu_b = zb_tr.mean(dim=0)
    ca = za_tr - mu_a
    cb = zb_tr - mu_b

    # Optional PCA rank reduction (Plato's Key Fig. 4b: keep top-r PCs, set remainder to train mean!)
    if svd_rank is not None:
        r_a = min(svd_rank, ca.shape[0], ca.shape[1])
        r_b = min(svd_rank, cb.shape[0], cb.shape[1])
        _, _, vh_a = torch.linalg.svd(ca, full_matrices=False)
        _, _, vh_b = torch.linalg.svd(cb, full_matrices=False)
        pa = vh_a[:r_a].T  # [dA, r_a]
        pb = vh_b[:r_b].T  # [dB, r_b]
        ca_use = ca @ pa
        cb_use = cb @ pb
    else:
        pa = None
        pb = None
        ca_use = ca
        cb_use = cb

    # 1. Plain Frobenius O(d) Procrustes (Plato's Key baseline)
    cross = cb_use.T @ ca_use  # [dB', dA']
    u_m, s_vals, vh_m = torch.linalg.svd(cross, full_matrices=False)
    r_orth = u_m @ vh_m  # [dB', dA'] semi-orthogonal
    norm_a = float(ca_use.norm().item())
    norm_b = float(cb_use.norm().item())
    s_frob = norm_b / max(1e-8, norm_a)
    s_ols = float(s_vals.sum().item()) / max(1e-8, norm_a * norm_a)
    mean_rad_b = float(cb.norm(dim=-1).mean().item())

    # 2. Portal x/pi Quadrupole SphereMap-Aligned Procrustes
    eps_std = 1e-3
    std_a = ca.std(dim=0, unbiased=False).clamp_min(eps_std)
    std_b = cb.std(dim=0, unbiased=False).clamp_min(eps_std)
    qa = ca / std_a
    qb = cb / std_b
    ua = qa / qa.norm(dim=-1, keepdim=True).clamp_min(1e-6)
    ub = qb / qb.norm(dim=-1, keepdim=True).clamp_min(1e-6)
    u_s, _, vh_s = torch.linalg.svd(ub.T @ ua, full_matrices=False)
    r_sph = u_s @ vh_s

    # 3. Null controls: Random orthogonal rotation & Shuffled-pair Procrustes
    gen = torch.Generator(device="cpu").manual_seed(seed)
    g_rand = torch.randn((cb_use.shape[1], ca_use.shape[1]), generator=gen, dtype=torch.float32)
    u_r, _, vh_r = torch.linalg.svd(g_rand, full_matrices=False)
    r_rand = u_r @ vh_r

    perm = torch.randperm(ca_use.shape[0], generator=gen)
    u_sh, _, vh_sh = torch.linalg.svd(cb_use.T @ ca_use[perm], full_matrices=False)
    r_shuf = u_sh @ vh_sh

    def _apply_linear_r(z_a: Any, r_mat: Any, scale: float, shell_norm: bool = False) -> Any:
        c = z_a - mu_a
        if pa is not None:
            proj = (c @ pa) @ r_mat.T
            mapped = proj @ pb.T
        else:
            mapped = c @ r_mat.T
        if shell_norm:
            return mu_b + mean_rad_b * (mapped / mapped.norm(dim=-1, keepdim=True).clamp_min(1e-6))
        return mu_b + scale * mapped

    def _apply_spheremap(z_a: Any) -> Any:
        q = (z_a - mu_a) / std_a
        u = q / q.norm(dim=-1, keepdim=True).clamp_min(1e-6)
        v = (u @ r_sph.T) * std_b
        return mu_b + mean_rad_b * (v / v.norm(dim=-1, keepdim=True).clamp_min(1e-6))

    return {
        "s_frob": round(s_frob, 6),
        "s_ols": round(s_ols, 6),
        "ols_over_frob_ratio": round(s_ols / max(1e-8, s_frob), 6),
        "maps": {
            "Frob_Procrustes": lambda z: _apply_linear_r(z, r_orth, s_frob, shell_norm=False),
            "OLS_Procrustes": lambda z: _apply_linear_r(z, r_orth, s_ols, shell_norm=False),
            "ShellNorm_Procrustes": lambda z: _apply_linear_r(z, r_orth, 1.0, shell_norm=True),
            "SphereMap_Quadrupole_Procrustes": _apply_spheremap,
            "Random_Orthogonal_Null": lambda z: _apply_linear_r(z, r_rand, s_frob, shell_norm=False),
            "Shuffled_Pair_Null": lambda z: _apply_linear_r(z, r_shuf, s_frob, shell_norm=False),
        },
    }


def _eval_swap_accuracy_on_recipient(
    torch: Any,
    model_b: Any,
    tok_b: Any,
    layer_b: int,
    eval_pairs: Sequence[Tuple[str, str, str, Any]],  # (rel, target_subj, donor_ans, swapped_vec_cpu)
    device: Any,
) -> float:
    """Inject swapped hidden vector at layer_b's input/output on target_subj's last token & measure % answering donor_ans."""
    if not eval_pairs:
        return 0.0
    hits = 0
    # Hook onto model_b.model.layers[layer_b - 1] output (matches hidden_states[layer_b]!)
    target_block = model_b.model.layers[layer_b - 1]

    with torch.no_grad():
        for rel, tgt_subj, donor_ans, swap_vec in eval_pairs:
            p_tgt = FACT_TEMPLATES[rel][0].format(subject=tgt_subj)
            ids_full, subj_pos = _locate_subject_last_token(tok_b, p_tgt, tgt_subj)
            inp = torch.tensor([ids_full], dtype=torch.long, device=device)
            sv_dev = swap_vec.to(device=device)
            injected = {"done": False}

            def _hook(_mod: Any, _in: Any, out: Any) -> Any:
                if injected["done"]:
                    return out
                injected["done"] = True
                if isinstance(out, tuple):
                    h = out[0].clone()
                    h[0, subj_pos] = sv_dev.to(h.dtype)
                    return (h,) + out[1:]
                h = out.clone()
                h[0, subj_pos] = sv_dev.to(h.dtype)
                return h

            handle = target_block.register_forward_hook(_hook)
            try:
                gen_txt = _greedy_decode_kv(torch, model_b, tok_b, inp, max_new_tokens=5)
            finally:
                handle.remove()
            if _answer_matches(gen_txt, donor_ans):
                hits += 1
    return hits / float(len(eval_pairs))


def _filter_shared_and_dm_facts(
    splits: Dict[str, List[Tuple[str, str, str]]],
    all_facts: Sequence[Tuple[str, str, str]],
    ex_a: Dict[str, Any],
    ex_b: Dict[str, Any],
) -> Tuple[List[Tuple[str, str, str]], List[Tuple[str, str, str]], List[Tuple[str, str, str]], List[Tuple[str, str, str]]]:
    """Pure-stdlib Probe B shared-recall split filter and dark-memory selector."""
    tr_shared = [f for f in splits["train"] if ex_a["direct_ok"][f[1]] and ex_b["direct_ok"][f[1]]]
    va_shared = [f for f in splits["val"] if ex_a["direct_ok"][f[1]] and ex_b["direct_ok"][f[1]]]
    te_shared = [f for f in splits["test"] if ex_a["direct_ok"][f[1]] and ex_b["direct_ok"][f[1]]]
    dm_facts = [
        f for f in all_facts
        if ex_a["direct_ok"][f[1]] and (not ex_b["direct_ok"][f[1]]) and ex_b["dark_mem_ok"][f[1]]
    ]
    return tr_shared, va_shared, te_shared, dm_facts


def _eval_probe_b_gates(
    pair_results: Dict[str, Dict[str, Any]],
    mean_frob: float,
    mean_ols: float,
    mean_shell: float,
    mean_rand: float,
    mean_shuf: float,
) -> Tuple[bool, bool]:
    """Pure-stdlib Probe B W11-B1 and W11-B2 gate evaluator."""
    w11_b1_pass = (mean_frob - max(mean_rand, mean_shuf) >= 0.15) and (max(mean_rand, mean_shuf) <= 0.05)
    w11_b2_pass = all(v["scales"]["s_ols"] < v["scales"]["s_frob"] for v in pair_results.values()) and (mean_ols <= max(mean_frob, mean_shell) + 1e-6)
    return w11_b1_pass, w11_b2_pass


def _run_probe_b_platos_key_spheremap(torch: Any, device: Any) -> Dict[str, Any]:
    """Probe B (EXP-Q25b / EXP-Q26a) across Qwen2.5-0.5B, Qwen2.5-1.5B, and SmolLM2-360M."""
    from transformers import AutoModelForCausalLM, AutoTokenizer  # type: ignore[import-not-found]

    splits = build_subject_disjoint_fact_splits(20261125)
    all_facts = splits["train"] + splits["val"] + splits["test"]
    model_ids = ("Qwen/Qwen2.5-1.5B", "Qwen/Qwen2.5-0.5B", "HuggingFaceTB/SmolLM2-360M")

    extracted: Dict[str, Dict[str, Any]] = {}
    for mid in model_ids:
        sys.stderr.write(f"[Probe B] Extracting keys & recall for {mid} ({len(all_facts)} facts)...\n")
        sys.stderr.flush()
        extracted[mid] = _extract_model_facts_and_keys(torch, mid, all_facts, device)
        n_ok = sum(1 for v in extracted[mid]["direct_ok"].values() if v)
        n_dm = sum(1 for v in extracted[mid]["dark_mem_ok"].values() if v)
        sys.stderr.write(f"[Probe B]   {mid}: direct_recall={n_ok}/{len(all_facts)}, dark_memories={n_dm}\n")
        sys.stderr.flush()

    # Evaluate 3 high-signal model pairs: within-family (1.5B->0.5B, 0.5B->1.5B) & cross-family (1.5B->SmolLM2-360M, SmolLM2-360M->0.5B)
    pairs = (
        ("Qwen/Qwen2.5-1.5B", "Qwen/Qwen2.5-0.5B"),
        ("Qwen/Qwen2.5-0.5B", "Qwen/Qwen2.5-1.5B"),
        ("Qwen/Qwen2.5-1.5B", "HuggingFaceTB/SmolLM2-360M"),
        ("HuggingFaceTB/SmolLM2-360M", "Qwen/Qwen2.5-0.5B"),
    )

    pair_results: Dict[str, Any] = {}
    # Group pairs by recipient so we load each recipient model only ONCE for swap inference!
    by_recip: Dict[str, List[str]] = {}
    for donor_id, recip_id in pairs:
        by_recip.setdefault(recip_id, []).append(donor_id)

    for recip_id, donor_list in by_recip.items():
        snap_b = _resolve_offline_hf_snapshot(recip_id)
        tok_b = AutoTokenizer.from_pretrained(str(snap_b), local_files_only=True)
        model_b = AutoModelForCausalLM.from_pretrained(
            str(snap_b), local_files_only=True, dtype=torch.bfloat16, attn_implementation="eager"
        ).to(device)
        model_b.eval()
        ex_b = extracted[recip_id]

        for donor_id in donor_list:
            ex_a = extracted[donor_id]
            pair_key = f"{donor_id.split('/')[-1]}_to_{recip_id.split('/')[-1]}"
            sys.stderr.write(f"[Probe B] Running swap transfer & dark-memory suite for {pair_key}...\n")
            sys.stderr.flush()

            # Filter splits to facts recalled directly by BOTH donor & recipient
            tr_shared, va_shared, te_shared, dm_facts = _filter_shared_and_dm_facts(splits, all_facts, ex_a, ex_b)
            va_swaps = make_swap_tuples(va_shared)
            te_swaps = make_swap_tuples(te_shared)

            # 1. Select optimal (l_A*, l_B*) on validation split via Frob_Procrustes (exact Plato's Key protocol!)
            best_val_acc = -1.0
            best_layers = (ex_a["cand_layers"][2], ex_b["cand_layers"][2])
            for la in ex_a["cand_layers"]:
                za_tr = torch.stack([ex_a["keys_by_layer"][la][f[1]] for f in tr_shared], dim=0)
                for lb in ex_b["cand_layers"]:
                    zb_tr = torch.stack([ex_b["keys_by_layer"][lb][f[1]] for f in tr_shared], dim=0)
                    fit = _fit_procrustes_maps(torch, za_tr, zb_tr, seed=2026)
                    fn_frob = fit["maps"]["Frob_Procrustes"]
                    va_eval = [
                        (rel, tgt_s, d_ans, fn_frob(ex_a["keys_by_layer"][la][d_s]))
                        for rel, d_s, d_ans, tgt_s in va_swaps
                    ]
                    acc = _eval_swap_accuracy_on_recipient(torch, model_b, tok_b, lb, va_eval, device)
                    if acc > best_val_acc:
                        best_val_acc = acc
                        best_layers = (la, lb)

            la_star, lb_star = best_layers
            za_tr = torch.stack([ex_a["keys_by_layer"][la_star][f[1]] for f in tr_shared], dim=0)
            zb_tr = torch.stack([ex_b["keys_by_layer"][lb_star][f[1]] for f in tr_shared], dim=0)
            fit_full = _fit_procrustes_maps(torch, za_tr, zb_tr, seed=2026)

            # 2. Evaluate all 6 maps + Self_Swap upper bound on held-out test swaps!
            test_accs: Dict[str, float] = {}
            for mname, fn in fit_full["maps"].items():
                te_eval = [
                    (rel, tgt_s, d_ans, fn(ex_a["keys_by_layer"][la_star][d_s]))
                    for rel, d_s, d_ans, tgt_s in te_swaps
                ]
                test_accs[mname] = round(_eval_swap_accuracy_on_recipient(torch, model_b, tok_b, lb_star, te_eval, device), 4)

            self_eval = [
                (rel, tgt_s, d_ans, ex_b["keys_by_layer"][lb_star][d_s])
                for rel, d_s, d_ans, tgt_s in te_swaps
            ]
            test_accs["Self_Swap_UpperBound"] = round(
                _eval_swap_accuracy_on_recipient(torch, model_b, tok_b, lb_star, self_eval, device), 4
            )

            # 3. SVD Rank Compression Curve (r in {16, 64, 128, 256, full}) for Frob_Procrustes!
            rank_curve: Dict[str, float] = {}
            for rk in (16, 64, 128, 256):
                fit_r = _fit_procrustes_maps(torch, za_tr, zb_tr, seed=2026, svd_rank=rk)
                fn_r = fit_r["maps"]["Frob_Procrustes"]
                te_r = [
                    (rel, tgt_s, d_ans, fn_r(ex_a["keys_by_layer"][la_star][d_s]))
                    for rel, d_s, d_ans, tgt_s in te_swaps
                ]
                rank_curve[f"r{rk}"] = round(_eval_swap_accuracy_on_recipient(torch, model_b, tok_b, lb_star, te_r, device), 4)
            rank_curve["full"] = test_accs["Frob_Procrustes"]

            # 4. Dark-Memory Recovery Test (facts donor recalls directly, recipient misses directly, recipient passes 3-shot/paraphrase!)
            dm_recovery: Dict[str, Any] = {"n_dark_memories": len(dm_facts)}
            if dm_facts:
                for mname in ("Frob_Procrustes", "OLS_Procrustes", "ShellNorm_Procrustes", "SphereMap_Quadrupole_Procrustes", "Random_Orthogonal_Null"):
                    fn = fit_full["maps"][mname]
                    dm_eval = [
                        (rel, subj, ans, fn(ex_a["keys_by_layer"][la_star][subj]))
                        for rel, subj, ans in dm_facts
                    ]
                    dm_recovery[mname] = round(_eval_swap_accuracy_on_recipient(torch, model_b, tok_b, lb_star, dm_eval, device), 4)

            pair_results[pair_key] = {
                "donor": donor_id,
                "recipient": recip_id,
                "shared_counts": {"train": len(tr_shared), "val": len(va_shared), "test": len(te_shared)},
                "n_val_swaps": len(va_swaps),
                "n_test_swaps": len(te_swaps),
                "optimal_layers": {"donor_lA": la_star, "recipient_lB": lb_star, "val_frob_acc": round(best_val_acc, 4)},
                "scales": {
                    "s_frob": fit_full["s_frob"],
                    "s_ols": fit_full["s_ols"],
                    "ols_over_frob_ratio": fit_full["ols_over_frob_ratio"],
                },
                "test_transfer_accuracy": test_accs,
                "svd_rank_curve_frob": rank_curve,
                "dark_memory_recovery": dm_recovery,
            }
            sys.stderr.write(
                f"[Probe B] {pair_key} (lA={la_star}, lB={lb_star}): "
                f"Frob={test_accs['Frob_Procrustes']:.3f} OLS={test_accs['OLS_Procrustes']:.3f} "
                f"Shell={test_accs['ShellNorm_Procrustes']:.3f} SphereMap={test_accs['SphereMap_Quadrupole_Procrustes']:.3f} "
                f"Self={test_accs['Self_Swap_UpperBound']:.3f} Null={test_accs['Random_Orthogonal_Null']:.3f} DM={dm_recovery}\n"
            )
            sys.stderr.flush()

        del model_b
        gc.collect()
        torch.cuda.empty_cache()

    # Aggregate literal Probe B gate verdicts
    n_p = float(len(pair_results))
    mean_frob = sum(v["test_transfer_accuracy"]["Frob_Procrustes"] for v in pair_results.values()) / n_p
    mean_ols = sum(v["test_transfer_accuracy"]["OLS_Procrustes"] for v in pair_results.values()) / n_p
    mean_shell = sum(v["test_transfer_accuracy"]["ShellNorm_Procrustes"] for v in pair_results.values()) / n_p
    mean_sph = sum(v["test_transfer_accuracy"]["SphereMap_Quadrupole_Procrustes"] for v in pair_results.values()) / n_p
    mean_self = sum(v["test_transfer_accuracy"]["Self_Swap_UpperBound"] for v in pair_results.values()) / n_p
    mean_rand = sum(v["test_transfer_accuracy"]["Random_Orthogonal_Null"] for v in pair_results.values()) / n_p
    mean_shuf = sum(v["test_transfer_accuracy"]["Shuffled_Pair_Null"] for v in pair_results.values()) / n_p

    # Pooled dark-memory recovery across all pairs with dark memories
    tot_dm = sum(v["dark_memory_recovery"]["n_dark_memories"] for v in pair_results.values())
    dm_frob_hits = sum(
        round(v["dark_memory_recovery"]["n_dark_memories"] * v["dark_memory_recovery"].get("Frob_Procrustes", 0.0))
        for v in pair_results.values()
    )
    dm_sph_hits = sum(
        round(v["dark_memory_recovery"]["n_dark_memories"] * v["dark_memory_recovery"].get("SphereMap_Quadrupole_Procrustes", 0.0))
        for v in pair_results.values()
    )
    dm_rand_hits = sum(
        round(v["dark_memory_recovery"]["n_dark_memories"] * v["dark_memory_recovery"].get("Random_Orthogonal_Null", 0.0))
        for v in pair_results.values()
    )
    dm_frob_rate = dm_frob_hits / float(max(1, tot_dm))
    dm_sph_rate = dm_sph_hits / float(max(1, tot_dm))
    dm_rand_rate = dm_rand_hits / float(max(1, tot_dm))

    w11_b1_pass, w11_b2_pass = _eval_probe_b_gates(pair_results, mean_frob, mean_ols, mean_shell, mean_rand, mean_shuf)
    diff_sph_frob = mean_sph - mean_frob
    w11_b3_verdict = grade_probe_b_verdict(
        w11_b1_pass=w11_b1_pass,
        mean_frob=mean_frob,
        mean_sph=mean_sph,
        mean_rand=mean_rand,
        mean_shuf=mean_shuf,
        tot_dm=tot_dm,
        dm_frob_rate=dm_frob_rate,
        dm_sph_rate=dm_sph_rate,
        dm_rand_rate=dm_rand_rate,
    )

    return {
        "model_recall_summary": {
            mid: {
                "n_layers": ex["n_layers"],
                "d_model": ex["d_model"],
                "direct_recall_count": sum(1 for v in ex["direct_ok"].values() if v),
                "dark_memory_count": sum(1 for v in ex["dark_mem_ok"].values() if v),
                "total_facts": len(all_facts),
            }
            for mid, ex in extracted.items()
        },
        "pairs": pair_results,
        "summary": {
            "mean_frob_procrustes": round(mean_frob, 4),
            "mean_ols_procrustes": round(mean_ols, 4),
            "mean_shellnorm_procrustes": round(mean_shell, 4),
            "mean_spheremap_quadrupole": round(mean_sph, 4),
            "mean_self_swap": round(mean_self, 4),
            "mean_random_null": round(mean_rand, 4),
            "mean_shuffled_null": round(mean_shuf, 4),
            "spheremap_minus_frob_pp": round(100.0 * diff_sph_frob, 2),
            "pooled_dark_memories_total": tot_dm,
            "pooled_dark_memory_frob_rate": round(dm_frob_rate, 4),
            "pooled_dark_memory_spheremap_rate": round(dm_sph_rate, 4),
            "pooled_dark_memory_random_null_rate": round(dm_rand_rate, 4),
            "gate_W11_B1_plato_replication_pass": w11_b1_pass,
            "gate_W11_B2_ols_shrinkage_pass": w11_b2_pass,
            "gate_W11_B3_spheremap_verdict": w11_b3_verdict,
        },
    }


def run_all_wave11_live_probes(
    *,
    ckpt_path: Path,
    eval_bin_path: Path,
    out_json: Path,
    git_head: Optional[str] = None,
    repo_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    try:
        import torch  # type: ignore[import-not-found]
    except ImportError as exc:
        raise Wave11ProbeError("TORCH_MISSING", "--run-gpu requires PyTorch (torch)") from exc

    _require_cuda_available(bool(torch.cuda.is_available()))
    torch.use_deterministic_algorithms(True)
    prereg_sha, _ = _resolve_prereg_sha256()
    if git_head is None:
        head_sha, head_status = _capture_git_head(repo_dir if repo_dir is not None else _expedition_root())
        git_fields = build_zone_b_git_head_fields(head_sha, dirty=(head_status == "captured_dirty"))
    else:
        git_fields = build_zone_b_git_head_fields(git_head)

    device = torch.device("cuda:0")
    t0 = time.perf_counter()
    probe_a = _run_probe_a_loopcd_and_strang(torch, device, ckpt_path, eval_bin_path)
    probe_b = _run_probe_b_platos_key_spheremap(torch, device)

    payload: Dict[str, Any] = {
        "schema": SCHEMA_W11_LIVE,
        "prereg_filename": PREREG_FILENAME,
        "prereg_sha256": prereg_sha,
        **git_fields,
        "gpu_name": str(torch.cuda.get_device_name(0)),
        "probe_a_loopcd_strang_holosphere_v3": probe_a,
        "probe_b_platos_key_spheremap_procrustes": probe_b,
        "wall_seconds": round(time.perf_counter() - t0, 2),
    }
    payload["payload_sha256"] = hashlib.sha256(_canonical_json_bytes(payload)).hexdigest()

    out_json.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False) + "\n", encoding="utf-8")
    os.chmod(out_json, 0o644)
    return payload


def _safe_write_stream(stream: Any, text: str) -> bool:
    try:
        stream.write(text)
        stream.flush()
        return True
    except OSError:
        return False


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Wave-11 Live RTX 3080 Probes: LoopCD/Strang + Plato's Key/SphereMap")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--selftest-stdlib", action="store_true")
    mode.add_argument("--check-zone-b", action="store_true")
    mode.add_argument("--run-gpu", action="store_true")
    parser.add_argument("--track-dir", type=Path, default=None)
    parser.add_argument("--require-committed-pins", action="store_true")
    parser.add_argument("--allow-missing-zone-b", action="store_true")
    parser.add_argument("--ckpt", type=Path, default=None)
    parser.add_argument("--eval-bin", type=Path, default=None)
    parser.add_argument("--out-json", type=Path, default=None)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    tag = "S121_ZONE_B" if args.check_zone_b else "S121_W11_PROBE"
    try:
        if args.run_gpu:
            require_ok(args.ckpt is not None and args.eval_bin is not None and args.out_json is not None, "BAD_ARGS", "Need --ckpt, --eval-bin, --out-json")
            res = run_all_wave11_live_probes(ckpt_path=args.ckpt, eval_bin_path=args.eval_bin, out_json=args.out_json)
        elif args.check_zone_b:
            pins_opt = True if args.require_committed_pins else None
            zb = verify_w11_zone_b_bundle(args.track_dir, verify_committed_pins=pins_opt)
            out_zb = (
                json.dumps(zb, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False) + "\n"
                if args.json
                else f"PASS S121_ZONE_B receipt_sha256={zb['receipt_sha256']}\n"
            )
            return 0 if _safe_write_stream(sys.stdout, out_zb) else 2
        else:
            res = run_stdlib_selftest(allow_missing_zone_b=args.allow_missing_zone_b)
    except (Wave11ProbeError, OSError, OverflowError) as exc:
        code = exc.code if isinstance(exc, Wave11ProbeError) else "IO_ERROR"
        message = exc.message if isinstance(exc, Wave11ProbeError) else type(exc).__name__
        if args.json:
            _safe_write_stream(
                sys.stdout,
                json.dumps(
                    {"passed": False, "code": code, "message": message},
                    indent=2,
                    sort_keys=True,
                    ensure_ascii=True,
                    allow_nan=False,
                )
                + "\n",
            )
        else:
            _safe_write_stream(sys.stderr, f"FAIL {tag} code={code} message={message}\n")
        return 2

    out_res = (
        json.dumps(res, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False) + "\n"
        if (args.json or args.selftest_stdlib)
        else f"OK {res['schema']} payload_sha256={res['payload_sha256']}\n"
    )
    return 0 if _safe_write_stream(sys.stdout, out_res) else 2


if __name__ == "__main__":
    raise SystemExit(main())
