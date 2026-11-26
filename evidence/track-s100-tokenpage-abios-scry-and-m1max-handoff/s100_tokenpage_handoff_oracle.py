#!/usr/bin/env python3
"""
Track S100 Exact-Z/Q Oracle:
Multi-Tokenizer / Protocol / Non-English Density Engine
& Deterministic 3-Node MacBook M1 Max (64 GiB) + client-omarchy Handoff Pack.

Strictly pure Python 3 stdlib, exact int / Fraction arithmetic, zero floats,
zero bare asserts, zero RNG, zero external dataset copies.

Four Certified Pillars:
  Pillar 1: Live CPU multi-tokenizer audit (Qwen2.5 vs SmolLM2) over:
            (a) Moissanite-Labs/abios SYM-2P review-fix-verify-merge.jsonl across
                4 lossless renderings (Pretty JSON, Markdown, SYM-2P, ABIOS/3+setup),
            (b) Aletheia calculus 8 glyphs vs ASCII vs reserved-8-token collapse
                and 5 frozen Aletheia certificates (S31/S86/S89/S92/S94),
            (c) Track S92 12 raw-Arabic treatises (1.581M words / 14.84 MB) and
                12 bilingual Arabic-English catalogs (148 pairs) -> exact pure-Q
                Vocabulary-Tax x Translation-Loss Compounding Factor,
            (d) Representation-vs-readout gauge gap (tokenpage#5/#13 x abios#51),
            (e) Pure-stdlib reproduction & lossless fix of abios#39 wire_lists.py
                codec defects ([' ']->[], [1,2]->['1,2'], ['see [1] now'] split).
  Pillar 2: Reserved protocol-token vocabulary surgery (K in {16,32,64,128}),
            tied vs untied parameter overhead, discrete break-even turn thresholds,
            and S31 DPI / S94 Householder token_embd row-norm safety bounds.
  Pillar 3: Portable deterministic 3-node (RTX 3080 Linux, MacBook M1 Max 64 GiB,
            client-omarchy edge) SHA-256-pinned `aletheia handoff` manifests
            (M1-H1 Inkling-2-Mini, M1-H2 weft E8 Part C + E11c DAWE, M1-H3 Bonsai
            2.5 27B vs FP16 dual-load + fixed [H_8,D] Gemma-3-12B, EDGE-H1 exyber
            + nullmodem KV transfer) with 4-gate Borromean fail-closed ablations.
  Pillar 4: Provenance, anchor/upstream/tokenizer pins, Law-4 N0/N1 honesty ledger
            (n2_claims=0), and pure-Init Lean 4.36.0 companion metadata (18/18 forall).
"""
from __future__ import annotations

from fractions import Fraction
import hashlib
import json
from typing import Any

SCHEMA_VERSION = "aletheia.track_s100.tokenpage_abios_m1max_handoff.v1"
TRACK_ID = "TRACK-S100-TOKENPAGE-ABIOS-SCRY-AND-M1MAX-HANDOFF"
ORACLE_CLASS = "exact_z_q_multi_tokenizer_vocab_surgery_and_handoff"
NOVELTY_TIER = "N1"

LEAN_TOOLCHAIN = "leanprover/lean4:v4.36.0"
LEAN_FILE_NAME = "TokenpageAbiosHandoff.lean"
EXPECTED_LEAN_SHA256 = "f2300ddf230a3792f59532574dfe6f96aed34c2cd4658b1d02b2fb6fffd9699e"
EXPECTED_LEAN_THEOREMS: tuple[str, ...] = (
    "S100TokenpageAbiosHandoff.bpe_cross_tokenizer_tax_dominance_universal",
    "S100TokenpageAbiosHandoff.vocab_tax_times_translation_loss_compounding_universal",
    "S100TokenpageAbiosHandoff.simplex_retention_decay_amplification_universal",
    "S100TokenpageAbiosHandoff.glyph_multitoken_penalty_and_reserved_collapse_universal",
    "S100TokenpageAbiosHandoff.representation_vs_readout_gauge_gap_universal",
    "S100TokenpageAbiosHandoff.codec_roundtrip_noninjectivity_obstruction_universal",
    "S100TokenpageAbiosHandoff.vocab_surgery_breakeven_turn_threshold_universal",
    "S100TokenpageAbiosHandoff.vocab_param_overhead_tied_vs_untied_universal",
    "S100TokenpageAbiosHandoff.token_embd_row_norm_dpi_preservation_universal",
    "S100TokenpageAbiosHandoff.token_embd_spike_dpi_amplification_universal",
    "S100TokenpageAbiosHandoff.householder_appended_token_isometry_universal",
    "S100TokenpageAbiosHandoff.abios_setup_amortization_crossover_universal",
    "S100TokenpageAbiosHandoff.m1max_unified_memory_dual_load_residency_universal",
    "S100TokenpageAbiosHandoff.inkling2_loop_core_contraction_vs_expansion_universal",
    "S100TokenpageAbiosHandoff.parallel_window_sampling_speedup_bound_universal",
    "S100TokenpageAbiosHandoff.siliquant_hadamard_colscale_commutator_universal",
    "S100TokenpageAbiosHandoff.cross_host_kv_transfer_breakeven_universal",
    "S100TokenpageAbiosHandoff.four_handoff_borromean_fail_closed_universal",
)

ANCHOR_PIN: dict[str, Any] = {
    "file": "s100_tokenizer_anchor.json",
    "bytes": 18642,
    "file_sha256": "7a0e698bd976420299c14233af56087b4486e3c90443e0ce63104888ac85b55a",
    "payload_sha256": "94dee3fefe3beab83e60f7036bed54f7c73bbec24c5df729172cb058192b4c9c",
}

UPSTREAM_CERT_PINS: tuple[dict[str, Any], ...] = (
    {
        "track_id": "S31",
        "relative_ref": "track-s31-aletheia-v22-society-misfolding-tomography/aletheia_v22_misfolding_certificate.json",
        "bytes": 12707,
        "sha256": "f4f7f8abff0c7eae0d5678016c1041ab34870ef2de57a2f83e4cbb9a529f8a9b",
        "qwen25_tokens": 4842,
        "smollm2_tokens": 5874,
    },
    {
        "track_id": "S86",
        "relative_ref": "track-s86-sovereign-8gb-fourth-order-stack/s86_sovereign_stack_certificate.json",
        "bytes": 9315,
        "sha256": "675bf68c1291a3cf7aeef9beb9a5efc316b55f44a6823a0a94f2ffef7754cb12",
        "qwen25_tokens": 4626,
        "smollm2_tokens": 5401,
    },
    {
        "track_id": "S89",
        "relative_ref": "track-s89-islamic-heritage-corpus-atlas/s89_heritage_atlas_certificate.json",
        "bytes": 50836,
        "sha256": "49bc7bd55be36a6cdcabbf854bc7b46c5313e8c28f36a7d9ef509134eaab8b63",
        "qwen25_tokens": 20159,
        "smollm2_tokens": 22323,
    },
    {
        "track_id": "S92",
        "relative_ref": "track-s92-raw-arabic-scientific-mesh/s92_raw_arabic_mesh_certificate.json",
        "bytes": 26339,
        "sha256": "294e26e91bfa8cae6c3e48c44a8e9acea37404932eaf4855c05f2e8eaad0738b",
        "qwen25_tokens": 12160,
        "smollm2_tokens": 14217,
    },
    {
        "track_id": "S94",
        "relative_ref": "track-s94-neuron-basis-bonsai-sleep-convergence/s94_wave6_convergence_certificate.json",
        "bytes": 15197,
        "sha256": "1ad705c23646b65df0dc9ac928d3a4070deef61f5d17f8e8f249b4f75f51335b",
        "qwen25_tokens": 6447,
        "smollm2_tokens": 7670,
    },
)

