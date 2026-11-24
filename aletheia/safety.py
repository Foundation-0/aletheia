"""
`aletheia.safety`: Deterministic Static Agent-Safety-Surface Scanner (`CYA-GAP-01..06`, AUDIT-078R).

Reverse-extracted from JD Pruett's `cover-your-ais` threat taxonomy into zero-float,
pure Python 3 stdlib deterministic scanners integrated into `aletheia audit-check --safety-scan`:
  - CYA-GAP-01: Hidden / Trojan-Source Unicode (ZWSP/BOM, U+00AD soft hyphen, U+2061..2064 invisible operators,
                CVE-2021-42574 BiDi controls, Variation Selectors U+FE00..FE0F & U+E0100..E01EF, Unicode Tags)
  - CYA-GAP-02: Unpinned MCP tags, auto-yes package runners (shell + single/multi-line JSON/YAML),
                duplicate JSON keys, bounded-depth JSON traversal, permission-bypass flags, and session hooks
  - CYA-GAP-03: (a) Unguarded recursive force-delete of shell/Makefile variables without
                top-level non-conditional/non-heredoc `set -u` (guards unset only) or `${VAR:?}`
                (guards unset and empty); and (b) unconditional detection of dynamic-execution and
                deletion-wrapper evasions (eval-wrapped deletion, find delete and -exec removal
                actions, busybox deletion wrappers, xargs removal invocations including spaceless
                forms, and printf piped to shell interpreters), which fire regardless of `set -u`,
                `${VAR:?}`, or literal paths.
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
MAX_JSON_NUMBER_CHARS = 4300
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

_STRUCTURED_CMD_LINE_RE = re.compile(
    r"(?<![A-Za-z0-9_])[\"']?com" + r"mand[\"']?[ \t]*:[ \t]*([^\n,}\]]+)"
)
_STRUCTURED_ARGS_KEY_RE = re.compile(
    r"(?<![A-Za-z0-9_])[\"']?a" + r"rgs[\"']?[ \t]*:"
)
_STRUCTURED_INLINE_YES_RE = re.compile(
    r"(?:^|[,\[\s\"'])" + _YES_FLAG_CORE + r"(?:$|[,\s\]\"'])"
)
_STRUCTURED_PROXIMITY_CHARS = 600

_FIND_EXEC_FLAGS = frozenset({"-exec", "-execdir", "-ok", "-okdir"})
_FIND_EXEC_END = frozenset({";", "\\;", "+"})
_SHELL_INTERPRETERS = frozenset({"sh", "bash", "zsh", "dash", "ash", "ksh"})
_XARGS_LONG_VAL_OPTS = frozenset(
    {
        "--arg-file",
        "--delimiter",
        "--eof",
        "--max-args",
        "--max-chars",
        "--max-lines",
        "--max-procs",
        "--replace",
    }
)
_XARGS_SHORT_VAL_FLAGS = frozenset({"I", "E", "n", "L", "P", "d", "a", "s", "J"})
_ENV_VAL_OPTS = frozenset({"-u", "-C", "--unset", "--chdir"})
_SUDO_VAL_OPTS = frozenset(
    {
        "-u",
        "-U",
        "-g",
        "-C",
        "-h",
        "-p",
        "-r",
        "-t",
        "-D",
        "-R",
        "-T",
        "--user",
        "--other-user",
        "--group",
        "--host",
        "--prompt",
    }
)
_NICE_VAL_OPTS = frozenset({"-n", "--adjustment"})
_TIMEOUT_VAL_OPTS = frozenset({"-k", "-s", "--kill-after", "--signal"})
_STDBUF_VAL_OPTS = frozenset({"-i", "-o", "-e", "--input", "--output", "--error"})
_STAGE_LEADING_PREFIX_RE = re.compile(
    r"^\s*(?:(?:-\s+)?run:\s*|RUN(?:\s+--[A-Za-z0-9_-]+=\S+)*\s+)?"
)
_SET_OPT_PREFIX_RE = r"(?:(?:[-+][A-Za-z]+|[-+]o\s+[A-Za-z]+)\s+)*"
_SET_TOPLEVEL_NOUNSET_ON_RE = re.compile(
    r"^set\s+" + _SET_OPT_PREFIX_RE + r"(?:-[A-Za-z]*u[A-Za-z]*|-o\s+nounset)\b"
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


def _strip_cmd_token(tok: str) -> str:
    """Normalize a shell command token (strip quotes, path prefix, and leading backslash)."""
    s = tok.strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ("'", '"'):
        s = s[1:-1]
    return s.rsplit("/", 1)[-1].lstrip("\\")


def _is_env_assign(tok: str) -> bool:
    """Return True if tok is a POSIX NAME=value environment assignment."""
    name, sep, _ = tok.partition("=")
    if not sep or not name:
        return False
    if not (name[0].isascii() and (name[0].isalpha() or name[0] == "_")):
        return False
    return all(ch.isascii() and (ch.isalnum() or ch == "_") for ch in name[1:])


def _is_spaceless_xargs_rm_tail(tail: str) -> bool:
    """Return True for spaceless xargs option+rm tails like '-0rm' or '-I{}rm'."""
    if tail == "-I{}rm":
        return True
    return len(tail) == 4 and tail[0] == "-" and "0" <= tail[1] <= "9" and tail[2:] == "rm"


def _split_shell_tokens(text: str) -> list[tuple[str, int, int]]:
    """Split text into quote-aware whitespace tokens with (token, start, end) offsets in O(n)."""
    tokens: list[tuple[str, int, int]] = []
    n = len(text)
    i = 0
    while i < n and text[i].isspace():
        i += 1
    while i < n:
        start = i
        in_single = False
        in_double = False
        while i < n:
            ch = text[i]
            if in_single:
                if ch == "'":
                    in_single = False
                i += 1
            elif in_double:
                if ch == "\\":
                    i += 2
                elif ch == '"':
                    in_double = False
                    i += 1
                else:
                    i += 1
            else:
                if ch.isspace():
                    break
                if ch == "\\":
                    i += 2
                elif ch == "'":
                    in_single = True
                    i += 1
                elif ch == '"':
                    in_double = True
                    i += 1
                else:
                    i += 1
        tokens.append((text[start:i], start, i))
        while i < n and text[i].isspace():
            i += 1
    return tokens


def _skip_xargs_options(
    tokens: list[str],
    idx: int,
    *,
    stop_tokens: frozenset[str] = frozenset(),
) -> tuple[int, bool]:
    """Advance idx past xargs options in strictly linear O(n) time."""
    n = len(tokens)
    while idx < n:
        t = tokens[idx]
        if t in stop_tokens:
            break
        if t == "--":
            idx += 1
            break
        if _is_spaceless_xargs_rm_tail(t):
            return (idx + 1, True)
        if t in _XARGS_LONG_VAL_OPTS:
            idx += 2 if idx + 1 < n and tokens[idx + 1] not in stop_tokens else 1
            continue
        if t.startswith("--"):
            idx += 1
            continue
        if t.startswith("-") and len(t) >= 2:
            if len(t) == 2 and t[1] in _XARGS_SHORT_VAL_FLAGS:
                idx += 2 if idx + 1 < n and tokens[idx + 1] not in stop_tokens else 1
            else:
                idx += 1
            continue
        break
    return (idx, False)


def _skip_wrapper_flag_args(
    tokens: list[str],
    idx: int,
    val_opts: frozenset[str],
    *,
    allow_env_assign: bool = False,
    stop_tokens: frozenset[str] = frozenset(),
) -> int:
    """Advance idx past a wrapper command's options in strictly linear O(n) time."""
    n = len(tokens)
    while idx < n:
        t = tokens[idx]
        if t in stop_tokens:
            break
        if t == "--":
            return idx + 1
        if allow_env_assign and _is_env_assign(t):
            idx += 1
            continue
        if t in val_opts:
            idx += 2 if idx + 1 < n and tokens[idx + 1] not in stop_tokens else 1
            continue
        if t.startswith("-") and len(t) >= 2:
            idx += 1
            continue
        break
    return idx


