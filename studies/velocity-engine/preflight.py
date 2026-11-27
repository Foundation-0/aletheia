"""
`preflight.py`: Track S168 (EXP-Q56a) 2-Second Shift-Left Pre-Audit Gate.

Runs automatically before external CLI audits to catch the 6 recurring Wave-22
multi-round failure classes in < 2.0 seconds:
  (i)   Prose/Typst Lean theorem citations absent from `*.lean`
  (ii)  Scientific-notation / integer witness mismatches & bidirectional verdict contradictions vs `certificate.json`
  (iii) Stale or unhashed `results.json` relative to `bench.py` / `verify.py` (AST-verified)
  (iv)  AST anti-patterns (`bool==int` cert equality, missing `allow_abbrev=False` incl. subclasses/add_parser,
        bare `assert`, unsafe `--write`, dropped gate-pass variables)
  (v)   Public-hygiene leaks across all UTF-8 files incl. `.env`/dotfiles (paths, handles, models, secrets)
  (vi)  `.lake/` / `__pycache__/` / symlink / hardlink / CRLF / BOM residue & strict `< 2000 ms` budget gate.

Stdlib-only, zero bare asserts, zero floats on trust paths, 3x -I bit-identical.
"""
from __future__ import annotations

import ast
import json
import os
from pathlib import Path
import re
import stat
import sys
import time
from typing import Any, Sequence

_SELF_DIR = str(Path(__file__).resolve().parent)
if _SELF_DIR not in sys.path:
    sys.path.insert(0, _SELF_DIR)

from trust_core import (  # noqa: E402
    MAX_FILE_BYTES,
    TrustCoreError,
    audit_lakefile_bytes,
    audit_lean4_source_static,
    extract_lean4_theorems,
    make_strict_parser,
    parse_strict_json_bytes,
    require_tc,
    run_fail_closed_cli,
    sha256_bytes,
    strip_lean4_comments_and_literals,
)

__all__ = [
    "DEFAULT_BUDGET_MS",
    "MAX_BUDGET_MS",
    "run_preflight",
    "build_parser",
    "main",
]

DEFAULT_BUDGET_MS = 2000
MAX_BUDGET_MS = 60000

_STRICT_TEXT_EXTS = frozenset({
    ".py", ".md", ".typ", ".txt", ".json", ".toml", ".lean", ".yml", ".yaml", ".sh", ".jsonl", ".env",
})
_PROSE_EXTS = frozenset({".md", ".typ"})
_SKIP_VCS_DIRS = frozenset({".git"})

_LEAN_DEF_RE = re.compile(
    r"^\s*(?:@\[[^\]]*\]\s*)*(?:(?:private|protected|noncomputable|unsafe|partial|scoped|local)\s+)*"
    r"(?:def|abbrev|structure|inductive|class|opaque|instance|theorem|lemma)\s+([A-Za-z_][A-Za-z0-9_.']*)"
)
_LEAN_NS_RE = re.compile(r"^\s*namespace\s+([A-Za-z_][A-Za-z0-9_.']*)")
_BACKTICK_RE = re.compile(r"`([A-Za-z_][A-Za-z0-9_.']{3,})`")
_QUALIFIED_THM_RE = re.compile(r"\A([A-Z][A-Za-z0-9_]*)\.([a-z_][A-Za-z0-9_']*)\Z")
_THM_CONTEXT_RE = re.compile(
    r"(?:\btheorems?\b|\blemmas?\b|\bThm\b|\bLean\b|\.lean\b|#print\s+axioms|Formalization|Theorem\s+Inventory)",
    re.IGNORECASE,
)
_THM_LIKE_SUFFIX_RE = re.compile(
    r"(?:_witness(?:es)?|_valid|_iff|_obstruction|_monotone|_exact|_dominance|_strict_gain"
    r"|_for_all_q_ge_\d+|_of_allPos|_of_ge_\d+|_of_ge|_matches|_eq_z\dBilin|_eq_bilin"
    r"|_not_log_concave|_smaller_of_ge_\d+|_all_pairs_valid)\Z"
)
_SCI_TIMES_RE = re.compile(
    r"([+\-\u2212]?)\s*([1-9])(?:\.(\d{1,10}))?(?:…|\.\.\.|\\ldots)?\s*(?:×|\\times|\*)\s*10\^\{?(\d{1,3})\}?"
)
_SCI_ENOT_RE = re.compile(
    r"(?<![A-Za-z0-9_.])([+\-\u2212]?)([1-9])(?:\.(\d{1,10}))?[eE]\+?(\d{1,3})(?![A-Za-z0-9_])"
)
_BIG_INT_RE = re.compile(r"(?<![A-Za-z0-9_/.])([+\-\u2212]?\d{18,})(?![A-Za-z0-9_/]|\.\d)")
_STR_BIG_INT_RE = re.compile(r"\A[+-]?\d{7,}\Z")
_SHA_HEX_RE = re.compile(r"\A[0-9a-fA-F]{16,64}\Z")
_UPPER_TOKEN_RE = re.compile(r"\A[A-Z0-9_]+\Z")
_KNOWN_FILE_EXTS = (".lean", ".py", ".json", ".toml", ".md", ".typ", ".txt", ".sh", ".pdf", ".yml", ".yaml", ".jsonl")
_KNOWN_NON_THEOREM_PREFIXES = frozenset({
    "Quot", "Classical", "Lean", "Init", "Nat", "Int", "Bool", "List", "String", "Array",
    "Option", "IO", "Std", "Mathlib", "Macro", "Path", "Fraction", "Decimal", "SystemExit",
    "ArgumentParser", "StrictArgumentParser", "TrustCoreError", "VerifierError", "MutantSite",
    "TestCase", "ThreadPoolExecutor", "CompletedProcess", "TimeoutExpired",
})
_LEAN_BUILTIN_KEYWORDS = frozenset({
    "run_cmd", "run_meta", "run_elab", "run_tac", "by_elab", "native_decide",
    "bv_decide", "bv_check", "macro_rules", "elab_rules", "declare_syntax_cat",
    "builtin_initialize", "implemented_by", "default_instance", "guard_msgs",
    "check_failure", "extern_lib", "lean_lib", "lean_exe", "sorry_ax", "sorryAx",
    "ofReduceBool", "ofReduceNat", "trustCompiler", "mkSorry",
})
_AT_HANDLE_RE = re.compile(
    r"(?<![A-Za-z0-9_.\\])@([a-z][a-z0-9_-]{2,})(?![A-Za-z0-9_.\[])"
)
_SAFE_AT_WORDS = frozenset({"staticmethod", "classmethod", "property", "dataclass", "abstractmethod", "override", "overload"})
_CERT_VAR_NAMES = frozenset({"cert", "payload", "expected", "loaded", "expected_cert", "loaded_cert", "certificate", "doc"})
_STRICT_EQ_HELPER_NAMES = frozenset({"strict_json_equal", "exact_json_equal", "strict_equal"})
_READ_FUNC_NAMES = frozenset({
    "strict_read_bytes_nofollow",
    "read_strict_bytes",
    "read_nofollow_bytes",
    "_read_bytes_and_stat",
    "_strict_read_bytes_and_stat_nofollow",
    "open_regular_file",
    "read_bytes",
    "open",
})
_HASH_FUNC_NAMES = frozenset({"sha256", "sha256_bytes", "_sha256"})


