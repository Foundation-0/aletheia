"""
`aletheia.safety`: Deterministic Static Agent-Safety-Surface Scanner (`CYA-GAP-01..06`, AUDIT-078R).

Reverse-extracted from JD Pruett's `cover-your-ais` threat taxonomy into zero-float,
pure Python 3 stdlib deterministic scanners integrated into `aletheia audit-check --safety-scan`:
  - CYA-GAP-01: Hidden / Trojan-Source Unicode (ZWSP/BOM, U+00AD soft hyphen, U+2061..2064 invisible operators,
                CVE-2021-42574 BiDi controls, Variation Selectors U+FE00..FE0F & U+E0100..E01EF, Unicode Tags)
  - CYA-GAP-02: Unpinned MCP tags, auto-yes package runners (shell + single/multi-line JSON/YAML),
                permission-bypass flags, and session hooks
  - CYA-GAP-03: Unguarded recursive force-delete of shell/Makefile variables across shell scripts, YAML `run:`,
                command substitutions, backslash continuations, `xargs`, `sh -c`, and Makefiles without top-level
                non-conditional/non-heredoc `set -u` (guards unset only) or `${VAR:?}` (guards unset and empty)
  - CYA-GAP-04: Untrusted CI workflow privilege (`pull_request_target` with secrets, `secrets: inherit`, write
                permissions, or untrusted PR head checkout via dot/bracket exprs, step outputs, `pull/N/head`, or `gh pr checkout`)
  - CYA-GAP-05: Prose-only governance illusions & host-home tilde path dependencies in rule/prompt docs
  - CYA-GAP-06: Optional host-hygiene checks (interactive delete aliases & cloud-sync folder hazards)
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
from typing import Any

_VCS_IGNORE_DIRS = {".git"}

_ZERO_WIDTH_CODEPOINTS = frozenset(
    {0x00AD, 0x200B, 0x200C, 0x200D, 0x200E, 0x200F, 0x2060, 0x2061, 0x2062, 0x2063, 0x2064, 0xFEFF}
)
_BIDI_CODEPOINTS = frozenset({0x061C, 0x202A, 0x202B, 0x202C, 0x202D, 0x202E, 0x2066, 0x2067, 0x2068, 0x2069})

_NPX_TOKEN = "n" + "px"
_YES_FLAG_CORE = r"(?:-[A-Za-z]*y[A-Za-z]*|--y" + r"es)"
_YES_FLAG_EXACT_RE = re.compile(_YES_FLAG_CORE)

_MCP_BYPASS_RULES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"@" + r"latest\b"), "unpinned_latest_tag"),
    (re.compile(r"\b" + _NPX_TOKEN + r"\b[^\n]*?\s" + _YES_FLAG_CORE + r"\b"), "npx_auto_yes"),
    (re.compile(r"--dangerously-" + r"skip-permissions\b"), "dangerously_skip_permissions"),
    (re.compile(r"(?<!\w)--" + r"yolo\b"), "yolo_mode_flag"),
    (re.compile(r"\bSession" + r"Start\b"), "session_start_hook"),
)

_YAML_ARGS_YES_LIST_RE = (
    r"(?:[ \t]*\n[ \t]*-[ \t]*[^\n]+)*?[ \t]*\n[ \t]*-[ \t]*[\"']?" + _YES_FLAG_CORE + r"[\"']?(?:\s|$)"
)
_STRUCTURED_NPX_YES_CMD_FIRST_RE = re.compile(
    r"(?:[\"']?com" + r"mand[\"']?\s*:\s*[\"']?"
    + _NPX_TOKEN
    + r"[\"']?)"
    r"(?:(?!\bcom" + r"mand\s*:)[\s\S]){0,600}?"
    r"(?:[\"']?a" + r"rgs[\"']?\s*:\s*"
    r"(?:\[[^\]]*?[\"']" + _YES_FLAG_CORE + r"[\"']"
    r"|" + _YAML_ARGS_YES_LIST_RE + r"))"
)
_STRUCTURED_NPX_YES_ARGS_FIRST_RE = re.compile(
    r"(?:[\"']?a" + r"rgs[\"']?\s*:\s*"
    r"(?:\[[^\]]*?[\"']" + _YES_FLAG_CORE + r"[\"'][^\]]*\]"
    r"|" + _YAML_ARGS_YES_LIST_RE + r"(?:[ \t]*\n[ \t]*-[ \t]*[^\n]+)*))"
    r"(?:(?!\ba" + r"rgs\s*:)[\s\S]){0,600}?"
    r"[\"']?com" + r"mand[\"']?\s*:\s*[\"']?"
    + _NPX_TOKEN
    + r"[\"']?\b"
)

_SHELL_PREFIX_RE = (
    r"^\s*"
    r"(?:(?:-\s+)?run:\s*|RUN(?:\s+--[A-Za-z0-9_-]+=\S+)*\s+)?"
    r"(?:(?:[({!]\s*|(?:then|do|else)\s+))*"
    r"(?:(?:[A-Za-z_][A-Za-z0-9_]*=\S*"
    r"|sudo(?:\s+(?:-[uUgChp]\s+\S+|-[A-Za-z]+))*"
    r"|command(?:\s+(?:-[pvV]+|--))*"
    r"|env(?:\s+(?:-[uC]\s+\S+|-[A-Za-z]+))*"
    r"|xargs(?:\s+(?:-[IEnLP]\s+\S+|-[A-Za-z0-9]+))*"
    r"|builtin|exec|nohup|nice(?:\s+-n\s+\S+)?|time)\s+)*"
)
_SET_OPT_PREFIX_RE = r"(?:(?:[-+][A-Za-z]+|[-+]o\s+[A-Za-z]+)\s+)*"
_SET_TOPLEVEL_NOUNSET_ON_RE = re.compile(
    r"^set\s+" + _SET_OPT_PREFIX_RE + r"(?:-[A-Za-z]*u[A-Za-z]*|-o\s+nounset)\b"
)
_SET_NOUNSET_OFF_RE = re.compile(
    _SHELL_PREFIX_RE + r"set\s+" + _SET_OPT_PREFIX_RE + r"(?:\+[A-Za-z]*u[A-Za-z]*|\+o\s+nounset)\b"
)
_RM_CMD_RE = re.compile(_SHELL_PREFIX_RE + r"(?:[@+-]+\s*)?(?:(?:/[A-Za-z0-9._-]+)+/|\\)?rm\s+([^\n;&|]+)")
_SHELL_SEG_SPLIT_RE = re.compile(r"(?:&&|\|\||;|\||(?<![<>])&(?!>))")
_VAR_REF_RE = re.compile(r"\$(?:\{([^}]+)\}|\(([A-Za-z_][A-Za-z0-9_]*)\)|([A-Za-z_][A-Za-z0-9_]*))")
_HEREDOC_START_RE = re.compile(r"<<(-)?\s*['\"]?([A-Za-z_][A-Za-z0-9_]*)['\"]?")
_BLOCK_OPEN_RE = re.compile(r"(?:^\s*(?:if|for|while|until|case)\b|(?:^|\s)\{(?:\s|$)|(?:^|\s)\($)")
_BLOCK_CLOSE_RE = re.compile(r"(?:^\s*(?:fi|done|esac)\b|(?:^|\s)\}(?:\s|$)|^\)$)")
_CMD_SUB_RE = re.compile(r"\$\(([^()\n]+)\)|`([^`\n]+)`")
_SHELL_C_RE = re.compile(
    r"\b(?:ba|z|da|a|k)?sh\s+((?:-[A-Za-z]+\s+)*-[A-Za-z]*c[A-Za-z]*)\s+(?:'([^']*)'|\"((?:\\.|[^\"\\])*)\")"
)

_CI_PRT_RE = re.compile(r"\bpull_request_target\b")
_CI_PRIV_RE = re.compile(
    r"(?:secrets\s*(?:\.|\[\s*['\"]|:\s*inherit\b)|toJSON\s*\(\s*secrets\s*\)|\bwrite-all\b|\b[a-z-]+:\s*write\b)",
    re.IGNORECASE,
)
_CI_UNTRUSTED_HEAD_RE = re.compile(
    r"(?:github(?:\.event|\[\s*['\"]event['\"]\s*\])(?:\.pull_request|\[\s*['\"]pull_request['\"]\s*\])"
    r"(?:\.head|\[\s*['\"]head['\"]\s*\])(?:\.(?:sha|ref|repo)\b|\[\s*['\"](?:sha|ref|repo)['\"]\s*\])"
    r"|\bgithub(?:\.head_ref\b|\[\s*['\"]head_ref['\"]\s*\])"
    r"|(?:refs/)?pull/[^\n'\"]*?/(?:head|merge)\b"
    r"|\bgh\s+pr\s+checkout\b"
    r"|\bref\s*:\s*['\"]?\$\{\{\s*(?:steps|needs)\.[A-Za-z0-9_-]+\.outputs\.[A-Za-z0-9_-]+\s*\}\}['\"]?)",
    re.IGNORECASE,
)

_PROSE_RULE_RE = re.compile(
    r"\b(?:commit\s+only\s+when\s+asked|no\s+prs\b|never\s+push|code\s+freeze|git\s+add\s+-A)\b",
    re.IGNORECASE,
)
_TILDE_PATH_RE = re.compile(r"(?:^|[\s(`\"'])~/[A-Za-z0-9._/-]+")

_ALIAS_RM_RE = re.compile(r"\balias\s+rm\s*=")
_CLOUD_SYNC_RE = re.compile(r"(?:Mobile\s+Documents|iCloud|Dropbox|OneDrive)", re.IGNORECASE)

_RULE_DOC_NAMES = frozenset({".cursorrules", ".windsurfrules", ".clinerules"})
_RULE_DOC_EXTS = (".md", ".mdc", ".txt")
_CI_YAML_EXTS = (".yml", ".yaml", ".yml.j2", ".yaml.j2")


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
        if tok == "--recursive":
            has_r = True
        elif tok == "--force":
            has_f = True
        elif tok.startswith("-") and not tok.startswith("--"):
            flags = tok[1:]
            if "r" in flags or "R" in flags:
                has_r = True
            if "f" in flags:
                has_f = True
    return has_r and has_f


def _has_unescaped_trailing_backslash(line: str) -> bool:
    count = 0
    for ch in reversed(line):
        if ch == "\\":
            count += 1
        else:
            break
    return count % 2 == 1


def _join_backslash_continuations(lines: list[str]) -> list[tuple[int, str]]:
    logical: list[tuple[int, str]] = []
    buf: list[str] = []
    start_line = 1
    for lineno, line in enumerate(lines, start=1):
        if not buf:
            start_line = lineno
        if _has_unescaped_trailing_backslash(line):
            buf.append(line[:-1])
        else:
            buf.append(line)
            logical.append((start_line, " ".join(buf)))
            buf = []
    if buf:
        logical.append((start_line, " ".join(buf)))
    return logical


def _extract_nested_rm_segments(seg: str, parent_nounset: bool) -> list[tuple[str, bool]]:
    candidates: list[tuple[str, bool]] = [(seg, parent_nounset)]
    for m_sub in _CMD_SUB_RE.finditer(seg):
        inner = m_sub.group(1) if m_sub.group(1) is not None else m_sub.group(2)
        if any(ch.isspace() for ch in inner):
            for part in _SHELL_SEG_SPLIT_RE.split(inner):
                candidates.append((part.strip(), parent_nounset))
    for m_sh in _SHELL_C_RE.finditer(seg):
        flags = m_sh.group(1)
        body = m_sh.group(2) if m_sh.group(2) is not None else m_sh.group(3).replace('\\"', '"')
        child_nounset = "u" in flags
        for part in _SHELL_SEG_SPLIT_RE.split(body):
            sub = part.strip()
            if _SET_TOPLEVEL_NOUNSET_ON_RE.search(sub):
                child_nounset = True
            if _SET_NOUNSET_OFF_RE.search(sub):
                child_nounset = False
            candidates.append((sub, child_nounset))
    return candidates


def _decode_text_bytes(raw: bytes) -> str | None:
    """Decode UTF-8 or UTF-16 (with or without BOM); return None for binary/undecodable bytes."""
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        try:
            return raw.decode("utf-16")
        except UnicodeDecodeError:
            return None
    if b"\x00" in raw:
        if len(raw) >= 4 and len(raw) % 2 == 0:
            half = len(raw) // 2
            even_nuls = raw[0::2].count(0)
            odd_nuls = raw[1::2].count(0)
            enc: str | None = None
            if odd_nuls * 4 >= 3 * half and even_nuls == 0:
                enc = "utf-16-le"
            elif even_nuls * 4 >= 3 * half and odd_nuls == 0:
                enc = "utf-16-be"
            if enc is not None:
                try:
                    decoded = raw.decode(enc)
                except UnicodeDecodeError:
                    return None
                if any(ord(ch) < 32 and ch not in ("\t", "\n", "\r") for ch in decoded):
                    return None
                return decoded
        return None
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return None


def _find_json_npx_yes_objects(obj: Any) -> int:
    """Recursively count JSON objects invoking an auto-yes package runner."""
    hits = 0
    if isinstance(obj, dict):
        cmd = obj.get("command")
        args = obj.get("args")
        if isinstance(cmd, str) and cmd.strip() == _NPX_TOKEN and isinstance(args, list):
            if any(isinstance(a, str) and _YES_FLAG_EXACT_RE.fullmatch(a.strip()) is not None for a in args):
                hits += 1
        for val in obj.values():
            hits += _find_json_npx_yes_objects(val)
    elif isinstance(obj, list):
        for item in obj:
            hits += _find_json_npx_yes_objects(item)
    return hits


def scan_hidden_unicode(text: str, file_label: str = "<input>") -> list[dict[str, Any]]:
    """CYA-GAP-01: Detect zero-width/BOM/soft-hyphen/invisible-op, BiDi controls, variation selectors, and Unicode Tags."""
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
            cat = "zero_width_or_invisible_format"
        elif cp in _BIDI_CODEPOINTS:
            cat = "bidi_trojan_source"
        elif 0xFE00 <= cp <= 0xFE0F or 0xE0100 <= cp <= 0xE01EF:
            cat = "variation_selector_smuggling"
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

    # CYA-GAP-02: Unpinned MCP / permission bypass (line-based + recursive JSON + multi-line YAML/embedded)
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
    json_parsed = False
    if text.lstrip().startswith(("{", "[")):
        try:
            parsed_json = json.loads(text)
            json_parsed = True
        except json.JSONDecodeError:
            parsed_json = None
        if json_parsed:
            for _ in range(_find_json_npx_yes_objects(parsed_json)):
                findings.append(
                    {
                        "gap_id": "CYA-GAP-02",
                        "file": file_label,
                        "line": 1,
                        "detail": "npx_auto_yes_structured_config",
                    }
                )
    if not json_parsed:
        for pat in (_STRUCTURED_NPX_YES_CMD_FIRST_RE, _STRUCTURED_NPX_YES_ARGS_FIRST_RE):
            for m_struct in pat.finditer(text):
                findings.append(
                    {
                        "gap_id": "CYA-GAP-02",
                        "file": file_label,
                        "line": text.count("\n", 0, m_struct.start()) + 1,
                        "detail": "npx_auto_yes_structured_config",
                    }
                )

    # CYA-GAP-03: Unguarded recursive force-delete of shell/Makefile variables
    nounset_active = False
    heredoc_delim: str | None = None
    heredoc_strip_tabs = False
    block_depth = 0
    for lineno, raw_line in _join_backslash_continuations(lines):
        in_heredoc = heredoc_delim is not None
        if heredoc_delim is not None:
            candidate_end = raw_line.lstrip("\t") if heredoc_strip_tabs else raw_line
            if candidate_end == heredoc_delim:
                heredoc_delim = None
                continue
        code_line = _strip_shell_comment(raw_line)
        if not in_heredoc:
            m_hd = _HEREDOC_START_RE.search(code_line)
            if m_hd is not None:
                heredoc_strip_tabs = m_hd.group(1) == "-"
                heredoc_delim = m_hd.group(2)
        indented = raw_line[:1] in (" ", "\t")
        segments = _SHELL_SEG_SPLIT_RE.split(code_line)
        for seg_idx, raw_seg in enumerate(segments):
            seg = raw_seg.strip()
            if not in_heredoc and _BLOCK_OPEN_RE.search(seg):
                block_depth += 1
            if not in_heredoc and block_depth == 0 and not indented and seg_idx == 0 and _SET_TOPLEVEL_NOUNSET_ON_RE.search(seg):
                nounset_active = True
            if _SET_NOUNSET_OFF_RE.search(seg):
                nounset_active = False
            for cand_seg, cand_nounset in _extract_nested_rm_segments(seg, nounset_active):
                m_rm = _RM_CMD_RE.search(cand_seg)
                if m_rm is None:
                    continue
                arg_str = m_rm.group(1)
                tokens = arg_str.split()
                if not _rm_args_are_recursive_force(tokens):
                    continue
                if cand_nounset:
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
            if not in_heredoc and _BLOCK_CLOSE_RE.search(seg):
                block_depth = max(0, block_depth - 1)

    # CYA-GAP-04: pull_request_target + privileged access or untrusted PR head checkout in CI YAML
    lower_label = file_label.lower()
    if lower_label.endswith(_CI_YAML_EXTS) and _CI_PRT_RE.search(text) is not None:
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
            if _CI_UNTRUSTED_HEAD_RE.search(line) is not None:
                findings.append(
                    {
                        "gap_id": "CYA-GAP-04",
                        "file": file_label,
                        "line": lineno,
                        "detail": "pull_request_target_untrusted_head_checkout",
                    }
                )

    # CYA-GAP-05: Prose-only governance rules & host-home ~/ path dependencies
    base_name = Path(file_label).name.lower()
    is_rule_doc = lower_label.endswith(_RULE_DOC_EXTS) or base_name in _RULE_DOC_NAMES
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
    """Scan a file or directory tree for CYA-GAP-01..06 safety findings.

    Scans all working-tree text files (including dotfiles, extensionless files, build/dist/node_modules,
    and UTF-16 files; excluding only `.git` VCS metadata). Fails closed (`clean=False`) whenever any
    findings, skipped entries, undecodable/binary files, or unreadable files/directories are present.
    """
    resolved = target_path.resolve()
    if not resolved.exists():
        raise ValueError("SAFETY_TARGET_NOT_FOUND")

    all_findings: list[dict[str, Any]] = []
    skipped_files: list[dict[str, str]] = []
    undecodable_files: list[dict[str, str]] = []
    unreadable_files: list[dict[str, str]] = []
    files_scanned = 0

    def _scan_one(p: Path, label: str) -> None:
        nonlocal files_scanned
        if p.is_symlink() and not p.exists():
            skipped_files.append({"file": label, "reason": "broken_symlink"})
            return
        try:
            raw = p.read_bytes()
        except OSError as exc:
            unreadable_files.append({"file": label, "error": type(exc).__name__, "detail": str(exc)})
            return
        decoded = _decode_text_bytes(raw)
        if decoded is None:
            undecodable_files.append({"file": label, "reason": "undecodable_or_binary"})
            return
        files_scanned += 1
        res = scan_text_safety_surface(decoded, label, include_host_hygiene=include_host_hygiene)
        all_findings.extend(res["findings"])

    if resolved.is_file():
        _scan_one(resolved, resolved.name)
    else:
        def _on_walk_err(exc: OSError) -> None:
            err_path = getattr(exc, "filename", None) or str(resolved)
            try:
                rel = str(Path(err_path).resolve().relative_to(resolved))
            except ValueError:
                rel = str(err_path)
            unreadable_files.append({"file": rel, "error": type(exc).__name__, "detail": str(exc)})

        for dirpath, dirnames, filenames in os.walk(resolved, topdown=True, onerror=_on_walk_err, followlinks=False):
            dp = Path(dirpath)
            kept_dirs: list[str] = []
            for d in sorted(dirnames):
                if d in _VCS_IGNORE_DIRS:
                    continue
                sub = dp / d
                if sub.is_symlink():
                    skipped_files.append(
                        {"file": str(sub.relative_to(resolved)), "reason": "symlink_directory_not_followed"}
                    )
                    continue
                kept_dirs.append(d)
            dirnames[:] = kept_dirs
            for fn in sorted(filenames):
                fp = dp / fn
                label = str(fp.relative_to(resolved))
                _scan_one(fp, label)

    clean = (
        len(all_findings) == 0
        and len(skipped_files) == 0
        and len(undecodable_files) == 0
        and len(unreadable_files) == 0
    )
    return {
        "clean": clean,
        "target": str(resolved),
        "files_scanned": files_scanned,
        "finding_count": len(all_findings),
        "gap_ids_present": sorted({f["gap_id"] for f in all_findings}),
        "findings": all_findings,
        "skipped_files": skipped_files,
        "undecodable_files": undecodable_files,
        "unreadable_files": unreadable_files,
    }