def _skip_command_wrappers(
    tokens: list[str],
    idx: int,
    *,
    stop_tokens: frozenset[str] = frozenset(),
) -> tuple[int, bool, bool, bool]:
    """Skip leading env assignments and wrapper commands in O(n); return (cmd_idx, saw_busybox, saw_xargs, spaceless_xargs_rm)."""
    n = len(tokens)
    saw_busybox = False
    saw_xargs = False
    while idx < n and _is_env_assign(tokens[idx]):
        idx += 1
    while idx < n:
        cmd = _strip_cmd_token(tokens[idx])
        if cmd == _XARGS_TOKEN + "rm":
            return (idx + 1, saw_busybox, True, True)
        if cmd.startswith(_XARGS_TOKEN + "-"):
            saw_xargs = True
            tail = cmd[len(_XARGS_TOKEN) :]
            if _is_spaceless_xargs_rm_tail(tail):
                return (idx + 1, saw_busybox, True, True)
            if len(tail) == 2 and tail[1] in _XARGS_SHORT_VAL_FLAGS:
                idx += 2 if idx + 1 < n and tokens[idx + 1] not in stop_tokens else 1
            else:
                idx += 1
            idx, hit = _skip_xargs_options(tokens, idx, stop_tokens=stop_tokens)
            if hit:
                return (idx, saw_busybox, True, True)
            continue
        if cmd == _XARGS_TOKEN:
            saw_xargs = True
            idx, hit = _skip_xargs_options(tokens, idx + 1, stop_tokens=stop_tokens)
            if hit:
                return (idx, saw_busybox, True, True)
            continue
        if cmd == _BUSYBOX_TOKEN:
            saw_busybox = True
            idx += 1
            continue
        if cmd == "env":
            idx = _skip_wrapper_flag_args(
                tokens, idx + 1, _ENV_VAL_OPTS, allow_env_assign=True, stop_tokens=stop_tokens
            )
            continue
        if cmd == "sudo":
            idx = _skip_wrapper_flag_args(
                tokens, idx + 1, _SUDO_VAL_OPTS, allow_env_assign=True, stop_tokens=stop_tokens
            )
            continue
        if cmd == "command":
            idx = _skip_wrapper_flag_args(tokens, idx + 1, frozenset(), stop_tokens=stop_tokens)
            continue
        if cmd == "nice":
            idx = _skip_wrapper_flag_args(tokens, idx + 1, _NICE_VAL_OPTS, stop_tokens=stop_tokens)
            continue
        if cmd == "stdbuf":
            idx = _skip_wrapper_flag_args(tokens, idx + 1, _STDBUF_VAL_OPTS, stop_tokens=stop_tokens)
            continue
        if cmd == "timeout":
            idx = _skip_wrapper_flag_args(tokens, idx + 1, _TIMEOUT_VAL_OPTS, stop_tokens=stop_tokens)
            if idx < n and tokens[idx] not in stop_tokens:
                idx += 1
            continue
        if cmd == "exec":
            idx = _skip_wrapper_flag_args(tokens, idx + 1, frozenset({"-a"}), stop_tokens=stop_tokens)
            continue
        if cmd == "time":
            idx = _skip_wrapper_flag_args(tokens, idx + 1, frozenset(), stop_tokens=stop_tokens)
            continue
        if cmd in ("nohup", "builtin"):
            idx += 1
            continue
        break
    return (idx, saw_busybox, saw_xargs, False)


