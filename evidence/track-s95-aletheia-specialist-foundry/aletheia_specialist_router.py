#!/usr/bin/env python3
"""
Track S95: Local Aletheia Specialist Router with Mandatory Law-3 (`⫩`) Deterministic Gates.

Routes recurring expedition subtasks to the 3 local merged Qwen2.5-0.5B specialists
(`aletheia-scribe-0.5b`, `aletheia-weaver-0.5b`, `aletheia-prover-0.5b`) and wraps
EVERY micro-model output in deterministic fail-closed Law-3 verification gates:
  - `scribe`: strict JSON schema + type/range check + hygiene invariant audit.
  - `weaver`: strict JSON schema + bijective (pathway_class <-> canonical_glyph) + CS-03 gate.
  - `prover_audit`: strict JSON schema + R10+ 15-class escape-class allowlist check.
  - `prover_tactic`: R10+ 15-class static scanner + live `Lean 4.36.0` kernel (`lean --stdin`)
                     `rc=0`, `stderr=""`, `#print axioms` strictly in `{propext, Quot.sound}`.

Zero unverified micro-model output can pass through this router. Pure stdlib for all
Law-3 gates; PyTorch/Transformers imported lazily only when invoking local model weights.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Any

SCRIBE_KEYS = frozenset(
    {
        "track_id",
        "novelty",
        "oracle_class",
        "lean_theorems",
        "leak_flags",
        "four_mode_violation",
        "crlf_or_assert_flag",
    }
)
ALLOWED_NOVELTY = frozenset({"N0", "N1", "N2"})
ALLOWED_ORACLE_CLASSES = frozenset({"PURE_Z_Q_EXACT", "HYBRID_GPU_CERTIFIED", "EMPIRICAL_AUDIT"})

WEAVER_KEYS = frozenset(
    {
        "pathway_class",
        "canonical_glyph",
        "operator_tag",
        "is_language_smuggling",
        "suggested_mediator_class",
    }
)
PATHWAY_TO_GLYPH: dict[str, str] = {
    "EXACT_COMMUTE": "⧅",
    "CONDITIONAL_BRIDGE": "⦺",
    "EXACT_OBSTRUCTION": "⧇",
}
ALLOWED_OPERATOR_TAGS = frozenset(
    {
        "SCHUR_PUSHFORWARD",
        "BOUNDARY_WALL",
        "HOLONOMY_CURVATURE",
        "PHASE_CROSSOVER",
        "GAUGE_QUOTIENT",
        "CLASSICAL_ALGEBRAIC",
        "SMUGGLING_BLOCKED",
    }
)
ALLOWED_MEDIATORS = frozenset(
    {
        "DIRECT_IDENTITY",
        "REGIME_BOUND_MEDIATOR",
        "OBSTRUCTION_BLOWUP_MEDIATOR",
        "EXACT_OPERATOR_PROOF_REQUIRED",
    }
)

PROVER_AUDIT_KEYS = frozenset({"clean", "escape_class"})
ALLOWED_ESCAPE_CLASSES = frozenset(
    {
        "CLEAN",
        "LEAN4_SORRY",
        "LEAN4_ADMIT",
        "LEAN4_AXIOM",
        "LEAN4_UNSAFE",
        "LEAN4_NATIVE_DECIDE",
        "LEAN4_DECIDE_NATIVE",
        "LEAN4_SORRY_AX",
        "LEAN4_MK_SORRY",
        "LEAN4_OF_REDUCE_BOOL",
        "LEAN4_TRUST_COMPILER",
        "LEAN4_META_SYNTAX_ESCAPE",
        "LEAN4_NON_INIT_IMPORT",
        "LEAN4_PARTIAL",
        "LEAN4_SKIP_KERNEL_TC",
        "LEAN4_EVAL_SPOOF",
        "LEAN4_ATTR_TRUST_ESCAPE",
    }
)

ALLOWED_LEAN_AXIOMS = frozenset({"propext", "Quot.sound"})

# End-anchored R10+ 15-class static Lean 4.36.0 scanner
_R10_RULES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bsorry\b"), "LEAN4_SORRY"),
    (re.compile(r"\badmit\b"), "LEAN4_ADMIT"),
    (re.compile(r"(?<!\.)\baxiom\b"), "LEAN4_AXIOM"),
    (re.compile(r"(?<!\.)\bunsafe\b"), "LEAN4_UNSAFE"),
    (re.compile(r"\b(?:native_decide|bv_decide)\b"), "LEAN4_NATIVE_DECIDE"),
    (re.compile(r"\bsorryAx\b"), "LEAN4_SORRY_AX"),
    (re.compile(r"\b(?:Lean\.Meta\.)?mkSorry\b"), "LEAN4_MK_SORRY"),
    (re.compile(r"\b(?:Lean\.)?(?:ofReduceBool|ofReduceNat)\b"), "LEAN4_OF_REDUCE_BOOL"),
    (re.compile(r"\b(?:Lean\.)?trustCompiler\b"), "LEAN4_TRUST_COMPILER"),
    (
        re.compile(
            r"(?<!\.)\b(?:macro|macro_rules|elab|elab_rules|syntax|declare_syntax_cat|"
            r"notation|prefix|infix|infixl|infixr|postfix)(?![\w'.!?])"
            r"|\binterpolatedStr\b"
        ),
        "LEAN4_META_SYNTAX_ESCAPE",
    ),
    (
        re.compile(r"(?<!\.)\b(?:partial\s+(?:def|instance|abbrev|theorem)|opaque\s+[A-Za-z_][A-Za-z0-9_.']*)"),
        "LEAN4_PARTIAL",
    ),
    (
        re.compile(r"\bdebug\s*\.\s*(?:skipKernelTC|byAsSorry|proofAsSorry|terminalTacticsAsSorry)\b|\bset_option\b"),
        "LEAN4_SKIP_KERNEL_TC",
    ),
    (
        re.compile(
            r"#(?:eval!?(?![\w'!?])|reduce(?![\w'!?])|exit(?![\w'!?])|guard_msgs(?![\w'!?])|"
            r"print(?![\w'!?])(?!\s+axioms[ \t]+(?!example\b|def\b|theorem\b|lemma\b)[A-Za-z0-9_.]+\s*(?:\n|\Z)))|"
            r"(?<!\.)\b(?:run_cmd|run_meta|initialize|builtin_initialize|dbg_trace|dbg_sleep|dbg_stack_trace)(?![\w'.!?])|"
            r"\b(?:dbgTrace|dbgTraceVal|dbgTraceIfShared|dbgSleep|dbgStackTrace|panicCore|panicWithPosWithDecl)\b|"
            r"(?<!\.)\b(?:panic|unreachable)!(?![\w'!?])"
        ),
        "LEAN4_EVAL_SPOOF",
    ),
    (
        re.compile(
            r"(?:@\[|\battribute\s*\[)[^\]]*\b(?:extern|implemented_by|export|csimp|init|builtin_init|"
            r"term_elab|command_elab|tactic|macro|macro_rules|"
            r"builtin_term_elab|builtin_command_elab|builtin_tactic|builtin_macro|builtin_macro_rules)\b"
        ),
        "LEAN4_ATTR_TRUST_ESCAPE",
    ),
    (
        re.compile(
            r"(?<!\w)\+\s*native\b|"
            r"\bnative\s*:=(?!\s*(?:Bool\.)?false\s*(?:[),}]|\Z))|"
            r"\bDecide(?:Config|\.Config)\b|"
            r"\bdecide\s*\(\s*config\s*:=(?!\s*\{\s*native\s*:=\s*(?:Bool\.)?false\s*\}\s*\))"
        ),
        "LEAN4_DECIDE_NATIVE",
    ),
)
_R10_IMPORT_RE = re.compile(r"(?:^|\n)[ \t]*(?:(?:public|private|meta)\s+)*import\s+([A-Za-z0-9_.]+)")
_R10_GUIL_RE = re.compile(r"«([A-Za-z_][A-Za-z0-9_']*)»")
_AXIOM_LINE_RE = re.compile(
    r"^'([^']+)' (?:does not depend on any axioms|depends on axioms: \[([^\]]*)\])$"
)


class GateError(ValueError):
    """Fail-closed deterministic Law-3 (`⫩`) verification gate rejection."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


