"""
`aletheia.safety`: Deterministic Static Agent-Safety-Surface Scanner (`CYA-GAP-01..06`, AUDIT-078R).

Reverse-extracted from JD Pruett's `cover-your-ais` threat taxonomy into zero-float,
pure Python 3 stdlib deterministic scanners integrated into `aletheia audit-check --safety-scan`:
  - CYA-GAP-01: Hidden / Trojan-Source Unicode (ZWSP/BOM, CVE-2021-42574 BiDi controls, Tag smuggling)
  - CYA-GAP-02: Unpinned MCP tags, auto-yes package runners, permission-bypass flags, and session hooks
  - CYA-GAP-03: Unguarded recursive force-delete of shell variables without active nounset or `:?` guard
  - CYA-GAP-04: Untrusted CI workflow privilege (`pull_request_target` with secrets or write permissions)
  - CYA-GAP-05: Prose-only governance illusions & host-home tilde path dependencies in rule/prompt docs
  - CYA-GAP-06: Optional host-hygiene checks (interactive delete aliases & cloud-sync folder hazards)
"""
from __future__ import annotations

from pathlib import Path
import re
from typing import Any

_SKIP_DIRS = {".git", "__pycache__", ".venv", "venv", "node_modules", "dist", "build"}
_TEXT_EXTS = {".py", ".md", ".sh", ".bash", ".zsh", ".yml", ".yaml", ".json", ".toml", ".txt", ".mdc", ".cfg", ".ini"}

_ZERO_WIDTH_CODEPOINTS = frozenset({0x200B, 0x200C, 0x200D, 0x200E, 0x200F, 0x2060, 0xFEFF})
_BIDI_CODEPOINTS = frozenset({0x061C, 0x202A, 0x202B, 0x202C, 0x202D, 0x202E, 0x2066, 0x2067, 0x2068, 0x2069})

_MCP_BYPASS_RULES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"@" + r"latest\b"), "unpinned_latest_tag"),
    (re.compile(r"\bnpx\b[^\n]*?(?:\s-[A-Za-z]*y[A-Za-z]*\b|\s--yes\b)"), "npx_auto_yes"),
    (re.compile(r"--dangerously-" + r"skip-permissions\b"), "dangerously_skip_permissions"),
    (re.compile(r"(?<!\w)--" + r"yolo\b"), "yolo_mode_flag"),
    (re.compile(r"\bSession" + r"Start\b"), "session_start_hook"),
)

_SET_NOUNSET_ON_RE = re.compile(r"(?:^|[;&|]\s*)set\s+(?:-[A-Za-z]*u[A-Za-z]*|-o\s+nounset)\b")
_SET_NOUNSET_OFF_RE = re.compile(r"(?:^|[;&|]\s*)set\s+(?:\+[A-Za-z]*u[A-Za-z]*|\+o\s+nounset)\b")
_RM_CMD_RE = re.compile(r"(?:^|[;&|]\s*)rm\s+([^\n;&|]+)")
_VAR_REF_RE = re.compile(r"\$(?:\{([^}]+)\}|([A-Za-z_][A-Za-z0-9_]*))")

_CI_PRT_RE = re.compile(r"\bpull_request_target\b")
_CI_PRIV_RE = re.compile(
    r"(?:secrets\s*(?:\.|\[\s*['\"])|toJSON\s*\(\s*secrets\s*\)|\bwrite-all\b|\b[a-z-]+:\s*write\b)",
    re.IGNORECASE,
)

_PROSE_RULE_RE = re.compile(
    r"\b(?:commit\s+only\s+when\s+asked|no\s+prs\b|never\s+push|code\s+freeze|git\s+add\s+-A)\b",
    re.IGNORECASE,
)
_TILDE_PATH_RE = re.compile(r"(?:^|[\s(`\"'])~/[A-Za-z0-9._/-]+")

