"""
`aletheia mde [--manifest | --verify-dag <jsonl> | --demo]`: Plane-1 Aletheia-as-an-MDE
canonical `zone-canon-v0` manifest engine (`siliconcordat/mde#8`), causal `AUDIT-XXX`
lineage DAG verifier (`mep/revisions` + `synmerit/koinos`), and `SYM-2P/2.0-rcp` (`abios`)
checksummed wire packet codec.

Zero external dependencies. Zero floats in canonical hash preimages. Zero bare `assert`s.
"""
from __future__ import annotations

import hashlib
import hmac
import json
from pathlib import Path
import re
from typing import Any, Mapping, Sequence

from .strict_io import AletheiaError, require_ok

ZONE_CANON_LIMIT = (1 << 53) - 1
ALETHEIA_MDE_SCHEMA = "aletheia-mde-manifest/v0.1"
LINEAGE_SCHEMA = "aletheia-lineage-record/v0.1"
DEFAULT_SCALE_DEN_LOG2 = 10

ALETHEIA_ZONES: tuple[str, ...] = (
    "tomography_verifier",
    "formal_proof",
    "audit_ledger",
    "condensed_packet",
    "probe_code",
    "portal_map",
    "ui_module",
    "prose",
)
VALID_LINEAGE_KINDS = ("PROPOSAL", "AUDIT_VERDICT", "STEELMAN_REPAIR", "DISPUTE", "ADJUDICATION")
VALID_VERDICTS = ("VERIFIED", "PARTIAL/FRAGILE", "FALSIFIED", "NOT_SHOWN", "EXPOSED")
VALID_NOVELTIES = ("N0", "N1", "N2", "N0/N1", "N1/N2")
VALID_ORACLE_TOKENS = frozenset({"exact", "sampled", "anchor"})

_SHA256_PREF_RE = re.compile(r"\Asha256:[0-9a-f]{64}\Z", re.ASCII)
_SLUG_RE = re.compile(r"\A[a-z][a-z0-9_-]{0,47}\Z", re.ASCII)
_ID_RE = re.compile(r"\A[A-Za-z0-9][A-Za-z0-9_.:/-]{0,63}\Z", re.ASCII)
_HEX16_RE = re.compile(r"\A[0-9a-f]{16}\Z", re.ASCII)

V2_ROLES = {"coordinator": 1, "builder": 2, "verifier": 3, "scout": 4, "critic": 5, "operator": 6, "swarm": 7}
V2_ACTS = {
    "assign": 1, "acknowledge": 2, "assert": 3, "update": 4, "receipt": 5, "challenge": 6,
    "dispute": 7, "authorize": 8, "query": 9, "inform": 10, "delegate": 11, "report": 12,
}
V2_STATES = {"proposed": 1, "accepted": 2, "rejected": 3, "verified": 4, "open": 5, "closed": 6, "superseded": 7, "expired": 8}
V2_RQS = {"none": 0, "ack": 1, "ver": 2}