def strip_lean_comments_and_strings(source: str) -> tuple[str, list[str]]:
    """Strip Lean 4 nested block comments, line comments, and plain/raw/char literals."""
    out: list[str] = []
    errs: list[str] = []
    i = 0
    n = len(source)
    depth = 0
    in_str = False
    raw_hashes = -1
    while i < n:
        ch = source[i]
        nxt = source[i + 1] if i + 1 < n else ""
        if depth > 0:
            if ch == "/" and nxt == "-":
                depth += 1
                out.append("  ")
                i += 2
            elif ch == "-" and nxt == "/":
                depth -= 1
                out.append("  ")
                i += 2
            else:
                out.append("\n" if ch == "\n" else " ")
                i += 1
            continue
        if raw_hashes >= 0:
            close_seq = '"' + ("#" * raw_hashes)
            if source.startswith(close_seq, i):
                out.append(" " * len(close_seq))
                i += len(close_seq)
                raw_hashes = -1
            else:
                out.append("\n" if ch == "\n" else " ")
                i += 1
            continue
        if in_str:
            if ch == "\\":
                out.append(" \n" if nxt == "\n" else "  ")
                i += 2
            elif ch == '"':
                in_str = False
                out.append(" ")
                i += 1
            else:
                out.append("\n" if ch == "\n" else " ")
                i += 1
            continue
        if ch == "/" and nxt == "-":
            depth = 1
            out.append("  ")
            i += 2
            continue
        if ch == "-" and nxt == "-":
            while i < n and source[i] != "\n":
                out.append(" ")
                i += 1
            continue
        if ch == '"':
            # Catch interpolated strings `s!"{sorry}"` by NOT masking when preceded by `!`
            if i > 0 and source[i - 1] == "!":
                out.append(" ")
                i += 1
                continue
            in_str = True
            out.append(" ")
            i += 1
            continue
        if ch == "'" and (i == 0 or not (source[i - 1].isalnum() or source[i - 1] in "_'")):
            if i + 2 < n and source[i + 1] != "\\" and source[i + 1] != "\n" and source[i + 2] == "'":
                out.append("   ")
                i += 3
                continue
            if i + 3 < n and source[i + 1] == "\\" and source[i + 3] == "'":
                out.append("    ")
                i += 4
                continue
        if ch == "r" and (i == 0 or not (source[i - 1].isalnum() or source[i - 1] == "_")):
            j = i + 1
            while j < n and source[j] == "#":
                j += 1
            if j < n and source[j] == '"':
                raw_hashes = j - (i + 1)
                out.append(" " * (j - i + 1))
                i = j + 1
                continue
        out.append(ch)
        i += 1
    if depth > 0:
        errs.append("LEAN4_UNTERMINATED_COMMENT")
    elif in_str or raw_hashes >= 0:
        errs.append("LEAN4_UNTERMINATED_STRING")
    return "".join(out), errs


