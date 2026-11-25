"""Pure-Z/Q cross-org Zone-B, NaN-swallowing & -O bare-assert tomography oracle for aska-physical.

Zero external dependencies, zero IEEE-754 floats, zero bare asserts, zero RNG.
Provides:
  1. Deterministic pure-Z AST tomography scanner (`scan_python_source_exact`) counting
     four orthogonal verification-trust defect families:
       - F1 (`bare_assert_count`): bare `assert` statements stripped by `python3 -O`
       - F2 (`all_builtin_maxmin_count` / `const_first_maxmin_count`): Python builtin
         `max`/`min` calls susceptible to IEEE-754 NaN swallowing (`max(0.0, NaN) == 0.0`)
       - F3 (`cert_dict_eq_count`): parsed-dict equality (`json.loads(...) != cert` /
         `saved != cert` / `fresh != saved`) vulnerable to ZB06/ZB07/ZB08/ZB10/ZB14
       - F4 (`unguarded_json_load_count`): unguarded `json.loads`/`json.load` calls
         crashing with raw tracebacks on ZB03/ZB15/ZB16
  2. Live AST execution over real minimal repro snippets extracted from public
     `aska-physical` main branches plus a Law-2b zero-exposure micro-shim steelman.
  3. Exact pure-Q exposure prevalence, 4x4 co-occurrence, and exhaustive search over
     all 2^3 - 1 = 7 non-empty subsets of the 3 shim primitives for the minimal
     remediation hitting-set analysis across all 9 public `aska-physical`
     engineering repositories (pinned at verified main HEAD SHAs and re-verifiable
     against live read-only clones via `verify_live_repos_dir`).
"""
from __future__ import annotations

import ast
from fractions import Fraction
import hashlib
import os
from pathlib import Path
from typing import Any

MAX_SOURCE_BYTES = 524_288
MAX_LIVE_FILE_BYTES = 1_048_576
MAX_RATIONAL_BITS = 4000
_EXACT_PATH_TYPES = (Path, type(Path()))