def _build_hygiene_rules() -> tuple[
    list[tuple[str, re.Pattern[str]]],
    list[tuple[str, re.Pattern[str]]],
    list[tuple[str, re.Pattern[str]]],
]:
    """Assemble leak/model/secret patterns programmatically so static scanners never self-trigger."""
    sl = chr(47)
    bs = chr(92)
    path_rules = [
        ("unix_home_path", re.compile(sl + "ho" + "me" + sl + r"[A-Za-z0-9._-]+")),
        ("macos_users_path", re.compile(sl + "Us" + "ers" + sl + r"[A-Za-z0-9._-]+")),
        ("win_users_path", re.compile(r"[A-Za-z]:" + bs + bs + "Us" + "ers" + bs + bs + r"[A-Za-z0-9._-]+")),
        ("tilde_home_path", re.compile(r"(?:^|[\s(`\"'])~" + sl + r"[A-Za-z0-9._/-]+")),
    ]
    model_tokens = [
        ("claude_model", r"\b" + "clau" + r"de(?:-[a-z0-9.]+|\s+\d+\.\d+)"),
        ("gemini_model", r"\b" + "gem" + r"ini(?:-[a-z0-9.]+|\s+\d+\.\d+)"),
        ("gpt_model", r"\b" + "gp" + r"t-[45][a-z0-9.-]*"),
        ("mistral_large_model", r"\b" + "mist" + r"ral-large-[0-9.-]+"),
        ("qwen_max_model", r"\b" + "qwe" + r"n4-max\b"),
        ("grok_model", r"\b" + "gro" + r"k-[0-9][a-z0-9.-]*"),
    ]
    model_rules = [(name, re.compile(pat, re.IGNORECASE)) for name, pat in model_tokens]
    cred_rules = [
        ("gh_pat", re.compile("gh" + "p_" + r"[A-Za-z0-9]{20,}")),
        ("gh_fg_pat", re.compile("github_" + "pat_" + r"[A-Za-z0-9_]{20,}")),
        ("aws_key", re.compile("AK" + "IA" + r"[0-9A-Z]{16}")),
        ("openai_key", re.compile("sk" + "-proj-" + r"[A-Za-z0-9_-]{20,}")),
        ("anthropic_key", re.compile("sk" + "-ant-" + r"[A-Za-z0-9_-]{12,}")),
        ("priv_key", re.compile("-----BEGIN " + r"(?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ]
    return path_rules, model_rules, cred_rules


def _read_regular_nofollow_under(root: Path, rel: Path, max_bytes: int = MAX_FILE_BYTES) -> tuple[bytes, os.stat_result]:
    dir_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    cur_fd = -1
    file_fd = -1
    try:
        cur_fd = os.open(os.fspath(root), dir_flags)
        parts = rel.parts
        for seg in parts[:-1]:
            nxt = os.open(seg, dir_flags, dir_fd=cur_fd)
            os.close(cur_fd)
            cur_fd = nxt
        file_fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=cur_fd)
        st = os.fstat(file_fd)
        require_tc(stat.S_ISREG(st.st_mode), "NON_REGULAR_FILE", f"{rel}: non-regular file")
        require_tc(st.st_nlink == 1, "HARDLINK_FORBIDDEN", f"{rel}: hardlinked file forbidden (nlink={st.st_nlink})")
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = os.read(file_fd, 65536)
            if not chunk:
                break
            total += len(chunk)
            require_tc(total <= max_bytes, "FILE_TOO_LARGE", f"{rel}: exceeds {max_bytes} bytes")
            chunks.append(chunk)
        return b"".join(chunks), st
    except OSError as exc:
        raise TrustCoreError("PREFLIGHT_IO_ERROR", f"{rel}: {exc}") from exc
    finally:
        if file_fd >= 0:
            os.close(file_fd)
        if cur_fd >= 0:
            os.close(cur_fd)


def _open_dir_nofollow_under(root: Path, rel_dir: Path) -> int:
    dir_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    cur_fd = os.open(os.fspath(root), dir_flags)
    try:
        if rel_dir != Path("."):
            for seg in rel_dir.parts:
                nxt = os.open(seg, dir_flags, dir_fd=cur_fd)
                os.close(cur_fd)
                cur_fd = nxt
        return cur_fd
    except OSError:
        os.close(cur_fd)
        raise


def _walk_track_inventory(root: Path, findings: list[dict[str, Any]]) -> list[Path]:
    """Walk track root using bounded O(1) `O_NOFOLLOW` directory FDs (no FD accumulation across DFS)."""
    regular_files: list[Path] = []
    stack: list[Path] = [Path(".")]
    try:
        while stack:
            cur_rel = stack.pop()
            cur_dfd = _open_dir_nofollow_under(root, cur_rel)
            try:
                names = sorted(os.listdir(cur_dfd))
                subdirs: list[Path] = []
                for name in names:
                    rel = name if cur_rel == Path(".") else os.path.join(os.fspath(cur_rel), name)
                    rel_p = Path(rel)
                    st = os.lstat(name, dir_fd=cur_dfd)
                    mode = st.st_mode
                    if stat.S_ISLNK(mode):
                        findings.append({"check": "residue", "code": "SYMLINK_RESIDUE", "file": rel, "detail": "symlink forbidden"})
                        continue
                    if stat.S_ISDIR(mode):
                        if name in _SKIP_VCS_DIRS:
                            continue
                        if name == ".lake":
                            findings.append({"check": "residue", "code": "LAKE_RESIDUE", "file": rel, "detail": ".lake directory residue"})
                            continue
                        if name == "__pycache__":
                            findings.append({"check": "residue", "code": "PYCACHE_RESIDUE", "file": rel, "detail": "__pycache__ residue"})
                            continue
                        subdirs.append(rel_p)
                    elif stat.S_ISREG(mode):
                        if st.st_nlink != 1:
                            findings.append({"check": "residue", "code": "HARDLINK_FORBIDDEN", "file": rel, "detail": f"hardlinked file forbidden (nlink={st.st_nlink})"})
                            continue
                        if name.endswith((".pyc", ".pyo")):
                            findings.append({"check": "residue", "code": "PYCACHE_RESIDUE", "file": rel, "detail": "bytecode residue"})
                        elif name.endswith(".olean"):
                            findings.append({"check": "residue", "code": "LAKE_RESIDUE", "file": rel, "detail": ".olean residue"})
                        regular_files.append(rel_p)
                    else:
                        findings.append({"check": "residue", "code": "NON_REGULAR_FILE", "file": rel, "detail": "non-regular entry"})
                stack.extend(reversed(subdirs))
            finally:
                os.close(cur_dfd)
    except OSError as exc:
        raise TrustCoreError("PREFLIGHT_IO_ERROR", f"directory walk failed: {exc}") from exc
    return sorted(regular_files)


def _collect_json_strings_and_ints(obj: Any) -> tuple[set[str], list[int]]:
    keys_vals: set[str] = set()
    big_ints: list[int] = []
    stack: list[Any] = [obj]
    while stack:
        cur = stack.pop()
        if type(cur) is dict:
            for k, v in cur.items():
                keys_vals.add(k)
                stack.append(v)
        elif type(cur) is list:
            stack.extend(cur)
        elif type(cur) is str:
            if len(cur) <= 128:
                keys_vals.add(cur)
            if _STR_BIG_INT_RE.match(cur) is not None:
                val_i = int(cur)
                if abs(val_i) >= 1_000_000:
                    big_ints.append(val_i)
        elif type(cur) is int:
            if abs(cur) >= 1_000_000:
                big_ints.append(cur)
    return keys_vals, big_ints


def _check_cert_verdict_contradictions(cert_file: str, obj: Any, findings: list[dict[str, Any]]) -> None:
    """Catch bidirectional verdict contradictions: FALSIFIED+pass=True AND VERIFIED/PASS+pass=False."""
    stack: list[tuple[str, Any]] = [("$", obj)]
    while stack:
        path_s, cur = stack.pop()
        if type(cur) is dict:
            has_partial = any(type(v) is str and "PARTIAL" in v.upper() for v in cur.values())
            neg_verdicts = [
                k for k, v in cur.items()
                if type(v) is str and v.upper() in ("FALSIFIED", "FAIL", "REJECTED") and "verdict" in k.lower()
            ]
            pos_verdicts = [
                k for k, v in cur.items()
                if type(v) is str and v.upper() in ("VERIFIED", "CONFIRMED", "PASS", "PASSED") and "verdict" in k.lower()
            ]
            if neg_verdicts and not has_partial:
                passing_gates = [
                    k for k, v in cur.items()
                    if type(v) is bool and v is True and ("gate_pass" in k.lower() or k.lower().endswith("_pass") or k.lower() == "passed")
                ]
                if passing_gates:
                    findings.append({
                        "check": "witness",
                        "code": "CERT_VERDICT_CONTRADICTION",
                        "file": cert_file,
                        "detail": f"{path_s}: negative verdict {neg_verdicts} while sibling gate booleans {passing_gates} are True",
                    })
            if pos_verdicts and not has_partial:
                failing_gates = [
                    k for k, v in cur.items()
                    if type(v) is bool and v is False and ("gate_pass" in k.lower() or k.lower().endswith("_pass") or k.lower() == "passed")
                ]
                if failing_gates:
                    findings.append({
                        "check": "witness",
                        "code": "CERT_VERDICT_CONTRADICTION",
                        "file": cert_file,
                        "detail": f"{path_s}: positive verdict {pos_verdicts} while sibling gate booleans {failing_gates} are False",
                    })
            for k, v in cur.items():
                stack.append((f"{path_s}.{k}", v))
        elif type(cur) is list:
            for idx, item in enumerate(cur):
                stack.append((f"{path_s}[{idx}]", item))


def _int_sci_profile(val: int) -> tuple[int, str, int]:
    """Return exact `(sign, digits, exp10)` for nonzero integer `val` using pure integer/string ops."""
    sign = -1 if val < 0 else 1
    digits = str(abs(val))
    return sign, digits, len(digits) - 1


def _digits_prefix_matches(cert_digits: str, prose_digits: str) -> bool:
    """Check if prose mantissa digits match cert integer digits (allowing truncation or +/-1 ULP rounding)."""
    k = len(prose_digits)
    if len(cert_digits) < k:
        return False
    trunc = int(cert_digits[:k])
    prose = int(prose_digits)
    return abs(trunc - prose) <= 1


def _check_prose_theorems_and_witnesses(
    prose_texts: dict[str, str],
    lean_theorems: set[str],
    lean_defs: set[str],
    lean_namespaces: set[str],
    py_symbols: set[str],
    json_tokens: set[str],
    cert_big_ints: list[int],
    has_cert_json: bool,
    findings: list[dict[str, Any]],
) -> None:
    cert_profiles = [_int_sci_profile(v) for v in cert_big_ints]
    cert_int_strs = {str(v) for v in cert_big_ints} | {str(abs(v)) for v in cert_big_ints}

    for rel, text in sorted(prose_texts.items()):
        in_thm_table = False
        in_lean_section = False
        for lineno, line in enumerate(text.splitlines(), start=1):
            stripped = line.strip()
            if stripped.startswith("#"):
                in_lean_section = ("lean" in stripped.lower() or "theorem" in stripped.lower())
                in_thm_table = False
            if "|" in stripped and ("public theorem" in stripped.lower() or "| theorem" in stripped.lower()):
                in_thm_table = True
                continue
            if in_thm_table and not stripped.startswith("|"):
                in_thm_table = False

            # (i) Ghost Lean theorem citation detection (incl. undeclared namespaces like `Ghost.fake_thm`)
            is_thm_line = in_thm_table or _THM_CONTEXT_RE.search(line) is not None
            for m_bt in _BACKTICK_RE.finditer(line):
                tok = m_bt.group(1)
                if tok.endswith(_KNOWN_FILE_EXTS):
                    continue
                if "." in tok:
                    head = tok.split(".", 1)[0]
                    tail = tok.split(".")[-1]
                    if head in lean_namespaces:
                        if tok not in lean_theorems and tok not in lean_defs and tail not in lean_theorems and tail not in lean_defs:
                            findings.append({
                                "check": "lean_citations",
                                "code": "GHOST_LEAN_THEOREM",
                                "file": rel,
                                "line": lineno,
                                "detail": f"cited Lean identifier `{tok}` absent from *.lean",
                            })
                        continue
                    m_q = _QUALIFIED_THM_RE.match(tok)
                    if m_q is not None and head not in _KNOWN_NON_THEOREM_PREFIXES:
                        if (
                            tok not in lean_theorems
                            and tok not in lean_defs
                            and tail not in py_symbols
                            and head not in py_symbols
                            and tok not in json_tokens
                        ):
                            findings.append({
                                "check": "lean_citations",
                                "code": "GHOST_LEAN_THEOREM",
                                "file": rel,
                                "line": lineno,
                                "detail": f"qualified theorem citation `{tok}` absent from *.lean",
                            })
                    continue
                if not lean_theorems:
                    continue
                if _SHA_HEX_RE.match(tok) or _UPPER_TOKEN_RE.match(tok) or tok in _LEAN_BUILTIN_KEYWORDS:
                    continue
                if tok in lean_theorems or tok in lean_defs or tok in py_symbols or tok in json_tokens:
                    continue
                looks_like_thm = _THM_LIKE_SUFFIX_RE.search(tok) is not None
                if looks_like_thm or (in_thm_table and "_" in tok) or (in_lean_section and is_thm_line and "_" in tok and not tok.startswith("s1")):
                    findings.append({
                        "check": "lean_citations",
                        "code": "GHOST_LEAN_THEOREM",
                        "file": rel,
                        "line": lineno,
                        "detail": f"cited Lean theorem `{tok}` absent from *.lean",
                    })

            # (ii-a) Scientific notation exponent audit vs certificate.json (integer or 1..10 frac digits + e/E notation)
            sci_matches = list(_SCI_TIMES_RE.finditer(line)) + list(_SCI_ENOT_RE.finditer(line))
            for m_sci in sci_matches:
                raw_sign, lead, frac, exp_s = m_sci.groups()
                frac_s = frac or ""
                sign = -1 if raw_sign in ("-", "\u2212") else 1
                prose_digits = lead + frac_s
                prose_exp = int(exp_s)
                if prose_exp < 6:
                    continue
                mant_disp = f"{raw_sign}{lead}.{frac_s}" if frac_s else f"{raw_sign}{lead}"
                matched_exps = [
                    c_exp for (c_sign, c_digits, c_exp) in cert_profiles
                    if c_sign == sign and _digits_prefix_matches(c_digits, prose_digits)
                ]
                if matched_exps:
                    if prose_exp not in matched_exps:
                        findings.append({
                            "check": "witness",
                            "code": "SCI_NOTATION_MISMATCH",
                            "file": rel,
                            "line": lineno,
                            "detail": f"prose 10^{prose_exp} ({mant_disp}) disagrees with certificate 10^{matched_exps[0]}",
                        })
                elif has_cert_json and prose_exp >= 7:
                    findings.append({
                        "check": "witness",
                        "code": "SCI_NOTATION_UNBACKED",
                        "file": rel,
                        "line": lineno,
                        "detail": f"prose scientific witness {mant_disp}e{prose_exp} has no backing large integer in certificate.json",
                    })

            # (ii-b) Exact large integer witness check (>= 18 digits)
            if cert_int_strs:
                for m_big in _BIG_INT_RE.finditer(line):
                    raw_num = m_big.group(1).replace("\u2212", "-").lstrip("+")
                    if raw_num not in cert_int_strs and raw_num.lstrip("-") not in cert_int_strs:
                        if any(len(raw_num.lstrip("-")) == len(c.lstrip("-")) and raw_num.lstrip("-")[:6] == c.lstrip("-")[:6] for c in cert_int_strs):
                            findings.append({
                                "check": "witness",
                                "code": "INTEGER_WITNESS_MISMATCH",
                                "file": rel,
                                "line": lineno,
                                "detail": f"large integer witness {raw_num[:20]}... differs from certificate.json",
                            })


_CONDITIONAL_STMT_TYPES: tuple[type, ...] = (
    ast.If, ast.For, ast.AsyncFor, ast.While, ast.Try, getattr(ast, "TryStar", ast.Try),
    ast.With, ast.AsyncWith, ast.Match, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef,
)


def _class_forces_allow_abbrev_false(cls_node: ast.ClassDef) -> bool:
    """
    AST-verify `__init__` UNCONDITIONALLY (top-level statement, never inside `if`/loop/`try`/`with`/nested def)
    sets `kwargs['allow_abbrev'] = False` or passes `allow_abbrev=False` (never `setdefault`) (Delta-5 LOW-4).
    """
    for item in cls_node.body:
        if isinstance(item, ast.FunctionDef) and item.name == "__init__":
            top_level_nodes = [sub for stmt in item.body if not isinstance(stmt, _CONDITIONAL_STMT_TYPES) for sub in ast.walk(stmt)]
            for sub in top_level_nodes:
                if isinstance(sub, ast.Assign) and isinstance(sub.value, ast.Constant) and sub.value.value is False:
                    for tgt in sub.targets:
                        if (
                            isinstance(tgt, ast.Subscript)
                            and isinstance(tgt.slice, ast.Constant)
                            and tgt.slice.value == "allow_abbrev"
                        ):
                            return True
                elif isinstance(sub, ast.Call) and _has_allow_abbrev_false_kw(sub):
                    return True
    return False


def _base_class_name(base: ast.expr) -> str | None:
    if isinstance(base, ast.Name):
        return base.id
    if isinstance(base, ast.Attribute):
        return base.attr
    return None


def _fn_uses_type_check(fn_node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    for sub in ast.walk(fn_node):
        if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name) and sub.func.id == "type":
            return True
    return False


def _has_allow_abbrev_false_kw(call: ast.Call) -> bool:
    for kw in call.keywords:
        if kw.arg == "allow_abbrev" and isinstance(kw.value, ast.Constant) and kw.value.value is False:
            return True
    return False


def _call_is_non_atomic_write(fn_node: ast.FunctionDef | ast.AsyncFunctionDef) -> str | None:
    has_atomic_call = False
    has_o_trunc = False
    has_non_atomic_open = False
    for sub in ast.walk(fn_node):
        if isinstance(sub, ast.Name) and sub.id == "O_TRUNC":
            has_o_trunc = True
        elif isinstance(sub, ast.Attribute) and sub.attr == "O_TRUNC":
            has_o_trunc = True
        elif isinstance(sub, ast.Call):
            fn = sub.func
            if isinstance(fn, ast.Attribute) and fn.attr == "replace" and isinstance(fn.value, ast.Name) and fn.value.id == "os":
                has_atomic_call = True
            elif isinstance(fn, ast.Name) and fn.id in ("atomic_write_json_nofollow", "atomic_write_nofollow"):
                has_atomic_call = True
            elif isinstance(fn, ast.Attribute) and fn.attr in ("atomic_write_json_nofollow", "atomic_write_nofollow"):
                has_atomic_call = True
            elif isinstance(fn, ast.Attribute) and fn.attr in ("write_text", "write_bytes"):
                has_non_atomic_open = True
            elif isinstance(fn, ast.Name) and fn.id == "open":
                mode_arg: ast.expr | None = sub.args[1] if len(sub.args) >= 2 else None
                for kw in sub.keywords:
                    if kw.arg == "mode":
                        mode_arg = kw.value
                if isinstance(mode_arg, ast.Constant) and type(mode_arg.value) is str and "w" in mode_arg.value:
                    has_non_atomic_open = True
    if has_atomic_call:
        return None
    if has_o_trunc:
        return "UNSAFE_WRITE_O_TRUNC"
    if has_non_atomic_open:
        return "UNSAFE_WRITE_NON_ATOMIC"
    return None


def _expr_cert_tag(expr: ast.expr) -> str | None:
    if isinstance(expr, ast.Name):
        nm = expr.id.lower()
        return nm if nm in _CERT_VAR_NAMES else None
    if isinstance(expr, ast.Call):
        fn = expr.func
        fnm = (fn.id if isinstance(fn, ast.Name) else (fn.attr if isinstance(fn, ast.Attribute) else "")).lower()
        if any(tok in fnm for tok in ("cert", "payload", "json", "load")):
            return fnm
        return None
    if isinstance(expr, (ast.Subscript, ast.Attribute)) and isinstance(expr.value, ast.Name):
        nm = expr.value.id.lower()
        return nm if nm in _CERT_VAR_NAMES else None
    return None


def _scan_python_ast_antipatterns(
    rel: str,
    text: str,
    findings: list[dict[str, Any]],
    *,
    external_unsafe_parsers: dict[str, set[str]] | None = None,
) -> set[str]:
    """Scan Python AST for bare asserts, missing allow_abbrev=False, bool==int cert eq, unsafe writes, dropped gate vars."""
    symbols: set[str] = set()
    try:
        tree = ast.parse(text, filename=rel)
    except SyntaxError as exc:
        findings.append({"check": "ast", "code": "PYTHON_SYNTAX_ERROR", "file": rel, "line": exc.lineno or 0, "detail": str(exc)})
        return symbols

    is_test = Path(rel).name.startswith("test_")
    class_defs: list[ast.ClassDef] = []
    strict_eq_compare_ids: set[int] = set()
    argparser_aliases: set[str] = {"ArgumentParser"}
    var_aliases: list[tuple[str, str]] = []
    ext_map = external_unsafe_parsers or {}

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            symbols.add(node.name)
            if node.name in _STRICT_EQ_HELPER_NAMES and _fn_uses_type_check(node):
                for sub in ast.walk(node):
                    if isinstance(sub, ast.Compare):
                        strict_eq_compare_ids.add(id(sub))
        elif isinstance(node, ast.ClassDef):
            symbols.add(node.name)
            class_defs.append(node)
        elif isinstance(node, ast.ImportFrom):
            mod_tail = (node.module or "").split(".")[-1]
            for alias in node.names:
                bound = alias.asname or alias.name
                symbols.add(bound)
                if node.module == "argparse" and alias.name == "ArgumentParser":
                    argparser_aliases.add(bound)
                elif mod_tail in ext_map and alias.name in ext_map[mod_tail]:
                    argparser_aliases.add(bound)
        elif isinstance(node, ast.Import):
            # `import mod; mod.UnsafeSub()` -- module-qualified unsafe parser subclasses (Delta-5 LOW-4)
            for alias in node.names:
                imp_tail = alias.name.split(".")[-1]
                if imp_tail in ext_map:
                    argparser_aliases.update(ext_map[imp_tail])
        elif isinstance(node, (ast.Assign, ast.AnnAssign)) and node.value is not None:
            # `P = argparse.ArgumentParser; P()` -- local variable aliases (Delta-5 LOW-4)
            val_name = _base_class_name(node.value)
            if val_name is not None:
                tgts = node.targets if isinstance(node, ast.Assign) else [node.target]
                for tgt in tgts:
                    if isinstance(tgt, ast.Name):
                        var_aliases.append((tgt.id, val_name))
        elif isinstance(node, ast.Assert):
            findings.append({"check": "ast", "code": "BARE_ASSERT", "file": rel, "line": node.lineno, "detail": "bare assert forbidden (R4 -O parity)"})

    # Fixed-point transitive ArgumentParser, variable-alias & subclass tracking (catches `as AP` & imported/indirect subclasses)
    unsafe_parser_subclasses: set[str] = set(argparser_aliases)
    changed_cls = True
    while changed_cls:
        changed_cls = False
        for var_name, val_name in var_aliases:
            if var_name not in unsafe_parser_subclasses and (val_name in unsafe_parser_subclasses or val_name == "add_parser"):
                unsafe_parser_subclasses.add(var_name)
                changed_cls = True
        for cdef in class_defs:
            if cdef.name in unsafe_parser_subclasses:
                continue
            base_names = {_base_class_name(b) for b in cdef.bases}
            if any(bn in unsafe_parser_subclasses for bn in base_names) and not _class_forces_allow_abbrev_false(cdef):
                unsafe_parser_subclasses.add(cdef.name)
                changed_cls = True

    if not is_test:
        for node in ast.walk(tree):
            # Missing allow_abbrev=False on ArgumentParser(...), aliases, subclasses, and add_parser(...)
            if isinstance(node, ast.Call):
                fn = node.func
                is_argparser = (
                    (isinstance(fn, ast.Attribute) and (fn.attr in ("ArgumentParser", "add_parser") or fn.attr in unsafe_parser_subclasses))
                    or (isinstance(fn, ast.Name) and fn.id in unsafe_parser_subclasses)
                )
                if is_argparser and not _has_allow_abbrev_false_kw(node):
                    findings.append({
                        "check": "ast",
                        "code": "MISSING_ALLOW_ABBREV_FALSE",
                        "file": rel,
                        "line": node.lineno,
                        "detail": "ArgumentParser/alias/subclass/add_parser missing allow_abbrev=False",
                    })

            # bool == int equality risk on certificate / payload objects (Name/Call/Subscript, NEVER disabled file-wide!)
            if isinstance(node, ast.Compare) and id(node) not in strict_eq_compare_ids:
                if len(node.ops) == 1 and isinstance(node.ops[0], (ast.Eq, ast.NotEq)):
                    lt = _expr_cert_tag(node.left)
                    rt = _expr_cert_tag(node.comparators[0])
                    if lt is not None and rt is not None:
                        findings.append({
                            "check": "ast",
                            "code": "BOOL_INT_EQ_RISK",
                            "file": rel,
                            "line": node.lineno,
                            "detail": f"raw equality `{ast.unparse(node.left)} == {ast.unparse(node.comparators[0])}` allows True==1/False==0 spoof; use strict_json_equal",
                        })

            # Unsafe --write helper using O_TRUNC or non-atomic open("w")/write_text/write_bytes
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and ("write_cert" in node.name or "write_json" in node.name):
                wcode = _call_is_non_atomic_write(node)
                if wcode is not None:
                    findings.append({
                        "check": "ast",
                        "code": wcode,
                        "file": rel,
                        "line": node.lineno,
                        "detail": f"{node.name} writes non-atomically without O_EXCL + os.replace",
                    })

            # Dropped gate-pass variable inside a function (catches both partial AND all-dropped gates!)
            if isinstance(node, ast.FunctionDef):
                assigned_gates: dict[str, int] = {}
                used_gate_names: set[str] = set()
                for sub in ast.walk(node):
                    if isinstance(sub, ast.Assign) and len(sub.targets) == 1 and isinstance(sub.targets[0], ast.Name):
                        nm = sub.targets[0].id
                        if nm.endswith(("_ppl_pass", "_hmse_pass", "_gate_pass")):
                            assigned_gates[nm] = sub.lineno
                    elif isinstance(sub, (ast.If, ast.BoolOp, ast.Return, ast.Call)):
                        target_expr: ast.AST = sub.test if isinstance(sub, ast.If) else sub
                        for leaf in ast.walk(target_expr):
                            if isinstance(leaf, ast.Name) and isinstance(leaf.ctx, ast.Load):
                                used_gate_names.add(leaf.id)
                for gname, glino in sorted(assigned_gates.items()):
                    if gname not in used_gate_names:
                        findings.append({
                            "check": "ast",
                            "code": "DROPPED_GATE_VARIABLE",
                            "file": rel,
                            "line": glino,
                            "detail": f"gate boolean `{gname}` assigned but omitted from verdict/guard evaluation",
                        })
    return symbols


def _scope_hashes_results(nodes: Sequence[ast.AST], res_name: str) -> bool:
    calls_bind = False
    calls_read_res = False
    calls_hash = False
    for root in nodes:
        for node in ast.walk(root):
            if isinstance(node, ast.Call):
                fn = node.func
                fn_name = fn.id if isinstance(fn, ast.Name) else (fn.attr if isinstance(fn, ast.Attribute) else "")
                if fn_name == "bind_empirical_artifact":
                    calls_bind = True
                if fn_name in _HASH_FUNC_NAMES:
                    calls_hash = True
                if fn_name in _READ_FUNC_NAMES:
                    call_src = ast.unparse(node)
                    if (
                        res_name in call_src
                        or "results_path" in call_src
                        or "res_path" in call_src
                        or "emp_results" in call_src
                        or "empirical_results" in call_src
                    ):
                        calls_read_res = True
    return calls_bind or (calls_read_res and calls_hash)


def _verifier_ast_hashes_results(v_src: str, res_name: str) -> bool:
    """AST-verified per-scope check that a verifier calls `bind_empirical_artifact` or reads+hashes results in the same function/module scope."""
    try:
        tree = ast.parse(v_src)
    except SyntaxError:
        return False

    top_stmts: list[ast.AST] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if _scope_hashes_results([node], res_name):
                return True
        else:
            top_stmts.append(node)
    return _scope_hashes_results(top_stmts, res_name)


def _check_empirical_provenance(
    regular_files: list[Path],
    file_bytes: dict[str, bytes],
    file_stats: dict[str, os.stat_result],
    py_texts: dict[str, str],
    findings: list[dict[str, Any]],
) -> str:
    """Catch stale, mismatched, or unhashed `results.json` files with AST-verified verifier inspection."""
    results_files = [
        os.fspath(p) for p in regular_files
        if p.suffix == ".json" and "results" in p.name.lower()
    ]
    bench_files = [
        os.fspath(p) for p in regular_files
        if p.suffix == ".py" and "bench" in p.name.lower() and not p.name.startswith("test_")
    ]
    if not results_files:
        return "NOT_APPLICABLE"

    verify_files = [
        rel for rel in py_texts
        if Path(rel).name.startswith("verify") or "oracle" in Path(rel).name.lower()
    ]
    bench_shas = {b_rel: sha256_bytes(file_bytes[b_rel]) for b_rel in bench_files if b_rel in file_bytes}

    for res_rel in results_files:
        res_st = file_stats[res_rel]
        res_name = Path(res_rel).name
        emb_bench_sha: str | None = None
        try:
            res_obj = parse_strict_json_bytes(file_bytes[res_rel], label=res_rel, allow_float=True, require_trailing_lf=False)
            if type(res_obj) is dict and type(res_obj.get("bench_script_sha256")) is str:
                emb_bench_sha = res_obj["bench_script_sha256"]
        except TrustCoreError:
            pass

        if bench_files:
            matched_benches = [b_rel for b_rel, b_sha in bench_shas.items() if emb_bench_sha is not None and b_sha == emb_bench_sha]
            if emb_bench_sha is not None and len(matched_benches) == 0:
                findings.append({
                    "check": "provenance",
                    "code": "RESULTS_BENCH_SHA_MISMATCH",
                    "file": res_rel,
                    "detail": f"{res_rel} embedded bench_script_sha256 matches none of {bench_files}",
                })
            stale_targets = matched_benches if matched_benches else bench_files
            for bench_rel in stale_targets:
                bench_st = file_stats[bench_rel]
                if res_st.st_mtime_ns <= bench_st.st_mtime_ns:
                    findings.append({
                        "check": "provenance",
                        "code": "STALE_RESULTS_JSON",
                        "file": res_rel,
                        "detail": f"{res_rel} mtime ({res_st.st_mtime_ns}) does not post-date {bench_rel} ({bench_st.st_mtime_ns})",
                    })

        if not verify_files:
            findings.append({
                "check": "provenance",
                "code": "MISSING_VERIFIER_FOR_RESULTS",
                "file": res_rel,
                "detail": f"{res_rel} present with no verifier/oracle script in track",
            })
        else:
            hashed_on_disk = any(_verifier_ast_hashes_results(py_texts[v_rel], res_name) for v_rel in verify_files)
            if not hashed_on_disk:
                findings.append({
                    "check": "provenance",
                    "code": "UNHASHED_RESULTS_JSON",
                    "file": res_rel,
                    "detail": f"{res_rel} is never read and SHA-256 hashed on disk by verifier/oracle (AST check)",
                })
    return "APPLIED"


def _check_public_hygiene(
    rel: str,
    text: str,
    path_rules: Sequence[tuple[str, re.Pattern[str]]],
    model_rules: Sequence[tuple[str, re.Pattern[str]]],
    cred_rules: Sequence[tuple[str, re.Pattern[str]]],
    findings: list[dict[str, Any]],
) -> None:
    is_prose = Path(rel).suffix in _PROSE_EXTS
    is_py = Path(rel).suffix == ".py"
    for lineno, line in enumerate(text.splitlines(), start=1):
        for rname, rx in path_rules:
            if rx.search(line) is not None:
                findings.append({"check": "hygiene", "code": "HYGIENE_PATH_LEAK", "file": rel, "line": lineno, "detail": rname})
        for rname, rx in cred_rules:
            if rx.search(line) is not None:
                findings.append({"check": "hygiene", "code": "HYGIENE_CREDENTIAL_LEAK", "file": rel, "line": lineno, "detail": rname})
        if is_prose:
            for rname, rx in model_rules:
                if rx.search(line) is not None:
                    findings.append({"check": "hygiene", "code": "HYGIENE_MODEL_LEAK", "file": rel, "line": lineno, "detail": rname})
            for m_at in _AT_HANDLE_RE.finditer(line):
                handle = m_at.group(1)
                if handle not in _SAFE_AT_WORDS:
                    findings.append({"check": "hygiene", "code": "HYGIENE_HANDLE_LEAK", "file": rel, "line": lineno, "detail": f"@{handle}"})
        elif is_py:
            stripped = line.lstrip()
            if not stripped.startswith("@"):
                for m_at in _AT_HANDLE_RE.finditer(line):
                    handle = m_at.group(1)
                    if handle not in _SAFE_AT_WORDS and any(tok in handle for tok in ("coordinator", "council", "router", "delta", "auditor")):
                        findings.append({"check": "hygiene", "code": "HYGIENE_HANDLE_LEAK", "file": rel, "line": lineno, "detail": f"@{handle}"})


def _collect_track_unsafe_parsers(py_texts: dict[str, str]) -> dict[str, set[str]]:
    """Collect unsafe `ArgumentParser` subclasses exported by each module stem for cross-file import checks."""
    out: dict[str, set[str]] = {}
    for rel, text in sorted(py_texts.items()):
        try:
            tree = ast.parse(text, filename=rel)
        except SyntaxError:
            continue
        aliases: set[str] = {"ArgumentParser"}
        class_defs: list[ast.ClassDef] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "argparse":
                for alias in node.names:
                    if alias.name == "ArgumentParser":
                        aliases.add(alias.asname or alias.name)
            elif isinstance(node, ast.ClassDef):
                class_defs.append(node)
        unsafe: set[str] = set(aliases)
        changed = True
        while changed:
            changed = False
            for cdef in class_defs:
                if cdef.name in unsafe:
                    continue
                if any(_base_class_name(b) in unsafe for b in cdef.bases) and not _class_forces_allow_abbrev_false(cdef):
                    unsafe.add(cdef.name)
                    changed = True
        exported = unsafe - aliases
        if exported:
            out.setdefault(Path(rel).stem, set()).update(exported)
    return out


def run_preflight(
    track_dir: str | Path,
    *,
    max_bytes: int = MAX_FILE_BYTES,
    budget_ms: int = DEFAULT_BUDGET_MS,
) -> dict[str, Any]:
    """Run all 6 shift-left pre-audit gates + strict `< budget_ms` timing gate on `track_dir` (read-only)."""
    t0_ns = time.monotonic_ns()
    require_tc(
        type(budget_ms) is int and 1 <= budget_ms <= MAX_BUDGET_MS,
        "INVALID_BUDGET_MS",
        f"budget_ms must be int in [1, {MAX_BUDGET_MS}]",
    )
    p = Path(track_dir) if type(track_dir) is str else track_dir
    require_tc(isinstance(p, Path), "INVALID_TRACK_DIR", "track_dir must be str or Path")
    require_tc("\x00" not in os.fspath(p), "NUL_IN_PATH", "NUL byte forbidden in track_dir")
    try:
        st_root = os.lstat(p)
    except OSError as exc:
        raise TrustCoreError("TRACK_DIR_NOT_FOUND", f"track_dir unavailable: {exc}") from exc
    require_tc(stat.S_ISDIR(st_root.st_mode), "TRACK_DIR_NOT_DIR", f"not a regular directory: {p}")

    findings: list[dict[str, Any]] = []
    regular_files = _walk_track_inventory(p, findings)
    require_tc(len(regular_files) > 0 or len(findings) > 0, "EMPTY_TRACK_DIR", f"no files found in {p}")

    path_rules, model_rules, cred_rules = _build_hygiene_rules()

    file_bytes: dict[str, bytes] = {}
    file_stats: dict[str, os.stat_result] = {}
    prose_texts: dict[str, str] = {}
    py_texts: dict[str, str] = {}
    lean_theorems: set[str] = set()
    lean_unique_theorems: set[str] = set()
    lean_defs: set[str] = set()
    lean_namespaces: set[str] = set()
    py_symbols: set[str] = set()
    json_tokens: set[str] = set()
    cert_big_ints: list[int] = []
    has_lean_files = False
    has_cert_json = False

    for rel_p in regular_files:
        rel = os.fspath(rel_p)
        ext = rel_p.suffix.lower()
        name = rel_p.name
        is_known_text = (ext in _STRICT_TEXT_EXTS) or (name in ("lean-toolchain", ".env")) or name.startswith(".env.")
        raw, st = _read_regular_nofollow_under(p, rel_p, max_bytes=max_bytes)
        file_bytes[rel] = raw
        file_stats[rel] = st

        if not is_known_text and b"\x00" in raw:
            continue

        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            if is_known_text:
                findings.append({"check": "residue", "code": "INVALID_UTF8", "file": rel, "detail": str(exc)})
            continue

        if is_known_text or ext == "":
            if raw.startswith(b"\xef\xbb\xbf"):
                findings.append({"check": "residue", "code": "BOM_RESIDUE", "file": rel, "detail": "UTF-8 BOM forbidden"})
            if b"\r" in raw:
                findings.append({"check": "residue", "code": "CRLF_RESIDUE", "file": rel, "detail": "CR/CRLF line endings forbidden"})

        _check_public_hygiene(rel, text, path_rules, model_rules, cred_rules, findings)

        if ext == ".lean" and name != "lakefile.lean":
            has_lean_files = True
            st_res = audit_lean4_source_static(text)
            for lf in st_res["findings"]:
                findings.append({"check": "lean_static", "file": rel, **lf})
            for full_thm in extract_lean4_theorems(text):
                lean_unique_theorems.add(full_thm)
                lean_theorems.add(full_thm)
                lean_theorems.add(full_thm.split(".")[-1])
            cleaned, _ = strip_lean4_comments_and_literals(text)
            for line in cleaned.splitlines():
                m_ns = _LEAN_NS_RE.match(line)
                if m_ns is not None:
                    lean_namespaces.add(m_ns.group(1).split(".")[0])
                m_def = _LEAN_DEF_RE.match(line)
                if m_def is not None:
                    lean_defs.add(m_def.group(1))
                    lean_defs.add(m_def.group(1).split(".")[-1])
        elif name in ("lakefile.toml", "lakefile.lean"):
            has_lean_files = True
            try:
                for lf in audit_lakefile_bytes(name, raw):
                    findings.append({"check": "lean_static", "file": rel, "code": lf["code"], "detail": lf["excerpt"]})
            except TrustCoreError as exc:
                findings.append({"check": "lean_static", "file": rel, "code": exc.code, "detail": exc.message})
        elif ext == ".py":
            py_texts[rel] = text
        elif ext == ".json":
            is_results = "results" in name.lower()
            try:
                obj = parse_strict_json_bytes(
                    raw,
                    label=rel,
                    allow_float=is_results,
                    require_trailing_lf=True,
                )
            except TrustCoreError as exc:
                findings.append({"check": "json", "code": exc.code, "file": rel, "detail": exc.message})
                continue
            toks, ints = _collect_json_strings_and_ints(obj)
            json_tokens.update(toks)
            if "certificate" in name.lower():
                has_cert_json = True
                cert_big_ints.extend(ints)
                _check_cert_verdict_contradictions(rel, obj, findings)
        elif ext in _PROSE_EXTS:
            prose_texts[rel] = text

    external_unsafe_parsers = _collect_track_unsafe_parsers(py_texts)
    for py_rel, py_src in sorted(py_texts.items()):
        py_symbols.update(_scan_python_ast_antipatterns(py_rel, py_src, findings, external_unsafe_parsers=external_unsafe_parsers))

    _check_prose_theorems_and_witnesses(
        prose_texts,
        lean_theorems,
        lean_defs,
        lean_namespaces,
        py_symbols,
        json_tokens,
        cert_big_ints,
        has_cert_json,
        findings,
    )
    prov_status = _check_empirical_provenance(regular_files, file_bytes, file_stats, py_texts, findings)

    elapsed_ms = (time.monotonic_ns() - t0_ns) // 1_000_000
    within_budget = elapsed_ms < budget_ms
    if not within_budget:
        findings.append({
            "check": "budget",
            "code": "PREFLIGHT_BUDGET_EXCEEDED",
            "file": ".",
            "detail": f"preflight elapsed {elapsed_ms}ms >= budget {budget_ms}ms",
        })

    checks_applicability = {
        "residue": "APPLIED",
        "hygiene": "APPLIED",
        "lean_static": "APPLIED" if has_lean_files else "NOT_APPLICABLE",
        "lean_citations": "APPLIED" if prose_texts else "NOT_APPLICABLE",
        "witness": "APPLIED" if (has_cert_json or cert_big_ints) else "NOT_APPLICABLE",
        "provenance": prov_status,
        "ast": "APPLIED" if py_texts else "NOT_APPLICABLE",
        "budget": "APPLIED",
    }

    passed = len(findings) == 0
    return {
        "status": "PASS" if passed else "FAIL",
        "passed": passed,
        "track_name": p.resolve().name,
        "files_scanned": len(regular_files),
        "lean_unique_theorems": len(lean_unique_theorems),
        "lean_theorems_indexed": len(lean_theorems),
        "finding_count": len(findings),
        "budget_ms": budget_ms,
        "within_budget": within_budget,
        "elapsed_ms": int(elapsed_ms),
        "checks_applicability": checks_applicability,
        "findings": findings,
    }


def build_parser() -> Any:
    parser = make_strict_parser("preflight", "Track S168 2-second shift-left pre-audit gate")
    parser.add_argument("track_dir", type=Path, help="Track directory to preflight (strictly read-only)")
    parser.add_argument("--budget-ms", type=int, default=DEFAULT_BUDGET_MS, help="Latency budget in ms (default: 2000)")
    parser.add_argument("--include-timing", action="store_true", help="Include non-deterministic wall-clock elapsed_ms")
    parser.add_argument("--json", action="store_true", help="Emit canonical JSON output")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    def _run(args: Any) -> dict[str, Any]:
        res = run_preflight(args.track_dir, budget_ms=args.budget_ms)
        if not res["passed"]:
            detail = json.dumps(res["findings"], sort_keys=True, separators=(",", ":"), ensure_ascii=True)
            raise TrustCoreError("PREFLIGHT_FAILED", f"{res['finding_count']} preflight findings: {detail}")
        if not args.include_timing:
            return {k: v for k, v in res.items() if k != "elapsed_ms"}
        return res

    return run_fail_closed_cli(_run, parser_builder=build_parser, argv=argv)


if __name__ == "__main__":
    raise SystemExit(main())
