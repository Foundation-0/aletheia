"""
aletheia: Zero-dependency Python 3 stdlib toolkit for The Aletheia Method
(Portal-Driven Resonance & Adversarial Tomography).

Zero external dependencies. Zero bare asserts on trust paths.
Safe under:
  python3 -I -B
  python3 -I -O -B
  python3 -I -B -W error
"""
from __future__ import annotations

__version__ = "1.4.0"

from .strict_io import (
    AletheiaError,
    parse_strict_json_text,
    loads_strict_json,
    load_strict_json_file,
    load_strict_jsonl_file,
)
from .scaffold import init_workspace
from .audit_check import run_audit_check, verify_ancestor_dir_modes, audit_ancestor_dir_permissions
from .mutator import run_mutation_suite, discover_local_refusal_wrappers
from .diagnose import diagnose_expedition
from .handoff import validate_handoff_manifest, create_handoff_template
from .installer import install_adapter
from .calculus import list_glyphs, eval_calculus_expression, run_calculus_self_test

__all__ = [
    "__version__",
    "AletheiaError",
    "parse_strict_json_text",
    "loads_strict_json",
    "load_strict_json_file",
    "load_strict_jsonl_file",
    "init_workspace",
    "run_audit_check",
    "verify_ancestor_dir_modes",
    "audit_ancestor_dir_permissions",
    "run_mutation_suite",
    "discover_local_refusal_wrappers",
    "diagnose_expedition",
    "validate_handoff_manifest",
    "create_handoff_template",
    "install_adapter",
    "list_glyphs",
    "eval_calculus_expression",
    "run_calculus_self_test",
]