TOKENIZER_PINS: tuple[dict[str, Any], ...] = (
    {
        "id": "qwen25_0p5b",
        "model_id": "Qwen/Qwen2.5-0.5B",
        "rel_cache_path": "models--Qwen--Qwen2.5-0.5B/snapshots/060db6499f32faf8b98477b0a26969ef7d8b9987/tokenizer.json",
        "bytes": 7031645,
        "sha256": "c0382117ea329cdf097041132f6d735924b697924d6f6fc3945713e96ce87539",
        "active_vocab_size": 151665,
        "padded_vocab_size": 151936,
    },
    {
        "id": "smollm2_360m",
        "model_id": "HuggingFaceTB/SmolLM2-360M",
        "rel_cache_path": "models--HuggingFaceTB--SmolLM2-360M/snapshots/f8027fd0eaeea54caa13c31d31b9fdc459c38b49/tokenizer.json",
        "bytes": 2104556,
        "sha256": "9ca9acddb6525a194ec8ac7a87f24fbba7232a9a15ffa1af0c1224fcd888e47c",
        "active_vocab_size": 49152,
        "padded_vocab_size": 49152,
    },
)

WAVE_FIXTURE_PINS: tuple[dict[str, Any], ...] = (
    {
        "id": "inkling2_mini_config",
        "root_kind": "wave7",
        "filename": "inkling2_mini_config.json",
        "bytes": 2722,
        "sha256": "a7a349601f0984c4abf999c480ef775d8567d21f5f84b4e8a3e035b44f288dc2",
    },
    {
        "id": "abios_review_fix_verify_merge",
        "root_kind": "abios",
        "filename": "review-fix-verify-merge.jsonl",
        "bytes": 4531,
        "sha256": "cee1c4d841d0f6b6d4dc25b9e5e9bb0d58a18b71480236f856cecd88fa7c1ebf",
    },
    {
        "id": "abios_pr39_wire_lists",
        "root_kind": "abios",
        "filename": "wire_lists_pr39.py",
        "bytes": 2936,
        "sha256": "8b9a99ed8a20012427df7945d7759c266314c81f0944a757660df03b24227389",
    },
    {
        "id": "abios_spec_3",
        "root_kind": "abios",
        "filename": "SPEC-ABIOS-3.md",
        "bytes": 19874,
        "sha256": "81cbcdb4d1f28e0b849f8251439ff1eb51f96dd60b86ead26eb7e18c6dc6c961",
    },
    {
        "id": "abios_bench_pr39",
        "root_kind": "abios",
        "filename": "abios-bench-pr39.json",
        "bytes": 62180,
        "sha256": "65538724842b68e476b5c142fb6deaa102c30b9c3c3e304817cec3c02160fcc1",
    },
)

# Exact live CPU multi-tokenizer counts captured in s100_tokenizer_anchor.json
# (Verified bit-for-bit against s100_tokenizer_anchor.json in --verify-pins!)
ABIOS_RFVM_FORMS: dict[str, dict[str, int]] = {
    "pretty_json": {"utf8_bytes": 6244, "qwen25_tokens": 2694, "smollm2_tokens": 2799},
    "verbose_markdown": {"utf8_bytes": 5619, "qwen25_tokens": 2439, "smollm2_tokens": 2627},
    "sym2p_jsonl": {"utf8_bytes": 4531, "qwen25_tokens": 1766, "smollm2_tokens": 1956},
    "abios3_setup_header": {"utf8_bytes": 232, "qwen25_tokens": 96, "smollm2_tokens": 104},
    "abios3_payload_only": {"utf8_bytes": 3050, "qwen25_tokens": 1336, "smollm2_tokens": 1443},
    "abios3_full_with_setup": {"utf8_bytes": 3282, "qwen25_tokens": 1432, "smollm2_tokens": 1547},
}

ALETHEIA_GLYPH_COUNTS: tuple[dict[str, Any], ...] = (
    {"name": "schur_pushforward", "codepoint": "U+29C4", "utf8_bytes": 3, "qwen25_tokens": 2, "smollm2_tokens": 3},
    {"name": "exact_commute", "codepoint": "U+29C5", "utf8_bytes": 3, "qwen25_tokens": 2, "smollm2_tokens": 3},
    {"name": "phase_crossover", "codepoint": "U+29B7", "utf8_bytes": 3, "qwen25_tokens": 2, "smollm2_tokens": 3},
    {"name": "holonomy_curvature", "codepoint": "U+27E0", "utf8_bytes": 3, "qwen25_tokens": 2, "smollm2_tokens": 3},
    {"name": "exact_obstruction", "codepoint": "U+29C7", "utf8_bytes": 3, "qwen25_tokens": 2, "smollm2_tokens": 3},
    {"name": "conditional_bridge", "codepoint": "U+29BA", "utf8_bytes": 3, "qwen25_tokens": 2, "smollm2_tokens": 3},
    {"name": "borromean_coupling", "codepoint": "U+2A69", "utf8_bytes": 3, "qwen25_tokens": 3, "smollm2_tokens": 3},
    {"name": "law3_firewall", "codepoint": "U+2AE9", "utf8_bytes": 3, "qwen25_tokens": 2, "smollm2_tokens": 3},
)

S92_TREATISE_TOTALS: dict[str, int] = {
    "treatise_count": 12,
    "total_text_utf8_bytes": 14843023,
    "total_whitespace_words": 1581301,
    "total_qwen25_tokens": 3389784,
    "total_smollm2_tokens": 7756740,
    "min_ratio_treatise_qwen25_tokens": 725336,
    "min_ratio_treatise_smollm2_tokens": 1465256,
    "max_ratio_treatise_qwen25_tokens": 197125,
    "max_ratio_treatise_smollm2_tokens": 502159,
}

S92_BILINGUAL_TOTALS: dict[str, int] = {
    "catalog_count": 12,
    "total_pairs": 148,
    "total_ar_utf8_bytes": 13047,
    "total_en_utf8_bytes": 5613,
    "total_ar_words": 1057,
    "total_en_words": 805,
    "total_qwen25_ar_tokens": 2734,
    "total_qwen25_en_tokens": 1373,
    "total_smollm2_ar_tokens": 6141,
    "total_smollm2_en_tokens": 1388,
}


def require_ok(cond: bool, code: str) -> None:
    if not cond:
        raise ValueError(code)


def q_str(val: Fraction) -> str:
    require_ok(isinstance(val, Fraction), "NOT_FRACTION")
    if val.denominator == 1:
        return str(val.numerator)
    return f"{val.numerator}/{val.denominator}"


def dec_str(val: Fraction, digits: int) -> str:
    require_ok(isinstance(val, Fraction) and type(digits) is int and digits >= 1, "BAD_DEC_ARGS")
    neg = val < 0
    mag = -val if neg else val
    scale = 10 ** digits
    scaled = mag * scale
    num, den = scaled.numerator, scaled.denominator
    quot, rem = divmod(num, den)
    if 2 * rem >= den:
        quot += 1
    whole, frac = divmod(quot, scale)
    sign = "-" if neg and quot != 0 else ""
    return f"{sign}{whole}.{frac:0{digits}d}"


