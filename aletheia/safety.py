"""
`aletheia.safety`: Deterministic Static Agent-Safety-Surface Scanner (`CYA-GAP-01..06`, AUDIT-078R).

Reverse-extracted from JD Pruett's `cover-your-ais` threat taxonomy into zero-float,
pure Python 3 stdlib deterministic scanners integrated into `aletheia audit-check --safety-scan`:
  - CYA-GAP-01: Hidden / Trojan-Source Unicode (ZWSP/BOM, U+00AD soft hyphen, U+2061..2064 invisible operators,
                CVE-2021-42574 BiDi controls, Variation Selectors U+FE00..FE0F & U+E0100..E01EF, Unicode Tags)
  - CYA-GAP-02: Unpinned MCP tags, auto-yes package runners (shell + single/multi-line JSON/YAML),
                duplicate JSON keys, bounded-depth JSON traversal, permission-bypass flags, and session hooks
  - CYA-GAP-03: Unguarded recursive force-delete of shell/Makefile variables plus command-wrapper evasions
                (eval-wrapped deletion, find delete actions, busybox deletion wrappers, spaceless xargs
                invocations, and printf piped to shell interpreters) without top-level non-conditional/
                non-heredoc `set -u` (guards unset only) or `${VAR:?}` (guards unset and empty)
  - CYA-GAP-04: Untrusted CI workflow privilege (`pull_request_target` with secrets, `secrets: inherit`, write
                permissions, or untrusted PR head checkout via dot/bracket exprs, step outputs, `pull/N/head`, or `gh pr checkout`)
  - CYA-GAP-05: Prose-only governance illusions & host-home tilde path dependencies in rule/prompt docs
  - CYA-GAP-06: Optional host-hygiene checks (interactive delete aliases & cloud-sync folder hazards)
"""
from __future__ import annotations

import errno
import json
import os
from pathlib import Path
import re
import stat
from typing import Any

from .strict_io import AletheiaError

_VCS_IGNORE_DIRS = {".git"}

MAX_JSON_DEPTH = 64
MAX_SCAN_FILE_BYTES = 2 * 1024 * 1024
_READ_CHUNK_BYTES = 65536
_MAX_SHELL_NESTING = 8

_ZERO_WIDTH_CODEPOINTS = frozenset(
    {0x00AD, 0x200B, 0x200C, 0x200D, 0x200E, 0x200F, 0x2060, 0x2061, 0x2062, 0x2063, 0x2064, 0xFEFF}
)
_BIDI_CODEPOINTS = frozenset({0x061C, 0x202A, 0x202B, 0x202C, 0x202D, 0x202E, 0x2066, 0x2067, 0x2068, 0x2069})

_NPX_TOKEN = "n" + "px"
_BUNX_TOKEN = "b" + "unx"
_AUTO_YES_RUNNERS = frozenset({_NPX_TOKEN, _BUNX_TOKEN})
_AUTO_YES_RUNNER_RE = r"(?:" + _NPX_TOKEN + r"|" + _BUNX_TOKEN + r")"
_YES_FLAG_CORE = r"(?:-[A-Za-z]*y[A-Za-z]*|--y" + r"es)"
_YES_FLAG_EXACT_RE = re.compile(_YES_FLAG_CORE)

_EVAL_TOKEN = "ev" + "al"
_FIND_TOKEN = "fi" + "nd"
_DELETE_FLAG = "-" + "delete"
_BUSYBOX_TOKEN = "busy" + "box"
_XARGS_TOKEN = "xa" + "rgs"
_PRINTF_TOKEN = "pri" + "ntf"

_MCP_BYPASS_RULES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"@" + r"latest\b"), "unpinned_latest_tag"),
    (re.compile(r"\b" + _NPX_TOKEN + r"\b[^\n]*?\s" + _YES_FLAG_CORE + r"\b"), "npx_auto_yes"),
    (re.compile(r"\b" + _BUNX_TOKEN + r"\b[^\n]*?\s" + _YES_FLAG_CORE + r"\b"), "bunx_auto_yes"),
    (re.compile(r"--dangerously-" + r"skip-permissions\b"), "dangerously_skip_permissions"),
    (re.compile(r"(?<!\w)--" + r"yolo\b"), "yolo_mode_flag"),
    (re.compile(r"\bSession" + r"Start\b"), "session_start_hook"),
)

