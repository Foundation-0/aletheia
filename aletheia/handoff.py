"""
`aletheia handoff <manifest.json> [--init-template]`: Generate and strictly validate
portable `aletheia.compute_handoff.v1` Wave 2+ compute handoff manifests for stronger machines.
"""
from __future__ import annotations

from datetime import date
import json
from pathlib import Path
import re
from typing import Any

from .strict_io import (
    AletheiaError,
    load_strict_json_file,
    require_ok,
    scan_text_for_leaks,
    write_lf_text,
)

SUPPORTED_SCHEMAS = ("aletheia.compute_handoff.v1", "expedition.next_waves.v1")
VALID_ORACLE_TOKENS = {"exact", "sampled", "anchor"}
_DATE_RE = re.compile(r"\A[0-9]{4}-[0-9]{2}-[0-9]{2}\Z", re.ASCII)


def build_handoff_template_dict(
    *,
    source_repo: str = "https://github.com/org/repo",
    snapshot_date: str | None = None,
    domain: str = "general",
) -> dict[str, Any]:
    snap = snapshot_date or date.today().isoformat()
    return {
        "schema": "aletheia.compute_handoff.v1",
        "generated_by": "aletheia-cli",
        "snapshot_date": snap,
        "source_repo": source_repo,
        "compute_tiers": {
            "tier_1_cpu": {
                "label": "Tier 1: Multi-Core Exact & Scientific CPU",
                "hardware": "16-32 CPU cores, 32-64 GiB RAM",
                "toolchain": ["python3>=3.11", "git"],
            },
            "tier_2_formal_heavy_exact": {
                "label": "Tier 2: Heavy Exact Algebra & Machine-Checked Proof Assistants",
                "hardware": "64+ CPU cores, 128-256 GiB RAM",
                "toolchain": ["python3>=3.11", "lean4", "lake", "git"],
            },
        },
        "waves": [
            {
                "wave_id": "Wave-2A",
                "name": f"Wave 2 Continuation ({domain})",
                "tasks": [
                    {
                        "id": "W2A-1",
                        "title": f"Heavy exact verification follow-up for {domain}",
                        "compute_tier": "tier_1_cpu",
                        "target_repos": [source_repo],
                        "bootstrap_command": "python3 -I -O -B -W error tests/run_all.py",
                        "hypothesis": "State the explicit falsifiable mathematical or scientific hypothesis to test in Wave 2.",
                        "oracle_class": "exact",
                        "falsification_gate": "Falsified if any clean-room exact check violates the claimed bound or fails R4/R5 parity.",
                    }
                ],
            }
        ],
    }


def create_handoff_template(
    out_path: Path,
    *,
    source_repo: str = "https://github.com/org/repo",
    domain: str = "general",
    force: bool = False,
) -> dict[str, Any]:
    if out_path.exists() and not force:
        raise AletheiaError("MANIFEST_EXISTS", f"manifest already exists at {out_path} (pass --force to overwrite)")
    tpl = build_handoff_template_dict(source_repo=source_repo, domain=domain)
    write_lf_text(out_path, json.dumps(tpl, indent=2) + "\n")
    return {"status": "TEMPLATE_CREATED", "path": str(out_path), "schema": tpl["schema"]}


_LEGACY_ORACLE_PART_RE = re.compile(r"\A(exact|sampled|anchor)(?:\s*\([^()]+\))?\Z")


def _validate_oracle_class(raw: Any, task_id: str, *, allow_qualifiers: bool = False) -> list[str]:
    if not isinstance(raw, str) or not raw.strip():
        raise AletheiaError("INVALID_ORACLE_CLASS", f"task {task_id}: oracle_class must be a non-empty string")
    parts = [p.strip() for p in raw.split("+")]
    if not parts:
        raise AletheiaError("INVALID_ORACLE_CLASS", f"task {task_id}: empty oracle_class")
    normalized: list[str] = []
    for p in parts:
        if p in VALID_ORACLE_TOKENS:
            normalized.append(p)
        elif allow_qualifiers:
            m = _LEGACY_ORACLE_PART_RE.match(p)
            if m is not None:
                normalized.append(m.group(1))
            else:
                raise AletheiaError(
                    "INVALID_ORACLE_CLASS",
                    f"task {task_id}: oracle_class {raw!r} must combine only {sorted(VALID_ORACLE_TOKENS)}",
                )
        else:
            raise AletheiaError(
                "INVALID_ORACLE_CLASS",
                f"task {task_id}: oracle_class {raw!r} must combine only {sorted(VALID_ORACLE_TOKENS)}",
            )
    return normalized


