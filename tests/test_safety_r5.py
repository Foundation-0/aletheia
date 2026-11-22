#!/usr/bin/env python3
"""R5 adversarial & mutation-killing test suite for aletheia/safety.py (CYA-GAP-01..06).

Zero bare asserts. Covers every scanner rule, boundary codepoint, nounset toggle,
and fail-closed input guard.
"""
from __future__ import annotations

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
        # Exact boundary codepoints for Tags (0xE0000 and 0xE007F) + non-tag neighbors (0xDFFFF, 0xE0080)
        sample = "ok\n\u200b\u202e" + chr(0xE0000) + chr(0xE007F) + chr(0xE0080)
        hits = safety.scan_hidden_unicode(sample, "test.py")
        self.assertEqual([h["codepoint"] for h in hits], ["U+200B", "U+202E", "U+E0000", "U+E007F"])
        self.assertEqual([h["category"] for h in hits], [
            "zero_width_or_bom",
            "bidi_trojan_source",
            "unicode_tag_smuggling",
            "unicode_tag_smuggling",
        ])
        self.assertEqual(hits[0]["line"], 2)
        self.assertEqual(hits[0]["col"], 1)

    def test_02_gaps_02_through_06_and_input_guards(self) -> None:
        with self.assertRaisesRegex(ValueError, "SAFETY_TEXT_NOT_STR"):
            safety.scan_text_safety_surface(None)  # type: ignore[arg-type]
        with self.assertRaisesRegex(ValueError, "SAFETY_INVALID_FILE_LABEL"):
            safety.scan_text_safety_surface("ok", " ")
        with self.assertRaisesRegex(ValueError, "SAFETY_INVALID_HOST_FLAG"):
            safety.scan_text_safety_surface("ok", "a.sh", include_host_hygiene=1)  # type: ignore[arg-type]

        # CYA-GAP-02: MCP / permission bypass
        r2 = safety.scan_text_safety_surface(
            "npx -q -y pkg@latest --yolo --dangerously-skip-permissions\nSessionStart:\n",
            "mcp.sh",
        )
        self.assertEqual(r2["gap_ids_present"], ["CYA-GAP-02"])
        self.assertEqual(r2["finding_count"], 5)

        # CYA-GAP-03: rm -rf "$VAR" with set -u / set +u / ${VAR:?} / comments / -- stop
        sh_safe = (
            'set -u\n'
            'rm -rf "$TARGET"\n'
            'set +u\n'
            '# rm -rf "$COMMENTED"\n'
            'rm --recursive --force "${TARGET:?}"\n'
            'rm -r "$ONLY_R"\n'
            'rm -- -rf "$STOPPED"\n'
        )
        self.assertTrue(safety.scan_text_safety_surface(sh_safe, "safe.sh")["clean"])
        sh_bad = 'set -o nounset\nset +o nounset\nrm --recursive -f "$DIR"\nrm -R --force "$DIR2"\n'
        r3 = safety.scan_text_safety_surface(sh_bad, "bad.sh")
        self.assertEqual(r3["gap_ids_present"], ["CYA-GAP-03"])
        self.assertEqual(r3["finding_count"], 2)

        # Comment stripping preserves quotes
        self.assertEqual(safety._strip_shell_comment("echo 'a#b' \"c#d\" # tail"), "echo 'a#b' \"c#d\" ")

        # CYA-GAP-04: pull_request_target + secrets/write
        ci_safe = "on:\n  pull_request:\npermissions:\n  contents: write\n"
        self.assertTrue(safety.scan_text_safety_surface(ci_safe, "ci.yml")["clean"])
        ci_bad = "on:\n  pull_request_target:\npermissions:\n  contents: write\n  token: ${{ secrets.GH_TOKEN }}\n"
        r4 = safety.scan_text_safety_surface(ci_bad, "ci.yml")
        self.assertEqual(r4["gap_ids_present"], ["CYA-GAP-04"])
        self.assertEqual(r4["finding_count"], 2)

        # CYA-GAP-05: prose-only governance rules & ~/ paths (only in rule docs)
        r5 = safety.scan_text_safety_surface("Commit only when asked.\nCache at ~/scratch/data.bin\n", "CLAUDE.md")
        self.assertEqual(r5["gap_ids_present"], ["CYA-GAP-05"])
        self.assertEqual(r5["finding_count"], 2)
        self.assertTrue(safety.scan_text_safety_surface("Commit only when asked.\n", "code.py")["clean"])

        # CYA-GAP-06: optional host hygiene
        host_txt = "alias rm='rm -i'\nREPO=~/Dropbox/work\n"
        self.assertTrue(safety.scan_text_safety_surface(host_txt, "env.sh", include_host_hygiene=False)["clean"])
        r6 = safety.scan_text_safety_surface(host_txt, "env.sh", include_host_hygiene=True)
        self.assertEqual(r6["gap_ids_present"], ["CYA-GAP-06"])
        self.assertEqual(r6["finding_count"], 2)

    def test_03_directory_and_file_scan(self) -> None:
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

            file_res = safety.scan_directory_safety_surface(root / "clean.py")
            self.assertTrue(file_res["clean"])
            self.assertEqual(file_res["files_scanned"], 1)


if __name__ == "__main__":
    unittest.main()