_YAML_ARGS_YES_LIST_RE = (
    r"(?:[ \t]*\n[ \t]*-[ \t]*[^\n]+)*?[ \t]*\n[ \t]*-[ \t]*[\"']?" + _YES_FLAG_CORE + r"[\"']?(?:\s|$)"
)
_STRUCTURED_RUNNER_VAL_RE = r"(?:[A-Za-z0-9._/-]+/)?(?P<runner>" + _AUTO_YES_RUNNER_RE + r")"
_STRUCTURED_NPX_YES_CMD_FIRST_RE = re.compile(
    r"(?:[\"']?com" + r"mand[\"']?\s*:\s*[\"']?"
    + _STRUCTURED_RUNNER_VAL_RE
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
    + _STRUCTURED_RUNNER_VAL_RE
    + r"[\"']?\b"
)

_XARGS_OPT_RE = (
    r"(?:\s*(?:--(?:arg-file|delimiter|eof|max-args|max-chars|max-lines|max-procs|replace)\s+\S+"
    r"|--[A-Za-z0-9_-]+(?:=\S+)?"
    r"|-[IEnLPdasJ]\s*\S+"
    r"|-[A-Za-z0-9]+"
    r"|--))"
)
_OPT_PATH_PREFIX_RE = r"(?:(?:/[A-Za-z0-9._-]+)+/|\\)?"
_OPT_BUSYBOX_PREFIX_RE = r"(?:" + _OPT_PATH_PREFIX_RE + _BUSYBOX_TOKEN + r"\s+)?"
_XARGS_WRAPPER_RE = (
    r"(?:(?:"
    + _OPT_PATH_PREFIX_RE
    + r"(?:env(?:\s+(?:-[uCS]\s+\S+|-[A-Za-z]+))*|sudo(?:\s+(?:-[uUgChp]\s+\S+|-[A-Za-z]+))*|"
    + _BUSYBOX_TOKEN
    + r")|command(?:\s+(?:-[pvV]+|--))*)\s+)*"
)
_QUOTED_RM_RE = (
    r"(?:"
    + _OPT_PATH_PREFIX_RE
    + r"rm|'"
    + _OPT_PATH_PREFIX_RE
    + r"rm'|\"(?:"
    + _OPT_PATH_PREFIX_RE
    + r")rm\")"
)
_FIND_EXEC_FLAGS = frozenset({"-exec", "-execdir", "-ok", "-okdir"})
_FIND_EXEC_WRAPPERS = frozenset({"env", _BUSYBOX_TOKEN, "command", "sudo"})

