#!/usr/bin/env python3
"""R5 adversarial & mutation-killing test suite for aletheia/safety.py (CYA-GAP-01..06).

Zero bare asserts. Covers CYA-GAP-01..06 scanner rules, all listed invisible/BiDi
codepoints, JSON/YAML npx -y, shell/YAML/Makefile rm -rf + braced ${D} + top-level/
heredoc/conditional nounset, CI pwn-request, UTF-16 decoding, fail-closed UTF-32 BOM/NUL
and non-regular-file (FIFO) handling, isolated unreadable-only trees, and all 4/4
raise-guard deletions plus 14/14 `aletheia mutate` sites.
"""
from __future__ import annotations

import codecs
import os
from pathlib import Path
import sys
import tempfile
import unittest

CLI_ROOT = Path(__file__).resolve().parent.parent
if str(CLI_ROOT) not in sys.path:
    sys.path.insert(0, str(CLI_ROOT))

from aletheia import safety


class TestSafetyR5(unittest.TestCase):
    def test_01_hidden_unicode_gap01_and_guards(self) -> None:
        with self.assertRaisesRegex(ValueError, "SAFETY_TEXT_NOT_STR"):
            safety.scan_hidden_unicode(123)  # type: ignore[arg-type]

        self.assertEqual(safety.scan_hidden_unicode("clean ascii\nline2"), [])
        # Exact boundary codepoints for invisible format, BiDi, Variation Selectors, and Tags
        sample = (
            "ok\n"
            "\u00ad\u200b\u2061\u2064\u202e"
            + chr(0xFDFF) + chr(0xFE00) + chr(0xFE0F) + chr(0xFE10)
            + chr(0xE0000) + chr(0xE007F) + chr(0xE0080)
            + chr(0xE0100) + chr(0xE01EF) + chr(0xE01F0)
        )
        hits = safety.scan_hidden_unicode(sample, "test.py")
        self.assertEqual(
            [h["codepoint"] for h in hits],
            [
                "U+00AD", "U+200B", "U+2061", "U+2064", "U+202E",
                "U+FE00", "U+FE0F", "U+E0000", "U+E007F", "U+E0100", "U+E01EF",
            ],
        )
        self.assertEqual(hits[0]["category"], "zero_width_or_invisible_format")
        self.assertEqual(hits[4]["category"], "bidi_trojan_source")
        self.assertEqual(hits[5]["category"], "variation_selector_smuggling")
        self.assertEqual(hits[7]["category"], "unicode_tag_smuggling")
        self.assertEqual(hits[9]["category"], "variation_selector_smuggling")
        self.assertEqual(hits[0]["line"], 2)
        self.assertEqual(hits[0]["col"], 1)

        # Verify every listed zero-width/invisible and BiDi codepoint individually (review 6012061680)
        for cp in (0x00AD, 0x200B, 0x200C, 0x200D, 0x200E, 0x200F, 0x2060, 0x2061, 0x2062, 0x2063, 0x2064, 0xFEFF):
            cp_hits = safety.scan_hidden_unicode(f"a{chr(cp)}b", "zw.py")
            self.assertEqual(len(cp_hits), 1, msg=f"missed U+{cp:04X}")
            self.assertEqual(cp_hits[0]["codepoint"], f"U+{cp:04X}")
            self.assertEqual(cp_hits[0]["category"], "zero_width_or_invisible_format")

        for cp in (0x061C, 0x202A, 0x202B, 0x202C, 0x202D, 0x202E, 0x2066, 0x2067, 0x2068, 0x2069):
            cp_hits = safety.scan_hidden_unicode(f"a{chr(cp)}b", "bidi.py")
            self.assertEqual(len(cp_hits), 1, msg=f"missed U+{cp:04X}")
            self.assertEqual(cp_hits[0]["codepoint"], f"U+{cp:04X}")
            self.assertEqual(cp_hits[0]["category"], "bidi_trojan_source")

    def test_02_gaps_02_through_06_and_input_guards(self) -> None:
        with self.assertRaisesRegex(ValueError, "SAFETY_TEXT_NOT_STR"):
            safety.scan_text_safety_surface(None)  # type: ignore[arg-type]
        with self.assertRaisesRegex(ValueError, "SAFETY_INVALID_FILE_LABEL"):
            safety.scan_text_safety_surface("ok", " ")
        with self.assertRaisesRegex(ValueError, "SAFETY_INVALID_HOST_FLAG"):
            safety.scan_text_safety_surface("ok", "a.sh", include_host_hygiene=1)  # type: ignore[arg-type]

        # CYA-GAP-02: shell + single-line/multi-line JSON & YAML npx -y
        r2 = safety.scan_text_safety_surface(
            "npx -q -y pkg@latest --yolo --dangerously-skip-permissions\nSessionStart:\n",
            "mcp.sh",
        )
        self.assertEqual(r2["gap_ids_present"], ["CYA-GAP-02"])
        self.assertEqual(r2["finding_count"], 5)

        for idx, cfg in enumerate(
            (
                '{"command":"npx","args":["-y","some-mcp-server"]}\n',
                '{"command":"npx","env":{"NODE_ENV":"prod"},"args":["-y","some-mcp-server"]}\n',
                '{"mcpServers":{"s":{"command":"npx","env":{"A":"1"},"args":["-q","--yes","pkg"]}}}\n',
                '[{"command":"npx","args":["-y","pkg"]}]\n',
                '{\n  "command": "npx",\n  "args": [\n    "-y",\n    "some-mcp-server"\n  ]\n}\n',
                '{"args": ["--yes", "some-mcp-server"], "command": "npx"}\n',
                "command: npx\nenv:\n  NODE_ENV: prod\nargs:\n  - -q\n  - -y\n  - some-mcp-server\n",
                "args:\n  - -y\n  - some-mcp-server\ncommand: npx\n",
                'args:\n  - "-y"\n  - some-mcp-server\ncommand: npx\n',
                '```json\n{"command":"npx","args":["-y","embedded"]}\n```\n',
            )
        ):
            r_cfg = safety.scan_text_safety_surface(cfg, f"mcp_{idx}.json")
            self.assertFalse(r_cfg["clean"], msg=f"missed structured npx -y case {idx}")
            self.assertEqual(r_cfg["gap_ids_present"], ["CYA-GAP-02"])

        # CYA-GAP-03: rm -rf "$VAR" with top-level set -u / set +u / ${VAR:?} / comments / -- stop
        sh_safe = (
            'set -u\n'
            'rm -rf "$TARGET"\n'
            'if true; then\n'
            '  rm -rf "$ALSO_GUARDED_BY_TOPLEVEL"\n'
            'fi\n'
            'bash -cu \'rm -rf $CHILD_GUARDED\'\n'
            'set +u\n'
            '# rm -rf "$COMMENTED"\n'
            'rm --recursive --force "${TARGET:?}"\n'
            'rm -r "$ONLY_R"\n'
            'rm -- -rf "$STOPPED"\n'
            'echo ok \\\\\n'
        )
        self.assertTrue(safety.scan_text_safety_surface(sh_safe, "safe.sh")["clean"])

        sh_bad = 'set -o nounset\nset +o nounset\nrm --recursive -f "$DIR"\nrm -R --force "$DIR2"\n'
        r3 = safety.scan_text_safety_surface(sh_bad, "bad.sh")
        self.assertEqual(r3["gap_ids_present"], ["CYA-GAP-03"])
        self.assertEqual(r3["finding_count"], 2)

        # Trailing dangling backslash at EOF still scanned
        r_eof_bs = safety.scan_text_safety_surface('rm -rf "$DIR"\\', "eof.sh")
        self.assertEqual(r_eof_bs["gap_ids_present"], ["CYA-GAP-03"])

        # Regression (AUDIT-093 + review 6010931420 #6): shell/YAML/Makefile/subshell/xargs/heredoc/conditional set -u
        for idx, shell_snippet in enumerate(
            (
                'if true; then\n  rm -rf "$BUILD_DIR"\nfi\n',
                'set +u; rm -rf "$BUILD_DIR"\n',
                'echo ok && rm -rf "$BUILD_DIR"\n',
                'set -u\n  set +u\nrm -rf "$BUILD_DIR"\n',
                'if true; then rm -rf "$BUILD_DIR"; fi\n',
                'sudo rm -rf "$BUILD_DIR"\n',
                '/bin/rm -rf "$BUILD_DIR"\n',
                'command /usr/bin/rm -rf "$BUILD_DIR"\n',
                'env FOO=1 \\rm -rf "$BUILD_DIR"\n',
                'rm -rf "${D}"\n',
                'set -- -u\nrm -rf "$BUILD_DIR"\n',
                'run: rm -rf "$DIR"\n',
                '      - run: rm -rf "$DIR"\n',
                'RUN rm -rf "$TMPDIR"\n',
                'RUN --mount=type=cache,target=/tmp rm -rf "$TMPDIR"\n',
                'out=$(rm -rf "$DIR")\n',
                'out=`rm -rf "$DIR"`\n',
                'rm \\\n  -rf "$DIR"\n',
                'xargs rm -rf $DIR\n',
                "bash -c 'rm -rf $DIR'\n",
                'set -u\nbash -c \'rm -rf $DIR\'\n',
                'sh -c "set -u; set +u; rm -rf \\"$DIR\\""\n',
                'clean:\n\t@rm -rf $(BUILD)/\n',
                'if false; then\n  set -u\nfi\nrm -rf "$DIR"\n',
                'if false; then set -u; fi; rm -rf "$DIR"\n',
                'foo() {\nset -u\n}\nrm -rf "$DIR"\n',
                '{\nset -u\n}\nrm -rf "$DIR"\n',
                '(\nset -u\n)\nrm -rf "$DIR"\n',
                'cat <<\'EOF\'\nset -u\nEOF\nrm -rf "$DIR"\n',
                'cat <<-EOF\n\tset -u\n\tEOF\nrm -rf "$DIR"\n',
            )
        ):
            r_reg = safety.scan_text_safety_surface(shell_snippet, f"bug03_{idx}.sh")
            self.assertFalse(r_reg["clean"], msg=f"missed CYA-GAP-03 on snippet {idx}: {shell_snippet!r}")
            self.assertEqual(r_reg["gap_ids_present"], ["CYA-GAP-03"])

        self.assertEqual(safety._strip_shell_comment("echo 'a#b' \"c#d\" # tail"), "echo 'a#b' \"c#d\" ")

        # CYA-GAP-04: pull_request_target + secrets/secrets:inherit/write OR untrusted PR head checkout
        ci_safe = "on:\n  pull_request:\npermissions:\n  contents: write\nsteps:\n  - uses: actions/checkout@v4\n    with:\n      ref: ${{ github.event.pull_request.head.sha }}\n"
        self.assertTrue(safety.scan_text_safety_surface(ci_safe, "ci.yml")["clean"])
        ci_prt_safe = "on:\n  pull_request_target:\njobs:\n  label:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo ok\n"
        self.assertTrue(safety.scan_text_safety_surface(ci_prt_safe, "prt_safe.yml")["clean"])
        ci_bad = "on:\n  pull_request_target:\npermissions:\n  contents: write\n  token: ${{ secrets.GH_TOKEN }}\n  secrets: inherit\n"
        r4 = safety.scan_text_safety_surface(ci_bad, "ci.yml")
        self.assertEqual(r4["gap_ids_present"], ["CYA-GAP-04"])
        self.assertEqual(r4["finding_count"], 3)

        for idx, pwn_line in enumerate(
            (
                "      ref: ${{ github.event.pull_request.head.sha }}",
                "      ref: ${{ github.event.pull_request.head.ref }}",
                "      repository: ${{ github.event.pull_request.head.repo.full_name }}",
                "      ref: ${{ github['event']['pull_request']['head']['sha'] }}",
                "      ref: ${{ github.head_ref }}",
                "      ref: ${{ github['head_ref'] }}",
                "      ref: refs/pull/${{ github.event.pull_request.number }}/head",
                "      run: git fetch origin pull/42/head",
                "      run: gh pr checkout ${{ github.event.pull_request.number }}",
                "      ref: ${{ steps.meta.outputs.pr_sha }}",
                "      ref: ${{ needs.prep.outputs.head_ref }}",
            )
        ):
            pwn_yml = f"on:\n  pull_request_target:\njobs:\n  t:\n    steps:\n      - uses: actions/checkout@v4\n{pwn_line}\n"
            r_pwn = safety.scan_text_safety_surface(pwn_yml, f"pwn_{idx}.yml.j2")
            self.assertFalse(r_pwn["clean"], msg=f"missed CYA-GAP-04 pwn-request {idx}: {pwn_line}")
            self.assertEqual(r_pwn["gap_ids_present"], ["CYA-GAP-04"])
            self.assertEqual(r_pwn["findings"][0]["detail"], "pull_request_target_untrusted_head_checkout")

        # CYA-GAP-05: prose-only governance rules & ~/ paths (incl. .cursorrules)
        r5 = safety.scan_text_safety_surface("Commit only when asked.\nCache at ~/scratch/data.bin\n", ".cursorrules")
        self.assertEqual(r5["gap_ids_present"], ["CYA-GAP-05"])
        self.assertEqual(r5["finding_count"], 2)
        self.assertTrue(safety.scan_text_safety_surface("Commit only when asked.\n", "code.py")["clean"])

        # CYA-GAP-06: optional host hygiene
        host_txt = "alias rm='rm -i'\nREPO=~/Dropbox/work\n"
        self.assertTrue(safety.scan_text_safety_surface(host_txt, "env.sh", include_host_hygiene=False)["clean"])
        r6 = safety.scan_text_safety_surface(host_txt, "env.sh", include_host_hygiene=True)
        self.assertEqual(r6["gap_ids_present"], ["CYA-GAP-06"])
        self.assertEqual(r6["finding_count"], 2)

    def test_03_directory_utf16_dotfiles_undecodable_and_unreadable(self) -> None:
        # Unit checks on _decode_text_bytes covering UTF-16 BOM, BOM-less LE/BE, invalid UTF-16, binary NUL, bad UTF-8
        self.assertEqual(safety._decode_text_bytes("hello".encode("utf-16")), "hello")
        self.assertEqual(safety._decode_text_bytes("hello".encode("utf-16-le")), "hello")
        self.assertEqual(safety._decode_text_bytes("hello".encode("utf-16-be")), "hello")
        self.assertIsNone(safety._decode_text_bytes(b"\xff\xfe\x00"))
        self.assertIsNone(safety._decode_text_bytes(b"\x00\x01\x02\xff"))
        self.assertIsNone(safety._decode_text_bytes(b"\x00\x01\x00\x02"))
        self.assertIsNone(safety._decode_text_bytes(b"\x00\x00\x01\x02"))
        self.assertIsNone(safety._decode_text_bytes(b"\x00\x01\x00\x02\x00"))
        self.assertIsNone(safety._decode_text_bytes(b"\xff\x01\xfe"))
        # Invalid surrogate pair in BOM-less UTF-16-LE / UTF-16-BE triggers decode failure cleanly
        self.assertIsNone(safety._decode_text_bytes(b"a\x00b\x00\x00\xd8c\x00"))
        self.assertIsNone(safety._decode_text_bytes(b"\x00a\x00b\xd8\x00\x00c"))
        # UTF-32-LE/BE with or without BOM and UTF-16-with-BOM containing NUL MUST fail closed as undecodable
        wf_u32 = "on: pull_request_target\npermissions: write-all\n"
        self.assertIsNone(safety._decode_text_bytes(wf_u32.encode("utf-32-le")))
        self.assertIsNone(safety._decode_text_bytes(codecs.BOM_UTF32_LE + wf_u32.encode("utf-32-le")))
        self.assertIsNone(safety._decode_text_bytes(codecs.BOM_UTF32_BE + wf_u32.encode("utf-32-be")))
        self.assertIsNone(safety._decode_text_bytes(("a\x00b").encode("utf-16")))

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            with self.assertRaisesRegex(ValueError, "SAFETY_TARGET_NOT_FOUND"):
                safety.scan_directory_safety_surface(root / "missing")

            (root / "clean.py").write_text("x = 1\n", encoding="utf-8")
            (root / "bad.sh").write_text('rm -rf "$TARGET"\n', encoding="utf-8")
            (root / ".git").mkdir()
            (root / ".git" / "ignored.sh").write_text('rm -rf "$IGNORED"\n', encoding="utf-8")

            dir_res = safety.scan_directory_safety_surface(root)
            self.assertFalse(dir_res["clean"])
            self.assertEqual(dir_res["files_scanned"], 2)
            self.assertEqual(dir_res["gap_ids_present"], ["CYA-GAP-03"])
            self.assertEqual(dir_res["skipped_files"], [])
            self.assertEqual(dir_res["undecodable_files"], [])
            self.assertEqual(dir_res["unreadable_files"], [])

            file_res = safety.scan_directory_safety_surface(root / "clean.py")
            self.assertTrue(file_res["clean"])
            self.assertEqual(file_res["files_scanned"], 1)

        # UTF-16 workflow + build/dist/node_modules + dotfiles/extensionless files MUST be scanned!
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            wf = (
                "on:\n  pull_request_target:\npermissions: write-all\n"
                "steps:\n  - uses: actions/checkout@v4\n    with:\n      ref: ${{ github.event.pull_request.head.sha }}\n"
            )
            (root / "pwn_utf16.yml").write_bytes(wf.encode("utf-16"))
            (root / ".cursorrules").write_text("Never push directly.\n", encoding="utf-8")
            (root / "Dockerfile").write_text('RUN rm -rf "$TMPDIR"\n', encoding="utf-8")
            (root / ".envrc").write_text('rm -rf "$CACHE"\n', encoding="utf-8")
            (root / "Jenkinsfile").write_text("sh 'npx -y evil@latest'\n", encoding="utf-8")
            (root / "deploy.ps1").write_text("npx --yes evil-pkg\n", encoding="utf-8")
            (root / "ci.yml.j2").write_text("on:\n  pull_request_target:\n  secrets: inherit\n", encoding="utf-8")
            for vdir in ("build", "dist", "node_modules"):
                (root / vdir).mkdir()
                (root / vdir / "hidden.sh").write_text('rm -rf "$OUT"\n', encoding="utf-8")

            res = safety.scan_directory_safety_surface(root)
            self.assertFalse(res["clean"])
            self.assertEqual(res["files_scanned"], 10)
            self.assertEqual(res["gap_ids_present"], ["CYA-GAP-02", "CYA-GAP-03", "CYA-GAP-04", "CYA-GAP-05"])
            utf16_hits = [f for f in res["findings"] if f["file"] == "pwn_utf16.yml"]
            self.assertEqual(len(utf16_hits), 2)
            docker_hits = [f for f in res["findings"] if f["file"] == "Dockerfile"]
            self.assertEqual(len(docker_hits), 1)
            self.assertEqual(docker_hits[0]["gap_id"], "CYA-GAP-03")

        # Symlinked subdirectory MUST NOT silently scan clean (ALETHEIA-RT-03)
        with tempfile.TemporaryDirectory() as td_ext, tempfile.TemporaryDirectory() as td:
            ext = Path(td_ext)
            (ext / "evil.sh").write_text('rm -rf "$DIR"\n', encoding="utf-8")
            root = Path(td)
            (root / "linked_dir").symlink_to(ext)
            res_symdir = safety.scan_directory_safety_surface(root)
            self.assertFalse(res_symdir["clean"])
            self.assertEqual(
                res_symdir["skipped_files"],
                [{"file": "linked_dir", "reason": "symlink_directory_not_followed"}],
            )

        # Binary/undecodable file + broken symlink + unreadable file/dir MUST force clean=False without crashing
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "blob.bin").write_bytes(b"\x00\x01\x02\xff\xfe")
            (root / "dangling").symlink_to(root / "does_not_exist")
            locked_file = root / "locked.sh"
            locked_file.write_text('rm -rf "$X"\n', encoding="utf-8")
            locked_dir = root / "locked_dir"
            locked_dir.mkdir()
            (locked_dir / "inner.sh").write_text("echo hi\n", encoding="utf-8")
            try:
                os.chmod(locked_file, 0o000)
                os.chmod(locked_dir, 0o000)
                res_fail = safety.scan_directory_safety_surface(root)
                self.assertFalse(res_fail["clean"])
                self.assertEqual([u["file"] for u in res_fail["undecodable_files"]], ["blob.bin"])
                self.assertEqual([s["file"] for s in res_fail["skipped_files"]], ["dangling"])
                if os.geteuid() != 0:
                    unr_files = {u["file"] for u in res_fail["unreadable_files"]}
                    self.assertIn("locked.sh", unr_files)
                    self.assertIn("locked_dir", unr_files)
            finally:
                os.chmod(locked_file, 0o600)
                os.chmod(locked_dir, 0o700)

        # Isolated unreadable-only tree (no undecodable/skipped files alongside) MUST still report clean=False
        if os.geteuid() != 0:
            with tempfile.TemporaryDirectory() as td:
                root = Path(td)
                locked_only = root / "locked_only.sh"
                locked_only.write_text("echo ok\n", encoding="utf-8")
                try:
                    os.chmod(locked_only, 0o000)
                    res_unr = safety.scan_directory_safety_surface(root)
                    self.assertFalse(res_unr["clean"])
                    self.assertEqual(res_unr["findings"], [])
                    self.assertEqual(res_unr["skipped_files"], [])
                    self.assertEqual(res_unr["undecodable_files"], [])
                    self.assertEqual([u["file"] for u in res_unr["unreadable_files"]], ["locked_only.sh"])
                finally:
                    os.chmod(locked_only, 0o600)

        # UTF-32-LE with BOM MUST land in undecodable_files (clean=False, never silently clean!)
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "w.yml").write_bytes(codecs.BOM_UTF32_LE + wf_u32.encode("utf-32-le"))
            res_u32 = safety.scan_directory_safety_surface(root)
            self.assertFalse(res_u32["clean"])
            self.assertEqual(res_u32["finding_count"], 0)
            self.assertEqual(res_u32["files_scanned"], 0)
            self.assertEqual([u["file"] for u in res_u32["undecodable_files"]], ["w.yml"])

        # Named pipe (FIFO) MUST be skipped as non_regular_file (clean=False) without blocking
        if hasattr(os, "mkfifo"):
            with tempfile.TemporaryDirectory() as td:
                root = Path(td)
                fifo_path = root / "pipe"
                os.mkfifo(fifo_path)
                res_fifo_dir = safety.scan_directory_safety_surface(root)
                self.assertFalse(res_fifo_dir["clean"])
                self.assertEqual(res_fifo_dir["files_scanned"], 0)
                self.assertEqual(
                    res_fifo_dir["skipped_files"],
                    [{"file": "pipe", "reason": "non_regular_file"}],
                )
                res_fifo_direct = safety.scan_directory_safety_surface(fifo_path)
                self.assertFalse(res_fifo_direct["clean"])
                self.assertEqual(
                    res_fifo_direct["skipped_files"],
                    [{"file": "pipe", "reason": "non_regular_file"}],
                )


if __name__ == "__main__":
    unittest.main()