_ALIAS_RM_RE = re.compile(r"\balias\s+rm\s*=")
_CLOUD_SYNC_RE = re.compile(r"(?:Mobile\s+Documents|iCloud|Dropbox|OneDrive)", re.IGNORECASE)


def _strip_shell_comment(line: str) -> str:
    in_single = False
    in_double = False
    for idx, ch in enumerate(line):
        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        elif ch == "#" and not in_single and not in_double:
            return line[:idx]
    return line


def _rm_args_are_recursive_force(tokens: list[str]) -> bool:
    has_r = False
    has_f = False
    for tok in tokens:
        if tok == "--":
            break
        if tok in ("--recursive",):
            has_r = True
        elif tok in ("--force",):
            has_f = True
        elif tok.startswith("-") and not tok.startswith("--"):
            flags = tok[1:]
            if "r" in flags or "R" in flags:
                has_r = True
            if "f" in flags:
                has_f = True
    return has_r and has_f


def scan_hidden_unicode(text: str, file_label: str = "<input>") -> list[dict[str, Any]]:
    """CYA-GAP-01: Detect zero-width/BOM, CVE-2021-42574 BiDi controls, and Unicode Tags."""
    if not isinstance(text, str):
        raise ValueError("SAFETY_TEXT_NOT_STR")
    findings: list[dict[str, Any]] = []
    line = 1
    col = 0
    for ch in text:
        if ch == "\n":
            line += 1
            col = 0
            continue
        col += 1
        cp = ord(ch)
        cat: str | None = None
        if cp in _ZERO_WIDTH_CODEPOINTS:
            cat = "zero_width_or_bom"
        elif cp in _BIDI_CODEPOINTS:
            cat = "bidi_trojan_source"
        elif 0xE0000 <= cp <= 0xE007F:
            cat = "unicode_tag_smuggling"
        if cat is not None:
            findings.append(
                {
                    "gap_id": "CYA-GAP-01",
                    "file": file_label,
                    "line": line,
                    "col": col,
                    "codepoint": f"U+{cp:04X}",
                    "category": cat,
                }
            )
    return findings