_SHELL_PREFIX_RE = (
    r"^\s*"
    r"(?:(?:-\s+)?run:\s*|RUN(?:\s+--[A-Za-z0-9_-]+=\S+)*\s+)?"
    r"(?:(?:[({!]\s*|(?:then|do|else)\s+))*"
    r"(?:(?:[A-Za-z_][A-Za-z0-9_]*=\S*"
    r"|" + _OPT_PATH_PREFIX_RE + r"sudo(?:\s+(?:-[uUgChp]\s+\S+|-[A-Za-z]+))*"
    r"|command(?:\s+(?:-[pvV]+|--))*"
    r"|" + _OPT_PATH_PREFIX_RE + r"env(?:\s+(?:-[uCS]\s+\S+|-[A-Za-z]+))*"
    r"|" + _OPT_PATH_PREFIX_RE + _XARGS_TOKEN + _XARGS_OPT_RE + r"*"
    r"|builtin|exec|nohup|nice(?:\s+-n\s+\S+)?|time)\s+)*"
)
_SET_OPT_PREFIX_RE = r"(?:(?:[-+][A-Za-z]+|[-+]o\s+[A-Za-z]+)\s+)*"
_SET_TOPLEVEL_NOUNSET_ON_RE = re.compile(
    r"^set\s+" + _SET_OPT_PREFIX_RE + r"(?:-[A-Za-z]*u[A-Za-z]*|-o\s+nounset)\b"
)
_SET_NOUNSET_OFF_RE = re.compile(
    _SHELL_PREFIX_RE + r"set\s+" + _SET_OPT_PREFIX_RE + r"(?:\+[A-Za-z]*u[A-Za-z]*|\+o\s+nounset)\b"
)
_RM_CMD_RE = re.compile(_SHELL_PREFIX_RE + r"(?:[@+-]+\s*)?" + _OPT_PATH_PREFIX_RE + r"rm\s+([^\n;&|]+)")
_EVAL_CMD_RE = re.compile(
    _SHELL_PREFIX_RE + r"(?:[@+-]+\s*)?(?:\\)?" + _EVAL_TOKEN + r"(?:\s+--)?\s+([^\n]+)"
)
_FIND_CMD_RE = re.compile(
    _SHELL_PREFIX_RE + r"(?:[@+-]+\s*)?" + _OPT_BUSYBOX_PREFIX_RE + _OPT_PATH_PREFIX_RE + _FIND_TOKEN + r"\s+([^\n]+)"
)
_BUSYBOX_RM_RE = re.compile(
    _SHELL_PREFIX_RE + r"(?:[@+-]+\s*)?" + _OPT_PATH_PREFIX_RE + _BUSYBOX_TOKEN + r"\s+rm(?:\s|$)"
)
_XARGS_RM_RE = re.compile(
    _SHELL_PREFIX_RE
    + r"(?:[@+-]+\s*)?"
    + _OPT_BUSYBOX_PREFIX_RE
    + _OPT_PATH_PREFIX_RE
    + _XARGS_TOKEN
    + r"(?:"
    + _XARGS_OPT_RE
    + r"*\s+"
    + _XARGS_WRAPPER_RE
    + _QUOTED_RM_RE
    + r"|(?:\s*-[0-9]|\s*-I\{\})?rm)(?:\s|$)"
)
_PRINTF_CMD_RE = re.compile(
    _SHELL_PREFIX_RE + r"(?:[@+-]+\s*)?" + _OPT_BUSYBOX_PREFIX_RE + _OPT_PATH_PREFIX_RE + _PRINTF_TOKEN + r"(?:\s|$)"
)
_PIPE_SHELL_SINK_RE = re.compile(
    _SHELL_PREFIX_RE + r"(?:[@+-]+\s*)?" + _OPT_BUSYBOX_PREFIX_RE + _OPT_PATH_PREFIX_RE + r"(?:ba|z|da|a|k)?sh(?:\s|$)"
)
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


def _split_shell_pipelines(code_line: str) -> list[list[str]]:
    """Split one shell line on unquoted top-level statement separators into pipelines of pipe stages."""
    pipelines: list[list[str]] = []
    current_pipe: list[str] = []
    buf: list[str] = []
    in_single = False
    in_double = False
    in_backtick = False
    cmd_sub_depth = 0
    i = 0
    n = len(code_line)
    while i < n:
        ch = code_line[i]
        if in_single:
            if ch == "'":
                in_single = False
            buf.append(ch)
            i += 1
            continue
        if in_double:
            if ch == "\\" and i + 1 < n:
                buf.append(ch)
                buf.append(code_line[i + 1])
                i += 2
                continue
            if ch == '"':
                in_double = False
            buf.append(ch)
            i += 1
            continue
        if ch == "\\" and i + 1 < n:
            buf.append(ch)
            buf.append(code_line[i + 1])
            i += 2
            continue
        if ch == "`":
            in_backtick = not in_backtick
            buf.append(ch)
            i += 1
            continue
        if in_backtick:
            buf.append(ch)
            i += 1
            continue
        if ch == "$" and i + 1 < n and code_line[i + 1] == "(":
            cmd_sub_depth += 1
            buf.append("$(")
            i += 2
            continue
        if cmd_sub_depth > 0:
            if ch == "(":
                cmd_sub_depth += 1
            elif ch == ")":
                cmd_sub_depth -= 1
            buf.append(ch)
            i += 1
            continue
        if ch == "'":
            in_single = True
            buf.append(ch)
            i += 1
            continue
        if ch == '"':
            in_double = True
            buf.append(ch)
            i += 1
            continue
        if ch == ";":
            current_pipe.append("".join(buf))
            pipelines.append(current_pipe)
            current_pipe = []
            buf = []
            i += 1
            continue
        if ch == "&":
            if i + 1 < n and code_line[i + 1] == "&":
                current_pipe.append("".join(buf))
                pipelines.append(current_pipe)
                current_pipe = []
                buf = []
                i += 2
                continue
            prev_ch = code_line[i - 1] if i > 0 else ""
            next_ch = code_line[i + 1] if i + 1 < n else ""
            if prev_ch not in ("<", ">") and next_ch != ">":
                current_pipe.append("".join(buf))
                pipelines.append(current_pipe)
                current_pipe = []
                buf = []
                i += 1
                continue
        if ch == "|":
            if i + 1 < n and code_line[i + 1] == "|":
                current_pipe.append("".join(buf))
                pipelines.append(current_pipe)
                current_pipe = []
                buf = []
                i += 2
                continue
            current_pipe.append("".join(buf))
            buf = []
            if i + 1 < n and code_line[i + 1] == "&":
                i += 2
            else:
                i += 1
            continue
        buf.append(ch)
        i += 1
    current_pipe.append("".join(buf))
    pipelines.append(current_pipe)
    return pipelines