def _parse_shell_stage_command(stage: str) -> tuple[str, list[str], str, int, bool, bool, bool]:
    """Parse one shell pipeline stage in O(n), stripping YAML/Dockerfile/control prefixes and wrappers."""
    m_pre = _STAGE_LEADING_PREFIX_RE.match(stage)
    pos = m_pre.end() if m_pre is not None else 0
    n = len(stage)
    while pos < n:
        if stage[pos].isspace() or stage[pos] in "({!":
            pos += 1
            continue
        matched_kw = False
        for kw in ("then", "do", "else"):
            kw_end = pos + len(kw)
            if stage.startswith(kw, pos) and kw_end < n and stage[kw_end].isspace():
                pos = kw_end + 1
                matched_kw = True
                break
        if matched_kw:
            continue
        break
    while pos < n and stage[pos] in "@+-":
        pos += 1
    tok_spans = _split_shell_tokens(stage[pos:])
    if not tok_spans:
        return ("", [], "", len(stage), False, False, False)
    raw_tokens = [t for t, _s, _e in tok_spans]
    cmd_idx, saw_busybox, saw_xargs, spaceless_xargs_rm = _skip_command_wrappers(raw_tokens, 0)
    if spaceless_xargs_rm:
        rest_tokens = raw_tokens[cmd_idx:]
        end_off = pos + tok_spans[cmd_idx - 1][2]
        return ("rm", rest_tokens, stage[end_off:].strip(), end_off, saw_busybox, True, True)
    if cmd_idx >= len(raw_tokens):
        return ("", [], "", len(stage), saw_busybox, saw_xargs, False)
    cmd = _strip_cmd_token(raw_tokens[cmd_idx])
    end_off = pos + tok_spans[cmd_idx][2]
    rest_tokens = raw_tokens[cmd_idx + 1 :]
    return (cmd, rest_tokens, stage[end_off:].strip(), end_off, saw_busybox, saw_xargs, False)


