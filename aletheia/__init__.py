"""
aletheia: Zero-dependency Python 3 stdlib toolkit for The Aletheia Method
(Portal-Driven Resonance, Own-Terms-First, Transformational Steelman & Adversarial Tomography).

Zero external dependencies. Zero bare asserts on trust paths.
Safe under all three R4 isolated modes:
  python3 -I -B
  python3 -I -O -B
  python3 -I -B -W error
"""
from __future__ import annotations

__version__ = "2.1.0"

from .strict_io import (
    AletheiaError,
    parse_strict_json_text,
    loads_strict_json,
    load_strict_json_file,
    load_strict_jsonl_file,
)
from .scaffold import init_workspace
from .audit_check import run_audit_check, verify_ancestor_dir_modes, audit_ancestor_dir_permissions
from .mutator import run_mutation_suite, discover_local_refusal_wrappers, discover_imported_refusal_wrappers
from .diagnose import diagnose_expedition
from .handoff import validate_handoff_manifest, create_handoff_template
from .installer import install_adapter
from .calculus import list_glyphs, eval_calculus_expression, run_calculus_self_test
from .gates_v2 import (
    evaluate_r6_r7_gate,
    certify_two_direction_r3,
    evaluate_sampled_integrity,
    certify_oracle_contract,
    certify_gate8_subspace_latch,
    certify_transformational_steelman,
    certify_own_terms_phase1,
    run_v2_gates_self_test,
)
from .safety import scan_hidden_unicode, scan_text_safety_surface, scan_directory_safety_surface
from .context_hygiene import (
    audit_context_hygiene,
    evaluate_reactivation_policy,
    run_context_hygiene_demo,
    run_context_hygiene_self_test,
)

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
    "discover_imported_refusal_wrappers",
    "diagnose_expedition",
    "validate_handoff_manifest",
    "create_handoff_template",
    "install_adapter",
    "list_glyphs",
    "eval_calculus_expression",
    "run_calculus_self_test",
    "evaluate_r6_r7_gate",
    "certify_two_direction_r3",
    "evaluate_sampled_integrity",
    "certify_oracle_contract",
    "certify_gate8_subspace_latch",
    "certify_transformational_steelman",
    "certify_own_terms_phase1",
    "run_v2_gates_self_test",
    "scan_hidden_unicode",
    "scan_text_safety_surface",
    "scan_directory_safety_surface",
    "evaluate_reactivation_policy",
    "audit_context_hygiene",
    "run_context_hygiene_demo",
    "run_context_hygiene_self_test",
]