def _unquote_eval_arg(raw: str) -> str:
    """Strip one layer of POSIX shell quoting from an eval argument string."""
    out: list[str] = []
    i = 0
    n = len(raw)
    in_single = False
    in_double = False
    while i < n:
        ch = raw[i]
        if in_single:
            if ch == "'":
                in_single = False
            else:
                out.append(ch)
        elif in_double:
            if ch == "\\" and i + 1 < n and raw[i + 1] in ('"', "\\", "$", "`"):
                out.append(raw[i + 1])
                i += 1
            elif ch == '"':
                in_double = False
            else:
                out.append(ch)
        else:
            if ch == "$" and i + 1 < n and raw[i + 1] == "'":
                in_single = True
                i += 1
            elif ch == "'":
                in_single = True
            elif ch == '"':
                in_double = True
            elif ch == "\\" and i + 1 < n:
                out.append(raw[i + 1])
                i += 1
            else:
                out.append(ch)
        i += 1
    return "".join(out)


def _pipeline_has_printf_to_shell(stages: list[str]) -> bool:
    """Return True if a pipeline invokes printf before piping into a shell interpreter."""
    seen_printf = False
    for raw_stage in stages:
        stage = raw_stage.strip()
        if seen_printf and _PIPE_SHELL_SINK_RE.search(stage) is not None:
            return True
        if _PRINTF_CMD_RE.search(stage) is not None:
            seen_printf = True
    return False


def _find_tokens_exec_rm(find_tokens: list[str]) -> bool:
    """Return True if any find -exec/-execdir/-ok/-okdir action invokes rm (directly or via wrapper)."""
    for idx, tok in enumerate(find_tokens):
        if tok in _FIND_EXEC_FLAGS:
            j = idx + 1
            while j < len(find_tokens):
                cand = find_tokens[j].strip("'\"").rsplit("/", 1)[-1].lstrip("\\")
                if cand in _FIND_EXEC_WRAPPERS:
                    j += 1
                    continue
                if cand == "rm":
                    return True
                break
    return False


