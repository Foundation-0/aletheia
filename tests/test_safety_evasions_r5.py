#!/usr/bin/env python3
"""Regression & boundary test suite for aletheia/safety.py hardening (Foundation-0/aletheia#13).

Zero bare asserts (100% python3 -O parity). All adversarial test payloads are
assembled programmatically so this file itself scans clean under
`aletheia audit-check --strict-ancestors --safety-scan`.
"""
from __future__ import annotations

import errno
import json
import os
from pathlib import Path
import socket
import stat
import sys
import tempfile
import unittest
from unittest import mock

CLI_ROOT = Path(__file__).resolve().parent.parent
if str(CLI_ROOT) not in sys.path:
    sys.path.insert(0, str(CLI_ROOT))

from aletheia import safety
from aletheia.cli import main as cli_main
from aletheia.strict_io import AletheiaError

# Programmatically assembled tokens so static safety scanning of this test file stays clean.
_EV = "ev" + "al"
_RM = "r" + "m"
_RF = "-r" + "f"
_FN = "fi" + "nd"
_DEL = "-" + "delete"
_BB = "busy" + "box"
_XA = "xa" + "rgs"
_PR = "pri" + "ntf"
_BX = "b" + "unx"
_NX = "n" + "px"
_YF = "-" + "y"
_YESF = "--y" + "es"
_SH = "s" + "h"
_BASH = "ba" + _SH
_DASH = "da" + _SH
_ZSH = "z" + _SH
_CMD = "com" + "mand"
_ARGS = "a" + "rgs"