def validate_handoff_manifest(path: Path) -> dict[str, Any]:
    """
    Strictly validate a portable compute handoff JSON manifest under R1/R2/R3:
      - Zero CRLF, zero duplicate JSON keys, zero NaN/Infinity, zero personal path/secret leaks.
      - Required schema, metadata, compute_tiers, waves, tasks, cross-referenced tiers,
        unique task IDs, valid oracle_class, non-empty bootstrap_command & falsification_gate.
    """
    data = load_strict_json_file(path, allow_float=True, require_object=True)
    raw_text = path.read_text(encoding="utf-8")
    leaks = scan_text_for_leaks(raw_text)
    errors: list[dict[str, str]] = []
    for lk in leaks:
        errors.append({"code": f"LEAK_{lk['kind'].upper()}", "message": f"line {lk['line']}: matched {lk['rule']}"})

    schema = data.get("schema")
    if schema not in SUPPORTED_SCHEMAS:
        errors.append({
            "code": "UNSUPPORTED_SCHEMA",
            "message": f"schema {schema!r} not in {SUPPORTED_SCHEMAS}",
        })

    for field in ("generated_by", "snapshot_date"):
        val = data.get(field)
        if not isinstance(val, str) or not val.strip():
            errors.append({"code": "MISSING_REQUIRED_FIELD", "message": f"missing or empty {field!r}"})

    snap = data.get("snapshot_date")
    if isinstance(snap, str) and _DATE_RE.match(snap) is None:
        errors.append({"code": "INVALID_DATE_FORMAT", "message": f"snapshot_date {snap!r} must match YYYY-MM-DD"})

    if schema == "aletheia.compute_handoff.v1":
        sr = data.get("source_repo")
        if not isinstance(sr, str) or not sr.strip():
            errors.append({"code": "MISSING_REQUIRED_FIELD", "message": "missing or empty 'source_repo'"})

    tiers = data.get("compute_tiers")
    valid_tiers: set[str] = set()
    if not isinstance(tiers, dict) or len(tiers) == 0:
        errors.append({"code": "MISSING_COMPUTE_TIERS", "message": "compute_tiers must be a non-empty object"})
    else:
        for tid, tspec in tiers.items():
            if not isinstance(tspec, dict):
                errors.append({"code": "INVALID_TIER_SPEC", "message": f"tier {tid!r} must be an object"})
                continue
            valid_tiers.add(tid)
            for tf in ("label", "hardware"):
                if not isinstance(tspec.get(tf), str) or not tspec[tf].strip():
                    errors.append({"code": "MISSING_TIER_FIELD", "message": f"tier {tid!r} missing non-empty {tf!r}"})
            tc = tspec.get("toolchain")
            if not isinstance(tc, list) or len(tc) == 0 or not all(isinstance(x, str) and x.strip() for x in tc):
                errors.append({"code": "INVALID_TIER_TOOLCHAIN", "message": f"tier {tid!r} toolchain must be non-empty list[str]"})

    waves = data.get("waves")
    seen_task_ids: set[str] = set()
    total_tasks = 0
    tier_counts: dict[str, int] = {}

    if not isinstance(waves, list) or len(waves) == 0:
        errors.append({"code": "MISSING_WAVES", "message": "waves must be a non-empty list"})
    else:
        for w_idx, wave in enumerate(waves):
            if not isinstance(wave, dict):
                errors.append({"code": "INVALID_WAVE", "message": f"waves[{w_idx}] must be an object"})
                continue
            wid = wave.get("wave_id")
            if not isinstance(wid, str) or not wid.strip():
                errors.append({"code": "MISSING_WAVE_ID", "message": f"waves[{w_idx}] missing non-empty wave_id"})
            wname = wave.get("name")
            if not isinstance(wname, str) or not wname.strip():
                errors.append({"code": "MISSING_WAVE_NAME", "message": f"waves[{w_idx}] missing non-empty name"})
            tasks = wave.get("tasks")
            if not isinstance(tasks, list) or len(tasks) == 0:
                errors.append({"code": "EMPTY_WAVE_TASKS", "message": f"wave {wid!r} must have non-empty tasks list"})
                continue
            for t_idx, task in enumerate(tasks):
                if not isinstance(task, dict):
                    errors.append({"code": "INVALID_TASK", "message": f"wave {wid!r} tasks[{t_idx}] must be an object"})
                    continue
                total_tasks += 1
                tid = task.get("id")
                if not isinstance(tid, str) or not tid.strip():
                    errors.append({"code": "MISSING_TASK_ID", "message": f"wave {wid!r} tasks[{t_idx}] missing non-empty id"})
                    tid = f"{wid}[{t_idx}]"
                elif tid in seen_task_ids:
                    errors.append({"code": "DUPLICATE_TASK_ID", "message": f"duplicate task id {tid!r}"})
                else:
                    seen_task_ids.add(tid)

                for req_str in ("title", "bootstrap_command", "falsification_gate"):
                    val = task.get(req_str)
                    if not isinstance(val, str) or not val.strip():
                        errors.append({"code": "MISSING_TASK_FIELD", "message": f"task {tid}: missing non-empty {req_str!r}"})

                hyp = task.get("hypothesis") if "hypothesis" in task else task.get("mathematical_hypothesis")
                if not isinstance(hyp, str) or not hyp.strip():
                    errors.append({"code": "MISSING_TASK_HYPOTHESIS", "message": f"task {tid}: missing non-empty 'hypothesis'"})

                ct = task.get("compute_tier")
                if not isinstance(ct, str) or ct not in valid_tiers:
                    errors.append({
                        "code": "UNKNOWN_COMPUTE_TIER",
                        "message": f"task {tid}: compute_tier {ct!r} not declared in compute_tiers",
                    })
                else:
                    tier_counts[ct] = tier_counts.get(ct, 0) + 1

                trepos = task.get("target_repos")
                if not isinstance(trepos, list) or len(trepos) == 0 or not all(isinstance(x, str) and x.strip() for x in trepos):
                    errors.append({"code": "INVALID_TARGET_REPOS", "message": f"task {tid}: target_repos must be non-empty list[str]"})

                try:
                    _validate_oracle_class(
                        task.get("oracle_class"),
                        tid,
                        allow_qualifiers=(schema == "expedition.next_waves.v1"),
                    )
                except AletheiaError as exc:
                    errors.append({"code": exc.code, "message": exc.message})

    passed = len(errors) == 0
    return {
        "valid": passed,
        "status": "VALID" if passed else "INVALID",
        "path": str(path),
        "schema": schema,
        "wave_count": len(waves) if isinstance(waves, list) else 0,
        "task_count": total_tasks,
        "tasks_by_tier": tier_counts,
        "errors": errors,
    }