def scan_text_safety_surface(
    text: str,
    file_label: str = "<input>",
    *,
    include_host_hygiene: bool = False,
) -> dict[str, Any]:
    """Scan one text artifact for CYA-GAP-01..05 (and optional CYA-GAP-06 host hygiene)."""
    if not isinstance(file_label, str) or not file_label.strip():
        raise ValueError("SAFETY_INVALID_FILE_LABEL")
    if not isinstance(include_host_hygiene, bool):
        raise ValueError("SAFETY_INVALID_HOST_FLAG")

    findings: list[dict[str, Any]] = scan_hidden_unicode(text, file_label)
    lines = text.splitlines()

    # CYA-GAP-02: Unpinned MCP / permission bypass
    for lineno, line in enumerate(lines, start=1):
        for pat, detail in _MCP_BYPASS_RULES:
            for _m in pat.finditer(line):
                findings.append(
                    {
                        "gap_id": "CYA-GAP-02",
                        "file": file_label,
                        "line": lineno,
                        "detail": detail,
                    }
                )

    # CYA-GAP-03: Unguarded rm -rf "$VAR" with nounset state tracking
    nounset_active = False
    for lineno, raw_line in enumerate(lines, start=1):
        code_line = _strip_shell_comment(raw_line)
        segments = re.split(r"(?:&&|\|\||;)", code_line)
        for seg in segments:
            if _SET_NOUNSET_ON_RE.search(seg):
                nounset_active = True
            if _SET_NOUNSET_OFF_RE.search(seg):
                nounset_active = False
            m_rm = _RM_CMD_RE.search(seg)
            if m_rm is None:
                continue
            arg_str = m_rm.group(1)
            tokens = arg_str.split()
            if not _rm_args_are_recursive_force(tokens):
                continue
            if nounset_active:
                continue
            for vm in _VAR_REF_RE.finditer(arg_str):
                braced = vm.group(1)
                if braced is not None and ":?" in braced:
                    continue
                findings.append(
                    {
                        "gap_id": "CYA-GAP-03",
                        "file": file_label,
                        "line": lineno,
                        "detail": "unguarded_rm_rf_variable",
                    }
                )
                break

    # CYA-GAP-04: pull_request_target + secrets/write privilege in CI YAML
    if file_label.lower().endswith((".yml", ".yaml")) and _CI_PRT_RE.search(text) is not None:
        for lineno, line in enumerate(lines, start=1):
            if _CI_PRIV_RE.search(line) is not None:
                findings.append(
                    {
                        "gap_id": "CYA-GAP-04",
                        "file": file_label,
                        "line": lineno,
                        "detail": "pull_request_target_with_privileged_access",
                    }
                )

    # CYA-GAP-05: Prose-only governance rules & host-home ~/ path dependencies
    is_rule_doc = file_label.lower().endswith((".md", ".mdc", ".txt"))
    if is_rule_doc:
        for lineno, line in enumerate(lines, start=1):
            if _PROSE_RULE_RE.search(line) is not None:
                findings.append(
                    {
                        "gap_id": "CYA-GAP-05",
                        "file": file_label,
                        "line": lineno,
                        "detail": "prose_only_governance_rule",
                    }
                )
            if _TILDE_PATH_RE.search(line) is not None:
                findings.append(
                    {
                        "gap_id": "CYA-GAP-05",
                        "file": file_label,
                        "line": lineno,
                        "detail": "host_home_tilde_dependency",
                    }
                )

    # CYA-GAP-06: Optional host hygiene (alias rm= & cloud-sync paths)
    if include_host_hygiene:
        for lineno, line in enumerate(lines, start=1):
            if _ALIAS_RM_RE.search(line) is not None:
                findings.append(
                    {
                        "gap_id": "CYA-GAP-06",
                        "file": file_label,
                        "line": lineno,
                        "detail": "noninteractive_alias_rm_illusion",
                    }
                )
            if _CLOUD_SYNC_RE.search(line) is not None:
                findings.append(
                    {
                        "gap_id": "CYA-GAP-06",
                        "file": file_label,
                        "line": lineno,
                        "detail": "cloud_sync_folder_hazard",
                    }
                )

    gap_ids = sorted({f["gap_id"] for f in findings})
    return {
        "clean": len(findings) == 0,
        "file": file_label,
        "finding_count": len(findings),
        "gap_ids_present": gap_ids,
        "findings": findings,
    }


def scan_directory_safety_surface(
    target_path: Path,
    *,
    include_host_hygiene: bool = False,
) -> dict[str, Any]:
    """Scan a file or directory tree for CYA-GAP-01..06 safety findings."""
    resolved = target_path.resolve()
    if not resolved.exists():
        raise ValueError("SAFETY_TARGET_NOT_FOUND")

    files: list[Path]
    if resolved.is_file():
        files = [resolved]
    else:
        files = [
            p
            for p in sorted(resolved.rglob("*"))
            if p.is_file()
            and not any(part in _SKIP_DIRS for part in p.relative_to(resolved).parts)
            and (p.suffix.lower() in _TEXT_EXTS or p.name in ("CLAUDE.md", "AGENTS.md", "Makefile"))
        ]

    all_findings: list[dict[str, Any]] = []
    for p in files:
        label = p.name if resolved.is_file() else str(p.relative_to(resolved))
        txt = p.read_text(encoding="utf-8", errors="replace")
        res = scan_text_safety_surface(txt, label, include_host_hygiene=include_host_hygiene)
        all_findings.extend(res["findings"])

    return {
        "clean": len(all_findings) == 0,
        "target": str(resolved),
        "files_scanned": len(files),
        "finding_count": len(all_findings),
        "gap_ids_present": sorted({f["gap_id"] for f in all_findings}),
        "findings": all_findings,
    }