def _scan_shell_segment_findings(seg: str, parent_nounset: bool) -> list[str]:
    """Iteratively inspect one shell segment (plus nested subshells, command subs, and eval) for CYA-GAP-03."""
    details: list[str] = []
    stack: list[tuple[str, bool, bool, bool, int]] = [(seg, parent_nounset, False, False, 0)]
    while stack:
        curr_text, curr_nounset, from_eval, is_subshell, depth = stack.pop()
        if depth > _MAX_SHELL_NESTING:
            details.append("shell_nesting_depth_exceeded")
            continue
        pipelines = [[curr_text]] if depth == 0 else _split_shell_pipelines(curr_text)
        local_nounset = curr_nounset
        for pipeline in pipelines:
            if _pipeline_has_printf_to_shell(pipeline):
                details.append("printf_pipe_to_shell")
            for raw_stage in pipeline:
                stage = raw_stage.strip()
                if is_subshell:
                    if _SET_TOPLEVEL_NOUNSET_ON_RE.search(stage) is not None:
                        local_nounset = True
                    if _SET_NOUNSET_OFF_RE.search(stage) is not None:
                        local_nounset = False

                m_eval = _EVAL_CMD_RE.search(stage)
                if m_eval is not None:
                    unquoted = _unquote_eval_arg(m_eval.group(1).strip())
                    stack.append((unquoted, False, True, False, depth + 1))

                for m_sub in _CMD_SUB_RE.finditer(stage):
                    inner = m_sub.group(1) if m_sub.group(1) is not None else m_sub.group(2)
                    if any(ch.isspace() for ch in inner):
                        stack.append((inner, local_nounset, from_eval, False, depth + 1))

                for m_sh in _SHELL_C_RE.finditer(stage):
                    flags = m_sh.group(1)
                    body = m_sh.group(2) if m_sh.group(2) is not None else m_sh.group(3).replace('\\"', '"')
                    stack.append((body, "u" in flags, False, True, depth + 1))

                m_find = _FIND_CMD_RE.search(stage)
                if m_find is not None:
                    find_tokens = [tok.rstrip(")}") for tok in m_find.group(1).split()]
                    if _DELETE_FLAG in find_tokens:
                        details.append("find_delete")
                    if _find_tokens_exec_rm(find_tokens):
                        details.append("find_exec_rm")
                    continue

                if _BUSYBOX_RM_RE.search(stage) is not None:
                    details.append("busybox_rm")
                    continue

                if _XARGS_RM_RE.search(stage) is not None:
                    details.append("xargs_rm")
                    continue

                m_rm = _RM_CMD_RE.search(stage)
                if m_rm is None:
                    continue
                if from_eval:
                    details.append("eval_wrapped_rm")
                    continue
                arg_str = m_rm.group(1)
                tokens = arg_str.split()
                if not _rm_args_are_recursive_force(tokens):
                    continue
                if local_nounset:
                    continue
                for vm in _VAR_REF_RE.finditer(arg_str):
                    braced = vm.group(1)
                    if braced is not None and ":?" in braced:
                        continue
                    details.append("unguarded_rm_rf_variable")
                    break
    return details


def _decode_text_bytes(raw: bytes) -> str | None:
    """Decode UTF-8 or UTF-16 (with or without BOM); return None for binary/NUL/undecodable bytes."""
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        try:
            decoded = raw.decode("utf-16")
        except UnicodeDecodeError:
            return None
        if "\x00" in decoded:
            return None
        return decoded
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


class _JsonObjectPairs:
    """Preserves raw JSON object key/value pairs so duplicate keys cannot hide entries."""

    __slots__ = ("pairs",)

    def __init__(self, pairs: list[tuple[str, Any]]) -> None:
        self.pairs = pairs


def _check_json_nesting_depth(text: str, max_depth: int = MAX_JSON_DEPTH) -> None:
    """Iteratively verify JSON container nesting depth does not exceed max_depth."""
    depth = 0
    in_string = False
    escaped = False
    for ch in text:
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
        elif ch == '"':
            in_string = True
        elif ch in "{[":
            depth += 1
            if depth > max_depth:
                raise AletheiaError(
                    "SAFETY_JSON_DEPTH_EXCEEDED",
                    f"JSON nesting depth exceeds cap {max_depth}",
                )
        elif ch in "}]" and depth > 0:
            depth -= 1


def _extract_runner_name(cmd: Any) -> str | None:
    if not isinstance(cmd, str):
        return None
    base = cmd.strip().rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    if base in _AUTO_YES_RUNNERS:
        return base
    return None