def audit_lean4_r10_static(source: str) -> list[str]:
    """Run 15-class R10+ static Lean 4.36.0 trust-escape audit (empty list iff clean)."""
    if type(source) is not str:
        raise GateError("INVALID_LEAN_SOURCE", "Lean source must be strict str")
    cleaned, findings = strip_lean_comments_and_strings(source)
    cleaned = _R10_GUIL_RE.sub(r"\1", cleaned)
    for pat, code in _R10_RULES:
        if pat.search(cleaned) is not None and code not in findings:
            findings.append(code)
    for m_imp in _R10_IMPORT_RE.finditer(cleaned):
        root_pkg = m_imp.group(1).split(".")[0]
        if root_pkg not in ("Init", "Std") and "LEAN4_NON_INIT_IMPORT" not in findings:
            findings.append("LEAN4_NON_INIT_IMPORT")
    return findings


def _parse_strict_json_object(raw_text: str) -> dict[str, Any]:
    if type(raw_text) is not str:
        raise GateError("NON_STRING_OUTPUT", "model output must be str")
    s = raw_text.strip()
    if not s.startswith("{"):
        raise GateError("NON_JSON_OBJECT", "output does not start with '{'")
    # Extract first balanced JSON object (blocks trailing chatter while enforcing strict JSON)
    depth = 0
    in_str = False
    esc = False
    end_idx = -1
    for idx, ch in enumerate(s):
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
        elif ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end_idx = idx
                break
    if end_idx != len(s) - 1:
        raise GateError("TRAILING_OR_UNBALANCED_JSON", "output must be a single exact JSON object")
    try:
        obj = json.loads(
            s,
            parse_float=lambda tok: (_ for _ in ()).throw(GateError("FLOAT_FORBIDDEN", tok)),
            parse_constant=lambda tok: (_ for _ in ()).throw(GateError("NONFINITE_FORBIDDEN", tok)),
        )
    except GateError:
        raise
    except ValueError as exc:
        raise GateError("INVALID_JSON", str(exc)) from exc
    if type(obj) is not dict:
        raise GateError("NON_OBJECT_JSON", "JSON root must be dict")
    return obj