class TestSafetyEvasionsAndBounds(unittest.TestCase):
    def _assert_hits(self, text: str, filename: str, gap_id: str, detail: str) -> dict[str, object]:
        res = safety.scan_text_safety_surface(text, filename)
        self.assertFalse(res["clean"], msg=f"expected hit ({gap_id}/{detail}) for {text!r}")
        self.assertIn(gap_id, res["gap_ids_present"], msg=f"missing {gap_id} in {res}")
        details = [f.get("detail") for f in res["findings"]]
        self.assertIn(detail, details, msg=f"missing {detail!r} in {details} for {text!r}")
        return res

    def test_01_eval_wrapped_rm_and_unquote_boundaries(self) -> None:
        rm_root = f"{_RM} {_RF} /"
        rm_var = f'{_RM} {_RF} "$DIR"'
        cases = (
            f"{_EV} '{rm_root}'\n",
            f'{_EV} "{_RM} {_RF} /tmp/work"\n',
            f'{_EV} "{_RM} {_RF} \\"$DIR\\""\n',
            f"{_EV} 'echo ok; {rm_root}'\n",
            f"{_EV} {rm_root}\n",
            f'{_EV} "r""m {_RF} /"\n',
            f"{_EV} $'{rm_root}'\n",
            f"{_EV} r\\m {_RF} /\n",
            f"{_EV} -- '{rm_root}'\n",
            f"\\{_EV} '{rm_root}'\n",
            f"set -u\n{_EV} '{rm_var}'\n",
            f'{_BASH} -c "{_EV} \'{rm_root}\'"\n',
            f"out=$({_EV} '{rm_root}')\n",
            f"{_EV} '{_EV} \"{rm_root}\"'\n",
        )
        for idx, snippet in enumerate(cases):
            self._assert_hits(snippet, f"ev_{idx}.sh", "CYA-GAP-03", "eval_wrapped_rm")

        # Deeply nested eval chain fails closed at exact _MAX_SHELL_NESTING boundary (8 OK, 9 fails)
        benign_8 = "echo ok"
        for _ in range(safety._MAX_SHELL_NESTING):
            benign_8 = f"{_EV} {benign_8}"
        self.assertTrue(safety.scan_text_safety_surface(benign_8 + "\n", "ev_depth8.sh")["clean"])
        benign_9 = f"{_EV} {benign_8}"
        self._assert_hits(benign_9 + "\n", "ev_depth9.sh", "CYA-GAP-03", "shell_nesting_depth_exceeded")

        # Direct _unquote_eval_arg boundary & escaping tests
        self.assertEqual(safety._unquote_eval_arg("'a\"b'"), 'a"b')
        self.assertEqual(safety._unquote_eval_arg("a'b'"), "ab")
        self.assertEqual(safety._unquote_eval_arg('"a\\"b\\\\c\\$d\\`e\\xf"'), 'a"b\\c$d`e\\xf')
        self.assertEqual(safety._unquote_eval_arg('"unclosed\\'), "unclosed\\")
        self.assertEqual(safety._unquote_eval_arg("trail\\"), "trail\\")
        self.assertEqual(safety._unquote_eval_arg("end$"), "end$")
        self.assertEqual(safety._unquote_eval_arg("$VAR"), "$VAR")
        self.assertEqual(safety._unquote_eval_arg("$'x'"), "x")
        self.assertEqual(safety._unquote_eval_arg("a\\ b"), "a b")

        # Clean controls
        for idx, clean_snippet in enumerate(
            (
                f'{_EV} "$(ssh-agent -s)"\n',
                f"{_EV} 'echo {_RM}'\n",
                f"x = {_EV}('1 + 1')\n",
                f"python3 -m aletheia calculus --{_EV} '1 + 1'\n",
                f"# {_EV} '{rm_root}'\n",
            )
        ):
            res = safety.scan_text_safety_surface(clean_snippet, f"ev_clean_{idx}.sh")
            self.assertTrue(res["clean"], msg=f"false positive on {clean_snippet!r}: {res}")

    def test_02_find_delete_and_exec_rm(self) -> None:
        del_cases = (
            f"{_FN} /tmp {_DEL}\n",
            f'{_FN} "$DIR" -type f {_DEL}\n',
            f"/usr/bin/{_FN} . -name '*.o' {_DEL}\n",
            f"sudo {_FN} /var/tmp -maxdepth 1 {_DEL}\n",
            f"{_BB} {_FN} . {_DEL}\n",
            f"({_FN} . {_DEL})\n",
            f"run: {_FN} /tmp {_DEL}\n",
            f"RUN {_FN} /tmp {_DEL}\n",
            f"clean:\n\t@{_FN} $(BUILD) {_DEL}\n",
            f"{_SH} -c '{_FN} . {_DEL}'\n",
            f"{_EV} '{_FN} . {_DEL}'\n",
            f"out=$({_FN} . {_DEL})\n",
            f"{_FN} \\\n  . {_DEL}\n",
            f"{_FN} . -exec echo {{}} \\; {_DEL}\n",
            f"{_FN} . -name 'a;b' {_DEL}\n",
            f"{_FN} . -name 'a|b' {_DEL}\n",
        )
        for idx, snippet in enumerate(del_cases):
            self._assert_hits(snippet, f"fn_del_{idx}.sh", "CYA-GAP-03", "find_delete")

        exec_cases = (
            f"{_FN} /tmp -exec {_RM} {_RF} {{}} +\n",
            f"{_FN} . -execdir /bin/{_RM} {_RF} {{}} \\;\n",
            f"{_FN} . -exec \\{_RM} {_RF} {{}} +\n",
            f"{_FN} . -exec echo {{}} \\; -exec {_RM} {_RF} {{}} \\;\n",
            f"{_FN} . -exec '{_RM}' {_RF} {{}} +\n",
            f'{_FN} . -exec "{_RM}" {_RF} {{}} +\n',
            f"{_FN} . -exec {_BB} {_RM} {_RF} {{}} +\n",
            f"{_FN} . -exec /bin/{_BB} {_RM} {_RF} {{}} +\n",
            f"{_FN} . -exec env {_RM} {_RF} {{}} +\n",
            f"{_FN} . -exec /usr/bin/env /bin/{_RM} {_RF} {{}} +\n",
            f"{_FN} . -exec command {_RM} {_RF} {{}} +\n",
            f"{_FN} . -exec sudo {_RM} {_RF} {{}} +\n",
            f"{_FN} . -ok {_RM} {_RF} {{}} \\;\n",
            f"{_FN} . -okdir {_RM} {_RF} {{}} \\;\n",
        )
        for idx, snippet in enumerate(exec_cases):
            self._assert_hits(snippet, f"fn_exec_{idx}.sh", "CYA-GAP-03", "find_exec_rm")

        for idx, clean_snippet in enumerate(
            (
                f"{_FN} . -name '*.py' -print\n",
                f"{_FN} . -name 'auto{_DEL}.txt'\n",
                f"{_FN} . -name {_RM}\n",
                f"{_FN} . -exec echo {{}} +\n",
                f"{_FN} . -exec echo {{}} \\;\n",
                f"{_FN} . -execdir ls {{}} +\n",
                f"{_FN} . -ok echo {{}} \\;\n",
                f"{_FN} . -exec env\n",
                f"{_FN} . -exec\n",
                f"# {_FN} /tmp {_DEL}\n",
            )
        ):
            res = safety.scan_text_safety_surface(clean_snippet, f"fn_clean_{idx}.sh")
            self.assertTrue(res["clean"], msg=f"false positive on {clean_snippet!r}: {res}")

    def test_03_busybox_rm_and_spaceless_xargs(self) -> None:
        bb_cases = (
            f"{_BB} {_RM} {_RF} /\n",
            f'{_BB} {_RM} {_RF} "$DIR"\n',
            f'/bin/{_BB} {_RM} {_RF} "$DIR"\n',
            f"sudo /usr/bin/{_BB} {_RM} {_RF} /\n",
            f'set -u\n{_BB} {_RM} {_RF} "$DIR"\n',
            f"{_SH} -c '{_BB} {_RM} {_RF} /'\n",
            f"{_EV} '{_BB} {_RM} {_RF} /'\n",
            f"run: {_BB} {_RM} {_RF} /\n",
            f'RUN {_BB} {_RM} {_RF} "$TMP"\n',
        )
        for idx, snippet in enumerate(bb_cases):
            self._assert_hits(snippet, f"bb_{idx}.sh", "CYA-GAP-03", "busybox_rm")

        for idx, clean_bb in enumerate((f"{_BB} echo hi\n", f"{_BB} ls -la\n", f"# {_BB} {_RM} {_RF} /\n")):
            res = safety.scan_text_safety_surface(clean_bb, f"bb_clean_{idx}.sh")
            self.assertTrue(res["clean"], msg=f"false positive on {clean_bb!r}: {res}")

        xa_cases = (
            f"{_FN} . |{_XA} {_RM} {_RF}\n",
            f"{_FN} . |{_XA} {_RM}\n",
            f"{_FN} . -print0 |{_XA} -0 {_RM} {_RF}\n",
            f"{_FN} . -print0 | {_XA} -0 {_RM} {_RF}\n",
            f"{_FN} . -print0 | {_XA}-0 {_RM} {_RF}\n",
            f"echo / | {_XA}{_RM} {_RF}\n",
            f"echo / | {_XA}{_RM}\n",
            f"{_FN} . -print0 | {_XA} -0{_RM} {_RF}\n",
            f"{_FN} . -print0 | {_XA}-0{_RM} {_RF}\n",
            f"{_XA} -I{{}} {_RM} {_RF} {{}}\n",
            f"{_XA} -I{{}}{_RM} {_RF} {{}}\n",
            f"{_FN} . -print0 | {_XA} --null {_RM} {_RF}\n",
            f"{_FN} . | /usr/bin/{_XA} -0 /bin/{_RM} {_RF}\n",
            f"sudo {_XA} -0 -- {_RM} {_RF}\n",
            f"{_BB} {_XA} {_RM} {_RF}\n",
            f"{_XA} -n 1 -P 4 {_RM} {_RF}\n",
            f"{_XA} -a files.txt {_RM} {_RF}\n",
            f"echo / | {_XA} -s 1024 {_RM} {_RF}\n",
            f"echo / | {_XA} -J {{}} {_RM} {_RF} {{}}\n",
            f"echo / | {_XA} --max-args 1 {_RM} {_RF}\n",
            f"echo / | {_XA} --arg-file files.txt {_RM} {_RF}\n",
            f"echo / | {_XA} -0 env {_RM} {_RF}\n",
            f"echo / | {_XA} -0 /usr/bin/env {_RM} {_RF}\n",
            f"echo / | {_XA} -0 '{_RM}' {_RF}\n",
            f'echo / | {_XA} -0 "{_RM}" {_RF}\n',
            f"{_SH} -c '{_FN} . |{_XA} {_RM} {_RF}'\n",
        )
        for idx, snippet in enumerate(xa_cases):
            self._assert_hits(snippet, f"xa_{idx}.sh", "CYA-GAP-03", "xargs_rm")

        for idx, clean_xa in enumerate(
            (
                f"{_FN} . -name '*.py' | {_XA} wc -l\n",
                f"{_FN} . -print0 | {_XA} -0 grep pat\n",
                f"{_XA} -a files.txt echo\n",
                f"echo / | {_XA} --max-args 1 echo\n",
                f"echo a | {_XA} -0fo{_RM}\n",
                f"echo a | {_XA} --platfo{_RM} foo\n",
                f"echo a | {_XA} {_RM}dir\n",
                f"# {_FN} . |{_XA} {_RM} {_RF}\n",
            )
        ):
            res = safety.scan_text_safety_surface(clean_xa, f"xa_clean_{idx}.sh")
            self.assertTrue(res["clean"], msg=f"false positive on {clean_xa!r}: {res}")

    def test_04_printf_pipe_to_shell_and_pipeline_splitter(self) -> None:
        pipe_cases = (
            f"{_PR} '{_RM} {_RF} /\\n' | {_SH}\n",
            f"{_PR} 'id\\n' | {_BASH}\n",
            f"{_PR} 'id\\n'|{_DASH}\n",
            f"{_PR} 'id\\n' | {_ZSH}\n",
            f"{_PR} 'id\\n' | /bin/{_SH}\n",
            f"{_PR} 'id\\n' | /usr/bin/env {_BASH}\n",
            f"{_PR} 'id\\n' | /usr/bin/env -S {_ZSH}\n",
            f"{_PR} 'id\\n' | sudo {_SH}\n",
            f"{_PR} 'id\\n' | /bin/{_BB} {_SH}\n",
            f"{_PR} 'id\\n' |& {_BASH}\n",
            f"{_PR} 'a|b\\n' | {_SH}\n",
            f"{_PR} 'id\\n' | tr a b | {_SH}\n",
            f"{_PR} 'id\\n' \\\n  | {_SH}\n",
            f"run: {_PR} 'id\\n' | {_BASH}\n",
            f"RUN {_PR} 'id\\n' | {_SH}\n",
            f'{_BASH} -c \'{_PR} "id\\n" | {_DASH}\'\n',
            f"out=$({_PR} 'id\\n' | {_ZSH})\n",
            f"out=`{_PR} 'id\\n' | {_SH}`\n",
            f'{_EV} \'{_PR} "id\\n" | {_SH}\'\n',
        )
        for idx, snippet in enumerate(pipe_cases):
            self._assert_hits(snippet, f"pr_{idx}.sh", "CYA-GAP-03", "printf_pipe_to_shell")

        for idx, clean_pr in enumerate(
            (
                f"{_PR} 'hello %s\\n' \"$NAME\"\n",
                f"{_PR} 'a\\nb\\n' | sort\n",
                f"{_PR} 'a\\n' | {_SH}a256sum\n",
                f"{_PR} 'a\\n' | {_SH}uf\n",
                f"{_PR} 'echo hi | {_SH}\\n'\n",
                f"{_PR} 'ok\\n' && {_SH} script.sh\n",
                f"{_PR} 'ok\\n' || {_SH} script.sh\n",
                f"{_SH} script.sh | {_PR} 'ok\\n'\n",
                f"# {_PR} 'id\\n' | {_SH}\n",
            )
        ):
            res = safety.scan_text_safety_surface(clean_pr, f"pr_clean_{idx}.sh")
            self.assertTrue(res["clean"], msg=f"false positive on {clean_pr!r}: {res}")

        # Direct _split_shell_pipelines boundary & operator tests
        self.assertEqual(safety._split_shell_pipelines("echo 'a;b|c&&d'"), [["echo 'a;b|c&&d'"]])
        self.assertEqual(safety._split_shell_pipelines('echo "a;\\"b|c"'), [['echo "a;\\"b|c"']])
        self.assertEqual(safety._split_shell_pipelines('echo "unclosed\\'), [['echo "unclosed\\']])
        self.assertEqual(safety._split_shell_pipelines("echo a\\;b && echo c"), [["echo a\\;b "], [" echo c"]])
        self.assertEqual(safety._split_shell_pipelines("echo trail\\"), [["echo trail\\"]])
        self.assertEqual(safety._split_shell_pipelines("x=$(a | (b; c)); echo $"), [["x=$(a | (b; c))"], [" echo $"]])
        self.assertEqual(safety._split_shell_pipelines("x=`a | b`; y=1"), [["x=`a | b`"], [" y=1"]])
        self.assertEqual(safety._split_shell_pipelines("echo a & echo b"), [["echo a "], [" echo b"]])
        self.assertEqual(safety._split_shell_pipelines("&echo a"), [[""], ["echo a"]])
        self.assertEqual(safety._split_shell_pipelines("&echo >"), [[""], ["echo >"]])
        self.assertEqual(safety._split_shell_pipelines("echo a &"), [["echo a "], [""]])
        self.assertEqual(safety._split_shell_pipelines("echo ok 2>&1"), [["echo ok 2>&1"]])
        self.assertEqual(safety._split_shell_pipelines("cat <&0"), [["cat <&0"]])
        self.assertEqual(safety._split_shell_pipelines("echo ok &>out.log"), [["echo ok &>out.log"]])
        self.assertEqual(safety._split_shell_pipelines("a || b | c |& d"), [["a "], [" b ", " c ", " d"]])
        self.assertEqual(safety._split_shell_pipelines("echo a |"), [["echo a ", ""]])
        # Background & followed by unguarded rm -rf "$X" still triggers CYA-GAP-03
        self._assert_hits(f'echo bg & {_RM} {_RF} "$X"\n', "bg.sh", "CYA-GAP-03", "unguarded_rm_rf_variable")
        # Indented / non-first-segment set -u and heredoc block-depth isolation
        self._assert_hits(f'  set -u\n{_RM} {_RF} "$X"\n', "indent_u.sh", "CYA-GAP-03", "unguarded_rm_rf_variable")
        self._assert_hits(f'false && set -u\n{_RM} {_RF} "$X"\n', "seg1_u.sh", "CYA-GAP-03", "unguarded_rm_rf_variable")
        hd_open_safe = f"cat <<'EOF'\nif true; then\nEOF\nset -u\n{_RM} {_RF} \"$X\"\n"
        self.assertTrue(safety.scan_text_safety_surface(hd_open_safe, "hd_open_safe.sh")["clean"])
        hd_close_bad = f"if false; then\ncat <<'EOF'\nfi\nEOF\nset -u\nfi\n{_RM} {_RF} \"$X\"\n"
        self._assert_hits(hd_close_bad, "hd_close_bad.sh", "CYA-GAP-03", "unguarded_rm_rf_variable")

    def test_05_bunx_auto_yes_and_duplicate_json_keys(self) -> None:
        for idx, line in enumerate(
            (
                f"{_BX} {_YF} evil-pkg\n",
                f"{_BX} {_YESF} evil-pkg\n",
                f"{_BX} -q {_YF} evil-pkg\n",
                f"/usr/local/bin/{_BX} {_YF} evil-pkg\n",
            )
        ):
            self._assert_hits(line, f"bx_{idx}.sh", "CYA-GAP-02", "bunx_auto_yes")

        for clean_bx in (f"{_BX} safe-pkg\n", f"{_BX} --no-yes safe-pkg\n"):
            self.assertTrue(safety.scan_text_safety_surface(clean_bx, "bx_ok.sh")["clean"])

        # Structured JSON & YAML bunx auto-yes
        json_bx_cases = (
            json.dumps({_CMD: _BX, _ARGS: [_YF, "evil"]}),
            json.dumps({_CMD: f"/usr/local/bin/{_BX}", _ARGS: [_YESF, "evil"]}),
            json.dumps({_CMD: f"C:\\bin\\{_BX}", _ARGS: [_YF, "evil"]}),
        )
        for idx, cfg in enumerate(json_bx_cases):
            self._assert_hits(cfg, f"bx_{idx}.json", "CYA-GAP-02", "bunx_auto_yes_structured_config")

        # Non-string command / non-list args / non-args list / non-str arg element / safe string arg stay clean
        self.assertTrue(safety.scan_text_safety_surface(json.dumps({_CMD: 123, _ARGS: [_YF]}), "ok1.json")["clean"])
        self.assertTrue(safety.scan_text_safety_surface(json.dumps({_CMD: _BX, _ARGS: _YF}), "ok2.json")["clean"])
        self.assertTrue(safety.scan_text_safety_surface(json.dumps({_CMD: _BX, _ARGS: 123}), "ok3.json")["clean"])
        self.assertTrue(safety.scan_text_safety_surface(json.dumps({_CMD: _BX, "other": [_YF]}), "ok4.json")["clean"])
        self.assertTrue(safety.scan_text_safety_surface(json.dumps({_CMD: _BX, _ARGS: [123, "pkg"]}), "ok5.json")["clean"])
        self.assertTrue(safety.scan_text_safety_surface(json.dumps({_CMD: _BX, _ARGS: ["safe-pkg"]}), "ok6.json")["clean"])

        yaml_bx_cmd_first = f"{_CMD}: {_BX}\n{_ARGS}:\n  - {_YF}\n  - evil\n"
        yaml_bx_args_first = f"{_ARGS}:\n  - {_YESF}\n  - evil\n{_CMD}: /opt/bin/{_BX}\n"
        self._assert_hits(yaml_bx_cmd_first, "bx1.yml", "CYA-GAP-02", "bunx_auto_yes_structured_config")
        self._assert_hits(yaml_bx_args_first, "bx2.yml", "CYA-GAP-02", "bunx_auto_yes_structured_config")

        # Duplicate JSON keys (simple, nested, shadowed npx/bunx, unicode-escaped key, duplicate args, BOM)
        self._assert_hits('{"a":1,"a":2}\n', "dup1.json", "CYA-GAP-02", "duplicate_json_key")
        self._assert_hits('{"servers":[{"k":1,"k":2}]}\n', "dup2.json", "CYA-GAP-02", "duplicate_json_key")

        dup_shadow_npx = (
            '{"' + _CMD + '":"' + _NX + '","' + _CMD + '":"echo","' + _ARGS + '":["' + _YF + '","evil"]}'
        )
        r_sn = self._assert_hits(dup_shadow_npx, "dup_npx.json", "CYA-GAP-02", "duplicate_json_key")
        self.assertIn("npx_auto_yes_structured_config", [f["detail"] for f in r_sn["findings"]])

        dup_shadow_bx = (
            '{"' + _CMD + '":"' + _BX + '","' + _CMD + '":"echo","' + _ARGS + '":["' + _YF + '","evil"]}'
        )
        r_sb = self._assert_hits(dup_shadow_bx, "dup_bx.json", "CYA-GAP-02", "duplicate_json_key")
        self.assertIn("bunx_auto_yes_structured_config", [f["detail"] for f in r_sb["findings"]])

        dup_esc = (
            '{"\\u0063o' + "mmand" + '":"' + _NX + '","' + _CMD + '":"echo","' + _ARGS + '":["' + _YF + '","evil"]}'
        )
        r_esc = self._assert_hits(dup_esc, "dup_esc.json", "CYA-GAP-02", "duplicate_json_key")
        self.assertIn("npx_auto_yes_structured_config", [f["detail"] for f in r_esc["findings"]])

        dup_args = (
            '{"' + _CMD + '":"' + _NX + '","' + _ARGS + '":["' + _YF + '","evil"],"' + _ARGS + '":["--help"]}'
        )
        r_da = self._assert_hits(dup_args, "dup_args.json", "CYA-GAP-02", "duplicate_json_key")
        self.assertIn("npx_auto_yes_structured_config", [f["detail"] for f in r_da["findings"]])

        r_bom = self._assert_hits('\ufeff{"a":1,"a":2}', "dup_bom.json", "CYA-GAP-02", "duplicate_json_key")
        self.assertIn("CYA-GAP-01", r_bom["gap_ids_present"])

        # Same key in distinct nested objects is NOT a duplicate
        self.assertTrue(safety.scan_text_safety_surface('{"a":{"a":1},"b":[1,2]}\n', "ok_nest.json")["clean"])

    def test_06_iterative_bounded_json_depth_and_parse_limits(self) -> None:
        cap = safety.MAX_JSON_DEPTH
        # Exact boundary: depth == cap passes; depth == cap + 1 fails closed
        self.assertTrue(safety.scan_text_safety_surface("[" * cap + "0" + "]" * cap, "d64_v.json")["clean"])
        self.assertTrue(safety.scan_text_safety_surface("[" * cap + "]" * cap, "d64_e.json")["clean"])
        self.assertTrue(safety.scan_text_safety_surface('{"a":' * cap + "1" + "}" * cap, "d64_d.json")["clean"])

        self._assert_hits("[" * (cap + 1) + "0" + "]" * (cap + 1), "d65_v.json", "CYA-GAP-02", "json_nesting_depth_exceeded")
        self._assert_hits("[" * (cap + 1) + "]" * (cap + 1), "d65_e.json", "CYA-GAP-02", "json_nesting_depth_exceeded")
        self._assert_hits('{"a":' * (cap + 1) + "1" + "}" * (cap + 1), "d65_d.json", "CYA-GAP-02", "json_nesting_depth_exceeded")

        # Extreme nesting (2,000 levels) never raises RecursionError
        self._assert_hits("[" * 2000 + "0" + "]" * 2000, "d2000_l.json", "CYA-GAP-02", "json_nesting_depth_exceeded")
        self._assert_hits('{"a":' * 2000 + "1" + "}" * 2000, "d2000_d.json", "CYA-GAP-02", "json_nesting_depth_exceeded")

        # Brackets inside strings & escaped quotes/backslashes do not trip depth cap
        brackets_in_str = '{"a":"' + "[" * (cap + 30) + '","b":"\\"\\\\' + "{" * (cap + 30) + '","c":"\\\\"}'
        self.assertTrue(safety.scan_text_safety_surface(brackets_in_str, "str_br.json")["clean"])

        # Direct _check_json_nesting_depth boundary tests (siblings, string close before deep containers, underflow)
        flat_siblings = "[" + ('{"a":1},' * (cap + 10)) + '{"a":1}]'
        safety._check_json_nesting_depth(flat_siblings)
        self.assertTrue(safety.scan_text_safety_surface(flat_siblings, "flat_sib.json")["clean"])
        with self.assertRaises(AletheiaError) as ctx_d1:
            safety._check_json_nesting_depth('{"a":"x","b":' + "[" * (cap + 1) + "0" + "]" * (cap + 1) + "}")
        self.assertEqual(ctx_d1.exception.code, "SAFETY_JSON_DEPTH_EXCEEDED")
        with self.assertRaises(AletheiaError) as ctx_d2:
            safety._check_json_nesting_depth('{"a":' * (cap + 1) + "1" + "}" * (cap + 1))
        self.assertEqual(ctx_d2.exception.code, "SAFETY_JSON_DEPTH_EXCEEDED")
        with self.assertRaises(AletheiaError) as ctx_d3:
            safety._check_json_nesting_depth("{}}" + "[" * (cap + 1) + "]" * (cap + 1))
        self.assertEqual(ctx_d3.exception.code, "SAFETY_JSON_DEPTH_EXCEEDED")

        # Extra closing brace before cap+1 brackets must not underflow depth below 0
        self._assert_hits("{}}" + "[" * (cap + 1) + "]" * (cap + 1), "underflow.json", "CYA-GAP-02", "json_nesting_depth_exceeded")

        # Direct iterative tree API tests (plain dict, plain list, _JsonObjectPairs, scalar)
        self.assertEqual(safety._find_json_npx_yes_objects(42), 0)
        self.assertEqual(safety._find_json_npx_yes_objects([{_CMD: _BX, _ARGS: [_YF]}]), 1)

        nested_list_ok: object = 0
        nested_dict_ok: object = 0
        for _ in range(cap):
            nested_list_ok = [nested_list_ok]
            nested_dict_ok = {"a": nested_dict_ok}
        self.assertEqual(safety._find_json_npx_yes_objects(nested_list_ok), 0)
        self.assertEqual(safety._find_json_npx_yes_objects(nested_dict_ok), 0)

        for deep_obj in ([nested_list_ok], {"a": nested_dict_ok}, safety._JsonObjectPairs([("a", nested_dict_ok)])):
            with self.assertRaises(AletheiaError) as ctx:
                safety._find_json_npx_yes_objects(deep_obj)
            self.assertEqual(ctx.exception.code, "SAFETY_JSON_DEPTH_EXCEEDED")

        deep_2000: object = 0
        for _ in range(2000):
            deep_2000 = [deep_2000]
        with self.assertRaises(AletheiaError) as ctx2:
            safety._find_json_npx_yes_objects(deep_2000)
        self.assertEqual(ctx2.exception.code, "SAFETY_JSON_DEPTH_EXCEEDED")

        # Huge-digit JSON integer triggers ValueError in json.loads -> fail-closed finding, never crash
        huge_int_json = '{"n":1' + ("0" * 4500) + "}"
        self._assert_hits(huge_int_json, "huge_int.json", "CYA-GAP-02", "json_parse_limit_exceeded")

    def test_07_bounded_streaming_file_reads_and_special_files(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            clean_file = root / "ok.txt"
            clean_file.write_text("hello\n", encoding="utf-8")

            # Invalid max_file_bytes rejected fail-closed with AletheiaError
            for bad_cap in (False, True, 0, -1, "64"):
                with self.assertRaises(AletheiaError) as ctx:
                    safety.scan_directory_safety_surface(clean_file, max_file_bytes=bad_cap)  # type: ignore[arg-type]
                self.assertEqual(ctx.exception.code, "SAFETY_INVALID_MAX_BYTES")

            # Exact boundary: max_file_bytes == 64 (and == 1)
            f64 = root / "exact64.txt"
            f64.write_bytes(b"a" * 64)
            f65 = root / "over65.txt"
            f65.write_bytes(b"a" * 65)
            f1 = root / "one.txt"
            f1.write_bytes(b"x")
            f2 = root / "two.txt"
            f2.write_bytes(b"xy")

            r_eq = safety.scan_directory_safety_surface(f64, max_file_bytes=64)
            self.assertTrue(r_eq["clean"])
            self.assertEqual(r_eq["files_scanned"], 1)

            r_over = safety.scan_directory_safety_surface(f65, max_file_bytes=64)
            self.assertFalse(r_over["clean"])
            self.assertEqual(r_over["files_scanned"], 0)
            self.assertEqual(r_over["skipped_files"], [{"file": "over65.txt", "reason": "file_size_limit_exceeded"}])

            self.assertTrue(safety.scan_directory_safety_surface(f1, max_file_bytes=1)["clean"])
            r_two = safety.scan_directory_safety_surface(f2, max_file_bytes=1)
            self.assertFalse(r_two["clean"])
            self.assertEqual(r_two["skipped_files"], [{"file": "two.txt", "reason": "file_size_limit_exceeded"}])

            # Multi-chunk regular file (> 65536 B) succeeds when within cap
            big_ok = root / "multi_chunk.txt"
            big_len = safety._READ_CHUNK_BYTES + 128
            big_ok.write_bytes(b"x" * big_len)
            r_big = safety.scan_directory_safety_surface(big_ok, max_file_bytes=big_len)
            self.assertTrue(r_big["clean"])
            self.assertEqual(r_big["files_scanned"], 1)

            # Pseudo-regular file simulation (fstat reports st_size=0, streaming loop enforces cap)
            real_fstat = os.fstat

            def _zero_size_fstat(fd: int) -> os.stat_result:
                st = real_fstat(fd)
                vals = list(st)
                vals[stat.ST_SIZE] = 0
                return os.stat_result(vals)

            with mock.patch("aletheia.safety.os.fstat", side_effect=_zero_size_fstat):
                r_z_ok = safety.scan_directory_safety_surface(f64, max_file_bytes=64)
                self.assertTrue(r_z_ok["clean"])
                self.assertEqual(r_z_ok["files_scanned"], 1)

                r_z_over = safety.scan_directory_safety_surface(f65, max_file_bytes=64)
                self.assertFalse(r_z_over["clean"])
                self.assertEqual(r_z_over["files_scanned"], 0)
                self.assertEqual(
                    r_z_over["skipped_files"],
                    [{"file": "over65.txt", "reason": "file_size_limit_exceeded"}],
                )

            # Live /proc/kallsyms bounded read (when readable on host Linux)
            kallsyms = Path("/proc/kallsyms")
            if kallsyms.exists():
                r_ks = safety.scan_directory_safety_surface(kallsyms)
                self.assertFalse(r_ks["clean"])
                self.assertEqual(r_ks["files_scanned"], 0)
                if r_ks["skipped_files"]:
                    self.assertEqual(
                        r_ks["skipped_files"],
                        [{"file": "kallsyms", "reason": "file_size_limit_exceeded"}],
                    )

            # Character device (/dev/null) -> non_regular_file
            dev_null = Path("/dev/null")
            if dev_null.exists():
                r_dn = safety.scan_directory_safety_surface(dev_null)
                self.assertFalse(r_dn["clean"])
                self.assertEqual(r_dn["skipped_files"], [{"file": "null", "reason": "non_regular_file"}])

            # Symlink to regular file inside directory -> refused via O_NOFOLLOW (ELOOP)
            sym_dir = root / "sym_case"
            sym_dir.mkdir()
            sym_file = sym_dir / "sym_file.txt"
            sym_file.symlink_to(clean_file)
            r_sym = safety.scan_directory_safety_surface(sym_dir)
            self.assertFalse(r_sym["clean"])
            self.assertEqual(r_sym["files_scanned"], 0)
            self.assertEqual(r_sym["skipped_files"], [{"file": "sym_file.txt", "reason": "symlink_not_followed"}])

            # Direct symlink target_path (regular file, directory, and broken) refused before resolve()
            r_dsf = safety.scan_directory_safety_surface(sym_file)
            self.assertFalse(r_dsf["clean"])
            self.assertEqual(r_dsf["files_scanned"], 0)
            self.assertEqual(r_dsf["skipped_files"], [{"file": "sym_file.txt", "reason": "symlink_not_followed"}])

            real_sub = root / "real_sub"
            real_sub.mkdir()
            (real_sub / "ok.txt").write_text("clean\n", encoding="utf-8")
            sym_dir_target = root / "sym_dir_target"
            sym_dir_target.symlink_to(real_sub)
            r_dsd = safety.scan_directory_safety_surface(sym_dir_target)
            self.assertFalse(r_dsd["clean"])
            self.assertEqual(r_dsd["files_scanned"], 0)
            self.assertEqual(
                r_dsd["skipped_files"],
                [{"file": "sym_dir_target", "reason": "symlink_directory_not_followed"}],
            )

            broken_sym = root / "broken_sym"
            broken_sym.symlink_to(root / "nonexistent_target")
            r_brk = safety.scan_directory_safety_surface(broken_sym)
            self.assertFalse(r_brk["clean"])
            self.assertEqual(r_brk["files_scanned"], 0)
            self.assertEqual(r_brk["skipped_files"], [{"file": "broken_sym", "reason": "symlink_not_followed"}])

            # UNIX domain socket -> non_regular_file via ENXIO/EOPNOTSUPP
            if hasattr(socket, "AF_UNIX"):
                sock_dir = root / "sock_case"
                sock_dir.mkdir()
                sock_path = sock_dir / "srv.sock"
                srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                try:
                    srv.bind(str(sock_path))
                    r_sock = safety.scan_directory_safety_surface(sock_dir)
                    self.assertFalse(r_sock["clean"])
                    self.assertEqual(r_sock["skipped_files"], [{"file": "srv.sock", "reason": "non_regular_file"}])
                finally:
                    srv.close()

            # Mid-read OSError -> unreadable_files + fd closed cleanly
            with mock.patch("aletheia.safety.os.read", side_effect=OSError(errno.EIO, "io failure")):
                r_io = safety.scan_directory_safety_surface(clean_file)
                self.assertFalse(r_io["clean"])
                self.assertEqual(r_io["files_scanned"], 0)
                self.assertEqual(len(r_io["unreadable_files"]), 1)
                self.assertEqual(r_io["unreadable_files"][0]["file"], "ok.txt")

            # CLI end-to-end check on deep JSON + duplicate JSON keys + bunx auto-yes (no crash, exit 1)
            cli_dir = root / "cli_case"
            cli_dir.mkdir()
            (cli_dir / "deep.json").write_text("[" * 1500 + "0" + "]" * 1500, encoding="utf-8")
            (cli_dir / "dup.json").write_text('{"a":1,"a":2}\n', encoding="utf-8")
            (cli_dir / "run.sh").write_text(f"{_BX} {_YF} pkg\n", encoding="utf-8")
            with mock.patch("sys.stdout") as _out:
                rc_cli = cli_main(["safety-scan", str(cli_dir), "--json"])
            self.assertEqual(rc_cli, 1)


if __name__ == "__main__":
    unittest.main()