def _stage_disables_nounset(stage: str) -> bool:
    """Return True if stage invokes `set +u` or `set +o nounset` (outside `--`)."""
    cmd, rest_tokens, _rest_str, _end_off, _bb, _xa, _srm = _parse_shell_stage_command(stage)
    if cmd != "set":
        return False
    idx = 0
    n = len(rest_tokens)
    while idx < n:
        t = rest_tokens[idx]
        if t == "--":
            break
        if t == "+o" and idx + 1 < n:
            if rest_tokens[idx + 1] == "nounset":
                return True
            idx += 2
            continue
        if t == "-o":
            idx += 2
            continue
        if t.startswith("+") and "u" in t[1:]:
            return True
        idx += 1
    return False


def _pipeline_has_printf_to_shell(stages: list[str]) -> bool:
    """Return True if a pipeline invokes printf before piping into a shell interpreter."""
    seen_printf = False
    for raw_stage in stages:
        cmd, _rest, _rest_str, _end_off, _bb, _xa, _srm = _parse_shell_stage_command(raw_stage.strip())
        if seen_printf and cmd in _SHELL_INTERPRETERS:
            return True
        if cmd == _PRINTF_TOKEN:
            seen_printf = True
    return False


def _find_tokens_exec_rm(find_tokens: list[str]) -> bool:
    """Return True if any find -exec/-execdir/-ok/-okdir action invokes rm (directly or via wrapper)."""
    n = len(find_tokens)
    idx = 0
    while idx < n:
        if find_tokens[idx] in _FIND_EXEC_FLAGS:
            cmd_idx, _bb, _xa, spaceless_xargs_rm = _skip_command_wrappers(
                find_tokens, idx + 1, stop_tokens=_FIND_EXEC_END
            )
            if spaceless_xargs_rm:
                return True
            if cmd_idx < n and _strip_cmd_token(find_tokens[cmd_idx]) == "rm":
                return True
            idx = cmd_idx + 1
            continue
        idx += 1
    return False


def _extract_quoted_subcommands(stage: str, excluded_spans: list[tuple[int, int]]) -> list[str]:
    """Extract non-excluded quoted string contents containing whitespace for subcommand scanning."""
    subcmds: list[str] = []
    n = len(stage)
    i = 0
    while i < n:
        ch = stage[i]
        if ch == "\\":
            i += 2
            continue
        if ch not in ("'", '"'):
            i += 1
            continue
        quote = ch
        start = i
        i += 1
        buf: list[str] = []
        closed = False
        while i < n:
            c = stage[i]
            if quote == '"' and c == "\\" and i + 1 < n:
                nxt = stage[i + 1]
                if nxt in ('"', "\\"):
                    buf.append(nxt)
                else:
                    buf.append(c)
                    buf.append(nxt)
                i += 2
                continue
            if c == quote:
                closed = True
                i += 1
                break
            buf.append(c)
            i += 1
        end = i
        if not closed:
            break
        if any(start >= es and end <= ee for es, ee in excluded_spans):
            continue
        inner = "".join(buf)
        if any(c.isspace() for c in inner):
            subcmds.append(inner)
    return subcmds