def gate_scribe_output(raw_text: str) -> dict[str, Any]:
    """Deterministic Law-3 (`⫩`) schema & hygiene gate for Aletheia-Scribe-0.5B."""
    obj = _parse_strict_json_object(raw_text)
    if set(obj.keys()) != SCRIBE_KEYS:
        raise GateError("SCRIBE_SCHEMA_KEYS", f"unexpected keys: {sorted(obj.keys())}")
    if type(obj["track_id"]) is not str or not obj["track_id"]:
        raise GateError("SCRIBE_BAD_TRACK_ID", "track_id must be non-empty str")
    if obj["novelty"] not in ALLOWED_NOVELTY:
        raise GateError("SCRIBE_BAD_NOVELTY", f"invalid novelty: {obj['novelty']!r}")
    if obj["oracle_class"] not in ALLOWED_ORACLE_CLASSES:
        raise GateError("SCRIBE_BAD_ORACLE_CLASS", f"invalid oracle_class: {obj['oracle_class']!r}")
    if type(obj["lean_theorems"]) is not int or obj["lean_theorems"] < 0 or obj["lean_theorems"] > 500:
        raise GateError("SCRIBE_BAD_LEAN_COUNT", "lean_theorems must be bounded non-negative int")
    for bk in ("leak_flags", "four_mode_violation", "crlf_or_assert_flag"):
        if type(obj[bk]) is not bool:
            raise GateError("SCRIBE_BAD_BOOL_FLAG", f"{bk} must be strict bool")
    return obj


def gate_weaver_output(raw_text: str) -> dict[str, Any]:
    """Deterministic Law-3 (`⫩`) mesh-algebra & CS-03 gate for Aletheia-Weaver-0.5B."""
    obj = _parse_strict_json_object(raw_text)
    if set(obj.keys()) != WEAVER_KEYS:
        raise GateError("WEAVER_SCHEMA_KEYS", f"unexpected keys: {sorted(obj.keys())}")
    pcls = obj["pathway_class"]
    if pcls not in PATHWAY_TO_GLYPH:
        raise GateError("WEAVER_BAD_PATHWAY", f"invalid pathway_class: {pcls!r}")
    if obj["canonical_glyph"] != PATHWAY_TO_GLYPH[pcls]:
        raise GateError("WEAVER_GLYPH_MISMATCH", f"glyph {obj['canonical_glyph']!r} != {PATHWAY_TO_GLYPH[pcls]!r}")
    if obj["operator_tag"] not in ALLOWED_OPERATOR_TAGS:
        raise GateError("WEAVER_BAD_OPERATOR_TAG", f"invalid operator_tag: {obj['operator_tag']!r}")
    if type(obj["is_language_smuggling"]) is not bool:
        raise GateError("WEAVER_BAD_SMUGGLING_FLAG", "is_language_smuggling must be strict bool")
    if obj["suggested_mediator_class"] not in ALLOWED_MEDIATORS:
        raise GateError("WEAVER_BAD_MEDIATOR", f"invalid mediator: {obj['suggested_mediator_class']!r}")
    # Law-5 CS-03 invariant: language smuggling MUST be blocked as EXACT_OBSTRUCTION (`⧇`)
    if obj["is_language_smuggling"] and pcls != "EXACT_OBSTRUCTION":
        raise GateError("WEAVER_CS03_INVARIANT", "language smuggling must map to EXACT_OBSTRUCTION")
    return obj


def gate_prover_audit_output(raw_text: str) -> dict[str, Any]:
    """Deterministic Law-3 (`⫩`) schema gate for Aletheia-Prover-0.5B R10+ escape classification."""
    obj = _parse_strict_json_object(raw_text)
    if set(obj.keys()) != PROVER_AUDIT_KEYS:
        raise GateError("PROVER_AUDIT_KEYS", f"unexpected keys: {sorted(obj.keys())}")
    if type(obj["clean"]) is not bool:
        raise GateError("PROVER_AUDIT_BAD_CLEAN", "clean must be strict bool")
    ecls = obj["escape_class"]
    if ecls not in ALLOWED_ESCAPE_CLASSES:
        raise GateError("PROVER_AUDIT_BAD_CLASS", f"invalid escape_class: {ecls!r}")
    if obj["clean"] and ecls != "CLEAN":
        raise GateError("PROVER_AUDIT_CONTRADICTION", "clean=true requires escape_class='CLEAN'")
    if (not obj["clean"]) and ecls == "CLEAN":
        raise GateError("PROVER_AUDIT_CONTRADICTION", "clean=false cannot have escape_class='CLEAN'")
    return obj


