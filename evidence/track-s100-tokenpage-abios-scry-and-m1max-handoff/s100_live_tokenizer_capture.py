#!/usr/bin/env python3
"""
Track S100 Live Offline CPU Multi-Tokenizer & Protocol Capture Script.

Runs 100% CPU-only and offline (CUDA_VISIBLE_DEVICES="" HF_HUB_OFFLINE=1) using
the locally cached HuggingFace Rust `tokenizers` JSON files for Qwen2.5-0.5B
and SmolLM2-360M. Reads all primary datasets strictly read-only from outside
`expedition/` (ZERO copies of datasets or weights inside `expedition/`).

Outputs canonical zero-float 0o600 `s100_tokenizer_anchor.json` containing:
  1. Exact tokenizer SHA-256 and vocabulary specs (Qwen2.5 vs SmolLM2)
  2. Live tokenization of Moissanite-Labs/abios `review-fix-verify-merge.jsonl`
     across 4 lossless wire forms (SYM-2P JSONL, Pretty JSON, Verbose Markdown,
     ABIOS/3 compact wire + explicit L-18 setup header)
  3. Live tokenization of all 8 Aletheia calculus glyphs vs ASCII names vs
     reserved-token baseline, plus all 5 frozen Aletheia certificates
     (S31, S86, S89, S92, S94)
  4. Live tokenization of all 12 Track S92 raw-Arabic scientific treatises
     (1.568M words / 14.76 MB) and all 12 bilingual Arabic-English catalogs
     (148 parallel pairs)
  5. Live execution receipt of Moissanite-Labs/abios PR #39 `wire_lists.py`
     codec edge cases (whitespace-only list loss, scalar-list corruption,
     bracket-with-space whitespace-split arity hazard)

Zero production floats in output JSON; all counts are exact integers and exact
canonical rational strings.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import secrets
import sys
from typing import Any

# Hard CPU-only & offline enforcement before importing tokenizers
os.environ["CUDA_VISIBLE_DEVICES"] = ""
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["OMP_NUM_THREADS"] = "1"

from tokenizers import Tokenizer  # type: ignore[import-not-found]


ANCHOR_SCHEMA_VERSION = "aletheia.track_s100.tokenizer_protocol_anchor.v1"

DEFAULT_QWEN25_TOKENIZER = (
    Path.home()
    / ".cache/huggingface/hub/models--Qwen--Qwen2.5-0.5B/snapshots/"
    "060db6499f32faf8b98477b0a26969ef7d8b9987/tokenizer.json"
)
DEFAULT_SMOLLM2_TOKENIZER = (
    Path.home()
    / ".cache/huggingface/hub/models--HuggingFaceTB--SmolLM2-360M/snapshots/"
    "f8027fd0eaeea54caa13c31d31b9fdc459c38b49/tokenizer.json"
)
DEFAULT_HERITAGE_ROOT = Path.home() / "hf-datasets/islamic-scientific-heritage-text"
DEFAULT_ABIOS_CACHE = Path.home() / "hf-datasets/wave8-language-stack-portals-20261124/abios-readonly"
DEFAULT_EXPEDITION_ROOT = Path(__file__).resolve().parent.parent

ALETHEIA_8_GLYPHS: tuple[tuple[str, str, str], ...] = (
    ("schur_pushforward", "\u29c4", "U+29C4"),
    ("exact_commute", "\u29c5", "U+29C5"),
    ("phase_crossover", "\u29b7", "U+29B7"),
    ("holonomy_curvature", "\u27e0", "U+27E0"),
    ("exact_obstruction", "\u29c7", "U+29C7"),
    ("conditional_bridge", "\u29ba", "U+29BA"),
    ("borromean_coupling", "\u2a69", "U+2A69"),
    ("law3_firewall", "\u2ae9", "U+2AE9"),
)

FROZEN_CERTS: tuple[tuple[str, str], ...] = (
    ("S31", "track-s31-aletheia-v22-society-misfolding-tomography/aletheia_v22_misfolding_certificate.json"),
    ("S86", "track-s86-sovereign-8gb-fourth-order-stack/s86_sovereign_stack_certificate.json"),
    ("S89", "track-s89-islamic-heritage-corpus-atlas/s89_heritage_atlas_certificate.json"),
    ("S92", "track-s92-raw-arabic-scientific-mesh/s92_raw_arabic_mesh_certificate.json"),
    ("S94", "track-s94-neuron-basis-bonsai-sleep-convergence/s94_wave6_convergence_certificate.json"),
)

TREATISES_12: tuple[tuple[str, str, str], ...] = (
    ("haytham_manazir", "optics", "04_physics_optics/openiti_classical_physics_optics/full_texts/02_\u0643\u062a\u0627\u0628_\u0627\u0644\u0645\u0646\u0627\u0638\u0631.md"),
    ("sina_shifa_phys", "physics", "04_physics_optics/openiti_classical_physics_optics/full_texts/01_\u0637\u0628\u064a\u0639\u064a\u0627\u062a_\u0643\u062a\u0627\u0628_\u0627\u0644\u0634\u0641\u0627\u0621__\u0627\u0644\u0633\u0645\u0627\u0639_\u0627\u0644\u0637\u0628\u064a\u0639\u064a.md"),
    ("sina_qanun", "medicine", "01_medicine/openiti_classical_medicine/full_texts/01_\u0627\u0644\u0642\u0627\u0646\u0648\u0646_\u0641\u064a_\u0627\u0644\u0637\u0628.md"),
    ("nafis_tashrih", "medicine", "01_medicine/openiti_classical_medicine/full_texts/02_\u0634\u0631\u062d_\u062a\u0634\u0631\u064a\u062d_\u0627\u0644\u0642\u0627\u0646\u0648\u0646.md"),
    ("battani_zij", "astronomy", "02_astronomy/openiti_classical_astronomy/full_texts/01_\u0632\u064a\u062c_\u0627\u0644\u0635\u0627\u0628\u0626__\u0627\u0644\u0632\u064a\u062c_.md"),
    ("biruni_masudi", "astronomy", "02_astronomy/abu_al_rayhan_al_biruni_362_440h/al_qanun_al_masudi/al_biruni_qanun_masudi.jsonl"),
    ("biruni_asturlab", "astronomy", "02_astronomy/openiti_classical_astronomy/full_texts/02_\u0627\u0633\u062a\u064a\u0639\u0627\u0628_\u0627\u0644\u0648\u062c\u0648\u0647_\u0627\u0644\u0645\u0645\u0643\u0646\u0629_\u0641\u064a_\u0635\u0646\u0639\u0629_\u0627\u0644\u0623\u0633.md"),
    ("tusi_majisti", "astronomy", "02_astronomy/ptolemaeus_arabus_corpus/full_texts/09_C.1.18_Ta\u1e25r\u012br_al-Majis\u1e6d\u012b.md"),
    ("biruni_zilal", "mathematics", "03_mathematics/abu_al_rayhan_al_biruni_362_440h/ifrad_al_maqal_amr_al_zilal/al_biruni_amr_al_zilal.jsonl"),
    ("biruni_awtar", "mathematics", "03_mathematics/abu_al_rayhan_al_biruni_362_440h/istikhraj_al_awtar/al_biruni_istikhraj_al_awtar.jsonl"),
    ("thabit_niqumakhus", "mathematics", "03_mathematics/thabit_ibn_qurra_al_harrani_221_288h/madkhal_niqumakhus/thabit_ibn_qurra_niqumakhus_arithmetic.jsonl"),
    ("biruni_jamahir", "natural_history", "05_natural_history/openiti_classical_natural_history/full_texts/02_\u0627\u0644\u062c\u0645\u0627\u0647\u0631_\u0641\u064a_\u0645\u0639\u0631\u0641\u0629_\u0627\u0644\u062c\u0648\u0627\u0647\u0631.md"),
)

BILINGUAL_CATALOGS_12: tuple[tuple[str, str], ...] = (
    ("sina_qanun_books", "01_medicine/abu_ali_ibn_sina_370_428h/al_qanun_fi_al_tibb/al_qanun_fi_al_tibb_books_catalog.jsonl"),
    ("razi_judari", "01_medicine/abu_bakr_al_razi_251_313h/al_judari_wa_al_hasbah/al_judari_wa_al_hasbah_catalog.jsonl"),
    ("sufi_kawakib", "02_astronomy/abd_al_rahman_al_sufi_291_376h/suwar_al_kawakib_al_thabitah/suwar_al_kawakib_catalog.jsonl"),
    ("battani_zij_cat", "02_astronomy/abu_abdallah_al_battani_244_317h/al_zij_al_sabi/al_zij_al_sabi_catalog.jsonl"),
    ("biruni_tafhim", "02_astronomy/abu_al_rayhan_al_biruni_362_440h/al_tafhim_li_awail_al_tanjim/al_tafhim_chapters_catalog.jsonl"),
    ("khwarizmi_jabr", "03_mathematics/muhammad_ibn_musa_al_khwarizmi_164_232h/al_jabr_wa_al_muqabala/al_jabr_wa_al_muqabala_catalog.jsonl"),
    ("tusi_shakl_qatta", "03_mathematics/nasir_al_din_al_tusi_597_672h/kitab_shakl_al_qatta/shakl_al_qatta_catalog.jsonl"),
    ("haytham_manazir_cat", "04_optics_mechanics_chemistry/al_hasan_ibn_al_haytham_354_430h/kitab_al_manazir/kitab_al_manazir_maqalat_catalog.jsonl"),
    ("jazari_machines", "04_optics_mechanics_chemistry/badi_al_zaman_al_jazari_530_602h/al_hiyal_mechanical_devices/al_jazari_machines_catalog.jsonl"),
    ("banu_musa_hiyal", "04_optics_mechanics_chemistry/banu_musa_ibn_shakir_d265h/kitab_al_hiyal/banu_musa_hiyal_catalog.jsonl"),
    ("farisi_tanqih", "04_optics_mechanics_chemistry/kamal_al_din_al_farisi_665_718h/tanqih_al_manazir/tanqih_al_manazir_catalog.jsonl"),
    ("taqi_al_din_turuq", "04_optics_mechanics_chemistry/taqi_al_din_al_dimashqi_932_993h/al_turuq_al_saniyyah/al_turuq_al_saniyyah_catalog.jsonl"),
)


def canonical_json_bytes(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes()
    return hashlib.sha256(raw).hexdigest(), len(raw)


def tok_len(tok: Tokenizer, text: str) -> int:
    return len(tok.encode(text, add_special_tokens=False).ids)


def tok_ids(tok: Tokenizer, text: str) -> list[int]:
    return [int(x) for x in tok.encode(text, add_special_tokens=False).ids]


def read_treatise_text(path: Path) -> str:
    txt = path.read_bytes().decode("utf-8", errors="replace")
    if path.suffix == ".jsonl":
        return str(json.loads(txt.splitlines()[0]).get("full_text", ""))
    parts = txt.split("\n---\n", 1)
    return parts[1] if len(parts) > 1 else txt


def render_sym2p_lossless_markdown(packets: list[dict[str, Any]]) -> str:
    """Deterministic lossless Markdown prose rendering of all SYM-2P packets."""
    lines: list[str] = ["# SYM-2P Workflow Transcript (Lossless Markdown Prose)", ""]
    for idx, pkt in enumerate(packets, start=1):
        lines.append(f"## Packet {idx}: `{pkt.get('id', 'unknown')}`")
        for key in sorted(pkt.keys()):
            val = pkt[key]
            if isinstance(val, (dict, list)):
                rendered = json.dumps(val, sort_keys=True, separators=(", ", ": "), ensure_ascii=True)
            else:
                rendered = str(val)
            lines.append(f"- **{key}**: {rendered}")
        lines.append("")
    return "\n".join(lines)


def _abios3_encode_value(
    val: Any,
    session_refs: dict[str, str],
    content_table: dict[str, str],
    next_ref_num: list[int],
) -> str:
    """Deterministic ABIOS/3-style wire encoder with S-8 session refs & S-9 >=48B content refs."""
    if val is None:
        return "-"
    if type(val) is bool:
        return "1" if val else "0"
    if type(val) is int:
        return str(val)
    if type(val) is str:
        if val in session_refs:
            return session_refs[val]
        raw_b = val.encode("utf-8")
        if len(raw_b) >= 48:
            if val in content_table:
                return content_table[val]
            ref_lbl = f"#{next_ref_num[0]}"
            next_ref_num[0] += 1
            content_table[val] = ref_lbl
            return f"{ref_lbl}={json.dumps(val, ensure_ascii=True)}"
        if any(c in val for c in (" ", ";", '"', "\n", "\r", "[", "]")) or val == "":
            return json.dumps(val, ensure_ascii=True)
        return val
    canon = json.dumps(val, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    if len(canon.encode("utf-8")) >= 48:
        if canon in content_table:
            return content_table[canon]
        ref_lbl = f"#{next_ref_num[0]}"
        next_ref_num[0] += 1
        content_table[canon] = ref_lbl
        return f"{ref_lbl}={canon}"
    if isinstance(val, list) and all(isinstance(x, str) and ";" not in x and " " not in x and "[" not in x and "]" not in x for x in val):
        return "[" + ";".join(val) + "]"
    return canon


def render_sym2p_abios3_wire(packets: list[dict[str, Any]]) -> tuple[str, str]:
    """
    Lossless ABIOS/3-style wire rendering of review-fix-verify-merge.jsonl.
    Returns (setup_header, payload_lines) satisfying SPEC-ABIOS-3 L-18 decode-sufficiency.
    """
    setup_header = (
        "abios/3\n"
        "refs p=sym2integration t=mr1 a0=relay a1=cos a2=builder a3=qa f=f88 d=sym2p:1.0\n"
        "cmd Ea=assign Ec=accept Eu=update En=answer Ev=verify Eh=challenge Ed=done Ex=dispute Ez=decision\n"
        "defaults v=2 tk=t prj=p ext={sym2p:{rev:1.0}}\n"
    )
    session_refs = {
        "sym2integration": "p",
        "mr1": "t",
        "relay": "a0",
        "cos": "a1",
        "builder": "a2",
        "qa": "a3",
        "f88": "f",
    }
    act_codes = {
        "assign": "Ea",
        "accept": "Ec",
        "update": "Eu",
        "answer": "En",
        "verify": "Ev",
        "challenge": "Eh",
        "done": "Ed",
    }
    content_table: dict[str, str] = {}
    next_ref = [1]
    out_lines: list[str] = []
    for pkt in packets:
        if "a" in pkt and pkt["a"] in act_codes:
            cmd = act_codes[pkt["a"]]
            skip_keys = {"a"}
        elif pkt.get("type") == "dispute":
            cmd = "Ex"
            skip_keys = {"type"}
        elif pkt.get("type") == "decision":
            cmd = "Ez"
            skip_keys = {"type"}
        else:
            cmd = "Eo"
            skip_keys = set()

        # Omit exact default header fields (S-7) when matching defaults
        if pkt.get("v") == 2:
            skip_keys.add("v")
        if pkt.get("tk") == "mr1":
            skip_keys.add("tk")
        if pkt.get("prj") == "sym2integration":
            skip_keys.add("prj")
        if pkt.get("ext") == {"sym2p": {"rev": "1.0"}}:
            skip_keys.add("ext")

        keys = [k for k in sorted(pkt.keys()) if k not in skip_keys]
        vals = [
            _abios3_encode_value(pkt[k], session_refs, content_table, next_ref)
            for k in keys
        ]
        out_lines.append(f"{cmd} {'|'.join(keys)}| {' '.join(vals)}")
    return setup_header, "\n".join(out_lines) + "\n"


def probe_abios_pr39_wire_lists(wire_lists_path: Path) -> dict[str, Any]:
    wl_sha, wl_bytes = sha256_file(wire_lists_path)
    spec = importlib.util.spec_from_file_location("abios_pr39_wire_lists", str(wire_lists_path))
    if spec is None or spec.loader is None:
        raise RuntimeError("FAILED_TO_LOAD_WIRE_LISTS")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    # Defect 1: Whitespace-only list [' '] -> encode '[ ]' -> decode [] (silent loss!)
    w1_in = [" "]
    w1_can = bool(mod.can_encode_string_list(w1_in))
    w1_enc = str(mod.encode_string_list(w1_in))
    w1_dec = mod.decode_string_list(w1_enc)

    # Defect 2: Scalar list [1, 2] -> fallback JSON "[1,2]" -> decode ['1,2'] (silent corruption!)
    w2_in = [1, 2]
    w2_can = bool(mod.can_encode_string_list(w2_in))
    w2_fallback_wire = json.dumps(w2_in, separators=(",", ":"))
    w2_dec = mod.decode_string_list(w2_fallback_wire)

    # Defect 3: Bracket-with-space ['see [1] now'] -> fallback JSON '["see [1] now"]' -> space-split breaks token!
    w3_in = ["see [1] now"]
    w3_can = bool(mod.can_encode_string_list(w3_in))
    w3_fallback_wire = json.dumps(w3_in, separators=(",", ":"))
    w3_space_tokens = w3_fallback_wire.split(" ")
    w3_dec_whole = mod.decode_string_list(w3_fallback_wire)
    w3_dec_first_split = mod.decode_string_list(w3_space_tokens[0])

    # Clean controls
    c_empty_enc = str(mod.encode_string_list([]))
    c_empty_dec = mod.decode_string_list(c_empty_enc)
    c_norm_in = ["alpha", "beta;gamma", ""]
    c_norm_enc = str(mod.encode_string_list(c_norm_in))
    c_norm_dec = mod.decode_string_list(c_norm_enc)

    return {
        "source_commit": "3e251f0b92a8",
        "source_file": "scripts/protean-abios/wire_lists.py",
        "source_sha256": wl_sha,
        "source_bytes": wl_bytes,
        "defect_1_whitespace_loss": {
            "input": w1_in,
            "input_len": len(w1_in),
            "can_encode": w1_can,
            "encoded_wire": w1_enc,
            "decoded_output": w1_dec,
            "decoded_len": len(w1_dec) if isinstance(w1_dec, list) else -1,
            "roundtrip_exact": w1_dec == w1_in,
        },
        "defect_2_scalar_corruption": {
            "input": w2_in,
            "input_len": len(w2_in),
            "can_encode": w2_can,
            "fallback_wire": w2_fallback_wire,
            "decoded_output": w2_dec,
            "decoded_len": len(w2_dec) if isinstance(w2_dec, list) else -1,
            "roundtrip_exact": w2_dec == w2_in,
        },
        "defect_3_bracket_space_arity_split": {
            "input": w3_in,
            "can_encode": w3_can,
            "fallback_wire": w3_fallback_wire,
            "whitespace_split_token_count": len(w3_space_tokens),
            "decoded_whole_token": w3_dec_whole,
            "decoded_first_split_token": w3_dec_first_split,
            "split_breaks_arity": len(w3_space_tokens) > 1 and w3_dec_first_split is None,
        },
        "clean_controls": {
            "empty_roundtrip_exact": c_empty_dec == [],
            "escaped_semicolon_empty_roundtrip_exact": c_norm_dec == c_norm_in,
            "escaped_wire": c_norm_enc,
        },
    }


def write_0600_atomic(path: Path, data: bytes) -> None:
    tmp = path.parent / f".{path.name}.tmp.{secrets.token_hex(8)}"
    fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        view = memoryview(data)
        written = 0
        while written < len(view):
            written += os.write(fd, view[written:])
        os.fsync(fd)
    finally:
        os.close(fd)
    os.replace(str(tmp), str(path))


def capture_all(
    qwen_tok_path: Path,
    smol_tok_path: Path,
    heritage_root: Path,
    abios_cache: Path,
    expedition_root: Path,
) -> dict[str, Any]:
    qwen_sha, qwen_bytes = sha256_file(qwen_tok_path)
    smol_sha, smol_bytes = sha256_file(smol_tok_path)
    qwen = Tokenizer.from_file(str(qwen_tok_path))
    smol = Tokenizer.from_file(str(smol_tok_path))

    # 1. Corpus A: Moissanite-Labs/abios review-fix-verify-merge.jsonl across 4 lossless renderings
    rfvm_path = abios_cache / "review-fix-verify-merge.jsonl"
    rfvm_sha, rfvm_bytes = sha256_file(rfvm_path)
    rfvm_raw = rfvm_path.read_text(encoding="utf-8")
    packets = [json.loads(line) for line in rfvm_raw.splitlines() if line.strip()]
    pretty_json_text = "\n".join(json.dumps(p, indent=2, sort_keys=True, ensure_ascii=True) for p in packets) + "\n"
    md_text = render_sym2p_lossless_markdown(packets)
    abios_setup, abios_payload = render_sym2p_abios3_wire(packets)
    abios_full = abios_setup + abios_payload

    def _measure_text(s: str) -> dict[str, int]:
        return {
            "utf8_bytes": len(s.encode("utf-8")),
            "qwen25_tokens": tok_len(qwen, s),
            "smollm2_tokens": tok_len(smol, s),
        }

    per_packet_abios = []
    abios_lines = abios_payload.splitlines()
    for idx, (pkt, raw_line, a_line) in enumerate(zip(packets, rfvm_raw.splitlines(), abios_lines), start=1):
        per_packet_abios.append(
            {
                "index": idx,
                "packet_id": str(pkt.get("id", "")),
                "sym2p_bytes": len(raw_line.encode("utf-8")),
                "sym2p_qwen25_tokens": tok_len(qwen, raw_line),
                "sym2p_smollm2_tokens": tok_len(smol, raw_line),
                "abios3_bytes": len(a_line.encode("utf-8")),
                "abios3_qwen25_tokens": tok_len(qwen, a_line),
                "abios3_smollm2_tokens": tok_len(smol, a_line),
            }
        )

    corpus_a_abios = {
        "source_file": "examples/protean-sym2p/review-fix-verify-merge.jsonl",
        "source_sha256": rfvm_sha,
        "source_bytes": rfvm_bytes,
        "packet_count": len(packets),
        "forms": {
            "sym2p_jsonl": _measure_text(rfvm_raw),
            "pretty_json": _measure_text(pretty_json_text),
            "verbose_markdown": _measure_text(md_text),
            "abios3_setup_header": _measure_text(abios_setup),
            "abios3_payload_only": _measure_text(abios_payload),
            "abios3_full_with_setup": _measure_text(abios_full),
        },
        "per_packet": per_packet_abios,
    }

    # 2. Corpus B: Aletheia 8 glyphs + composite expression + 5 frozen Aletheia certs
    glyph_rows: list[dict[str, Any]] = []
    for name, glyph, codepoint in ALETHEIA_8_GLYPHS:
        q_ids = tok_ids(qwen, glyph)
        s_ids = tok_ids(smol, glyph)
        glyph_rows.append(
            {
                "name": name,
                "codepoint": codepoint,
                "utf8_bytes": len(glyph.encode("utf-8")),
                "qwen25_tokens": len(q_ids),
                "qwen25_ids": q_ids,
                "smollm2_tokens": len(s_ids),
                "smollm2_ids": s_ids,
                "ascii_qwen25_tokens": tok_len(qwen, name),
                "ascii_smollm2_tokens": tok_len(smol, name),
            }
        )

    expr_glyph = "A \u29c4 B \u29c5 C \u29b7 D \u27e0 E \u29c7 F \u29ba G \u2a69 H \u2ae9 I"
    expr_ascii = (
        "A schur_pushforward B exact_commute C phase_crossover D holonomy_curvature "
        "E exact_obstruction F conditional_bridge G borromean_coupling H law3_firewall I"
    )
    expr_base_only = "A B C D E F G H I"
    cert_rows: list[dict[str, Any]] = []
    for tid, rel in FROZEN_CERTS:
        p = expedition_root / rel
        c_sha, c_bytes = sha256_file(p)
        c_text = p.read_text(encoding="utf-8")
        cert_rows.append(
            {
                "track_id": tid,
                "relative_ref": rel,
                "sha256": c_sha,
                "utf8_bytes": c_bytes,
                "qwen25_tokens": tok_len(qwen, c_text),
                "smollm2_tokens": tok_len(smol, c_text),
            }
        )

    corpus_b_aletheia = {
        "glyph_count": len(glyph_rows),
        "glyphs": glyph_rows,
        "glyph_qwen25_total_tokens": sum(r["qwen25_tokens"] for r in glyph_rows),
        "glyph_smollm2_total_tokens": sum(r["smollm2_tokens"] for r in glyph_rows),
        "ascii_name_qwen25_total_tokens": sum(r["ascii_qwen25_tokens"] for r in glyph_rows),
        "ascii_name_smollm2_total_tokens": sum(r["ascii_smollm2_tokens"] for r in glyph_rows),
        "composite_expression": {
            "glyph_form": _measure_text(expr_glyph),
            "ascii_form": _measure_text(expr_ascii),
            "operand_scaffold_only": _measure_text(expr_base_only),
            "reserved_8tok_qwen25_tokens": tok_len(qwen, expr_base_only) + 8,
            "reserved_8tok_smollm2_tokens": tok_len(smol, expr_base_only) + 8,
        },
        "frozen_certificates": cert_rows,
    }

    # 3. Corpus C1: Track S92 12 Raw-Arabic Scientific Treatises
    treatise_rows: list[dict[str, Any]] = []
    for tid, disc, rel in TREATISES_12:
        p = heritage_root / rel
        f_sha, f_bytes = sha256_file(p)
        txt = read_treatise_text(p)
        treatise_rows.append(
            {
                "id": tid,
                "discipline": disc,
                "rel_path": rel,
                "file_sha256": f_sha,
                "file_bytes": f_bytes,
                "text_utf8_bytes": len(txt.encode("utf-8")),
                "whitespace_words": len(txt.split()),
                "qwen25_tokens": tok_len(qwen, txt),
                "smollm2_tokens": tok_len(smol, txt),
            }
        )

    # 4. Corpus C2: Track S92 12 Bilingual Arabic-English Scientific Catalogs (JSONL)
    catalog_rows: list[dict[str, Any]] = []
    for cid, rel in BILINGUAL_CATALOGS_12:
        p = heritage_root / rel
        c_sha, c_bytes = sha256_file(p)
        entries = [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]
        pair_count = 0
        ar_b = en_b = ar_w = en_w = q_ar = q_en = s_ar = s_en = 0
        for e in entries:
            if not isinstance(e, dict):
                continue
            ar = " ".join(str(e[k]) for k in sorted(e) if k.endswith("_ar") and e[k]).strip()
            en = " ".join(str(e[k]) for k in sorted(e) if k.endswith("_en") and e[k]).strip()
            if ar and en:
                ar_s, en_s = str(ar), str(en)
                pair_count += 1
                ar_b += len(ar_s.encode("utf-8"))
                en_b += len(en_s.encode("utf-8"))
                ar_w += len(ar_s.split())
                en_w += len(en_s.split())
                q_ar += tok_len(qwen, ar_s)
                q_en += tok_len(qwen, en_s)
                s_ar += tok_len(smol, ar_s)
                s_en += tok_len(smol, en_s)
        catalog_rows.append(
            {
                "id": cid,
                "rel_path": rel,
                "file_sha256": c_sha,
                "file_bytes": c_bytes,
                "pair_count": pair_count,
                "ar_utf8_bytes": ar_b,
                "en_utf8_bytes": en_b,
                "ar_words": ar_w,
                "en_words": en_w,
                "qwen25_ar_tokens": q_ar,
                "qwen25_en_tokens": q_en,
                "smollm2_ar_tokens": s_ar,
                "smollm2_en_tokens": s_en,
            }
        )

    # 5. Live wire_lists_pr39.py probe
    wire_lists_probe = probe_abios_pr39_wire_lists(abios_cache / "wire_lists_pr39.py")

    payload = {
        "anchor_schema_version": ANCHOR_SCHEMA_VERSION,
        "capture_mode": "cpu_only_offline_rust_tokenizers",
        "tokenizers": {
            "qwen25_0p5b": {
                "model_id": "Qwen/Qwen2.5-0.5B",
                "snapshot_rev": "060db6499f32faf8b98477b0a26969ef7d8b9987",
                "tokenizer_json_bytes": qwen_bytes,
                "tokenizer_json_sha256": qwen_sha,
                "active_vocab_size": int(qwen.get_vocab_size()),
                "padded_vocab_size": 151936,
                "hidden_size_0p5b": 896,
                "hidden_size_1p5b": 1536,
                "hidden_size_3b": 2048,
            },
            "smollm2_360m": {
                "model_id": "HuggingFaceTB/SmolLM2-360M",
                "snapshot_rev": "f8027fd0eaeea54caa13c31d31b9fdc459c38b49",
                "tokenizer_json_bytes": smol_bytes,
                "tokenizer_json_sha256": smol_sha,
                "active_vocab_size": int(smol.get_vocab_size()),
                "padded_vocab_size": 49152,
                "hidden_size_360m": 960,
            },
        },
        "corpus_a_abios_sym2p": corpus_a_abios,
        "corpus_b_aletheia_calculus_and_certs": corpus_b_aletheia,
        "corpus_c_s92_raw_arabic_treatises": {
            "treatise_count": len(treatise_rows),
            "total_text_utf8_bytes": sum(r["text_utf8_bytes"] for r in treatise_rows),
            "total_whitespace_words": sum(r["whitespace_words"] for r in treatise_rows),
            "total_qwen25_tokens": sum(r["qwen25_tokens"] for r in treatise_rows),
            "total_smollm2_tokens": sum(r["smollm2_tokens"] for r in treatise_rows),
            "treatises": treatise_rows,
        },
        "corpus_c_s92_bilingual_catalogs": {
            "catalog_count": len(catalog_rows),
            "total_pairs": sum(r["pair_count"] for r in catalog_rows),
            "total_ar_utf8_bytes": sum(r["ar_utf8_bytes"] for r in catalog_rows),
            "total_en_utf8_bytes": sum(r["en_utf8_bytes"] for r in catalog_rows),
            "total_ar_words": sum(r["ar_words"] for r in catalog_rows),
            "total_en_words": sum(r["en_words"] for r in catalog_rows),
            "total_qwen25_ar_tokens": sum(r["qwen25_ar_tokens"] for r in catalog_rows),
            "total_qwen25_en_tokens": sum(r["qwen25_en_tokens"] for r in catalog_rows),
            "total_smollm2_ar_tokens": sum(r["smollm2_ar_tokens"] for r in catalog_rows),
            "total_smollm2_en_tokens": sum(r["smollm2_en_tokens"] for r in catalog_rows),
            "catalogs": catalog_rows,
        },
        "corpus_d_abios_pr39_wire_lists_live_probe": wire_lists_probe,
    }
    payload_sha = hashlib.sha256(canonical_json_bytes(payload)).hexdigest()
    envelope = {
        "anchor_schema_version": ANCHOR_SCHEMA_VERSION,
        "anchor_payload_sha256": payload_sha,
        "payload": payload,
    }
    return envelope


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Capture Track S100 live CPU offline multi-tokenizer anchor.")
    parser.add_argument("--out", default=str(Path(__file__).resolve().parent / "s100_tokenizer_anchor.json"))
    parser.add_argument("--qwen25-tokenizer", default=str(DEFAULT_QWEN25_TOKENIZER))
    parser.add_argument("--smollm2-tokenizer", default=str(DEFAULT_SMOLLM2_TOKENIZER))
    parser.add_argument("--heritage-root", default=str(DEFAULT_HERITAGE_ROOT))
    parser.add_argument("--abios-cache", default=str(DEFAULT_ABIOS_CACHE))
    parser.add_argument("--expedition-root", default=str(DEFAULT_EXPEDITION_ROOT))
    args = parser.parse_args(argv)

    env = capture_all(
        Path(args.qwen25_tokenizer),
        Path(args.smollm2_tokenizer),
        Path(args.heritage_root),
        Path(args.abios_cache),
        Path(args.expedition_root),
    )
    raw = canonical_json_bytes(env)
    out_path = Path(args.out)
    write_0600_atomic(out_path, raw)
    file_sha = hashlib.sha256(raw).hexdigest()
    print(f"WROTE {out_path} bytes={len(raw)} file_sha256={file_sha} payload_sha256={env['anchor_payload_sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