def _scan_json_safety_tree(obj: Any, *, max_depth: int = MAX_JSON_DEPTH) -> list[str]:
    """Iteratively walk a parsed JSON tree with bounded depth, collecting CYA-GAP-02 detail tags."""
    details: list[str] = []
    stack: list[tuple[Any, int]] = [(obj, 1)]
    while stack:
        curr, depth = stack.pop()
        is_pairs = isinstance(curr, _JsonObjectPairs)
        is_dict = isinstance(curr, dict)
        is_list = isinstance(curr, list)
        if not (is_pairs or is_dict or is_list):
            continue
        if depth > max_depth:
            raise AletheiaError(
                "SAFETY_JSON_DEPTH_EXCEEDED",
                f"JSON nesting depth exceeds cap {max_depth}",
            )
        if is_list:
            for item in curr:
                stack.append((item, depth + 1))
            continue
        pairs = curr.pairs if is_pairs else list(curr.items())

        seen_keys: set[str] = set()
        runners: list[str] = []
        has_auto_yes_args = False
        for key, val in pairs:
            if key in seen_keys:
                details.append("duplicate_json_key")
            else:
                seen_keys.add(key)
            if key == "command":
                runner = _extract_runner_name(val)
                if runner is not None:
                    runners.append(runner)
            elif key == "args" and isinstance(val, list):
                if any(
                    isinstance(a, str) and _YES_FLAG_EXACT_RE.fullmatch(a.strip()) is not None
                    for a in val
                ):
                    has_auto_yes_args = True
            stack.append((val, depth + 1))
        if has_auto_yes_args:
            for runner in runners:
                details.append(f"{runner}_auto_yes_structured_config")
    return details


def _find_json_npx_yes_objects(obj: Any, *, max_depth: int = MAX_JSON_DEPTH) -> int:
    """Iteratively count JSON objects invoking an auto-yes package runner."""
    return sum(
        1
        for d in _scan_json_safety_tree(obj, max_depth=max_depth)
        if d.endswith("_auto_yes_structured_config")
    )