def find_lean_binary() -> str | None:
    found = shutil.which("lean")
    if found is not None:
        return found
    home_env = os.environ.get("HOME")
    if home_env:
        cand = Path(home_env) / ".elan" / "bin" / "lean"
        if cand.is_file():
            return str(cand)
    return None


def _scrubbed_lean_env() -> dict[str, str]:
    env: dict[str, str] = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
    }
    home_val = os.environ.get("HOME")
    if home_val:
        env["HOME"] = home_val
    return env


def gate_prover_tactic_output(
    preamble: str,
    theorem_header: str,
    full_theorem_name: str,
    generated_proof: str,
    *,
    lean_bin: str | None = None,
    timeout_s: int = 30,
) -> dict[str, Any]:
    """
    Deterministic Law-3 (`⫩`) static R12 + LIVE `Lean 4.36.0` kernel gate (`lean --stdin`).
    Refuses ANY proof with static R12 findings, compiler errors/warnings, or forbidden axioms.
    """
    proof = generated_proof.strip()
    if not proof:
        raise GateError("PROVER_EMPTY_PROOF", "empty generated proof")
    static_findings = audit_lean4_r10_static(proof)
    if static_findings:
        raise GateError("PROVER_R10_STATIC_REJECT", f"R10+ static findings: {static_findings}")
    # Auto-close any open namespace before `#print axioms <full_theorem_name>`
    open_ns = re.findall(r"(?m)^namespace\s+([A-Za-z0-9_.]+)", preamble)
    closed_ns = re.findall(r"(?m)^end\s+([A-Za-z0-9_.]+)", preamble)
    unclosed = open_ns[len(closed_ns) :]
    close_block = "".join(f"\nend {ns}" for ns in reversed(unclosed))
    full_src = f"{preamble}\n{theorem_header} {proof}{close_block}\n#print axioms {full_theorem_name}\n"
    full_findings = audit_lean4_r10_static(full_src)
    if full_findings:
        raise GateError("PROVER_R10_FULL_REJECT", f"R10+ full source findings: {full_findings}")
    lbin = lean_bin or find_lean_binary()
    if lbin is None:
        raise GateError("LEAN_BINARY_UNAVAILABLE", "lean binary not found on PATH or $HOME/.elan/bin")
    try:
        proc = subprocess.run(
            [lbin, "--stdin"],
            input=full_src,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
            env=_scrubbed_lean_env(),
        )
    except subprocess.TimeoutExpired as exc:
        raise GateError("PROVER_LEAN_TIMEOUT", f"lean timed out after {timeout_s}s") from exc
    if proc.returncode != 0:
        raise GateError("PROVER_LEAN_KERNEL_REJECT", proc.stdout.strip()[:200] or proc.stderr.strip()[:200])
    if proc.stderr.strip() != "":
        raise GateError("PROVER_LEAN_STDERR_NONEMPTY", proc.stderr.strip()[:200])
    axioms: list[str] = []
    matched = False
    for line in proc.stdout.splitlines():
        s = line.strip()
        m = _AXIOM_LINE_RE.match(s)
        if m is not None and m.group(1) == full_theorem_name:
            matched = True
            ax_raw = m.group(2)
            axioms = [] if ax_raw is None else [a.strip() for a in ax_raw.split(",") if a.strip()]
            for ax in axioms:
                if ax not in ALLOWED_LEAN_AXIOMS:
                    raise GateError("PROVER_FORBIDDEN_AXIOM", f"forbidden axiom: {ax}")
    if not matched:
        raise GateError("PROVER_AXIOM_LINE_MISSING", f"missing #print axioms output for {full_theorem_name}")
    return {"kernel_verified": True, "theorem": full_theorem_name, "axioms": axioms, "proof": proof}