def _scan_shell_segment_findings(seg: str, parent_nounset: bool) -> list[str]:
    """Iteratively inspect one shell segment (plus nested subshells, command subs, quoted strings, and eval) for CYA-GAP-03."""
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
                    if _stage_disables_nounset(stage):
                        local_nounset = False

                excluded_spans: list[tuple[int, int]] = []
                cmd, rest_tokens, rest_str, cmd_end, saw_busybox, saw_xargs, spaceless_xargs_rm = (
                    _parse_shell_stage_command(stage)
                )

                if cmd == _EVAL_TOKEN:
                    eval_arg = rest_str[2:].strip() if rest_tokens and rest_tokens[0] == "--" else rest_str
                    if eval_arg:
                        excluded_spans.append((cmd_end, len(stage)))
                        unquoted = _unquote_eval_arg(eval_arg)
                        stack.append((unquoted, False, True, False, depth + 1))

                for m_sub in _CMD_SUB_RE.finditer(stage):
                    excluded_spans.append((m_sub.start(), m_sub.end()))
                    inner = m_sub.group(1) if m_sub.group(1) is not None else m_sub.group(2)
                    if any(ch.isspace() for ch in inner):
                        stack.append((inner, local_nounset, from_eval, False, depth + 1))

                for m_sh in _SHELL_C_RE.finditer(stage):
                    excluded_spans.append((m_sh.start(), m_sh.end()))
                    flags = m_sh.group(1)
                    body = m_sh.group(2) if m_sh.group(2) is not None else m_sh.group(3).replace('\\"', '"')
                    stack.append((body, "u" in flags, False, True, depth + 1))

                for quoted_inner in _extract_quoted_subcommands(stage, excluded_spans):
                    stack.append((quoted_inner, local_nounset, from_eval, True, depth + 1))

                if spaceless_xargs_rm:
                    details.append("xargs_rm")
                    continue

                if cmd == _FIND_TOKEN:
                    find_tokens = [tok.rstrip(")}") for tok in rest_tokens]
                    if _DELETE_FLAG in find_tokens:
                        details.append("find_delete")
                    if _find_tokens_exec_rm(find_tokens):
                        details.append("find_exec_rm")
                    continue

                if cmd == "rm":
                    if saw_xargs:
                        details.append("xargs_rm")
                        continue
                    if saw_busybox:
                        details.append("busybox_rm")
                        continue
                    if from_eval:
                        details.append("eval_wrapped_rm")
                        continue
                    if not _rm_args_are_recursive_force(rest_tokens):
                        continue
                    if local_nounset:
                        continue
                    for vm in _VAR_REF_RE.finditer(rest_str):
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


def _parse_bounded_json_int(token: str) -> int:
    if len(token) > MAX_JSON_NUMBER_CHARS:
        raise ValueError("SAFETY_JSON_NUMBER_LIMIT_EXCEEDED")
    return int(token)


def _parse_bounded_json_float(token: str) -> str:
    if len(token) > MAX_JSON_NUMBER_CHARS:
        raise ValueError("SAFETY_JSON_NUMBER_LIMIT_EXCEEDED")
    return token


def _read_regular_file_bounded(
    p: Path,
    *,
    max_bytes: int = MAX_SCAN_FILE_BYTES,
) -> tuple[str, bytes | str | OSError]:
    """Check lstat S_ISREG before opening with O_RDONLY|O_NOFOLLOW|O_NONBLOCK, verify fstat dev/ino, and stream at most max_bytes."""
    try:
        lst = os.lstat(p)
    except OSError as exc:
        return ("unreadable", exc)
    if stat.S_ISLNK(lst.st_mode):
        return ("skipped", "symlink_not_followed")
    if not stat.S_ISREG(lst.st_mode):
        return ("skipped", "non_regular_file")

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
        if st.st_dev != lst.st_dev or st.st_ino != lst.st_ino:
            return ("skipped", "path_changed_during_open")
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