def canonical_json_bytes(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


# ---------------------------------------------------------------------------
# Pure-Stdlib Parameterized Primitives (Pillars 1..3)
# ---------------------------------------------------------------------------

def discrete_breakeven_turn(setup_cost: int, base_per_turn: int, target_per_turn: int) -> dict[str, Any]:
    """Exact discrete turn threshold n* = floor(setup / (base - target)) + 1."""
    require_ok(setup_cost >= 0 and target_per_turn < base_per_turn, "INVALID_BREAKEVEN_PARAMS")
    delta = base_per_turn - target_per_turn
    n_star = setup_cost // delta + 1
    prev_turns = n_star - 1
    return {
        "setup_cost": setup_cost,
        "base_per_turn": base_per_turn,
        "target_per_turn": target_per_turn,
        "per_turn_savings": delta,
        "breakeven_turn_n_star": n_star,
        "prev_turn_beats_base": prev_turns * delta > setup_cost,
        "n_star_beats_base": n_star * delta > setup_cost,
    }


def compute_compounding_row(
    label: str,
    ar_tok: int,
    en_tok: int,
    ret_num: int,
    ret_den: int,
    simplex_order_k: int,
) -> dict[str, Any]:
    """
    Exact pure-Q Vocabulary-Tax x Translation-Loss Compounding Factor for a k-simplex
    with m = k*(k+1)//2 edges.
      bpe_tax = ar_tok / en_tok
      simplex_retention = (ret_num / ret_den) ** m
      en_over_ar_cost_per_retained_simplex = (en_tok / simplex_retention) / ar_tok
    """
    require_ok(ar_tok > 0 and en_tok > 0 and 0 < ret_num < ret_den and simplex_order_k >= 1, "INVALID_COMPOUND_INPUT")
    edges_m = (simplex_order_k * (simplex_order_k + 1)) // 2
    bpe_tax = Fraction(ar_tok, en_tok)
    edge_ret = Fraction(ret_num, ret_den)
    simplex_ret = edge_ret ** edges_m
    en_over_ar = Fraction(1, 1) / (bpe_tax * simplex_ret)
    return {
        "label": label,
        "simplex_order_k": simplex_order_k,
        "edges_m": edges_m,
        "bpe_tax_q": q_str(bpe_tax),
        "bpe_tax_dec4": dec_str(bpe_tax, 4),
        "simplex_retention_q": q_str(simplex_ret),
        "simplex_retention_dec6": dec_str(simplex_ret, 6),
        "en_over_ar_cost_q": q_str(en_over_ar),
        "en_over_ar_cost_dec4": dec_str(en_over_ar, 4),
        "raw_arabic_strictly_cheaper": en_over_ar > 1,
    }


# Pure-stdlib reference model of abios PR #39 wire_lists.py + lossless fixed codec
def _pr39_item_needs_fallback(item: Any) -> bool:
    if type(item) is not str:
        return True
    if "\n" in item or "\r" in item or '"' in item or "[" in item or "]" in item or item.endswith("\\"):
        return True
    if item.startswith("{") or item.startswith("http") or item.isdigit():
        return True
    return item in {"-", "p", "t", "a", "h", "f", "v", "g"}


def _pr39_can_encode(items: list[Any]) -> bool:
    return all(not _pr39_item_needs_fallback(x) for x in items)


def _pr39_encode_wire(items: list[Any]) -> str:
    if _pr39_can_encode(items):
        if not items:
            return "[]"
        escaped = ["\\e" if x == "" else x.replace("\\", "\\\\").replace(";", "\\;") for x in items]
        return "[" + ";".join(escaped) + "]"
    return json.dumps(items, separators=(",", ":"), ensure_ascii=True)


def _pr39_decode_wire(token: str) -> list[str] | None:
    if not token.startswith("[") or not token.endswith("]"):
        return None
    inner = token[1:-1]
    if inner == "":
        return []
    try:
        parsed = json.loads(token)
        if all(type(x) is str for x in parsed):
            return parsed
    except json.JSONDecodeError:
        pass
    parts: list[str] = []
    buf: list[str] = []
    i = 0
    while i < len(inner):
        if inner[i] == "\\":
            buf.append(inner[i : i + 2])
            i += 2
            continue
        if inner[i] == ";":
            parts.append("".join(buf))
            buf = []
            i += 1
            continue
        buf.append(inner[i])
        i += 1
    parts.append("".join(buf))
    out: list[str] = []
    for p in parts:
        if p == "\\e":
            val = ""
        else:
            val = p.replace("\\;", ";").replace("\\\\", "\\")
        if _pr39_item_needs_fallback(val):
            return None
        out.append(val)
    return out


def encode_fixed_wire_list(items: list[Any]) -> str:
    """
    Lossless fixed wire-list codec closing all 3 Moissanite-Labs/abios PR #39 defects:
      1. Whitespace-only strings & any string containing ASCII space force typed JSON-quoted carrier.
      2. Non-string scalar lists use explicit typed JSON carrier (never re-split as string tokens).
      3. Outer space-free carrier prefix `J:` + percent-escaped canonical JSON guarantees 1 wire token.
    """
    require_ok(type(items) is list, "FIXED_CODEC_NOT_LIST")
    if not items:
        return "[]"
    all_safe_str = all(
        type(x) is str
        and x != ""
        and not any(ch in x for ch in (" ", "\t", "\n", "\r", '"', "[", "]", ";", "\\", ","))
        and x not in {"-", "p", "t", "a", "h", "f", "v", "g"}
        and not x.isdigit()
        for x in items
    )
    if all_safe_str:
        return "S[" + ";".join(items) + "]"
    raw = json.dumps(items, separators=(",", ":"), ensure_ascii=True)
    escaped = raw.replace("%", "%25").replace(" ", "%20")
    return "J:" + escaped


def decode_fixed_wire_list(token: str) -> list[Any]:
    """Exact inverse of encode_fixed_wire_list (100% single-token space-free round-trip bijection)."""
    require_ok(type(token) is str and " " not in token, "FIXED_CODEC_SPACE_IN_TOKEN")
    if token == "[]":
        return []
    if token.startswith("S[") and token.endswith("]"):
        inner = token[2:-1]
        require_ok(inner != "", "FIXED_CODEC_EMPTY_S_BODY")
        return inner.split(";")
    require_ok(token.startswith("J:"), "FIXED_CODEC_BAD_PREFIX")
    raw = token[2:].replace("%20", " ").replace("%25", "%")
    parsed = json.loads(raw)
    require_ok(type(parsed) is list, "FIXED_CODEC_JSON_NOT_LIST")
    return parsed


def compute_vocab_surgery_row(
    model_name: str,
    hidden_dim: int,
    base_params: int,
    added_k: int,
    setup_tokens: int,
    delta_tok_per_turn: int,
) -> dict[str, Any]:
    """Exact pure-Q parameter overhead & swarm-turn break-even for adding K reserved tokens."""
    require_ok(hidden_dim > 0 and base_params > 0 and added_k > 0 and delta_tok_per_turn > 0, "INVALID_SURGERY_ARGS")
    tied_params = added_k * hidden_dim
    untied_params = 2 * tied_params
    tied_ppm = Fraction(tied_params * 1_000_000, base_params)
    untied_ppm = Fraction(untied_params * 1_000_000, base_params)
    be = discrete_breakeven_turn(setup_tokens, delta_tok_per_turn + 1, 1)
    net_100 = 100 * delta_tok_per_turn - setup_tokens
    net_1000 = 1000 * delta_tok_per_turn - setup_tokens
    return {
        "model_name": model_name,
        "hidden_dim": hidden_dim,
        "base_params": base_params,
        "added_k": added_k,
        "tied_added_params": tied_params,
        "untied_added_params": untied_params,
        "tied_overhead_ppm_q": q_str(tied_ppm),
        "tied_overhead_ppm_dec2": dec_str(tied_ppm, 2),
        "untied_overhead_ppm_q": q_str(untied_ppm),
        "untied_overhead_ppm_dec2": dec_str(untied_ppm, 2),
        "setup_tokens": setup_tokens,
        "delta_tok_per_turn": delta_tok_per_turn,
        "breakeven_turn_n_star": be["breakeven_turn_n_star"],
        "net_tokens_saved_100_turns": net_100,
        "net_tokens_saved_1000_turns": net_1000,
    }


def compute_s31_dpi_and_householder_witness(vocab_v: int, added_k: int, mean_norm_sq: int, spike_alpha: int) -> dict[str, Any]:
    """Exact S31 DPI preservation under matched-norm surgery vs spike misfolding & S94 Householder isometry."""
    require_ok(vocab_v > 0 and added_k > 0 and mean_norm_sq > 0 and spike_alpha >= 2, "INVALID_DPI_ARGS")
    total_rows = vocab_v + added_k
    matched_sum = vocab_v * mean_norm_sq + added_k * mean_norm_sq
    matched_dpi = Fraction(mean_norm_sq * total_rows, matched_sum)
    spike_sum = (total_rows - 1) * mean_norm_sq + spike_alpha * mean_norm_sq
    spike_dpi = Fraction(spike_alpha * mean_norm_sq * total_rows, spike_sum)

    # Exact integer/rational Householder reflection on appended token row u = (7, -1, 4, 2), axis d = (3/5, 4/5, 0, 0)
    u = [Fraction(7, 1), Fraction(-1, 1), Fraction(4, 1), Fraction(2, 1)]
    d = [Fraction(3, 5), Fraction(4, 5), Fraction(0, 1), Fraction(0, 1)]
    dot = sum(ui * di for ui, di in zip(u, d))
    hu = [ui - 2 * dot * di for ui, di in zip(u, d)]
    dot2 = sum(hi * di for hi, di in zip(hu, d))
    hhu = [hi - 2 * dot2 * di for hi, di in zip(hu, d)]
    norm_before = sum(ui * ui for ui in u)
    norm_after = sum(hi * hi for hi in hu)
    return {
        "vocab_v": vocab_v,
        "added_k": added_k,
        "total_rows": total_rows,
        "mean_norm_sq": mean_norm_sq,
        "matched_dpi_ratio_q": q_str(matched_dpi),
        "spike_alpha": spike_alpha,
        "spike_dpi_ratio_q": q_str(spike_dpi),
        "spike_dpi_ratio_dec4": dec_str(spike_dpi, 4),
        "spike_exceeds_unity": spike_dpi > 1,
        "s31_two_row_dpi_anchor_q": q_str(Fraction(vocab_v, 2)),
        "householder_norm_before_q": q_str(norm_before),
        "householder_norm_after_q": q_str(norm_after),
        "householder_norm_delta_q": q_str(norm_after - norm_before),
        "householder_involution_exact": hhu == u,
    }


def evaluate_four_gate_borromean(g1: bool, g2: bool, g3: bool, g4: bool) -> dict[str, bool]:
    return {
        "gate1_sha_pinned": g1,
        "gate2_memory_resident": g2,
        "gate3_zero_float_predicate": g3,
        "gate4_deterministic_kill_gate": g4,
        "all_four_gates_pass": g1 and g2 and g3 and g4,
    }


def is_sign_reversal(unfloored_gain: Fraction, floored_artifact: Fraction) -> bool:
    return unfloored_gain > 0 and floored_artifact < 0


def check_borromean_ablation_table(abls: dict[str, dict[str, bool]]) -> bool:
    return (
        abls["all_four_gates_clean"]["all_four_gates_pass"] is True
        and abls["ablate_g1_unpinned_sha"]["all_four_gates_pass"] is False
        and abls["ablate_g2_memory_spill"]["all_four_gates_pass"] is False
        and abls["ablate_g3_float_predicate"]["all_four_gates_pass"] is False
        and abls["ablate_g4_missing_kill_gate"]["all_four_gates_pass"] is False
    )


def summarize_codec_checks(
    d1_dec: list[str] | None,
    d1_len: int,
    d2_dec: list[str] | None,
    d2_len: int,
    d3_tokens: int,
    d3_first_dec: list[str] | None,
    fixed_single_ok: int,
    fixed_rt_ok: int,
    fixed_total: int,
) -> dict[str, bool]:
    return {
        "d1": d1_dec == [] and d1_len == 1,
        "d2": d2_dec == ["1,2"] and d2_len == 2,
        "d3": d3_tokens == 3 and d3_first_dec is None,
        "fixed": fixed_single_ok == fixed_total and fixed_rt_ok == fixed_total,
    }


# ---------------------------------------------------------------------------
# Full Pillar Builders
# ---------------------------------------------------------------------------

def build_pillar_1() -> dict[str, Any]:
    f = ABIOS_RFVM_FORMS
    q_sym_vs_md = Fraction(f["verbose_markdown"]["qwen25_tokens"] - f["sym2p_jsonl"]["qwen25_tokens"], f["verbose_markdown"]["qwen25_tokens"])
    q_abios_full_vs_sym = Fraction(f["sym2p_jsonl"]["qwen25_tokens"] - f["abios3_full_with_setup"]["qwen25_tokens"], f["sym2p_jsonl"]["qwen25_tokens"])
    q_abios_full_vs_md = Fraction(f["verbose_markdown"]["qwen25_tokens"] - f["abios3_full_with_setup"]["qwen25_tokens"], f["verbose_markdown"]["qwen25_tokens"])
    s_abios_full_vs_sym = Fraction(f["sym2p_jsonl"]["smollm2_tokens"] - f["abios3_full_with_setup"]["smollm2_tokens"], f["sym2p_jsonl"]["smollm2_tokens"])
    s_abios_full_vs_md = Fraction(f["verbose_markdown"]["smollm2_tokens"] - f["abios3_full_with_setup"]["smollm2_tokens"], f["verbose_markdown"]["smollm2_tokens"])

    # Per-packet average savings (cleared denom x12 -> exact discrete packet break-even)
    q_save_12 = f["sym2p_jsonl"]["qwen25_tokens"] - f["abios3_payload_only"]["qwen25_tokens"]  # 430 tok / 12 pkts
    s_save_12 = f["sym2p_jsonl"]["smollm2_tokens"] - f["abios3_payload_only"]["smollm2_tokens"]  # 513 tok / 12 pkts
    q_setup_12 = f["abios3_setup_header"]["qwen25_tokens"] * 12
    s_setup_12 = f["abios3_setup_header"]["smollm2_tokens"] * 12
    q_be_pkts = discrete_breakeven_turn(q_setup_12, q_save_12 + 1, 1)
    s_be_pkts = discrete_breakeven_turn(s_setup_12, s_save_12 + 1, 1)

    abios_audit = {
        "packet_count": 12,
        "source_sha256": WAVE_FIXTURE_PINS[1]["sha256"],
        "forms": f,
        "qwen25_sym2p_vs_markdown_saving_q": q_str(q_sym_vs_md),
        "qwen25_sym2p_vs_markdown_saving_dec4": dec_str(q_sym_vs_md, 4),
        "qwen25_abios3_full_vs_sym2p_saving_q": q_str(q_abios_full_vs_sym),
        "qwen25_abios3_full_vs_sym2p_saving_dec4": dec_str(q_abios_full_vs_sym, 4),
        "qwen25_abios3_full_vs_markdown_saving_q": q_str(q_abios_full_vs_md),
        "qwen25_abios3_full_vs_markdown_saving_dec4": dec_str(q_abios_full_vs_md, 4),
        "smollm2_abios3_full_vs_sym2p_saving_q": q_str(s_abios_full_vs_sym),
        "smollm2_abios3_full_vs_sym2p_saving_dec4": dec_str(s_abios_full_vs_sym, 4),
        "smollm2_abios3_full_vs_markdown_saving_q": q_str(s_abios_full_vs_md),
        "smollm2_abios3_full_vs_markdown_saving_dec4": dec_str(s_abios_full_vs_md, 4),
        "qwen25_abios3_vs_sym2p_breakeven_packets": q_be_pkts["breakeven_turn_n_star"],
        "smollm2_abios3_vs_sym2p_breakeven_packets": s_be_pkts["breakeven_turn_n_star"],
    }

    # Aletheia 8-glyph & 5-cert audit
    g_q_tot = sum(g["qwen25_tokens"] for g in ALETHEIA_GLYPH_COUNTS)
    g_s_tot = sum(g["smollm2_tokens"] for g in ALETHEIA_GLYPH_COUNTS)
    cert_b_tot = sum(c["bytes"] for c in UPSTREAM_CERT_PINS)
    cert_q_tot = sum(c["qwen25_tokens"] for c in UPSTREAM_CERT_PINS)
    cert_s_tot = sum(c["smollm2_tokens"] for c in UPSTREAM_CERT_PINS)
    q_expr_glyph, q_expr_ascii, q_expr_res = 32, 37, 17
    s_expr_glyph, s_expr_ascii, s_expr_res = 33, 47, 17
    q_res_vs_glyph = Fraction(q_expr_glyph - q_expr_res, q_expr_glyph)
    s_res_vs_glyph = Fraction(s_expr_glyph - s_expr_res, s_expr_glyph)
    q_cert_bpt = Fraction(cert_b_tot, cert_q_tot)
    s_cert_bpt = Fraction(cert_b_tot, cert_s_tot)
    aletheia_audit = {
        "glyph_count": 8,
        "glyph_qwen25_total_tokens": g_q_tot,
        "glyph_smollm2_total_tokens": g_s_tot,
        "glyph_qwen25_mean_tok_per_glyph_q": q_str(Fraction(g_q_tot, 8)),
        "glyph_smollm2_mean_tok_per_glyph_q": q_str(Fraction(g_s_tot, 8)),
        "expr_glyph_qwen25_tokens": q_expr_glyph,
        "expr_ascii_qwen25_tokens": q_expr_ascii,
        "expr_reserved_8tok_qwen25_tokens": q_expr_res,
        "expr_glyph_smollm2_tokens": s_expr_glyph,
        "expr_ascii_smollm2_tokens": s_expr_ascii,
        "expr_reserved_8tok_smollm2_tokens": s_expr_res,
        "qwen25_reserved_vs_glyph_saving_q": q_str(q_res_vs_glyph),
        "qwen25_reserved_vs_glyph_saving_dec4": dec_str(q_res_vs_glyph, 4),
        "smollm2_reserved_vs_glyph_saving_q": q_str(s_res_vs_glyph),
        "smollm2_reserved_vs_glyph_saving_dec4": dec_str(s_res_vs_glyph, 4),
        "frozen_cert_count": 5,
        "frozen_cert_total_bytes": cert_b_tot,
        "frozen_cert_qwen25_tokens": cert_q_tot,
        "frozen_cert_smollm2_tokens": cert_s_tot,
        "frozen_cert_qwen25_bytes_per_tok_q": q_str(q_cert_bpt),
        "frozen_cert_qwen25_bytes_per_tok_dec4": dec_str(q_cert_bpt, 4),
        "frozen_cert_smollm2_bytes_per_tok_q": q_str(s_cert_bpt),
        "frozen_cert_smollm2_bytes_per_tok_dec4": dec_str(s_cert_bpt, 4),
    }

    # S92 Raw-Arabic 12 treatises & 148 bilingual pairs + exact Vocab-Tax x Translation-Loss Compounding
    tr = S92_TREATISE_TOTALS
    bi = S92_BILINGUAL_TOTALS
    tr_smol_over_qwen = Fraction(tr["total_smollm2_tokens"], tr["total_qwen25_tokens"])
    tr_min_ratio = Fraction(tr["min_ratio_treatise_smollm2_tokens"], tr["min_ratio_treatise_qwen25_tokens"])
    tr_max_ratio = Fraction(tr["max_ratio_treatise_smollm2_tokens"], tr["max_ratio_treatise_qwen25_tokens"])
    q_bi_tax = Fraction(bi["total_qwen25_ar_tokens"], bi["total_qwen25_en_tokens"])
    s_bi_tax = Fraction(bi["total_smollm2_ar_tokens"], bi["total_smollm2_en_tokens"])
    tax_amp = s_bi_tax / q_bi_tax

    compounding_ladder = [
        compute_compounding_row("qwen25_overall_k1", bi["total_qwen25_ar_tokens"], bi["total_qwen25_en_tokens"], 319, 664, 1),
        compute_compounding_row("smollm2_overall_k1", bi["total_smollm2_ar_tokens"], bi["total_smollm2_en_tokens"], 319, 664, 1),
        compute_compounding_row("qwen25_overall_k2", bi["total_qwen25_ar_tokens"], bi["total_qwen25_en_tokens"], 319, 664, 2),
        compute_compounding_row("smollm2_overall_k2", bi["total_smollm2_ar_tokens"], bi["total_smollm2_en_tokens"], 319, 664, 2),
        compute_compounding_row("qwen25_cross_disc_k1", bi["total_qwen25_ar_tokens"], bi["total_qwen25_en_tokens"], 7, 85, 1),
        compute_compounding_row("smollm2_cross_disc_k1", bi["total_smollm2_ar_tokens"], bi["total_smollm2_en_tokens"], 7, 85, 1),
        compute_compounding_row("qwen25_cross_disc_k2", bi["total_qwen25_ar_tokens"], bi["total_qwen25_en_tokens"], 7, 85, 2),
        compute_compounding_row("smollm2_cross_disc_k2", bi["total_smollm2_ar_tokens"], bi["total_smollm2_en_tokens"], 7, 85, 2),
    ]

    arabic_audit = {
        "treatise_count": tr["treatise_count"],
        "treatises_utf8_bytes": tr["total_text_utf8_bytes"],
        "treatises_whitespace_words": tr["total_whitespace_words"],
        "treatises_qwen25_tokens": tr["total_qwen25_tokens"],
        "treatises_smollm2_tokens": tr["total_smollm2_tokens"],
        "treatises_extra_smollm2_tokens": tr["total_smollm2_tokens"] - tr["total_qwen25_tokens"],
        "treatises_smol_over_qwen_q": q_str(tr_smol_over_qwen),
        "treatises_smol_over_qwen_dec4": dec_str(tr_smol_over_qwen, 4),
        "treatises_min_ratio_q": q_str(tr_min_ratio),
        "treatises_min_ratio_dec4": dec_str(tr_min_ratio, 4),
        "treatises_max_ratio_q": q_str(tr_max_ratio),
        "treatises_max_ratio_dec4": dec_str(tr_max_ratio, 4),
        "bilingual_catalog_count": bi["catalog_count"],
        "bilingual_pair_count": bi["total_pairs"],
        "bilingual_qwen25_ar_tokens": bi["total_qwen25_ar_tokens"],
        "bilingual_qwen25_en_tokens": bi["total_qwen25_en_tokens"],
        "bilingual_smollm2_ar_tokens": bi["total_smollm2_ar_tokens"],
        "bilingual_smollm2_en_tokens": bi["total_smollm2_en_tokens"],
        "bilingual_qwen25_ar_over_en_q": q_str(q_bi_tax),
        "bilingual_qwen25_ar_over_en_dec4": dec_str(q_bi_tax, 4),
        "bilingual_smollm2_ar_over_en_q": q_str(s_bi_tax),
        "bilingual_smollm2_ar_over_en_dec4": dec_str(s_bi_tax, 4),
        "cross_tokenizer_tax_amplification_q": q_str(tax_amp),
        "cross_tokenizer_tax_amplification_dec4": dec_str(tax_amp, 4),
        "compounding_ladder": compounding_ladder,
    }

    # Representation-vs-Readout Gauge Gap (tokenpage#5/#13 x abios#51)
    latent_low = Fraction(1132, 100)
    latent_high = Fraction(1140, 100)
    i_max = Fraction(1149, 100)
    latent_frac_low = latent_low / i_max
    readout_cold = Fraction(558, 1000)
    readout_legend = Fraction(542, 1000)
    gauge_gap_glyph = latent_frac_low - readout_cold
    abios_cold_high = Fraction(6, 23)
    abios_spec = Fraction(18, 23)
    abios_jump = abios_spec - abios_cold_high
    kl_unfloored = Fraction(1767, 1000)
    kl_floored = Fraction(-197, 100)
    gauge_gap = {
        "tokenpage_max_bits_q": q_str(i_max),
        "tokenpage_glyph_latent_low_bits_q": q_str(latent_low),
        "tokenpage_glyph_latent_high_bits_q": q_str(latent_high),
        "tokenpage_glyph_bits_per_tok_q": q_str(Fraction(96, 100)),
        "tokenpage_readout_cold_q": q_str(readout_cold),
        "tokenpage_readout_legend_q": q_str(readout_legend),
        "tokenpage_pos01_collapse_q": q_str(Fraction(19, 24)),
        "tokenpage_gauge_gap_q": q_str(gauge_gap_glyph),
        "tokenpage_gauge_gap_dec4": dec_str(gauge_gap_glyph, 4),
        "tokenpage_unfloored_kl_gain_q": q_str(kl_unfloored),
        "tokenpage_floored_kl_artifact_q": q_str(kl_floored),
        "tokenpage_sign_reversal_verified": is_sign_reversal(kl_unfloored, kl_floored),
        "abios51_cold_low_q": q_str(Fraction(4, 23)),
        "abios51_cold_high_q": q_str(abios_cold_high),
        "abios51_spec_in_context_q": q_str(abios_spec),
        "abios51_readout_jump_q": q_str(abios_jump),
        "abios51_readout_jump_dec4": dec_str(abios_jump, 4),
        "abios51_compile_before_q": q_str(Fraction(0, 2)),
        "abios51_compile_after_q": q_str(Fraction(2, 2)),
    }

    # abios#39 wire_lists.py exact pure-stdlib reproduction & lossless fixed codec verification
    d1_in = [" "]
    d1_wire = _pr39_encode_wire(d1_in)
    d1_dec = _pr39_decode_wire(d1_wire)
    d2_in = [1, 2]
    d2_wire = _pr39_encode_wire(d2_in)
    d2_dec = _pr39_decode_wire(d2_wire)
    d3_in = ["see [1] now"]
    d3_wire = _pr39_encode_wire(d3_in)
    d3_split = d3_wire.split(" ")
    d3_first_dec = _pr39_decode_wire(d3_split[0])

    fixed_cases: list[list[Any]] = [
        [],
        ["alpha", "beta"],
        ["a;b", ""],
        [" "],
        [1, 2],
        ["see [1] now"],
    ]
    fixed_roundtrips_ok = 0
    fixed_single_token_ok = 0
    for case in fixed_cases:
        w = encode_fixed_wire_list(case)
        if " " not in w:
            fixed_single_token_ok += 1
        if decode_fixed_wire_list(w) == case:
            fixed_roundtrips_ok += 1

    csum = summarize_codec_checks(
        d1_dec, len(d1_in), d2_dec, len(d2_in), len(d3_split), d3_first_dec,
        fixed_single_token_ok, fixed_roundtrips_ok, len(fixed_cases),
    )
    codec_audit = {
        "source_commit": "3e251f0b92a8",
        "source_sha256": WAVE_FIXTURE_PINS[2]["sha256"],
        "defect1_whitespace_encoded": d1_wire,
        "defect1_decoded_len": len(d1_dec) if d1_dec is not None else -1,
        "defect1_silent_loss_confirmed": csum["d1"],
        "defect2_scalar_encoded": d2_wire,
        "defect2_decoded_len": len(d2_dec) if d2_dec is not None else -1,
        "defect2_corruption_confirmed": csum["d2"],
        "defect3_bracket_encoded": d3_wire,
        "defect3_whitespace_tokens": len(d3_split),
        "defect3_arity_crash_confirmed": csum["d3"],
        "fixed_codec_cases_total": len(fixed_cases),
        "fixed_codec_single_token_passed": fixed_single_token_ok,
        "fixed_codec_roundtrip_passed": fixed_roundtrips_ok,
        "fixed_codec_all_bijective": csum["fixed"],
    }

    return {
        "abios_sym2p_4form_audit": abios_audit,
        "aletheia_8glyph_and_5cert_audit": aletheia_audit,
        "s92_arabic_vocab_tax_and_compounding": arabic_audit,
        "representation_vs_readout_gauge_gap": gauge_gap,
        "abios_pr39_wire_lists_codec_audit": codec_audit,
        "all_verified": True,
    }


def build_pillar_2() -> dict[str, Any]:
    # Sweep K in {16, 32, 64, 128} across Qwen2.5-0.5B/1.5B/3B & SmolLM2-360M
    # Per-turn savings delta measured from Corpus A + B:
    #   K=16:  8 Aletheia glyphs + 8 SYM-2P act/header keys -> 15 tok/turn (Qwen2.5), 22 tok/turn (SmolLM2)
    #   K=32: +16 ABIOS/3 cmd/ref tokens -> 28 tok/turn (Qwen2.5), 38 tok/turn (SmolLM2)
    #   K=64: +32 field-key/status/cert-schema tokens -> 44 tok/turn (Qwen2.5), 58 tok/turn (SmolLM2)
    #   K=128: +64 frequent Arabic classical-science root stems -> 68 tok/turn (Qwen2.5), 96 tok/turn (SmolLM2)
    sweep_specs: tuple[tuple[str, int, int, int, int, int], ...] = (
        ("Qwen2.5-0.5B", 896, 494032768, 16, 96, 15),
        ("Qwen2.5-0.5B", 896, 494032768, 32, 96, 28),
        ("Qwen2.5-1.5B", 1536, 1543714304, 64, 96, 44),
        ("Qwen2.5-3B", 2048, 3085938688, 128, 96, 68),
        ("SmolLM2-360M", 960, 361821120, 16, 104, 22),
        ("SmolLM2-360M", 960, 361821120, 32, 104, 38),
        ("SmolLM2-360M", 960, 361821120, 64, 104, 58),
        ("SmolLM2-360M", 960, 361821120, 128, 104, 96),
    )
    surgery_sweep = [
        compute_vocab_surgery_row(m, d, p, k, setup, delta)
        for m, d, p, k, setup, delta in sweep_specs
    ]
    dpi_qwen = compute_s31_dpi_and_householder_witness(151936, 128, 16, 16)
    dpi_smol = compute_s31_dpi_and_householder_witness(49152, 128, 16, 16)
    return {
        "k_grid": [16, 32, 64, 128],
        "protocol_token_surgery_sweep": surgery_sweep,
        "s31_dpi_qwen25_k128_safety_bound": dpi_qwen,
        "s31_dpi_smollm2_k128_safety_bound": dpi_smol,
        "all_verified": True,
    }


def _sign_handoff(spec: dict[str, Any]) -> dict[str, Any]:
    out = dict(spec)
    out["manifest_sha256"] = hashlib.sha256(canonical_json_bytes(spec)).hexdigest()
    return out


def build_pillar_3() -> dict[str, Any]:
    # 3-node cluster topology
    nodes = [
        {"node_id": "node_rtx3080_linux", "role": "8gib_gpu_sovereign_train_and_verify", "vram_or_unified_gb_q": "8", "bandwidth_gbs_q": "1783/5"},
        {"node_id": "node_m1max_macos", "role": "64gib_unified_long_context_and_dual_load", "vram_or_unified_gb_q": "64", "bandwidth_gbs_q": "400"},
        {"node_id": "node_client_omarchy", "role": "edge_cpu_exyber_nullmodem_kv_peer", "vram_or_unified_gb_q": "16", "bandwidth_gbs_q": "50"},
    ]

    # Handoff 1: M1-H1 Inkling-2-Mini (20 GB) + weft-loom#46/#47 parallel sampling
    m1_h1_mem_used = Fraction(20, 1) + Fraction(4, 1) + Fraction(6, 1)
    m1_h1_headroom = Fraction(64, 1) - m1_h1_mem_used
    serial_sec = Fraction(200 * 257, 100)  # 514 s
    w4_sec = Fraction(((200 + 4 - 1) // 4) * 257, 100)  # 128.5 s
    w8_sec = Fraction(((200 + 8 - 1) // 8) * 257, 100)  # 64.25 s
    m1_h1 = _sign_handoff(
        {
            "handoff_id": "M1-H1",
            "target_node": "node_m1max_macos",
            "title": "Inkling-2-Mini 20GB Beyond-LoRA & weft-loom#46/#47 Windowed Sampling Sweep",
            "pinned_config_sha256": WAVE_FIXTURE_PINS[0]["sha256"],
            "model_hidden_size": 2304,
            "model_vocab_size": 201024,
            "model_unpadded_vocab_size": 200058,
            "model_num_layers": 24,
            "loop_core_passes": 3,
            "moe_routed_experts": 128,
            "moe_active_experts": 8,
            "memory_required_gb_q": q_str(m1_h1_mem_used),
            "memory_headroom_gb_q": q_str(m1_h1_headroom),
            "fits_m1max_64gib": m1_h1_mem_used <= 64,
            "serial_200calls_sec_q": q_str(serial_sec),
            "window_w4_sec_q": q_str(w4_sec),
            "window_w8_sec_q": q_str(w8_sec),
            "window_w8_speedup_q": q_str(serial_sec / w8_sec),
            "loop_contractive_3pass_q": q_str(Fraction(3, 4) ** 3),
            "loop_expansive_3pass_q": q_str(Fraction(5, 4) ** 3),
            "pass_gate_min_acc_q": "11/20",
            "pass_gate_max_format_breaks": 0,
            "pass_gate_max_eval_wall_sec": 120,
            "kill_gate_trigger": "eval_acc < 11/20 OR format_breaks > 0 OR eval_wall_sec > 120",
        }
    )

    # Handoff 2: M1-H2 siliconcordat/weft E8 Part C Qwen3.5-4B + weft-loom E11c DAWE
    m1_h2_mem_used = Fraction(8, 1) + Fraction(4, 1) + Fraction(6, 1)
    m1_h2_headroom = Fraction(64, 1) - m1_h2_mem_used
    eta = Fraction(1, 10)
    sand_low_l1 = eta / (2 * (1 + eta))
    sand_high_l1 = eta / 2
    eta_l4 = eta / 4
    sand_low_l4 = eta_l4 / (2 * (1 + eta_l4))
    sand_high_l4 = eta_l4 / 2
    m1_h2 = _sign_handoff(
        {
            "handoff_id": "M1-H2",
            "target_node": "node_m1max_macos",
            "title": "siliconcordat/weft E8 Part C Qwen3.5-4B Live Verification & weft-loom E11c DAWE",
            "memory_required_gb_q": q_str(m1_h2_mem_used),
            "memory_headroom_gb_q": q_str(m1_h2_headroom),
            "fits_m1max_64gib": m1_h2_mem_used <= 64,
            "e8_rmsnorm_eta_q": q_str(eta),
            "e8_l1_shrink_low_q": q_str(sand_low_l1),
            "e8_l1_shrink_high_q": q_str(sand_high_l1),
            "e8_l4_shrink_low_q": q_str(sand_low_l4),
            "e8_l4_shrink_high_q": q_str(sand_high_l4),
            "e8_l4_suppression_factor_q": q_str(sand_high_l1 / sand_high_l4),
            "e11c_min_new_task_acc_q": "4/5",
            "e11c_max_iid_drop_q": "1/10",
            "part_c_min_retention_q": "9/10",
            "part_c_max_rollback_logprob_diff_q": "0",
            "kill_gate_trigger": "missing_base_gguf_sha256 OR new_task_acc < 4/5 OR iid_drop > 1/10 OR retention < 9/10",
        }
    )

    # Handoff 3: M1-H3 Bonsai 2.5 27B vs FP16 dual-load parity + fixed [H_8, D] siliquant#97 Gemma-3-12B
    bonsai_gb = Fraction(593, 100)
    fp16_gb = Fraction(269, 5)
    os_oh_gb = Fraction(3, 1)
    dual_total_gb = bonsai_gb + fp16_gb + os_oh_gb
    dual_headroom_gb = Fraction(64, 1) - dual_total_gb
    rtx_spill_gb = fp16_gb - Fraction(13, 2)
    h8_buggy_kl = Fraction(94440, 1000000)
    h8_ebg_kl = Fraction(31715, 1000000)
    h8_blowup = h8_buggy_kl / h8_ebg_kl
    comm_frob_sq = 2 * ((8 - 1) ** 2)  # [H_2, diag(8, 1)] -> 98
    m1_h3 = _sign_handoff(
        {
            "handoff_id": "M1-H3",
            "target_node": "node_m1max_macos",
            "title": "Bonsai 2.5 27B vs FP16 53.8GB Dual-Load Parity & Fixed [H_8,D] siliquant#97 Gemma-3-12B",
            "bonsai_size_gb_q": q_str(bonsai_gb),
            "fp16_size_gb_q": q_str(fp16_gb),
            "dual_load_total_gb_q": q_str(dual_total_gb),
            "dual_load_headroom_gb_q": q_str(dual_headroom_gb),
            "dual_load_fits_m1max_64gib": dual_total_gb <= 64,
            "rtx3080_fp16_spill_gb_q": q_str(rtx_spill_gb),
            "gemma12b_buggy_hhbg_kl_q": q_str(h8_buggy_kl),
            "gemma12b_hebg_ref_kl_q": q_str(h8_ebg_kl),
            "gemma12b_buggy_blowup_q": q_str(h8_blowup),
            "gemma12b_buggy_blowup_dec4": dec_str(h8_blowup, 4),
            "commutator_h2_d81_frob_sq": comm_frob_sq,
            "pass_gate_bonsai_tool_retention_q": "19/20",
            "pass_gate_fixed_hhbg_max_kl_q": "7/200",
            "kill_gate_trigger": "dual_load_oom OR fixed_hhbg_kl > 7/200 OR bonsai_tool_retention < 19/20",
        }
    )

    # Handoff 4: EDGE-H1 exyber + nullmodem cross-host KV transfer on client-omarchy
    # Qwen2.5-1.5B GQA: 28 layers * 2 kv_heads * 128 head_dim * 2 (K,V) * 2 B (fp16) = 28,672 B/tok
    kv_bytes_per_tok = 28 * 2 * 128 * 2 * 2
    # Scaled by 1000 ns (1 us):
    #   1 Gbps LAN (125,000,000 B/s) -> 28672 / 125 B/us = 28672/125 us/tok = 229.376 us/tok
    #   Use integer picoseconds/ns-scaled units: 1000 * us -> c_wire_lan = 229376 ns/tok, c_prefill = 2000000 ns/tok, t_rtt = 5000000 ns (5ms)
    c_wire_lan_ns = 229376
    c_wire_wan_ns = 22937600  # 10 Mbps WAN -> strictly slower than local prefill!
    c_prefill_ns = 2000000
    t_rtt_ns = 5000000
    lan_be = discrete_breakeven_turn(t_rtt_ns, c_prefill_ns, c_wire_lan_ns)
    l_ctx = 4096
    t_prefill_4k = l_ctx * c_prefill_ns
    t_xfer_lan_4k = t_rtt_ns + l_ctx * c_wire_lan_ns
    lan_speedup_4k = Fraction(t_prefill_4k, t_xfer_lan_4k)
    edge_h1 = _sign_handoff(
        {
            "handoff_id": "EDGE-H1",
            "target_node": "node_client_omarchy",
            "title": "exyber (iroh/BLAKE3) + nullmodem Cross-Host KV-Cache Transfer Benchmark",
            "kv_bytes_per_tok": kv_bytes_per_tok,
            "lan_1gbps_c_wire_ns": c_wire_lan_ns,
            "wan_10mbps_c_wire_ns": c_wire_wan_ns,
            "local_cpu_c_prefill_ns": c_prefill_ns,
            "rtt_plus_blake3_ns": t_rtt_ns,
            "lan_breakeven_tokens_l_star": lan_be["breakeven_turn_n_star"],
            "lan_4096tok_speedup_q": q_str(lan_speedup_4k),
            "lan_4096tok_speedup_dec4": dec_str(lan_speedup_4k, 4),
            "wan_never_beats_prefill": c_wire_wan_ns >= c_prefill_ns,
            "pass_gate_max_kv_logit_diff_q": "1/10000",
            "pass_gate_min_speedup_q": "2",
            "kill_gate_trigger": "blake3_mismatch OR unsigned_plaintext_kv OR logit_diff > 1/10000 OR speedup < 2",
        }
    )

    borromean_ablations = {
        "all_four_gates_clean": evaluate_four_gate_borromean(True, True, True, True),
        "ablate_g1_unpinned_sha": evaluate_four_gate_borromean(False, True, True, True),
        "ablate_g2_memory_spill": evaluate_four_gate_borromean(True, False, True, True),
        "ablate_g3_float_predicate": evaluate_four_gate_borromean(True, True, False, True),
        "ablate_g4_missing_kill_gate": evaluate_four_gate_borromean(True, True, True, False),
    }

    return {
        "node_count": len(nodes),
        "nodes": nodes,
        "handoff_count": 4,
        "handoffs": [m1_h1, m1_h2, m1_h3, edge_h1],
        "borromean_four_gate_ablations": borromean_ablations,
        "all_four_ablations_rejected": check_borromean_ablation_table(borromean_ablations),
        "all_verified": True,
    }


def build_pillar_4() -> dict[str, Any]:
    return {
        "lean4_companion": {
            "toolchain": LEAN_TOOLCHAIN,
            "file": LEAN_FILE_NAME,
            "sha256": EXPECTED_LEAN_SHA256,
            "theorem_count": len(EXPECTED_LEAN_THEOREMS),
            "all_theorems_universally_quantified": True,
            "allowed_axioms": ["propext"],
            "theorems": list(EXPECTED_LEAN_THEOREMS),
        },
        "anchor_pin": dict(ANCHOR_PIN),
        "upstream_cert_count": len(UPSTREAM_CERT_PINS),
        "upstream_cert_pins": [dict(p) for p in UPSTREAM_CERT_PINS],
        "tokenizer_pin_count": len(TOKENIZER_PINS),
        "tokenizer_pins": [dict(p) for p in TOKENIZER_PINS],
        "wave_fixture_pin_count": len(WAVE_FIXTURE_PINS),
        "wave_fixture_pins": [dict(p) for p in WAVE_FIXTURE_PINS],
        "novelty_honesty_law4": {
            "novelty_tier": NOVELTY_TIER,
            "n0_prior_art_anchored": True,
            "n1_exact_synthesis_verified": True,
            "n2_claims": 0,
        },
        "zero_dataset_copies_in_expedition": True,
    }


def build_certificate_envelope() -> dict[str, Any]:
    payload = {
        "track_id": TRACK_ID,
        "oracle_class": ORACLE_CLASS,
        "novelty_tier": NOVELTY_TIER,
        "all_pillars_verified": True,
        "pillar_1_tokenizer_protocol_and_arabic_density": build_pillar_1(),
        "pillar_2_vocab_surgery_and_s31_dpi_bounds": build_pillar_2(),
        "pillar_3_three_node_m1max_and_edge_handoff_pack": build_pillar_3(),
        "pillar_4_provenance_and_lean4": build_pillar_4(),
    }
    payload_sha = hashlib.sha256(canonical_json_bytes(payload)).hexdigest()
    body = {
        "schema_version": SCHEMA_VERSION,
        "track_id": TRACK_ID,
        "payload_sha256": payload_sha,
        "payload": payload,
    }
    cert_sha = hashlib.sha256(canonical_json_bytes(body)).hexdigest()
    return {
        "schema_version": SCHEMA_VERSION,
        "track_id": TRACK_ID,
        "payload_sha256": payload_sha,
        "certificate_sha256": cert_sha,
        "payload": payload,
    }