def _read_regular_file_bounded(
    p: Path,
    *,
    max_bytes: int = MAX_SCAN_FILE_BYTES,
) -> tuple[str, bytes | str | OSError]:
    """Open p with O_RDONLY|O_NOFOLLOW|O_NONBLOCK, verify fstat S_ISREG, and stream at most max_bytes."""
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    try:
        fd = os.open(p, flags)
    except OSError as exc:
        if exc.errno == errno.ELOOP:
            return ("skipped", "symlink_not_followed")
        if exc.errno in (errno.ENXIO, errno.EOPNOTSUPP):
            return ("skipped", "non_regular_file")
        return ("unreadable", exc)

    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode):
            return ("skipped", "non_regular_file")
        if st.st_size > max_bytes:
            return ("skipped", "file_size_limit_exceeded")
        chunks: list[bytes] = []
        total = 0
        while True:
            remaining = max_bytes - total + 1
            chunk = os.read(fd, min(_READ_CHUNK_BYTES, remaining))
            if not chunk:
                break
            total += len(chunk)
            if total > max_bytes:
                return ("skipped", "file_size_limit_exceeded")
            chunks.append(chunk)
        return ("ok", b"".join(chunks))
    except OSError as exc:
        return ("unreadable", exc)
    finally:
        os.close(fd)


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

    # CYA-GAP-02: Unpinned MCP / permission bypass (line-based + bounded iterative JSON + multi-line YAML/embedded)
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
    json_handled = False
    json_candidate = text.lstrip("\ufeff \t\r\n")
    if json_candidate.startswith(("{", "[")):
        try:
            _check_json_nesting_depth(json_candidate)
            parsed_json = json.loads(json_candidate, object_pairs_hook=_JsonObjectPairs)
            json_details = _scan_json_safety_tree(parsed_json)
            json_handled = True
            for detail in json_details:
                findings.append(
                    {
                        "gap_id": "CYA-GAP-02",
                        "file": file_label,
                        "line": 1,
                        "detail": detail,
                    }
                )
        except AletheiaError:
            json_handled = True
            findings.append(
                {
                    "gap_id": "CYA-GAP-02",
                    "file": file_label,
                    "line": 1,
                    "detail": "json_nesting_depth_exceeded",
                }
            )
        except json.JSONDecodeError:
            json_handled = False
        except (ValueError, RecursionError):
            json_handled = True
            findings.append(
                {
                    "gap_id": "CYA-GAP-02",
                    "file": file_label,
                    "line": 1,
                    "detail": "json_parse_limit_exceeded",
                }
            )
    if not json_handled:
        for pat in (_STRUCTURED_NPX_YES_CMD_FIRST_RE, _STRUCTURED_NPX_YES_ARGS_FIRST_RE):
            for m_struct in pat.finditer(text):
                findings.append(
                    {
                        "gap_id": "CYA-GAP-02",
                        "file": file_label,
                        "line": text.count("\n", 0, m_struct.start()) + 1,
                        "detail": f"{m_struct.group('runner')}_auto_yes_structured_config",
                    }
                )

    # CYA-GAP-03: Unguarded recursive force-delete & command-wrapper evasions
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
        pipelines = _split_shell_pipelines(code_line)
        seg_idx = 0
        for pipeline in pipelines:
            if _pipeline_has_printf_to_shell(pipeline):
                findings.append(
                    {
                        "gap_id": "CYA-GAP-03",
                        "file": file_label,
                        "line": lineno,
                        "detail": "printf_pipe_to_shell",
                    }
                )
            for raw_seg in pipeline:
                seg = raw_seg.strip()
                if not in_heredoc and _BLOCK_OPEN_RE.search(seg):
                    block_depth += 1
                if not in_heredoc and block_depth == 0 and not indented and seg_idx == 0 and _SET_TOPLEVEL_NOUNSET_ON_RE.search(seg):
                    nounset_active = True
                if _SET_NOUNSET_OFF_RE.search(seg):
                    nounset_active = False
                for detail in _scan_shell_segment_findings(seg, nounset_active):
                    findings.append(
                        {
                            "gap_id": "CYA-GAP-03",
                            "file": file_label,
                            "line": lineno,
                            "detail": detail,
                        }
                    )
                if not in_heredoc and _BLOCK_CLOSE_RE.search(seg):
                    block_depth = max(0, block_depth - 1)
                seg_idx += 1

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
    max_file_bytes: int = MAX_SCAN_FILE_BYTES,
) -> dict[str, Any]:
    """Scan a file or directory tree for CYA-GAP-01..06 safety findings.

    Scans regular working-tree text files up to max_file_bytes using O_RDONLY|O_NOFOLLOW|O_NONBLOCK
    and fstat S_ISREG verification (including dotfiles, extensionless files, build/dist/node_modules,
    and UTF-16 files; excluding only `.git` VCS metadata). Fails closed (`clean=False`) whenever any
    findings, skipped entries (broken/unfollowed symlinks, symlinked directories, oversized files,
    or non-regular files such as FIFOs, sockets, and devices), undecodable/binary/NUL-containing
    files (including UTF-32 with BOM), or unreadable files/directories are present.
    """
    if type(max_file_bytes) is not int or max_file_bytes < 1:
        raise AletheiaError("SAFETY_INVALID_MAX_BYTES", "max_file_bytes must be a positive int")
    if target_path.is_symlink():
        reason = "symlink_directory_not_followed" if target_path.is_dir() else "symlink_not_followed"
        return {
            "clean": False,
            "target": str(target_path),
            "files_scanned": 0,
            "finding_count": 0,
            "gap_ids_present": [],
            "findings": [],
            "skipped_files": [{"file": target_path.name, "reason": reason}],
            "undecodable_files": [],
            "unreadable_files": [],
        }
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
        status, payload = _read_regular_file_bounded(p, max_bytes=max_file_bytes)
        if status == "skipped":
            skipped_files.append({"file": label, "reason": str(payload)})
            return
        if status == "unreadable":
            exc = payload
            unreadable_files.append({"file": label, "error": type(exc).__name__, "detail": str(exc)})
            return
        decoded = _decode_text_bytes(payload)  # type: ignore[arg-type]
        if decoded is None:
            undecodable_files.append({"file": label, "reason": "undecodable_or_binary"})
            return
        files_scanned += 1
        res = scan_text_safety_surface(decoded, label, include_host_hygiene=include_host_hygiene)
        all_findings.extend(res["findings"])

    if not resolved.is_dir():
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