class TomographyError(ValueError):
    """Fail-closed typed error for Track S21c tomography and Zone-B checks."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


def format_rational(val: Fraction) -> str:
    if type(val) is not Fraction:
        raise TomographyError("INVALID_RATIONAL", "expected exact Fraction")
    if val.numerator.bit_length() > MAX_RATIONAL_BITS or val.denominator.bit_length() > MAX_RATIONAL_BITS:
        raise TomographyError("RATIONAL_TOO_LARGE", "rational numerator or denominator exceeds MAX_RATIONAL_BITS")
    if val.denominator == 1:
        return str(val.numerator)
    return f"{val.numerator}/{val.denominator}"


def require_exact_int(val: Any, label: str, lo: int | None = None, hi: int | None = None) -> int:
    if type(val) is not int:
        raise TomographyError("INVALID_INT", f"{label} must be exact int")
    if lo is not None and val < lo:
        raise TomographyError("INT_OUT_OF_RANGE", f"{label} < {lo}")
    if hi is not None and val > hi:
        raise TomographyError("INT_OUT_OF_RANGE", f"{label} > {hi}")
    return val


def coerce_exact_path(path: Any) -> Path:
    if type(path) is str:
        if not path:
            raise TomographyError("INVALID_PATH", "path must be non-empty str or exact Path")
        return Path(path)
    if type(path) in _EXACT_PATH_TYPES:
        return path
    raise TomographyError("INVALID_PATH", "path must be exact str or Path (no subclasses)")


def _reject_lexical_symlinks(path: Path) -> None:
    cur: Path | None = None
    for part in path.parts:
        cur = Path(part) if cur is None else cur / part
        if os.path.islink(cur):
            raise TomographyError("SYMLINK_FORBIDDEN", "symlink target or ancestor forbidden")


def reject_symlinks_on_path(path: Path) -> None:
    _reject_lexical_symlinks(path)
    if not path.is_absolute():
        _reject_lexical_symlinks(Path(os.environ.get("PWD", "")))


# ------------------------------------------------------------------ Pure-Z AST Tomography Engine

def _is_finite_const_arg(node: ast.AST) -> bool:
    if isinstance(node, ast.Constant) and type(node.value) in (int, float):
        return True
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return isinstance(node.operand, ast.Constant) and type(node.operand.value) in (int, float)
    return False


def _is_json_load_call(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call):
        return False
    fn = node.func
    return (
        isinstance(fn, ast.Attribute)
        and isinstance(fn.value, ast.Name)
        and fn.value.id == "json"
        and fn.attr in ("loads", "load")
    )


def _compare_is_cert_dict_eq(node: ast.Compare) -> bool:
    if not any(isinstance(op, (ast.Eq, ast.NotEq)) for op in node.ops):
        return False
    sides = [node.left, *node.comparators]
    cert_names = {"cert", "saved", "fresh", "ledger"}
    has_cert_var = any(isinstance(s, ast.Name) and s.id in cert_names for s in sides)
    has_json_call = any(
        _is_json_load_call(s)
        or (isinstance(s, ast.Call) and isinstance(s.func, ast.Name) and s.func.id == "read_json")
        for s in sides
    )
    if has_cert_var and has_json_call:
        return True
    names = {s.id for s in sides if isinstance(s, ast.Name)}
    return ("saved" in names and "cert" in names) or ("fresh" in names and "saved" in names)


def scan_python_source_exact(source: str, filename: str = "<snippet>") -> dict[str, int]:
    """Deterministically count F1..F4 defect-family sites in Python source via stdlib AST."""
    if type(source) is not str:
        raise TomographyError("INVALID_SOURCE", "source must be exact str")
    if type(filename) is not str or not filename:
        raise TomographyError("INVALID_FILENAME", "filename must be non-empty exact str")
    if "\x00" in source:
        raise TomographyError("NUL_IN_SOURCE", "NUL byte forbidden in Python source")
    try:
        raw = source.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise TomographyError("INVALID_UTF8_SOURCE", "source contains invalid Unicode surrogates") from exc
    if len(raw) > MAX_SOURCE_BYTES:
        raise TomographyError("SOURCE_TOO_LARGE", "source exceeds MAX_SOURCE_BYTES")
    try:
        tree = ast.parse(source, filename=filename)
    except (SyntaxError, ValueError, RecursionError) as exc:
        raise TomographyError("SYNTAX_ERROR", f"failed to parse Python AST: {exc}") from exc

    bare_assert = 0
    const_first_maxmin = 0
    all_builtin_maxmin = 0
    cert_dict_eq = 0
    unguarded_json_load = 0

    stack: list[tuple[ast.AST, bool]] = [(tree, False)]
    while stack:
        node, in_try = stack.pop()
        if isinstance(node, ast.Assert):
            bare_assert += 1
        elif isinstance(node, ast.Call):
            fn = node.func
            if isinstance(fn, ast.Name) and fn.id in ("max", "min"):
                all_builtin_maxmin += 1
                if len(node.args) >= 2 and _is_finite_const_arg(node.args[0]):
                    const_first_maxmin += 1
            elif _is_json_load_call(node) and not in_try:
                unguarded_json_load += 1
        elif isinstance(node, ast.Compare) and _compare_is_cert_dict_eq(node):
            cert_dict_eq += 1

        if isinstance(node, ast.Try):
            for child in node.handlers + node.orelse + node.finalbody:
                stack.append((child, in_try))
            for child in node.body:
                stack.append((child, True))
        else:
            for child in ast.iter_child_nodes(node):
                stack.append((child, in_try))

    return {
        "bare_assert_count": bare_assert,
        "const_first_maxmin_count": const_first_maxmin,
        "all_builtin_maxmin_count": all_builtin_maxmin,
        "cert_dict_eq_count": cert_dict_eq,
        "unguarded_json_load_count": unguarded_json_load,
    }


# ------------------------------------------------------------------ Pinned Live Snapshot (9 Public Repos)

PINNED_ASKA_REPOS: tuple[dict[str, Any], ...] = (
    {
        "repo": "fibral-rigidity",
        "visibility": "PUBLIC",
        "head": "06520520dff2e956715f18cfa3ba10e7ee83487b",
        "files": ("verify.py",),
        "file_sha256": {
            "verify.py": "750182ffc2c41fd7642ef88058d7f320e943c1ef0b6daee067f1ab9337e1bb38",
        },
        "cert_path": "results/certificate.json",
        "cert_sha256": "b7865e7683d19cd24cccee7b3bb4bda439852bb6835c20ebfb57249a39a33eaa",
        "uses_sympy": True,
        "bare_assert_count": 28,
        "const_first_maxmin_count": 0,
        "all_builtin_maxmin_count": 4,
        "cert_dict_eq_count": 1,
        "unguarded_json_load_count": 3,
        "live_subprocess_fuzzed": False,
        "live_nan_repro": "verify.py:206 max(0.0, nan, 0.0) == 0.0 passes err < 1e-11",
    },
    {
        "repo": "cfrp-truss",
        "visibility": "PUBLIC",
        "head": "3c11631e223b71227531d10286abd71bc04d67b7",
        "files": ("verify.py",),
        "file_sha256": {
            "verify.py": "77d0df4372ff596c3d80b1cd1d6fd41bacfde3c9ba3da1202f49d5f55f790c32",
        },
        "cert_path": "results/certificate.json",
        "cert_sha256": "3054d00ec6f69e2dfa3786ca2f69993adab04c6a9b3e59a670898a3faaeef659",
        "uses_sympy": True,
        "bare_assert_count": 7,
        "const_first_maxmin_count": 14,
        "all_builtin_maxmin_count": 36,
        "cert_dict_eq_count": 1,
        "unguarded_json_load_count": 1,
        "live_subprocess_fuzzed": False,
        "live_nan_repro": "verify.py:119,276 max(0.0, V_pry=nan) -> interaction_5_3=0.0; beta1(fc=nan)=0.85",
    },
    {
        "repo": "cfrp-masts",
        "visibility": "PUBLIC",
        "head": "a12b665f2baf32a8d6499ef39c296ef9fe78f630",
        "files": ("verify.py",),
        "file_sha256": {
            "verify.py": "2dc0bc542e241c30fd188ce07ef55d3058670d8ea75a24b6d690920fbb36bec2",
        },
        "cert_path": "results/certificate.json",
        "cert_sha256": "ff354f780e58999254b87eaf5ac6af3a387a662b320af714764c0b95718d664a",
        "uses_sympy": False,
        "bare_assert_count": 5,
        "const_first_maxmin_count": 0,
        "all_builtin_maxmin_count": 0,
        "cert_dict_eq_count": 1,
        "unguarded_json_load_count": 1,
        "live_subprocess_fuzzed": True,
        "live_nan_repro": "clean on F2 (0 builtin max/min, uses math.isfinite); 4 live Zone-B bypasses + 4 crashes",
    },
    {
        "repo": "cfrp-strengthening",
        "visibility": "PUBLIC",
        "head": "3f68cccf19556574b7652311be1b0dc0daa93144",
        "files": ("results/track-1-flexure/verify.py", "src/flexure440.py"),
        "file_sha256": {
            "results/track-1-flexure/verify.py": "fe082e2c63252463a1ff81aa18ae0941e247bb409c8513e9f09e0fdd8a241a56",
            "src/flexure440.py": "77583629134777eb507a39cc6cb47b8297d1b5d3336f2bbea66345179a81d872",
        },
        "cert_path": "results/track-1-flexure/certificate.json",
        "cert_sha256": "6d827c5911e7e8e270d4fa31533913d73097324e2018016a2994a706a3416055",
        "uses_sympy": False,
        "bare_assert_count": 0,
        "const_first_maxmin_count": 1,
        "all_builtin_maxmin_count": 5,
        "cert_dict_eq_count": 2,
        "unguarded_json_load_count": 5,
        "live_subprocess_fuzzed": True,
        "live_nan_repro": "clean on F1 (0 asserts); flexure440:109 beta1(fc=nan)=0.65; verify.py:160 DATE_ECHO_FORGERY rc=0",
    },
    {
        "repo": "funi-floors",
        "visibility": "PUBLIC",
        "head": "00eba18ceea0adf69f7dc12ca47d151622faa32a",
        "files": ("verify.py",),
        "file_sha256": {
            "verify.py": "274d87ced9d120cc331938a3a58b5cfc18265d624c2bc3d8f6d0c3ee5b517461",
        },
        "cert_path": "results/certificate.json",
        "cert_sha256": "85878c416fed3c290c1321ec0dc27af5a152d8ca4d264b8f802add2e5995d186",
        "uses_sympy": True,
        "bare_assert_count": 5,
        "const_first_maxmin_count": 6,
        "all_builtin_maxmin_count": 7,
        "cert_dict_eq_count": 1,
        "unguarded_json_load_count": 1,
        "live_subprocess_fuzzed": False,
        "live_nan_repro": "verify.py:178 evaluate_punching_shear_collar(fc_MPa=nan) -> active_collar_passes=True (0.8009)",
    },
    {
        "repo": "funi-frame",
        "visibility": "PUBLIC",
        "head": "97b326d237de5e03a2a227a02f32121005109fb8",
        "files": ("verify.py",),
        "file_sha256": {
            "verify.py": "cef9e47da460add38618b46fe4478855f80551f2c722dc73c64808375625a57e",
        },
        "cert_path": "results/certificate.json",
        "cert_sha256": "92e7bbcea389274d2967e463ec3881ec9311db7786c5e74559defcd936dfb9fa",
        "uses_sympy": True,
        "bare_assert_count": 7,
        "const_first_maxmin_count": 2,
        "all_builtin_maxmin_count": 2,
        "cert_dict_eq_count": 1,
        "unguarded_json_load_count": 1,
        "live_subprocess_fuzzed": False,
        "live_nan_repro": "verify.py:61,78 max(0.0, nan) swallows NaN thrust/tornado uplift to 0.0",
    },
    {
        "repo": "impedence-analyzers",
        "visibility": "PUBLIC",
        "head": "ed0a5e10e87e231262af697cb183aa8aa570ca83",
        "files": ("verify.py",),
        "file_sha256": {
            "verify.py": "c1bd1f457395d0118da812ff1424021335056fe908698c72860d63ebca749637",
        },
        "cert_path": "results/certificate.json",
        "cert_sha256": "0fc25ed8ef22bc42f7427a551a0f1f043847caf1861c870e251585469ba420ad",
        "uses_sympy": False,
        "bare_assert_count": 9,
        "const_first_maxmin_count": 4,
        "all_builtin_maxmin_count": 7,
        "cert_dict_eq_count": 1,
        "unguarded_json_load_count": 1,
        "live_subprocess_fuzzed": True,
        "live_nan_repro": "verify.py:55,65,78 fit_cole(z=nan) crashes TypeError on NoneType + 4 live Zone-B bypasses/crashes",
    },
    {
        "repo": "venturi-collars",
        "visibility": "PUBLIC",
        "head": "d53f85a35d17a7bd46d0b5320c8879fc9f381978",
        "files": ("verify.py",),
        "file_sha256": {
            "verify.py": "4d3ef70932572b25df4f93ce500b70f18bbf03ece77c26c99024175c36f3cb4e",
        },
        "cert_path": "results/certificate.json",
        "cert_sha256": "c93eb98b2431b2b733cb1702594c5dc1e00a77fc811d663cea561f20cb0c0170",
        "uses_sympy": False,
        "bare_assert_count": 5,
        "const_first_maxmin_count": 1,
        "all_builtin_maxmin_count": 1,
        "cert_dict_eq_count": 1,
        "unguarded_json_load_count": 1,
        "live_subprocess_fuzzed": True,
        "live_nan_repro": "verify.py:55,69,89 U_duct=nan (-O) -> P_total_harvested_mW=0.9244 + 5 live Zone-B bypasses + 4 crashes",
    },
    {
        "repo": "optifab",
        "visibility": "PUBLIC",
        "head": "74d68ea15ab7ed246c3266de6a9170837f7a7473",
        "files": ("verify.py",),
        "file_sha256": {
            "verify.py": "e1a898de08c87edeaf2efe465be91f16e2dcd49b3490cc7aadba5a6bb802be30",
        },
        "cert_path": "results/certificate.json",
        "cert_sha256": "fe5bb2a15cf23c8e576e7d093c0ff49149e548dc74daac369c0565757d3c890b",
        "uses_sympy": True,
        "bare_assert_count": 20,
        "const_first_maxmin_count": 1,
        "all_builtin_maxmin_count": 14,
        "cert_dict_eq_count": 2,
        "unguarded_json_load_count": 3,
        "live_subprocess_fuzzed": False,
        "live_nan_repro": "verify.py:311,332-336 ball_in_box_check(u=nan) -> all_within_limits=True; plant_radius=0.1989",
    },
)

# Real minimal repro snippets extracted from live main branches + Law-2b zero-exposure steelman
MINIMAL_REPRO_CORPUS: tuple[dict[str, Any], ...] = (
    {
        "id": "repro_fibral_nan_max",
        "source_ref": "fibral-rigidity/verify.py:206-208",
        "code": (
            "def f(a, b, c):\n"
            "    err = max(a, b, c)\n"
            "    max_err = max(0, err)\n"
            "    assert err < 1\n"
            "    return max_err\n"
        ),
        "expected": {
            "bare_assert_count": 1,
            "const_first_maxmin_count": 1,
            "all_builtin_maxmin_count": 2,
            "cert_dict_eq_count": 0,
            "unguarded_json_load_count": 0,
        },
    },
    {
        "id": "repro_optifab_ball_nan",
        "source_ref": "optifab/verify.py:332-336",
        "code": (
            "def f(u0, radius, worst):\n"
            "    worst = max(worst, max(u + radius for u in u0))\n"
            "    axis = max(u + radius for u in u0)\n"
            "    return max(axis, worst) <= 1\n"
        ),
        "expected": {
            "bare_assert_count": 0,
            "const_first_maxmin_count": 0,
            "all_builtin_maxmin_count": 4,
            "cert_dict_eq_count": 0,
            "unguarded_json_load_count": 0,
        },
    },
    {
        "id": "repro_funi_floors_punching_nan",
        "source_ref": "funi-floors/verify.py:178",
        "code": (
            "def f(fc):\n"
            "    return min(35, fc)\n"
        ),
        "expected": {
            "bare_assert_count": 0,
            "const_first_maxmin_count": 1,
            "all_builtin_maxmin_count": 1,
            "cert_dict_eq_count": 0,
            "unguarded_json_load_count": 0,
        },
    },
    {
        "id": "repro_venturi_nan_minus_o",
        "source_ref": "venturi-collars/verify.py:69,89",
        "code": (
            "def f(vel_factor, p_tot, p_fluid):\n"
            "    tip = min(4, vel_factor)\n"
            "    assert p_tot < p_fluid\n"
            "    return tip\n"
        ),
        "expected": {
            "bare_assert_count": 1,
            "const_first_maxmin_count": 1,
            "all_builtin_maxmin_count": 1,
            "cert_dict_eq_count": 0,
            "unguarded_json_load_count": 0,
        },
    },
    {
        "id": "repro_cfrp_truss_pryout_nan",
        "source_ref": "cfrp-truss/verify.py:276-277",
        "code": (
            "def f(v_pry, u_up, u_bd):\n"
            "    u_pr = max(0, v_pry)\n"
            "    inter = max(u_up, u_bd) + u_pr\n"
            "    return inter\n"
        ),
        "expected": {
            "bare_assert_count": 0,
            "const_first_maxmin_count": 1,
            "all_builtin_maxmin_count": 2,
            "cert_dict_eq_count": 0,
            "unguarded_json_load_count": 0,
        },
    },
    {
        "id": "repro_zoneb_cert_eq_crash",
        "source_ref": "aska-physical/*/verify.py",
        "code": (
            "import json\n"
            "def f(path, cert):\n"
            "    if json.loads(path.read_text()) != cert:\n"
            "        return 1\n"
            "    return 0\n"
        ),
        "expected": {
            "bare_assert_count": 0,
            "const_first_maxmin_count": 0,
            "all_builtin_maxmin_count": 0,
            "cert_dict_eq_count": 1,
            "unguarded_json_load_count": 1,
        },
    },
    {
        "id": "law2b_hardened_micro_shim",
        "source_ref": "Law-2b 3-primitive micro-shim",
        "code": (
            "import hmac, math, os\n"
            "def require(ok, msg):\n"
            "    if not ok:\n"
            "        raise RuntimeError(msg)\n"
            "def finite_clamp_lo(lo, x):\n"
            "    require(math.isfinite(x), 'non-finite')\n"
            "    return lo if x < lo else x\n"
            "def verify_cert_bytes(path, rendered_bytes):\n"
            "    if os.path.islink(path) or not os.path.isfile(path):\n"
            "        return False\n"
            "    try:\n"
            "        raw = path.read_bytes()\n"
            "    except OSError:\n"
            "        return False\n"
            "    return hmac.compare_digest(raw, rendered_bytes)\n"
        ),
        "expected": {
            "bare_assert_count": 0,
            "const_first_maxmin_count": 0,
            "all_builtin_maxmin_count": 0,
            "cert_dict_eq_count": 0,
            "unguarded_json_load_count": 0,
        },
    },
)

SHIM_PRIMITIVES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("require_no_assert", ("F1_BARE_ASSERT_O_STRIP",)),
    ("strict_finite_clamp", ("F2_NAN_SWALLOW_MAXMIN",)),
    ("verify_canonical_cert_bytes", ("F3_ZONEB_CERT_DICT_EQ", "F4_ZONEB_UNGUARDED_JSON_IO")),
)

DEFECT_FAMILIES: tuple[str, ...] = (
    "F1_BARE_ASSERT_O_STRIP",
    "F2_NAN_SWALLOW_MAXMIN",
    "F3_ZONEB_CERT_DICT_EQ",
    "F4_ZONEB_UNGUARDED_JSON_IO",
)


def _repo_family_flags(row: dict[str, Any]) -> dict[str, bool]:
    return {
        "F1_BARE_ASSERT_O_STRIP": row["bare_assert_count"] > 0,
        "F2_NAN_SWALLOW_MAXMIN": row["all_builtin_maxmin_count"] > 0,
        "F3_ZONEB_CERT_DICT_EQ": row["cert_dict_eq_count"] > 0,
        "F4_ZONEB_UNGUARDED_JSON_IO": row["unguarded_json_load_count"] > 0,
    }


def _validate_repo_row(row: Any) -> dict[str, Any]:
    if type(row) is not dict:
        raise TomographyError("INVALID_ROW", "repo row must be exact dict")
    if type(row.get("repo")) is not str or not row["repo"]:
        raise TomographyError("INVALID_ROW", "repo name must be non-empty str")
    out = dict(row)
    for k in (
        "bare_assert_count",
        "const_first_maxmin_count",
        "all_builtin_maxmin_count",
        "cert_dict_eq_count",
        "unguarded_json_load_count",
    ):
        require_exact_int(row.get(k), k, lo=0)
    if row["const_first_maxmin_count"] > row["all_builtin_maxmin_count"]:
        raise TomographyError("INVALID_ROW", "const_first_maxmin_count > all_builtin_maxmin_count")
    return out


def compute_exact_org_metrics(repo_rows: list[dict[str, Any]] | tuple[dict[str, Any], ...]) -> dict[str, Any]:
    """Compute exact pure-Z/Q cross-org exposure fractions, co-occurrence, and minimal hitting set."""
    if type(repo_rows) not in (list, tuple) or len(repo_rows) == 0:
        raise TomographyError("INVALID_ROWS", "repo_rows must be non-empty exact list or tuple")
    clean = [_validate_repo_row(r) for r in repo_rows]
    n_repos = len(clean)
    flags_per_repo = [_repo_family_flags(r) for r in clean]

    family_repo_counts: dict[str, int] = {}
    family_prevalence: dict[str, str] = {}
    for fam in DEFECT_FAMILIES:
        cnt = sum(1 for fl in flags_per_repo if fl[fam])
        family_repo_counts[fam] = cnt
        family_prevalence[fam] = format_rational(Fraction(cnt, n_repos))

    co_occurrence: dict[str, dict[str, int]] = {}
    for f_a in DEFECT_FAMILIES:
        co_occurrence[f_a] = {}
        for f_b in DEFECT_FAMILIES:
            co_occurrence[f_a][f_b] = sum(1 for fl in flags_per_repo if fl[f_a] and fl[f_b])

    total_cells = n_repos * len(DEFECT_FAMILIES)
    exposed_cells = sum(family_repo_counts.values())
    clean_cells = total_cells - exposed_cells
    all_four_repos = sum(1 for fl in flags_per_repo if all(fl.values()))
    min_families_per_repo = min(sum(1 for v in fl.values() if v) for fl in flags_per_repo)

    # Exhaustive search over all 2^3 - 1 = 7 non-empty subsets of SHIM_PRIMITIVES
    active_fams = {fam for fam, cnt in family_repo_counts.items() if cnt > 0}
    n_prims = len(SHIM_PRIMITIVES)
    min_hitting_size = n_prims + 1
    hitting_subsets: list[list[str]] = []
    for mask in range(1, 1 << n_prims):
        chosen: list[str] = []
        covered: set[str] = set()
        for bit in range(n_prims):
            if (mask >> bit) & 1:
                pname, pfams = SHIM_PRIMITIVES[bit]
                chosen.append(pname)
                covered.update(pfams)
        if active_fams.issubset(covered):
            if len(chosen) < min_hitting_size:
                min_hitting_size = len(chosen)
                hitting_subsets = [chosen]
            elif len(chosen) == min_hitting_size:
                hitting_subsets.append(chosen)

    primitive_shares: dict[str, str] = {}
    for pname, pfams in SHIM_PRIMITIVES:
        closed_cells = sum(family_repo_counts[f] for f in pfams)
        primitive_shares[pname] = format_rational(Fraction(closed_cells, exposed_cells)) if exposed_cells > 0 else "0"

    return {
        "n_public_repos": n_repos,
        "total_bare_asserts": sum(r["bare_assert_count"] for r in clean),
        "total_const_first_maxmin": sum(r["const_first_maxmin_count"] for r in clean),
        "total_all_builtin_maxmin": sum(r["all_builtin_maxmin_count"] for r in clean),
        "total_cert_dict_eq": sum(r["cert_dict_eq_count"] for r in clean),
        "total_unguarded_json_load": sum(r["unguarded_json_load_count"] for r in clean),
        "family_repo_counts": family_repo_counts,
        "family_prevalence_exact": family_prevalence,
        "co_occurrence_matrix": co_occurrence,
        "total_exposure_cells": total_cells,
        "exposed_cells": exposed_cells,
        "clean_cells": clean_cells,
        "exposure_density_exact": format_rational(Fraction(exposed_cells, total_cells)),
        "repos_with_all_four_families": all_four_repos,
        "min_families_per_repo": min_families_per_repo,
        "minimal_shim_hitting_set_size": min_hitting_size,
        "minimal_shim_hitting_sets": hitting_subsets,
        "primitive_closure_shares_exact": primitive_shares,
    }


def verify_minimal_repro_corpus() -> list[dict[str, Any]]:
    """Run scan_python_source_exact live on every embedded minimal repro + Law-2b steelman."""
    results: list[dict[str, Any]] = []
    for entry in MINIMAL_REPRO_CORPUS:
        observed = scan_python_source_exact(entry["code"], filename=f"{entry['id']}.py")
        if observed != entry["expected"]:
            raise TomographyError("CORPUS_SCAN_MISMATCH", f"AST scan mismatch on {entry['id']}")
        results.append({
            "id": entry["id"],
            "source_ref": entry["source_ref"],
            "observed_counts": observed,
            "code_sha256": hashlib.sha256(entry["code"].encode("utf-8")).hexdigest(),
        })
    return results


def _read_live_bytes(path: Path, label: str) -> bytes:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise TomographyError("LIVE_FILE_READ_ERROR", f"failed to read {label}: {exc}") from exc
    if len(raw) > MAX_LIVE_FILE_BYTES:
        raise TomographyError("LIVE_FILE_TOO_LARGE", f"file exceeds size cap: {label}")
    return raw


def verify_live_repos_dir(root_dir: Path | str) -> dict[str, Any]:
    """Read-only live verification of cloned aska-physical repos against pinned SHAs and AST counts."""
    root = coerce_exact_path(root_dir)
    reject_symlinks_on_path(root)
    if not os.path.isdir(root):
        raise TomographyError("LIVE_DIR_NOT_FOUND", "live-dir does not exist or is not a directory")
    verified_repos: list[str] = []
    for spec in PINNED_ASKA_REPOS:
        rdir = root / spec["repo"]
        reject_symlinks_on_path(rdir)
        if not os.path.isdir(rdir):
            raise TomographyError("LIVE_REPO_MISSING", f"missing repo directory {spec['repo']}")
        totals = {
            "bare_assert_count": 0,
            "const_first_maxmin_count": 0,
            "all_builtin_maxmin_count": 0,
            "cert_dict_eq_count": 0,
            "unguarded_json_load_count": 0,
        }
        for rel in spec["files"]:
            fpath = rdir / rel
            reject_symlinks_on_path(fpath)
            if not os.path.isfile(fpath):
                raise TomographyError("LIVE_FILE_MISSING", f"missing file {spec['repo']}/{rel}")
            raw = _read_live_bytes(fpath, rel)
            actual_sha = hashlib.sha256(raw).hexdigest()
            if actual_sha != spec["file_sha256"][rel]:
                raise TomographyError("LIVE_FILE_SHA_MISMATCH", f"SHA-256 drift on {spec['repo']}/{rel}")
            counts = scan_python_source_exact(raw.decode("utf-8"), filename=rel)
            for k in totals:
                totals[k] += counts[k]
        for k in totals:
            if totals[k] != spec[k]:
                raise TomographyError("LIVE_AST_COUNT_MISMATCH", f"count mismatch on {spec['repo']}.{k}")
        cpath = rdir / spec["cert_path"]
        reject_symlinks_on_path(cpath)
        if not os.path.isfile(cpath):
            raise TomographyError("LIVE_CERT_MISSING", f"missing cert {spec['repo']}/{spec['cert_path']}")
        csha = hashlib.sha256(_read_live_bytes(cpath, spec["cert_path"])).hexdigest()
        if csha != spec["cert_sha256"]:
            raise TomographyError("LIVE_CERT_SHA_MISMATCH", f"cert SHA-256 drift on {spec['repo']}")
        verified_repos.append(spec["repo"])
    return {"live_verified": True, "repos_verified": len(verified_repos), "repos": verified_repos}


def compute_tomography_payload() -> dict[str, Any]:
    """Compute the complete pure-Z/Q Track S21c tomography payload (zero floats)."""
    repro_results = verify_minimal_repro_corpus()
    metrics = compute_exact_org_metrics(PINNED_ASKA_REPOS)
    repos_out = [
        {
            "repo": r["repo"],
            "visibility": r["visibility"],
            "head": r["head"],
            "files": list(r["files"]),
            "file_sha256": dict(r["file_sha256"]),
            "cert_path": r["cert_path"],
            "cert_sha256": r["cert_sha256"],
            "uses_sympy": r["uses_sympy"],
            "live_subprocess_fuzzed": r["live_subprocess_fuzzed"],
            "counts": {
                "bare_assert_count": r["bare_assert_count"],
                "const_first_maxmin_count": r["const_first_maxmin_count"],
                "all_builtin_maxmin_count": r["all_builtin_maxmin_count"],
                "cert_dict_eq_count": r["cert_dict_eq_count"],
                "unguarded_json_load_count": r["unguarded_json_load_count"],
            },
            "family_flags": _repo_family_flags(r),
            "live_nan_repro": r["live_nan_repro"],
        }
        for r in PINNED_ASKA_REPOS
    ]
    return {
        "track_id": "TRACK-S21C-ASKA-PHYSICAL-ZONE-B-TOMOGRAPHY",
        "audit_mode": "pinned_snapshot_plus_live_ast_repro_corpus",
        "oracle_class": "pure-Z/Q-ast-tomography+zone-b-hardened",
        "novelty_tier": "N1",
        "org": "aska-physical",
        "org_metrics": metrics,
        "minimal_repro_corpus": repro_results,
        "repositories": repos_out,
    }