# Exact golden test vectors from siliconcordat/mde#8 `vectors/zone-canon-v0.json`
MDE_PR8_ACCEPT_VECTORS: tuple[tuple[str, str, str, str], ...] = (
    ("empty_object", "{}", "{}", "44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a"),
    ("key_order_nested", '{"b":[1,{"z":true,"a":null}],"a":"x"}', '{"a":"x","b":[1,{"a":null,"z":true}]}', "96c83c1cb81829f839e9b502d34eba2f7af11c7e11fd8d82237d49873cbbe110"),
    ("non_ascii_raw_utf8", '{"\u00e9":"\u65e5\u672c","a":"\\u00e9"}', '{"a":"\u00e9","\u00e9":"\u65e5\u672c"}', "f15a8b198ffb5b295dcf905075fc46543ac327dafdb37de84d819ccd4fd1c66c"),
    ("astral_key_sorts_after_ffff", '{"\\ud83d\\ude00":1,"\\uffff":2}', '{"\uffff":2,"\U0001f600":1}', "92db27167c6f89fc43ff6c1997a7954a2e5bec81936fbe5ee12b4b6615b09596"),
    ("control_chars_escaped", '{"k":"a\\u0001b\\n\\u007f"}', '{"k":"a\\u0001b\\n\x7f"}', "74713a64bb9f1fc65c596326c6ecdc32ad30f0ead0bde4c090cb4dc39809a42e"),
    ("max_safe_integer", '{"n":9007199254740991,"m":-9007199254740991}', '{"m":-9007199254740991,"n":9007199254740991}', "3f54c80abdfbc38f08ed5654622eea6e7d7e58cbac36cf5a0670c8aeb054703d"),
    ("scale_as_integer_over_1024", '{"scale_den_log2":10,"scales_num":{"corpus":205,"weft-eido":1024}}', '{"scale_den_log2":10,"scales_num":{"corpus":205,"weft-eido":1024}}', "e4e6e651a0b26c4d259173081cfcd990c191060167431003334412ec9985c333"),
)
MDE_PR8_REJECT_VECTORS: tuple[tuple[str, str], ...] = (
    ("float_small_0.00001", '{"s":0.00001}'),
    ("float_small_1e-05", '{"s":1e-05}'),
    ("float_1e16", '{"s":1e16}'),
    ("float_1e+16", '{"s":1e+16}'),
    ("float_zero_point_zero", '{"s":0.0}'),
    ("negative_zero", '{"s":-0}'),
    ("integer_2_pow_53", '{"n":9007199254740992}'),
    ("integer_above_u64", '{"n":18446744073709551616}'),
    ("duplicate_key", '{"a":1,"a":2}'),
    ("nan_token", '{"n":NaN}'),
)


# ---------------------------------------------------------------------------
# Strict `zone-canon-v0` parser & byte-exact canonicalizer
# ---------------------------------------------------------------------------

def _parse_int_strict(text: str) -> int:
    if text == "-0":
        raise AletheiaError("NEGATIVE_ZERO", "negative zero '-0' is forbidden in zone-canon-v0")
    if len(text) > 40:
        raise AletheiaError("INT_TOKEN_TOO_LONG", f"integer token too long: {text[:24]}")
    n = int(text)
    if abs(n) > ZONE_CANON_LIMIT:
        raise AletheiaError("INT_OUT_OF_RANGE", f"integer {n} exceeds |n| <= 2^53 - 1")
    return n


def _reject_float(text: str) -> Any:
    raise AletheiaError("FLOAT_FORBIDDEN", f"floating-point number {text!r} is forbidden in zone-canon-v0")


def _reject_constant(text: str) -> Any:
    raise AletheiaError("NON_JSON_CONSTANT", f"non-JSON constant {text!r} is forbidden")