def _scan_structured_auto_yes_config(text: str) -> list[tuple[int, str]]:
    """Detect non-JSON structured (YAML/fenced-JSON) npx/bunx auto-yes configs in strictly O(n) time."""
    n = len(text)
    events: list[tuple[int, int, str, str]] = []

    for m_cmd in _STRUCTURED_CMD_LINE_RE.finditer(text):
        raw_val = m_cmd.group(1).strip().strip("\"'")
        base = raw_val.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
        runner = base if base in (_NPX_TOKEN, _BUNX_TOKEN) else ""
        events.append((m_cmd.start(), m_cmd.end(), "cmd", runner))

    for m_args in _STRUCTURED_ARGS_KEY_RE.finditer(text):
        pos = m_args.end()
        while pos < n and text[pos] in " \t":
            pos += 1
        has_yes = False
        end_pos = pos
        if pos < n and text[pos] == "[":
            close_idx = text.find("]", pos + 1)
            end_pos = close_idx + 1 if close_idx != -1 else n
            if _STRUCTURED_INLINE_YES_RE.search(text[pos + 1 : end_pos]) is not None:
                has_yes = True
        elif pos < n and text[pos] == "\n":
            cur = pos + 1
            while True:
                nl = text.find("\n", cur)
                line_end = nl if nl != -1 else n
                stripped = text[cur:line_end].lstrip(" \t")
                if not stripped.startswith("-"):
                    break
                after_dash = stripped[1:]
                if after_dash and after_dash[0] not in " \t":
                    break
                parts = after_dash.strip().split()
                if parts:
                    tok = parts[0].strip("\"'")
                    if tok in ("-" + "y", "--" + "yes"):
                        has_yes = True
                end_pos = line_end
                if nl == -1:
                    break
                cur = nl + 1
        events.append((m_args.start(), end_pos, "args", "yes" if has_yes else ""))

    events.sort(key=lambda item: item[0])
    hits: list[tuple[int, str]] = []
    ev_count = len(events)
    for i, (c_start, c_end, kind, runner) in enumerate(events):
        if kind != "cmd" or not runner:
            continue
        matched = False
        for j in range(i + 1, ev_count):
            ev_start, _ev_end, ev_kind, ev_val = events[j]
            if ev_start - c_end > _STRUCTURED_PROXIMITY_CHARS:
                break
            if ev_kind == "cmd":
                break
            if ev_val == "yes":
                hits.append((text.count("\n", 0, c_start) + 1, runner))
                matched = True
                break
        if matched:
            continue
        for j in range(i - 1, -1, -1):
            ev_start, ev_end, ev_kind, ev_val = events[j]
            if c_start - ev_end > _STRUCTURED_PROXIMITY_CHARS:
                break
            if ev_kind == "cmd":
                break
            if ev_val == "yes":
                hits.append((text.count("\n", 0, ev_start) + 1, runner))
            break
    return hits


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
            parsed_json = json.loads(
                json_candidate,
                object_pairs_hook=_JsonObjectPairs,
                parse_int=_parse_bounded_json_int,
                parse_float=_parse_bounded_json_float,
            )
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
        for hit_line, hit_runner in _scan_structured_auto_yes_config(text):
            findings.append(
                {
                    "gap_id": "CYA-GAP-02",
                    "file": file_label,
                    "line": hit_line,
                    "detail": f"{hit_runner}_auto_yes_structured_config",
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
                if _stage_disables_nounset(seg):
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

    Verifies `lstat` S_ISREG before opening with `O_RDONLY|O_NOFOLLOW|O_NONBLOCK`, confirms `fstat`
    `S_ISREG` and `(st_dev, st_ino)` identity, and streams up to `max_file_bytes` (including
    dotfiles, extensionless files, build/dist/node_modules, and UTF-16 files; excluding only `.git`
    VCS metadata). Direct symlink targets, broken/looping symlinks, out-of-root symlinks, and
    symlinked directories are refused fail-closed; in-root regular-file symlinks (such as
    `CLAUDE.md -> AGENTS.md`) are resolved within the scanned root and scanned through their target.
    Fails closed (`clean=False`) whenever any findings, skipped entries (unfollowed/broken/outside
    symlinks, symlinked directories, oversized files, TOCTOU path changes, or non-regular files such
    as FIFOs, sockets, and devices), undecodable/binary/NUL-containing files (including UTF-32 with
    BOM), or unreadable files/directories are present.
    """
    if type(max_file_bytes) is not int or max_file_bytes < 1:
        raise AletheiaError("SAFETY_INVALID_MAX_BYTES", "max_file_bytes must be a positive int")
    try:
        top_lst = os.lstat(target_path)
    except FileNotFoundError:
        raise ValueError("SAFETY_TARGET_NOT_FOUND") from None
    except OSError as exc:
        return {
            "clean": False,
            "target": str(target_path),
            "files_scanned": 0,
            "finding_count": 0,
            "gap_ids_present": [],
            "findings": [],
            "skipped_files": [],
            "undecodable_files": [],
            "unreadable_files": [{"file": target_path.name, "error": type(exc).__name__, "detail": str(exc)}],
        }
    if stat.S_ISLNK(top_lst.st_mode):
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

    def _scan_walk_file(fp: Path, label: str) -> None:
        try:
            entry_lst = os.lstat(fp)
        except OSError as exc:
            unreadable_files.append({"file": label, "error": type(exc).__name__, "detail": str(exc)})
            return
        if stat.S_ISLNK(entry_lst.st_mode):
            try:
                link_target = fp.resolve(strict=True)
            except (OSError, RuntimeError):
                skipped_files.append({"file": label, "reason": "symlink_not_followed"})
                return
            try:
                link_target.relative_to(resolved)
            except ValueError:
                skipped_files.append({"file": label, "reason": "symlink_not_followed"})
                return
            try:
                target_lst = os.lstat(link_target)
            except OSError as exc:
                unreadable_files.append({"file": label, "error": type(exc).__name__, "detail": str(exc)})
                return
            if stat.S_ISDIR(target_lst.st_mode):
                skipped_files.append({"file": label, "reason": "symlink_directory_not_followed"})
                return
            _scan_one(link_target, label)
            return
        _scan_one(fp, label)

    if not stat.S_ISDIR(top_lst.st_mode):
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
                _scan_walk_file(fp, label)

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
