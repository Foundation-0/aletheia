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

__version__ = "1.2.0"

from .strict_io import AletheiaError, parse_strict_json_text, load_strict_json_file
from .scaffold import init_workspace
from .audit_check import run_audit_check
from .mutator import run_mutation_suite
from .diagnose import diagnose_expedition
from .handoff import validate_handoff_manifest, create_handoff_template
from .installer import install_adapter

__all__ = [
    "__version__",
    "AletheiaError",
    "parse_strict_json_text",
    "load_strict_json_file",
    "init_workspace",
    "run_audit_check",
    "run_mutation_suite",
    "diagnose_expedition",
    "validate_handoff_manifest",
    "create_handoff_template",
    "install_adapter",
]