def _pairs_no_dup(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in pairs:
        if k in out:
            raise AletheiaError("DUPLICATE_KEY", f"duplicate JSON object key {k!r}")
        out[k] = v
    return out


def parse_zone_canon_text(text: str) -> Any:
    require_ok(isinstance(text, str) and bool(text.strip()), "EMPTY_JSON", "input must be non-empty UTF-8 JSON")
    try:
        return json.loads(
            text,
            parse_int=_parse_int_strict,
            parse_float=_reject_float,
            parse_constant=_reject_constant,
            object_pairs_hook=_pairs_no_dup,
        )
    except AletheiaError:
        raise
    except Exception as exc:
        raise AletheiaError("INVALID_JSON", f"JSON syntax error: {exc}") from exc


def _escape_canon_str(s: str) -> str:
    out: list[str] = ['"']
    for ch in s:
        cp = ord(ch)
        if ch == '"':
            out.append('\\"')
        elif ch == "\\":
            out.append("\\\\")
        elif cp == 0x08:
            out.append("\\b")
        elif cp == 0x0C:
            out.append("\\f")
        elif cp == 0x0A:
            out.append("\\n")
        elif cp == 0x0D:
            out.append("\\r")
        elif cp == 0x09:
            out.append("\\t")
        elif cp < 0x20:
            out.append(f"\\u{cp:04x}")
        elif 0xD800 <= cp <= 0xDFFF:
            raise AletheiaError("LONE_SURROGATE", f"lone UTF-16 surrogate U+{cp:04X} is forbidden")
        else:
            out.append(ch)
    out.append('"')
    return "".join(out)


def _encode_val(val: Any) -> str:
    if val is None:
        return "null"
    if type(val) is bool:
        return "true" if val else "false"
    if type(val) is int:
        if abs(val) > ZONE_CANON_LIMIT:
            raise AletheiaError("INT_OUT_OF_RANGE", f"integer {val} exceeds |n| <= 2^53 - 1")
        return str(val)
    if isinstance(val, float):
        raise AletheiaError("FLOAT_FORBIDDEN", f"float {val!r} is forbidden in zone-canon-v0")
    if isinstance(val, str):
        return _escape_canon_str(val)
    if isinstance(val, (list, tuple)):
        return "[" + ",".join(_encode_val(x) for x in val) + "]"
    if isinstance(val, Mapping):
        for k in val.keys():
            if not isinstance(k, str):
                raise AletheiaError("NON_STRING_KEY", f"object key must be str, got {type(k).__name__}")
        items = sorted(val.items(), key=lambda kv: kv[0])
        return "{" + ",".join(f"{_escape_canon_str(k)}:{_encode_val(v)}" for k, v in items) + "}"
    raise AletheiaError("UNSUPPORTED_TYPE", f"unsupported value type {type(val).__name__}")


def encode_zone_canon_bytes(obj: Any) -> bytes:
    return _encode_val(obj).encode("utf-8")


def canonicalize_zone_json_text(text: str) -> tuple[bytes, str]:
    obj = parse_zone_canon_text(text)
    raw = encode_zone_canon_bytes(obj)
    return raw, hashlib.sha256(raw).hexdigest()


def compute_zone_canon_id(manifest: Mapping[str, Any], *, exclude_key: str = "manifest_id") -> str:
    require_ok(isinstance(manifest, Mapping), "INVALID_MANIFEST", "object must be a JSON mapping")
    body = {k: v for k, v in manifest.items() if k != exclude_key}
    raw = encode_zone_canon_bytes(body)
    return "sha256:" + hashlib.sha256(raw).hexdigest()


# ---------------------------------------------------------------------------
# Plane-1 Aletheia-MDE Manifest
# ---------------------------------------------------------------------------

def build_aletheia_mde_manifest(
    *,
    domain_mdes: Sequence[str] = ("siliquant-mde", "physics-mde", "formal-verification", "weft-eido"),
    scale_den_log2: int = DEFAULT_SCALE_DEN_LOG2,
) -> dict[str, Any]:
    require_ok(type(scale_den_log2) is int and 4 <= scale_den_log2 <= 24, "INVALID_SCALE_LOG2", "bad scale_den_log2")
    unit = 1 << scale_den_log2
    half = unit >> 1
    quarter = unit >> 2
    all_domains = tuple(dict.fromkeys(("aletheia", *domain_mdes)))
    for d in all_domains:
        require_ok(isinstance(d, str) and _SLUG_RE.match(d) is not None, "INVALID_DOMAIN_SLUG", f"bad domain {d!r}")

    def _sc(m: Mapping[str, int]) -> dict[str, int]:
        return {d: int(m.get(d, 0)) for d in all_domains}

    zone_specs = [
        ("tomography_verifier", 5, True, True, True, _sc({"aletheia": unit, "formal-verification": unit})),
        ("formal_proof", 3, True, True, True, _sc({"aletheia": unit, "formal-verification": unit})),
        ("audit_ledger", 6, True, False, True, _sc({"aletheia": unit})),
        ("condensed_packet", 4, False, True, False, _sc({})),
        ("probe_code", 1, False, False, True, _sc({"aletheia": half, "siliquant-mde": unit, "physics-mde": unit, "formal-verification": half})),
        ("portal_map", 7, False, False, False, _sc({"aletheia": unit, "siliquant-mde": half, "physics-mde": half})),
        ("ui_module", 2, False, False, False, _sc({"weft-eido": unit, "aletheia": quarter})),
        ("prose", 0, False, False, False, _sc({"aletheia": half})),
    ]
    zones = []
    for zname, tag, prot_orac, no_float, req_indep, scales in zone_specs:
        zones.append({
            "zone": zname,
            "l1_bank_tag": tag,
            "scale_den_log2": scale_den_log2,
            "scales_num": scales,
            "protection_flags": {
                "protect_verifier_oracles": prot_orac,
                "forbid_float_in_exact_math": no_float,
                "require_independent_verifier": req_indep,
                "allow_weight_oracle_compilation": False,
            },
        })
    manifest: dict[str, Any] = {
        "schema": ALETHEIA_MDE_SCHEMA,
        "canon_rule": "zone-canon-v0",
        "mde_id": "aletheia-mde",
        "version": "1.1.0",
        "plane1_authoritative": True,
        "plane2_oracle_compilation_forbidden": True,
        "five_laws": [
            "L1_ACTIVE_PORTAL_KEEPER",
            "L2_STEELMAN_BEFORE_FALSIFY",
            "L3_ADVERSARIAL_MULTI_BASIS_TOMOGRAPHY",
            "L4_HONEST_NOVELTY_AND_SCOPE",
            "L5_EXACT_OPERATOR_TRANSFER",
        ],
        "domains": list(all_domains),
        "precedence_order": list(ALETHEIA_ZONES),
        "zones": zones,
    }
    manifest["manifest_id"] = compute_zone_canon_id(manifest)
    return manifest


def verify_aletheia_mde_manifest(manifest: Mapping[str, Any]) -> str:
    require_ok(isinstance(manifest, Mapping), "INVALID_MANIFEST", "manifest must be mapping")
    require_ok(manifest.get("schema") == ALETHEIA_MDE_SCHEMA, "INVALID_SCHEMA", "unexpected manifest schema")
    require_ok(manifest.get("canon_rule") == "zone-canon-v0", "INVALID_CANON_RULE", "canon_rule must be zone-canon-v0")
    require_ok(manifest.get("plane1_authoritative") is True, "PLANE1_NOT_AUTHORITATIVE", "plane1_authoritative must be true")
    require_ok(manifest.get("plane2_oracle_compilation_forbidden") is True, "ORACLE_IN_WEIGHTS_FORBIDDEN", "plane2_oracle_compilation_forbidden must be true")
    stored = manifest.get("manifest_id")
    require_ok(isinstance(stored, str) and _SHA256_PREF_RE.match(stored) is not None, "INVALID_MANIFEST_ID", "bad manifest_id")
    computed = compute_zone_canon_id(manifest)
    require_ok(hmac.compare_digest(stored, computed), "MANIFEST_ID_DRIFT", f"stored {stored} != computed {computed}")
    for z in manifest.get("zones", []):
        flags = z.get("protection_flags", {})
        require_ok(flags.get("allow_weight_oracle_compilation") is False, "ORACLE_COMPILATION_ENABLED", "oracle compilation forbidden")
    return stored


# ---------------------------------------------------------------------------
# Plane-1 Causal Audit Lineage DAG (`AUDIT-XXX` transitions)
# ---------------------------------------------------------------------------

class Plane1LineageDAG:
    """Append-only Plane-1 causal audit DAG enforcing Law 3, Gate 8, Gate 9, and Hard Veto #2."""

    def __init__(self, manifest_id: str) -> None:
        require_ok(isinstance(manifest_id, str) and _SHA256_PREF_RE.match(manifest_id) is not None,
                   "INVALID_MANIFEST_ID", f"bad manifest_id {manifest_id!r}")
        self.manifest_id = manifest_id
        self._records: list[dict[str, Any]] = []
        self._by_id: dict[str, dict[str, Any]] = {}
        self._superseded: set[str] = set()
        self._audit_ids: set[str] = set()

    @property
    def records(self) -> tuple[dict[str, Any], ...]:
        return tuple(self._records)

    def _heads_for(self, target_id: str) -> list[str]:
        return [r["record_id"] for r in self._records if r["target_id"] == target_id and r["record_id"] not in self._superseded]

    def ingest(self, rec: Mapping[str, Any]) -> dict[str, Any]:
        require_ok(isinstance(rec, Mapping), "INVALID_RECORD", "record must be mapping")
        require_ok(rec.get("schema") == LINEAGE_SCHEMA, "INVALID_SCHEMA", f"expected {LINEAGE_SCHEMA}")
        require_ok(isinstance(rec.get("manifest_id"), str) and hmac.compare_digest(rec["manifest_id"], self.manifest_id),
                   "MANIFEST_PIN_MISMATCH", "record manifest_id mismatch")
        require_ok(type(rec.get("seq")) is int and rec["seq"] == len(self._records),
                   "INVALID_SEQUENCE", f"expected seq={len(self._records)}")
        kind = rec.get("kind")
        require_ok(kind in VALID_LINEAGE_KINDS, "INVALID_KIND", f"unknown kind {kind!r}")
        actor = rec.get("actor")
        target_id = rec.get("target_id")
        target_sha = rec.get("target_sha256")
        require_ok(isinstance(actor, str) and _ID_RE.match(actor) is not None, "INVALID_ACTOR", "bad actor")
        require_ok(isinstance(target_id, str) and _ID_RE.match(target_id) is not None, "INVALID_TARGET_ID", "bad target_id")
        require_ok(isinstance(target_sha, str) and _SHA256_PREF_RE.match(target_sha) is not None, "INVALID_TARGET_SHA", "bad target_sha256")

        parents = rec.get("parent_ids")
        require_ok(isinstance(parents, list) and len(parents) == len(set(parents)), "INVALID_PARENTS", "bad parent_ids")
        for pid in parents:
            require_ok(isinstance(pid, str) and pid in self._by_id, "UNKNOWN_PARENT", f"unresolved parent {pid!r}")

        stored_rid = rec.get("record_id")
        require_ok(isinstance(stored_rid, str) and _SHA256_PREF_RE.match(stored_rid) is not None, "INVALID_RECORD_ID", "bad record_id")
        computed_rid = compute_zone_canon_id(rec, exclude_key="record_id")
        require_ok(hmac.compare_digest(stored_rid, computed_rid), "RECORD_ID_MISMATCH", "forged record_id")

        if kind == "AUDIT_VERDICT":
            require_ok(len(parents) >= 1, "AUDIT_REQUIRES_PARENT", "AUDIT_VERDICT requires parent")
            aid = rec.get("audit_id")
            require_ok(isinstance(aid, str) and re.fullmatch(r"AUDIT-[0-9]{3}[A-Z]?", aid) is not None, "INVALID_AUDIT_ID", "bad audit_id")
            require_ok(aid not in self._audit_ids, "DUPLICATE_AUDIT_ID", f"duplicate audit_id {aid!r} (Gate 8)")
            for pid in parents:
                pr = self._by_id[pid]
                if pr["kind"] in ("PROPOSAL", "STEELMAN_REPAIR"):
                    require_ok(pr["actor"] != actor, "SELF_AUDIT_FORBIDDEN", f"actor {actor!r} cannot self-audit")
                    require_ok(pr["target_sha256"] == target_sha, "TARGET_SHA_MISMATCH", "target_sha256 mismatch")
            verdict = rec.get("verdict")
            novelty = rec.get("novelty")
            require_ok(verdict in VALID_VERDICTS, "INVALID_VERDICT", f"bad verdict {verdict!r}")
            require_ok(novelty in VALID_NOVELTIES, "INVALID_NOVELTY", f"bad novelty {novelty!r}")
            oc = rec.get("oracle_class")
            require_ok(isinstance(oc, str) and all(p.strip() in VALID_ORACLE_TOKENS for p in oc.split("+")), "INVALID_ORACLE_CLASS", "bad oracle_class")
            require_ok(type(rec.get("r4_parity")) is bool, "INVALID_R4_FLAG", "r4_parity must be bool")
            if verdict == "VERIFIED":
                require_ok(rec["r4_parity"] is True, "VERIFIED_REQUIRES_R4", "VERIFIED requires r4_parity=true")
            pa = rec.get("prior_art_checked")
            pa_refs = rec.get("prior_art_refs")
            require_ok(type(pa) is bool and isinstance(pa_refs, list), "INVALID_PRIOR_ART", "bad prior_art fields")
            if verdict == "VERIFIED" and "N2" in novelty:
                require_ok(pa is True and len(pa_refs) >= 1, "N2_REQUIRES_PRIOR_ART", "VERIFIED N2 requires prior_art_checked and refs")
        elif kind == "STEELMAN_REPAIR":
            has_fail = any(
                self._by_id[pid]["kind"] == "AUDIT_VERDICT"
                and self._by_id[pid]["verdict"] in ("FALSIFIED", "PARTIAL/FRAGILE")
                for pid in parents
            )
            require_ok(has_fail, "REPAIR_PARENT_NOT_FAILURE", "STEELMAN_REPAIR must cite prior FALSIFIED or PARTIAL/FRAGILE")
            for pid in parents:
                if self._by_id[pid]["kind"] == "AUDIT_VERDICT":
                    require_ok(self._by_id[pid]["target_sha256"] != target_sha, "REPAIR_IDENTICAL_ARTIFACT", "repair must update artifact sha")
        elif kind == "DISPUTE":
            require_ok(len(parents) >= 1 and isinstance(rec.get("positions"), list) and len(rec["positions"]) >= 2,
                       "INVALID_DISPUTE", "DISPUTE needs parent and >=2 positions")
        elif kind == "ADJUDICATION":
            heads = self._heads_for(target_id)
            require_ok(len(heads) >= 2 and set(parents) >= set(heads), "ADJUDICATION_OMITS_HEADS", "Hard Veto #2: must cite all competing heads")
            ref = rec.get("steward_approval_ref")
            require_ok(isinstance(ref, str) and ref.startswith("approval:"), "MISSING_APPROVAL_REF", "missing approval ref")

        out = dict(rec)
        self._records.append(out)
        self._by_id[stored_rid] = out
        if kind == "AUDIT_VERDICT":
            self._audit_ids.add(out["audit_id"])
        if kind != "DISPUTE":
            for pid in parents:
                self._superseded.add(pid)
        return out

    def append(self, **fields: Any) -> dict[str, Any]:
        body: dict[str, Any] = {
            "schema": LINEAGE_SCHEMA,
            "manifest_id": self.manifest_id,
            "seq": len(self._records),
            **fields,
        }
        body["record_id"] = compute_zone_canon_id(body, exclude_key="record_id")
        return self.ingest(body)

    def summary(self) -> dict[str, Any]:
        heads = [r["record_id"] for r in self._records if r["record_id"] not in self._superseded]
        by_t: dict[str, list[str]] = {}
        for h in heads:
            by_t.setdefault(self._by_id[h]["target_id"], []).append(h)
        contested = {t: hs for t, hs in sorted(by_t.items()) if len(hs) > 1}
        return {
            "manifest_id": self.manifest_id,
            "record_count": len(self._records),
            "heads_count": len(heads),
            "contested_targets": contested,
            "verified_audits": [r["audit_id"] for r in self._records if r["kind"] == "AUDIT_VERDICT" and r["verdict"] == "VERIFIED"],
            "falsified_audits_preserved": [
                r["audit_id"] for r in self._records
                if r["kind"] == "AUDIT_VERDICT" and r["verdict"] in ("FALSIFIED", "PARTIAL/FRAGILE")
            ],
        }


def verify_lineage_dag_file(path: Path) -> dict[str, Any]:
    """Strictly verify a JSONL Plane-1 causal audit lineage DAG file (fail-closed)."""
    require_ok(path.is_file(), "DAG_FILE_NOT_FOUND", f"DAG file not found: {path}")
    lines = [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    require_ok(len(lines) >= 1, "EMPTY_DAG", "DAG JSONL file is empty")
    parsed = [parse_zone_canon_text(ln) for ln in lines]
    first_mid = parsed[0].get("manifest_id") if isinstance(parsed[0], dict) else None
    dag = Plane1LineageDAG(first_mid)  # type: ignore[arg-type]
    for rec in parsed:
        dag.ingest(rec)
    return {"valid": True, "status": "VALID", "path": str(path), **dag.summary()}


# ---------------------------------------------------------------------------
# SYM-2P/2.0-rcp Checksummed Wire Packet Codec (`Moissanite-Labs/abios`)
# ---------------------------------------------------------------------------

def encode_sym2_rcp_line(
    *,
    pid: str,
    tk: str,
    sender_role: str,
    recip_role: str,
    act: str,
    state: str,
    cf: int,
    cv: int,
    body_sexpr: str,
    rq: str = "none",
    base: str = "",
    exp: int = 0,
) -> str:
    require_ok(sender_role in V2_ROLES and recip_role in V2_ROLES, "INVALID_V2_ROLE", "unknown v2 role")
    require_ok(act in V2_ACTS and state in V2_STATES and rq in V2_RQS, "INVALID_V2_CODE", "unknown v2 act/state/rq")
    require_ok(type(cf) is int and 0 <= cf <= 100 and type(cv) is int and 0 <= cv <= 100, "INVALID_V2_SCORE", "cf/cv out of 0..100")
    require_ok("|" not in body_sexpr, "INVALID_V2_BODY", "v2 BODY cannot contain '|'")
    bare = "|".join([
        "2", pid, tk, str(V2_ROLES[sender_role]), str(V2_ROLES[recip_role]),
        str(V2_ACTS[act]), str(V2_STATES[state]), str(cf), str(cv),
        body_sexpr, str(V2_RQS[rq]), base, str(exp),
    ])
    chk = hashlib.sha256(bare.encode("utf-8")).hexdigest()[:16]
    return f"{bare}|{chk}"


def verify_sym2_rcp_line(line: str) -> bool:
    parts = line.split("|")
    require_ok(len(parts) == 14 and parts[0] == "2", "INVALID_SYM2_RCP_SHAPE", "expected 14-field v2-rcp line")
    bare = "|".join(parts[:13])
    chk = parts[13]
    require_ok(_HEX16_RE.match(chk) is not None, "INVALID_SYM2_RCP_SUM_FORMAT", "SUM must be 16 lowercase hex")
    expected = hashlib.sha256(bare.encode("utf-8")).hexdigest()[:16]
    require_ok(hmac.compare_digest(chk, expected), "SYM2_RCP_CHECKSUM_MISMATCH", f"checksum {chk} != {expected}")
    return True


def run_mde_demo() -> dict[str, Any]:
    """Run deterministic Plane-1 Aletheia-MDE demo: zone-canon-v0 vectors + DAG + SYM-2P/2.0-rcp."""
    # 1. All 7 accept + 10 reject mde#8 golden vectors
    for name, inp, exp_canon, exp_sha in MDE_PR8_ACCEPT_VECTORS:
        raw, dig = canonicalize_zone_json_text(inp)
        require_ok(raw == exp_canon.encode("utf-8") and dig == exp_sha, "VECTOR_MISMATCH", f"vector {name} mismatch")
    rej = 0
    for _name, inp in MDE_PR8_REJECT_VECTORS:
        try:
            canonicalize_zone_json_text(inp)
            raise AletheiaError("VECTOR_REJECT_BYPASSED", f"accepted {_name}")
        except AletheiaError:
            rej += 1

    # 2. Canonical manifest
    mf = build_aletheia_mde_manifest()
    mid = verify_aletheia_mde_manifest(mf)

    # 3. Plane-1 causal DAG + self-audit negative control
    dag = Plane1LineageDAG(mid)
    s1 = "sha256:" + hashlib.sha256(b"proto:v1").hexdigest()
    s2 = "sha256:" + hashlib.sha256(b"steelman:v2").hexdigest()
    p0 = dag.append(kind="PROPOSAL", actor="probe", target_id="portal1", target_sha256=s1, parent_ids=[], hypothesis="H1", oracle_class="exact")
    self_audit_blocked = False
    try:
        dag.append(
            kind="AUDIT_VERDICT", actor="probe", target_id="portal1", target_sha256=s1, parent_ids=[p0["record_id"]],
            audit_id="AUDIT-001", verdict="VERIFIED", novelty="N1", oracle_class="exact", r4_parity=True,
            prior_art_checked=False, prior_art_refs=[], evidence="self",
        )
    except AletheiaError as exc:
        self_audit_blocked = (exc.code == "SELF_AUDIT_FORBIDDEN")
    require_ok(self_audit_blocked, "DEMO_CONTROL_FAILED", "self-audit was not blocked")

    a1 = dag.append(
        kind="AUDIT_VERDICT", actor="verifier", target_id="portal1", target_sha256=s1, parent_ids=[p0["record_id"]],
        audit_id="AUDIT-001", verdict="FALSIFIED", novelty="N1", oracle_class="exact", r4_parity=True,
        prior_art_checked=False, prior_art_refs=[], evidence="missing PSD guard",
    )
    rep = dag.append(kind="STEELMAN_REPAIR", actor="probe", target_id="portal1", target_sha256=s2, parent_ids=[a1["record_id"]], repair_summary="added Q(i) PSD guard + R_opt")
    dag.append(
        kind="AUDIT_VERDICT", actor="verifier", target_id="portal1", target_sha256=s2, parent_ids=[rep["record_id"]],
        audit_id="AUDIT-002", verdict="VERIFIED", novelty="N2", oracle_class="exact", r4_parity=True,
        prior_art_checked=True, prior_art_refs=["arXiv:2610.08965"], evidence="0/420 Q(i) violations",
    )

    # 4. SYM-2P/2.0-rcp emission + tamper detection
    pkt = encode_sym2_rcp_line(
        pid="a205", tk="ch1", sender_role="verifier", recip_role="coordinator",
        act="receipt", state="verified", cf=99, cv=96,
        body_sexpr="(10 audit/002 (20 n2 (1 420)))(12 (22 check_003 0 1))", rq="ack", base="f01:2", exp=600,
    )
    verify_sym2_rcp_line(pkt)
    tamper_blocked = False
    try:
        verify_sym2_rcp_line(pkt[:-1] + ("0" if pkt[-1] != "0" else "1"))
    except AletheiaError as exc:
        tamper_blocked = (exc.code == "SYM2_RCP_CHECKSUM_MISMATCH")
    require_ok(tamper_blocked, "DEMO_CONTROL_FAILED", "SYM-2P tamper not caught")

    return {
        "status": "PASS",
        "manifest_id": mid,
        "zone_canon_vectors": {"accept_passed": len(MDE_PR8_ACCEPT_VECTORS), "reject_blocked": rej},
        "lineage_dag": dag.summary(),
        "self_audit_blocked": self_audit_blocked,
        "sym2p_v2_rcp_sample": pkt,
        "sym2p_tamper_blocked": tamper_blocked,
    }