def _generate_with_local_specialist(model_dir: Path, prompt: str, max_new_tokens: int = 160) -> str:
    import torch  # noqa: PLC0415
    from transformers import AutoModelForCausalLM, AutoTokenizer  # noqa: PLC0415

    tok = AutoTokenizer.from_pretrained(str(model_dir), local_files_only=True)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    dtype = torch.bfloat16 if device == "cuda" else torch.float32
    model = AutoModelForCausalLM.from_pretrained(str(model_dir), local_files_only=True, dtype=dtype).to(device)
    model.eval()
    enc = tok(prompt, return_tensors="pt").to(device)
    with torch.no_grad():
        out_ids = model.generate(
            **enc,
            max_new_tokens=max_new_tokens,
            do_sample=False,
            pad_token_id=tok.eos_token_id,
            eos_token_id=tok.eos_token_id,
        )
    gen = out_ids[0, enc["input_ids"].shape[1] :]
    return tok.decode(gen, skip_special_tokens=True).strip()


def route_and_gate(
    task: str,
    payload: dict[str, Any],
    *,
    model_dir: Path | None = None,
    dry_run_response: str | None = None,
    lean_bin: str | None = None,
) -> dict[str, Any]:
    """Route a task to local specialist + enforce fail-closed Law-3 (`⫩`) gate."""
    if task not in ("scribe", "weaver", "prover_audit", "prover_tactic"):
        raise GateError("UNKNOWN_TASK", f"unsupported task: {task!r}")
    if dry_run_response is not None:
        raw_out = dry_run_response
    else:
        if model_dir is None or not model_dir.is_dir():
            raise GateError("MISSING_MODEL_DIR", "valid --model-dir required when --dry-run-response is unset")
        prompt = payload.get("prompt")
        if type(prompt) is not str or not prompt:
            raise GateError("MISSING_PROMPT", "payload must contain non-empty 'prompt'")
        raw_out = _generate_with_local_specialist(model_dir, prompt)

    if task == "scribe":
        verified = gate_scribe_output(raw_out)
    elif task == "weaver":
        verified = gate_weaver_output(raw_out)
    elif task == "prover_audit":
        verified = gate_prover_audit_output(raw_out)
    else:
        verified = gate_prover_tactic_output(
            str(payload.get("preamble", "")),
            str(payload.get("theorem_header", "")),
            str(payload.get("full_theorem_name", "")),
            raw_out,
            lean_bin=lean_bin,
        )
    return {"gate_status": "VERIFIED", "task": task, "output": verified}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Track S95 Law-3 Oracle-Gated Local Specialist Router")
    ap.add_argument("--task", required=False, choices=["scribe", "weaver", "prover_audit", "prover_tactic"])
    ap.add_argument("--model-dir", type=Path, default=None)
    ap.add_argument("--input-json", type=str, default="{}", help="JSON object payload string")
    ap.add_argument("--dry-run-response", type=str, default=None, help="Bypass GPU inference and test Law-3 gate")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    try:
        if args.task is None:
            sc_ok = gate_scribe_output(
                '{"crlf_or_assert_flag":false,"four_mode_violation":false,"leak_flags":false,'
                '"lean_theorems":16,"novelty":"N1","oracle_class":"HYBRID_GPU_CERTIFIED","track_id":"TRACK_S95"}'
            )
            wv_ok = gate_weaver_output(
                '{"canonical_glyph":"⧇","is_language_smuggling":true,"operator_tag":"SMUGGLING_BLOCKED",'
                '"pathway_class":"EXACT_OBSTRUCTION","suggested_mediator_class":"EXACT_OPERATOR_PROOF_REQUIRED"}'
            )
            pa_ok = gate_prover_audit_output('{"clean":true,"escape_class":"CLEAN"}')
            print(
                json.dumps(
                    {
                        "gate_status": "VERIFIED",
                        "self_check": "PASS",
                        "gates": ["scribe", "weaver", "prover_audit"],
                        "checked": {"scribe": sc_ok["track_id"], "weaver": wv_ok["pathway_class"], "prover_audit": pa_ok["escape_class"]},
                    },
                    sort_keys=True,
                    ensure_ascii=False,
                )
            )
            return 0
        payload = json.loads(args.input_json)
        if type(payload) is not dict:
            raise GateError("INVALID_INPUT_PAYLOAD", "--input-json must decode to JSON object")
        res = route_and_gate(
            args.task,
            payload,
            model_dir=args.model_dir,
            dry_run_response=args.dry_run_response,
        )
        print(json.dumps(res, sort_keys=True, ensure_ascii=False))
        return 0
    except (GateError, ValueError) as exc:
        err = {"gate_status": "REJECTED", "error": str(exc)}
        print(json.dumps(err, sort_keys=True, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
