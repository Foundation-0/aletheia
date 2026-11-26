#!/usr/bin/env python3
"""Regression & boundary test suite for aletheia/safety.py hardening (Foundation-0/aletheia#13).

Zero bare asserts (100% python3 -O parity). All adversarial test payloads are
assembled programmatically so this file itself scans clean under
`aletheia audit-check --strict-ancestors --safety-scan`.
"""
from __future__ import annotations

import errno
import io
import json
import os
from pathlib import Path
import random
import socket
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

CLI_ROOT = Path(__file__).resolve().parent.parent
if str(CLI_ROOT) not in sys.path:
    sys.path.insert(0, str(CLI_ROOT))

from aletheia import audit_check, safety
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
            f"{_FN} . -exec env FOO=1 {_RM} {_RF} {{}} +\n",
            f"{_FN} . -exec env -i {_RM} {_RF} {{}} +\n",
            f"{_FN} . -exec env -u HOME -- {_RM} {_RF} {{}} +\n",
            f"{_FN} . -exec command {_RM} {_RF} {{}} +\n",
            f"{_FN} . -exec command -p {_RM} {_RF} {{}} +\n",
            f"{_FN} . -exec command -- {_RM} {_RF} {{}} +\n",
            f"{_FN} . -exec sudo {_RM} {_RF} {{}} +\n",
            f"{_FN} . -exec sudo -n {_RM} {_RF} {{}} +\n",
            f"{_FN} . -exec sudo -u root {_RM} {_RF} {{}} +\n",
            f"{_FN} . -exec sudo FOO=1 -- {_RM} {_RF} {{}} +\n",
            f"{_FN} . -exec nice {_RM} {_RF} {{}} +\n",
            f"{_FN} . -exec nice -n 10 {_RM} {_RF} {{}} +\n",
            f"{_FN} . -exec nice -- {_RM} {_RF} {{}} +\n",
            f"{_FN} . -exec timeout 10 {_RM} {_RF} {{}} +\n",
            f"{_FN} . -exec timeout -s 9 10 {_RM} {_RF} {{}} +\n",
            f"{_FN} . -exec timeout -- 10 {_RM} {_RF} {{}} +\n",
            f"{_FN} . -exec stdbuf -oL {_RM} {_RF} {{}} +\n",
            f"{_FN} . -exec stdbuf -o L -- {_RM} {_RF} {{}} +\n",
            f"{_FN} . -exec nohup {_RM} {_RF} {{}} +\n",
            f"{_FN} . -exec builtin {_RM} {_RF} {{}} +\n",
            f"{_FN} . -exec time -p {_RM} {_RF} {{}} +\n",
            f"{_FN} . -exec exec -a alt -- {_RM} {_RF} {{}} +\n",
            f"{_FN} . -exec {_XA} -0 {_RM} {_RF} {{}} +\n",
            f"{_FN} . -exec {_XA}-0{_RM} {_RF} {{}} +\n",
            f"{_FN} . -exec sudo -u root env -i FOO=1 nice -n 5 timeout 10 stdbuf -oL command -p {_RM} {_RF} {{}} +\n",
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
                f"{_FN} . -exec env FOO=1 echo {{}} +\n",
                f"{_FN} . -exec command FOO=1 {_RM} {_RF} {{}} +\n",
                f"{_FN} . -exec sudo - {_RM} {{}} +\n",
                f"{_FN} . -exec sudo -u root ls {{}} +\n",
                f"{_FN} . -exec timeout 10 ls {{}} +\n",
                f"{_FN} . -exec timeout \\;\n",
                f"{_FN} . -exec timeout \\; {_RM} {_RF} {{}} +\n",
                f"{_FN} . -exec timeout\n",
                f"{_FN} . -exec env\n",
                f"{_FN} . -exec env -u\n",
                f"{_FN} . -exec env \\; -name {_RM}\n",
                f"{_FN} . -exec env -u \\; {_RM} {_RF} {{}} +\n",
                f"{_FN} . -exec env -u \\; -name {_RM}\n",
                f"{_FN} . -exec env -u + -name {_RM}\n",
                f"{_FN} . -exec sudo -u \\; -name {_RM}\n",
                f"{_FN} . -exec nice -n \\; -name {_RM}\n",
                f"{_FN} . -exec stdbuf -o \\; -name {_RM}\n",
                f"{_FN} . -exec {_XA} \\; -name {_RM}\n",
                f"{_FN} . -exec {_XA} -I \\; -name {_RM}\n",
                f"{_FN} . -exec {_XA} -I\n",
                f"{_FN} . -exec {_XA} --arg-file \\; -name {_RM}\n",
                f"{_FN} . -exec {_XA} --arg-file\n",
                f"{_FN} . -exec {_XA}-I \\; -name {_RM}\n",
                f"{_FN} . -exec {_XA}-I\n",
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
            f"echo / | {_XA} -I 'a b' {_RM} {_RF}\n",
            f"echo / | {_XA}-n 1 {_RM} {_RF}\n",
            f"echo / | {_XA}-n1 {_RM} {_RF}\n",
            f"echo / | {_XA} -1{_RM} {_RF}\n",
            f"echo / | {_XA}-0 -I{{}}{_RM} {_RF}\n",
            f"echo / | {_XA} -0 sudo -u root env -i FOO=1 command -p {_RM} {_RF}\n",
            f"{_SH} -c '{_FN} . |{_XA} {_RM} {_RF}'\n",
        )
        for idx, snippet in enumerate(xa_cases):
            self._assert_hits(snippet, f"xa_{idx}.sh", "CYA-GAP-03", "xargs_rm")

        # Linear-time ReDoS regression tests for repeated xargs/sudo/env options & dashes
        for label, payload, expect_clean in (
            ("xargs_a40", f"{_XA} " + "-a" * 40 + " X\n", True),
            ("xargs_dash54_echo", f"{_XA} " + "-" * 54 + " echo ok\n", True),
            ("xargs_dash54_rm", f"{_XA} " + "-" * 54 + f" {_RM} {_RF} /tmp/x\n", False),
            ("sudo_u40", "sudo " + "-u " * 40 + "X\n", True),
            ("env_u40", "env " + "-u " * 40 + "X\n", True),
        ):
            t0 = time.monotonic()
            r_perf = safety.scan_text_safety_surface(payload, f"{label}.sh")
            elapsed = time.monotonic() - t0
            self.assertLess(elapsed, 2.0, msg=f"ReDoS regression on {label}: {elapsed:.3f}s")
            self.assertEqual(r_perf["clean"], expect_clean, msg=f"unexpected result on {label}: {r_perf}")

        for idx, clean_xa in enumerate(
            (
                f"{_FN} . -name '*.py' | {_XA} wc -l\n",
                f"{_FN} . -print0 | {_XA} -0 grep pat\n",
                f"{_XA} -a files.txt echo\n",
                f"echo / | {_XA} --max-args 1 echo\n",
                f"echo a | {_XA} -0fo{_RM}\n",
                f"echo a | {_XA} --platfo{_RM} foo\n",
                f"echo a | {_XA} {_RM}dir\n",
                f"echo a | {_XA} -a -0 {_RM}dir\n",
                f"echo a | {_XA} - {_RM} {_RF}\n",
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

        # Quoted command strings (YAML run, package.json, ssh, Dockerfile exec-form)
        quoted_cases = (
            ("ci.yml", f'run: "cd build && {_RM} {_RF} $OUT_DIR"\n'),
            ("package.json", f'{{"scripts":{{"clean": "cd build && {_RM} {_RF} $OUT_DIR"}}}}\n'),
            ("deploy.sh", f'ssh host "cd /srv; {_RM} {_RF} $DIR"\n'),
            ("Dockerfile", f'RUN ["/bin/{_SH}", "-c", "cd /app; {_RM} {_RF} $BUILD"]\n'),
            ("escaped.json", f'{{"run": "cd /app && {_RM} {_RF} \\"$DIR\\""}}\n'),
            ("sub_after.sh", f'$(echo ok) "cd /a && {_RM} {_RF} $X"\n'),
            ("sub_before.sh", f'"cd /a && {_RM} {_RF} $X" $(echo ok)\n'),
            ("spaced_paren.sh", f'!  ( {_RM} {_RF} "$X" )\n'),
        )
        for fn, snippet in quoted_cases:
            self._assert_hits(snippet, fn, "CYA-GAP-03", "unguarded_rm_rf_variable")

        # Quoted clean controls & helper boundary coverage (_is_env_assign, _stage_disables_nounset, _split_shell_tokens)
        self.assertTrue(safety.scan_text_safety_surface(f"{_BASH} -cu '{_RM} {_RF} $CHILD'\n", "cu.sh")["clean"])
        self.assertTrue(safety.scan_text_safety_surface(f'echo "{_RM} {_RF} /tmp/static"\n', "lit.sh")["clean"])
        self.assertTrue(safety.scan_text_safety_surface('echo "unclosed quote\n', "uncl.sh")["clean"])
        self.assertTrue(safety.scan_text_safety_surface(f'do_{_RM} {_RF} "$X"\n', "do_pfx.sh")["clean"])
        self.assertTrue(safety.scan_text_safety_surface(f"{_EV}\n{_EV} --\n", "bare_ev.sh")["clean"])
        self.assertTrue(safety.scan_text_safety_surface(f'set -u\nset -- +u\n{_RM} {_RF} "$X"\n', "dash_u.sh")["clean"])
        self.assertTrue(safety.scan_text_safety_surface(f'set -u\nset -o errexit\n{_RM} {_RF} "$X"\n', "opt_e.sh")["clean"])
        self.assertTrue(safety.scan_text_safety_surface(f'set -u\nset +o errexit\n{_RM} {_RF} "$X"\n', "opt_pe.sh")["clean"])
        self._assert_hits(f'set -u\nset -e +u\n{_RM} {_RF} "$X"\n', "pe_u.sh", "CYA-GAP-03", "unguarded_rm_rf_variable")
        self._assert_hits(f'set -u\nset +o nounset\n{_RM} {_RF} "$X"\n', "po_u.sh", "CYA-GAP-03", "unguarded_rm_rf_variable")
        self.assertFalse(safety._stage_disables_nounset("echo +u"))
        self.assertFalse(safety._stage_disables_nounset("set +"))
        self.assertFalse(safety._stage_disables_nounset("set +e"))
        self.assertFalse(safety._stage_disables_nounset("set +o"))
        self.assertFalse(safety._stage_disables_nounset("set -o"))
        self.assertFalse(safety._stage_disables_nounset("set -o +u"))
        self.assertTrue(safety._stage_disables_nounset("set +u"))
        self.assertEqual(safety._strip_cmd_token("'"), "'")
        self.assertEqual(safety._strip_cmd_token('""'), "")
        self.assertEqual(safety._strip_cmd_token(f"'{_RM}"), f"'{_RM}")
        self.assertEqual(safety._strip_cmd_token(""), "")
        self.assertTrue(safety._is_spaceless_xargs_rm_tail(f"-0{_RM}"))
        self.assertTrue(safety._is_spaceless_xargs_rm_tail(f"-9{_RM}"))
        self.assertTrue(safety._is_spaceless_xargs_rm_tail(f"-I{{}}{_RM}"))
        self.assertFalse(safety._is_spaceless_xargs_rm_tail(f"--0{_RM}"))
        self.assertFalse(safety._is_spaceless_xargs_rm_tail(f"x0{_RM}"))
        self.assertFalse(safety._is_spaceless_xargs_rm_tail(f"-a{_RM}"))
        self.assertFalse(safety._is_spaceless_xargs_rm_tail("-0xx"))
        self.assertTrue(safety._is_env_assign("A_1=val"))
        self.assertTrue(safety._is_env_assign("_X=1"))
        self.assertFalse(safety._is_env_assign("no_equals"))
        self.assertFalse(safety._is_env_assign("=val"))
        self.assertFalse(safety._is_env_assign("1BAD=val"))
        self.assertFalse(safety._is_env_assign("A-B=val"))
        self.assertFalse(safety._is_env_assign("\u03b1=1"))
        self.assertFalse(safety._is_env_assign("A\u03b1=1"))
        self.assertEqual([t for t, _s, _e in safety._split_shell_tokens("a 'b c' \"d\\\"e\" f\\ g")], ["a", "'b c'", '"d\\"e"', "f\\ g"])
        self.assertEqual([t for t, _s, _e in safety._split_shell_tokens("   ")], [])
        self.assertEqual(safety._extract_quoted_subcommands('echo "a \\x b" \\"x\\"', []), ['a \\x b'])
        self.assertEqual(safety._extract_quoted_subcommands('"a b\\', []), [])
        self.assertEqual(safety._extract_quoted_subcommands("'a \\\" b'", []), ['a \\" b'])
        self.assertEqual(safety._extract_quoted_subcommands('"a b"', [(0, 5)]), [])

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

        # Multi-line YAML combined short flags (-qy / -yq) across both npx and bunx
        qy_flag = "-q" + "y"
        yq_flag = _YF + "q"
        self._assert_hits(f"{_CMD}: {_NX}\n{_ARGS}:\n  - {qy_flag}\n  - evil\n", "nx_qy.yml", "CYA-GAP-02", "npx_auto_yes_structured_config")
        self._assert_hits(f"{_CMD}: {_NX}\n{_ARGS}:\n  - {yq_flag}\n  - evil\n", "nx_yq.yml", "CYA-GAP-02", "npx_auto_yes_structured_config")
        self._assert_hits(f"{_CMD}: {_BX}\n{_ARGS}:\n  - {qy_flag}\n  - evil\n", "bx_qy.yml", "CYA-GAP-02", "bunx_auto_yes_structured_config")
        self._assert_hits(f"{_CMD}: {_BX}\n{_ARGS}:\n  - {yq_flag}\n  - evil\n", "bx_yq.yml", "CYA-GAP-02", "bunx_auto_yes_structured_config")
        self.assertTrue(safety.scan_text_safety_surface(f"{_CMD}: {_NX}\n{_ARGS}:\n  - --no-yes\n  - safe\n", "nx_noyes.yml")["clean"])
        self.assertTrue(safety.scan_text_safety_surface(f"{_CMD}: {_NX}\n{_ARGS}:\n  - -q\n  - yaml\n", "nx_q.yml")["clean"])

        # Windows CRLF (\r\n), bare CR (\r), and inline comment after args: regression controls
        self._assert_hits(f"{_CMD}: {_NX}\r\n{_ARGS}:\r\n  - {_YF}\r\n  - evil\r\n", "crlf_y.yml", "CYA-GAP-02", "npx_auto_yes_structured_config")
        self._assert_hits(f"{_CMD}: {_NX}\r\n{_ARGS}:\r\n  - {qy_flag}\r\n  - evil\r\n", "crlf_qy.yml", "CYA-GAP-02", "npx_auto_yes_structured_config")
        self._assert_hits(f"{_CMD}: {_BX}\r\n{_ARGS}:\r\n  - {_YESF}\r\n  - evil\r\n", "crlf_yes.yml", "CYA-GAP-02", "bunx_auto_yes_structured_config")
        self._assert_hits(f"{_ARGS}:\r\n  - {_YF}\r\n  - evil\r\n{_CMD}: {_NX}\r\n", "crlf_af.yml", "CYA-GAP-02", "npx_auto_yes_structured_config")
        self._assert_hits(f"{_CMD}: {_NX}\r{_ARGS}:\r  - {_YF}\r", "cr_y.yml", "CYA-GAP-02", "npx_auto_yes_structured_config")
        self._assert_hits(f"{_CMD}: {_NX}\n{_ARGS}: # inline note\n  - {_YF}\n", "cmt_y.yml", "CYA-GAP-02", "npx_auto_yes_structured_config")
        self.assertTrue(safety.scan_text_safety_surface(f"{_CMD}: {_NX}\r\n{_ARGS}:\r\n  - --help\r\n", "crlf_ok.yml")["clean"])
        self.assertTrue(safety.scan_text_safety_surface(f"{_CMD}: {_NX}\n{_ARGS}: # eof comment", "cmt_eof.yml")["clean"])

        # O(n) YAML/bracket args ReDoS & structured proximity/floor boundary regression tests (< 50 ms each)
        for label, payload, expect_clean in (
            ("yaml_npx_200", f"{_CMD}: {_NX}\n{_ARGS}:\n" + "  - foo\n" * 200 + "  - bar\n", True),
            ("yaml_bunx_200", f"{_CMD}: {_BX}\n{_ARGS}:\n" + "  - foo\n" * 200 + "  - bar\n", True),
            ("yaml_args_only_200", f"{_ARGS}:\n" + "  - foo\n" * 200 + "  - bar\n", True),
            ("yaml_args_yes_200_other", f"{_ARGS}:\n  - {_YF}\n" + "  - foo\n" * 200 + "other: 1\n", True),
            ("yaml_2space_200", f"{_CMD}: {_NX}\n{_ARGS}:\n" + "  -  foo\n" * 200, True),
            ("yaml_trail_space_200", f"{_CMD}: {_NX}\n{_ARGS}:\n" + "  - foo  \n" * 200, True),
            ("yaml_bracket_5000_open", f"{_ARGS}: [" * 5000, True),
            ("yaml_bracket_5000_closed", f"{_ARGS}: [" * 5000 + "]", True),
            ("yaml_nested_args_4000", f"{_ARGS}:\n" + f"  - {_ARGS}:\n" * 4000, True),
            ("yaml_bracket_adj_floor_hit", f'{_ARGS}: []{_ARGS}: ["{_YF}"]\n{_CMD}: {_NX}\n', False),
            ("yaml_bracket_second_elem_hit", f'{_CMD}: {_NX}\n{_ARGS}: ["--quiet", "{_YF}"]\n', False),
            ("yaml_bracket_nested_hit", f"{_ARGS}: [unclosed\n{_CMD}: echo\n{_CMD}: {_NX}\n{_ARGS}: [{_YF}]\n", False),
            ("yaml_bracket_nested_q_hit", f'{_ARGS}: [unclosed\n{_CMD}: echo\n{_CMD}: {_NX}\n{_ARGS}: ["{_YF}"]\n', False),
            ("yaml_bracket_nested_prior_ok", f'{_ARGS}: ["{_YF}", {_ARGS}: ["ok"]]\n{_CMD}: {_NX}\n', True),
            ("yaml_floor_adj_hit", f"{_ARGS}:\n  - a\n{_ARGS}:\n  - {_YF}\n{_CMD}: {_NX}\n", False),
            ("yaml_floor_nested_hit", f"{_ARGS}:\n  - {_ARGS}:\n  - {_YF}\n{_CMD}: {_NX}\n", False),
            ("yaml_floor_nested_line2_hit", f"{_ARGS}:\n  - {_ARGS}:\n  - foo\n  - {_YF}\n{_CMD}: {_NX}\n", False),
            ("yaml_floor_nested_prior_ok", f"{_ARGS}:\n  - {_YF}\n  - {_ARGS}:\n  - ok\n{_CMD}: {_NX}\n", True),
            ("yaml_npx_200_hit", f"{_CMD}: {_NX}\n{_ARGS}:\n" + "  - foo\n" * 200 + f"  - {_YF}\n", False),
            ("yaml_empty_dash_hit", f"{_CMD}: {_NX}\n{_ARGS}:  \n  -\n  - {_YF}", False),
            ("yaml_inline_unclosed_hit", f'{_CMD}: {_NX}\n{_ARGS}: ["{_YF}"', False),
            ("yaml_non_item_break", f"{_CMD}: {_NX}\n{_ARGS}:\n  --not-item\n  - {_YF}\n", True),
            ("yaml_eof_args_only", f"{_CMD}: {_NX}\n{_ARGS}:", True),
            ("yaml_eof_args_nl", f"{_CMD}: {_NX}\n{_ARGS}:\n", True),
            ("yaml_cmd_barrier_fwd", f"{_CMD}: {_NX}\n{_CMD}: echo\n{_ARGS}: [\"{_YF}\"]\n", True),
            ("yaml_cmd_barrier_bwd", f"{_ARGS}: [\"{_YF}\"]\n{_CMD}: echo\n{_CMD}: {_NX}\n", True),
            ("yaml_args_barrier_bwd", f"{_ARGS}: [\"{_YF}\"]\n{_ARGS}: [\"--help\"]\n{_CMD}: {_NX}\n", True),
            ("yaml_prox_fwd_600_hit", f"{_CMD}: {_NX}" + "\n" + "x" * 598 + f"\n{_ARGS}: [\"{_YF}\"]\n", False),
            ("yaml_prox_fwd_601_ok", f"{_CMD}: {_NX}" + "\n" + "x" * 599 + f"\n{_ARGS}: [\"{_YF}\"]\n", True),
            ("yaml_prox_bwd_600_hit", f"{_ARGS}: [\"{_YF}\"]" + " " * 600 + f"{_CMD}: {_NX}\n", False),
            ("yaml_prox_bwd_601_ok", f"{_ARGS}: [\"{_YF}\"]" + " " * 601 + f"{_CMD}: {_NX}\n", True),
            ("yaml_other_cmd_only", f"{_CMD}: echo\n{_ARGS}: [\"{_YF}\"]\n", True),
            ("yaml_inline_dash_scalar", f"{_CMD}: {_NX}\n{_ARGS}: -- {_YF}\n", True),
            ("yaml_two_args_no_cmd", f'{_ARGS}: ["{_YF}"]\n{_ARGS}: ["{_YF}"]\n', True),
        ):
            t0 = time.monotonic()
            safety._scan_structured_auto_yes_config(payload)
            struct_ms = (time.monotonic() - t0) * 1000.0
            self.assertLess(struct_ms, 50.0, msg=f"Structured scanner ReDoS regression on {label}: {struct_ms:.2f} ms")
            t1 = time.monotonic()
            r_y = safety.scan_text_safety_surface(payload, f"{label}.yml")
            elapsed_ms = (time.monotonic() - t1) * 1000.0
            self.assertLess(elapsed_ms, 300.0, msg=f"YAML ReDoS regression on {label}: {elapsed_ms:.2f} ms")
            self.assertEqual(r_y["clean"], expect_clean, msg=f"unexpected result on {label}: {r_y}")

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

        # Explicit JSON numeric token length cap (enforced even with CPython int_max_str_digits disabled)
        ncap = safety.MAX_JSON_NUMBER_CHARS
        prev_digits = sys.get_int_max_str_digits()
        sys.set_int_max_str_digits(0)
        try:
            self.assertTrue(safety.scan_text_safety_surface('{"n":1' + ("0" * (ncap - 1)) + "}", "int_ok.json")["clean"])
            self._assert_hits('{"n":1' + ("0" * ncap) + "}", "int_over.json", "CYA-GAP-02", "json_parse_limit_exceeded")
        finally:
            sys.set_int_max_str_digits(prev_digits)
        self.assertTrue(safety.scan_text_safety_surface('{"x":1.' + ("0" * (ncap - 2)) + "}", "flt_ok.json")["clean"])
        self._assert_hits('{"x":1.' + ("0" * (ncap - 1)) + "}", "flt_over.json", "CYA-GAP-02", "json_parse_limit_exceeded")

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

            # Symlink to regular file OUTSIDE directory -> refused as symlink_not_followed
            sym_dir = root / "sym_case"
            sym_dir.mkdir()
            sym_file = sym_dir / "sym_file.txt"
            sym_file.symlink_to(clean_file)
            r_sym = safety.scan_directory_safety_surface(sym_dir)
            self.assertFalse(r_sym["clean"])
            self.assertEqual(r_sym["files_scanned"], 0)
            self.assertEqual(r_sym["skipped_files"], [{"file": "sym_file.txt", "reason": "symlink_not_followed"}])

            # In-tree file symlink (CLAUDE.md -> AGENTS.md) is followed & scanned; audit-check --allow-symlinks passes
            in_root_dir = root / "in_root_sym"
            in_root_dir.mkdir()
            (in_root_dir / "AGENTS.md").write_text("# Clean repository guide\n", encoding="utf-8")
            (in_root_dir / "CLAUDE.md").symlink_to("AGENTS.md")
            r_inroot = safety.scan_directory_safety_surface(in_root_dir)
            self.assertTrue(r_inroot["clean"])
            self.assertEqual(r_inroot["files_scanned"], 2)
            self.assertEqual(r_inroot["skipped_files"], [])
            ac_allow = audit_check.run_audit_check(in_root_dir, safety_scan=True, allow_symlinks=True)
            self.assertTrue(ac_allow["passed"], msg=f"audit-check --safety-scan --allow-symlinks failed: {ac_allow['failures']}")

            # In-tree symlink to hazardous file reports findings on both files
            haz_dir = root / "in_root_haz"
            haz_dir.mkdir()
            (haz_dir / "a.sh").write_text(f'{_RM} {_RF} "$DIR"\n', encoding="utf-8")
            (haz_dir / "b.sh").symlink_to("a.sh")
            r_haz = safety.scan_directory_safety_surface(haz_dir)
            self.assertFalse(r_haz["clean"])
            self.assertEqual(r_haz["files_scanned"], 2)
            self.assertEqual(r_haz["finding_count"], 2)

            # In-tree symlink loop refused cleanly as symlink_not_followed
            loop_dir = root / "loop_case"
            loop_dir.mkdir()
            (loop_dir / "la").symlink_to("lb")
            (loop_dir / "lb").symlink_to("la")
            r_loop = safety.scan_directory_safety_surface(loop_dir)
            self.assertFalse(r_loop["clean"])
            self.assertEqual(len(r_loop["skipped_files"]), 2)
            self.assertTrue(all(s["reason"] == "symlink_not_followed" for s in r_loop["skipped_files"]))

            # FIFO blocked-writer non-release test (lstat before open never opens or breaks FIFO writers)
            if hasattr(os, "mkfifo"):
                fifo_dir = root / "fifo_live"
                fifo_dir.mkdir()
                fifo_live = fifo_dir / "pipe"
                os.mkfifo(fifo_live)
                (fifo_dir / "link_to_pipe").symlink_to("pipe")
                writer = subprocess.Popen(
                    [sys.executable, "-c", f"f=open({str(fifo_live)!r},'w'); print('OPENED', flush=True); f.write('x'); f.flush()"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                try:
                    time.sleep(0.15)
                    self.assertIsNone(writer.poll())
                    r_flive = safety.scan_directory_safety_surface(fifo_dir)
                    time.sleep(0.15)
                    self.assertIsNone(writer.poll(), msg="FIFO writer was released by scanner open()")
                    self.assertFalse(r_flive["clean"])
                    self.assertEqual(
                        r_flive["skipped_files"],
                        [
                            {"file": "link_to_pipe", "reason": "non_regular_file"},
                            {"file": "pipe", "reason": "non_regular_file"},
                        ],
                    )
                finally:
                    writer.terminate()
                    w_out, w_err = writer.communicate(timeout=3)
                self.assertEqual(w_out, "")
                self.assertNotIn("BrokenPipeError", w_err)

            # Direct _read_regular_file_bounded lstat/open/fstat TOCTOU race-window controls
            self.assertEqual(safety._read_regular_file_bounded(sym_file), ("skipped", "symlink_not_followed"))
            with mock.patch("aletheia.safety.os.open", side_effect=OSError(errno.ELOOP, "loop")):
                self.assertEqual(safety._read_regular_file_bounded(clean_file), ("skipped", "symlink_not_followed"))
            with mock.patch("aletheia.safety.os.open", side_effect=OSError(errno.ENXIO, "enxio")):
                self.assertEqual(safety._read_regular_file_bounded(clean_file), ("skipped", "non_regular_file"))
            with mock.patch("aletheia.safety.os.open", side_effect=OSError(errno.EACCES, "denied")):
                st_acc, _ = safety._read_regular_file_bounded(clean_file)
                self.assertEqual(st_acc, "unreadable")
            with mock.patch("aletheia.safety.os.lstat", side_effect=OSError(errno.EACCES, "denied")):
                st_ls, _ = safety._read_regular_file_bounded(clean_file)
                self.assertEqual(st_ls, "unreadable")
                r_top_err = safety.scan_directory_safety_surface(clean_file)
                self.assertFalse(r_top_err["clean"])
                self.assertEqual(len(r_top_err["unreadable_files"]), 1)

            def _fifo_fstat(fd: int) -> os.stat_result:
                vals = list(real_fstat(fd))
                vals[stat.ST_MODE] = stat.S_IFIFO | 0o600
                return os.stat_result(vals)

            def _ino_changed_fstat(fd: int) -> os.stat_result:
                vals = list(real_fstat(fd))
                vals[stat.ST_INO] = vals[stat.ST_INO] + 1
                return os.stat_result(vals)

            def _dev_changed_fstat(fd: int) -> os.stat_result:
                vals = list(real_fstat(fd))
                vals[stat.ST_DEV] = vals[stat.ST_DEV] + 1
                return os.stat_result(vals)

            with mock.patch("aletheia.safety.os.fstat", side_effect=_fifo_fstat):
                self.assertEqual(safety._read_regular_file_bounded(clean_file), ("skipped", "non_regular_file"))
            with mock.patch("aletheia.safety.os.fstat", side_effect=_ino_changed_fstat):
                self.assertEqual(safety._read_regular_file_bounded(clean_file), ("skipped", "path_changed_during_open"))
            with mock.patch("aletheia.safety.os.fstat", side_effect=_dev_changed_fstat):
                self.assertEqual(safety._read_regular_file_bounded(clean_file), ("skipped", "path_changed_during_open"))

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

    def test_08_quoted_subcommand_span_exclusion_is_exact_and_subquadratic(self) -> None:
        # Exact oracle: the pre-fix O(q*m) containment predicate, re-implemented with zero shared code.
        def _covered_ref(start: int, end: int, spans: list[tuple[int, int]]) -> bool:
            return any(start >= es and end <= ee for es, ee in spans)

        rng = random.Random(20261126)
        for _trial in range(3000):
            spans = []
            for _k in range(rng.randint(0, 6)):
                a = rng.randint(0, 12)
                spans.append((a, a + rng.randint(0, 8)))
            starts, cover_ends = safety._build_span_cover_index(spans)
            for _q in range(8):
                qs = rng.randint(0, 14)
                qe = qs + rng.randint(0, 8)
                self.assertEqual(
                    safety._span_is_covered(qs, qe, starts, cover_ends),
                    _covered_ref(qs, qe, spans),
                    msg=f"spans={spans} query=({qs},{qe})",
                )
        # Unsorted input, nested spans, and both equality boundaries (es == start, ee == end)
        st, ce = safety._build_span_cover_index([(10, 20), (0, 5), (2, 30), (40, 41)])
        self.assertEqual(st, [0, 2, 10, 40])
        self.assertEqual(ce, [5, 30, 30, 41])
        self.assertTrue(safety._span_is_covered(2, 30, st, ce))
        self.assertTrue(safety._span_is_covered(0, 5, st, ce))
        self.assertFalse(safety._span_is_covered(1, 31, st, ce))
        self.assertFalse(safety._span_is_covered(30, 41, st, ce))
        self.assertTrue(safety._span_is_covered(40, 41, st, ce))
        self.assertFalse(safety._span_is_covered(40, 42, st, ce))
        self.assertEqual(safety._build_span_cover_index([]), ([], []))
        self.assertFalse(safety._span_is_covered(0, 0, [], []))

        # _extract_quoted_subcommands: a quoted string exactly equal to a span is excluded; one byte wider is not
        stage = "x 'a b' y"
        self.assertEqual(safety._extract_quoted_subcommands(stage, []), ["a b"])
        self.assertEqual(safety._extract_quoted_subcommands(stage, [(2, 7)]), [])
        self.assertEqual(safety._extract_quoted_subcommands(stage, [(3, 7)]), ["a b"])
        self.assertEqual(safety._extract_quoted_subcommands(stage, [(2, 6)]), ["a b"])
        self.assertEqual(safety._extract_quoted_subcommands(stage, [(0, 3), (5, 9)]), ["a b"])

        # Complexity regression (review 6059703038): q quoted strings x m disjoint non-covering spans.
        # The pre-fix predicate walks every span per quote (q*m = 4e8 steps, ~13 s CPU measured locally); the indexed
        # check is O((q + m) log m). CPU-time bounds are far above the measured linear cost, robust to CI load.
        q = 20000
        flood = "'a b' " * q
        far_spans = [(len(flood) + 10 * i, len(flood) + 10 * i + 5) for i in range(q)]
        t0 = time.process_time()
        got = safety._extract_quoted_subcommands(flood, far_spans)
        self.assertLess(time.process_time() - t0, 3.0)
        self.assertEqual(len(got), q)
        # End-to-end: `sh -c '` flood (one excluded span per match), linear after the fix
        t1 = time.process_time()
        res = safety.scan_text_safety_surface((_SH + " -c '") * 64000, "flood.sh")
        self.assertLess(time.process_time() - t1, 15.0)
        self.assertTrue(res["clean"])

    def test_09_max_file_bytes_cli_override(self) -> None:
        # Strict parser: ASCII [1-9][0-9]{0,15} only (int() would accept or coerce every rejected form)
        for good, val in (("1", 1), ("64", 64), ("2097152", 2097152), ("9" * 16, int("9" * 16))):
            self.assertEqual(safety.parse_max_file_bytes_arg(good), val)
        for bad in ("0", "", "012", "+5", "-5", " 5", "5 ", "5\n", "1_000", "\u0665", "5.0", "1e3", "9" * 17, "00"):
            with self.assertRaises(ValueError, msg=repr(bad)):
                safety.parse_max_file_bytes_arg(bad)
        for bad_obj in (5, None, b"5"):
            with self.assertRaises(ValueError, msg=repr(bad_obj)):
                safety.parse_max_file_bytes_arg(bad_obj)
        self.assertEqual(safety.validate_max_file_bytes(1), 1)
        for bad_cap in (True, False, 0, -1, 1.0, "1", None):
            with self.assertRaises(AletheiaError) as ctx:
                safety.validate_max_file_bytes(bad_cap)
            self.assertEqual(ctx.exception.code, "SAFETY_INVALID_MAX_BYTES")

        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "cap_case"
            root.mkdir()
            (root / "data.txt").write_bytes(b"a" * 65)

            def _run(argv: list[str]) -> tuple[int, dict[str, object]]:
                with mock.patch("sys.stdout", new_callable=io.StringIO) as out:
                    rc = cli_main(argv)
                return rc, json.loads(out.getvalue())

            # safety-scan: default unchanged, override honoured at the exact boundary
            rc_def, rep_def = _run(["safety-scan", str(root), "--json"])
            self.assertEqual((rc_def, rep_def["files_scanned"]), (0, 1))
            rc_64, rep_64 = _run(["safety-scan", str(root), "--max-file-bytes", "64", "--json"])
            self.assertEqual(rc_64, 1)
            self.assertEqual(rep_64["skipped_files"], [{"file": "data.txt", "reason": "file_size_limit_exceeded"}])
            rc_65, rep_65 = _run(["safety-scan", str(root), "--max-file-bytes", "65", "--json"])
            self.assertEqual((rc_65, rep_65["clean"]), (0, True))

            # audit-check --safety-scan --safety-max-file-bytes
            rc_a64, rep_a64 = _run(["audit-check", str(root), "--safety-scan", "--safety-max-file-bytes", "64", "--json"])
            self.assertEqual(rc_a64, 1)
            self.assertEqual(
                rep_a64["safety_scan"]["skipped_files"],  # type: ignore[index]
                [{"file": "data.txt", "reason": "file_size_limit_exceeded"}],
            )
            rc_a65, rep_a65 = _run(["audit-check", str(root), "--safety-scan", "--safety-max-file-bytes", "65", "--json"])
            self.assertEqual(rc_a65, 0, msg=str(rep_a65.get("failures")))
            self.assertTrue(rep_a65["safety_scan"]["clean"])  # type: ignore[index]
            # Fail closed: the override without --safety-scan is refused, not silently ignored
            rc_noscan, rep_noscan = _run(["audit-check", str(root), "--safety-max-file-bytes", "64", "--json"])
            self.assertEqual((rc_noscan, rep_noscan["code"]), (2, "SAFETY_MAX_BYTES_WITHOUT_SCAN"))
            with self.assertRaises(AletheiaError) as ctx_api:
                audit_check.run_audit_check(root, safety_scan=True, safety_max_file_bytes=True)  # type: ignore[arg-type]
            self.assertEqual(ctx_api.exception.code, "SAFETY_INVALID_MAX_BYTES")
            api_ok = audit_check.run_audit_check(root, safety_scan=True, safety_max_file_bytes=65)
            self.assertTrue(api_ok["passed"], msg=str(api_ok["failures"]))

            # Bad CLI values exit 2 via argparse on both entry points
            for argv in (
                ["safety-scan", str(root), "--max-file-bytes", "0"],
                ["safety-scan", str(root), "--max-file-bytes", "1_000"],
                ["audit-check", str(root), "--safety-scan", "--safety-max-file-bytes", "-1"],
            ):
                with mock.patch("sys.stderr", new_callable=io.StringIO), self.assertRaises(SystemExit) as ctx_exit:
                    cli_main(argv)
                self.assertEqual(ctx_exit.exception.code, 2, msg=str(argv))

    def test_10_positional_shell_c_scripts_under_find_exec_and_xargs(self) -> None:
        # Previously missed: the rm script only sees "$1" / {} so no named variable fires
        self._assert_hits(f"{_FN} . -exec {_SH} -c '{_RM} {_RF} \"$1\"' _ {{}} \\;\n", "a.sh", "CYA-GAP-03", "find_exec_rm")
        self._assert_hits(f"{_FN} . -execdir {_BASH} -ec '{_RM} {_RF} \"$1\"' _ {{}} +\n", "a.sh", "CYA-GAP-03", "find_exec_rm")
        self._assert_hits(f"{_FN} . -exec {_SH} -c 'cd x; {_RM} \"$1\"' _ {{}} \\;\n", "a.sh", "CYA-GAP-03", "find_exec_rm")
        self._assert_hits(f"{_XA} -I{{}} {_SH} -c '{_RM} {_RF} {{}}'\n", "a.sh", "CYA-GAP-03", "xargs_rm")
        self._assert_hits(f"ls | {_XA} -0 {_DASH} -xc '{_RM} {_RF} \"$@\"' _\n", "a.sh", "CYA-GAP-03", "xargs_rm")
        # Benign controls: no rm in the script, no -c script, flags only, or a long option before -c
        for benign in (
            f"{_FN} . -exec {_SH} -c 'echo \"$1\"' _ {{}} \\;\n",
            f"{_FN} . -exec {_SH} -x \\;\n",
            f"ls | {_XA} {_SH} -c 'echo hi'\n",
            f"{_XA} {_SH} -c\n",
            f"{_XA} {_SH} -e\n",
            f"{_XA} {_SH} --login -c 'x'\n",
        ):
            res = safety.scan_text_safety_surface(benign, "b.sh")
            self.assertTrue(res["clean"], msg=f"unexpected hit for {benign!r}: {res['findings']}")
        # Direct helper: the -c flag is found in a combined cluster; missing script and flag-free args refuse
        self.assertTrue(safety._shell_c_script_runs_rm(["-e", "-uc", f"'{_RM} x'"]))
        self.assertFalse(safety._shell_c_script_runs_rm(["-c"]))
        self.assertFalse(safety._shell_c_script_runs_rm(["-x"]))
        self.assertFalse(safety._shell_c_script_runs_rm([f"'{_RM} x'"]))
        self.assertFalse(safety._shell_c_script_runs_rm(["--rcfile", "-c", f"'{_RM} x'"]))
        self.assertFalse(safety._shell_c_script_runs_rm([]))


if __name__ == "__main__":
    unittest.main()
