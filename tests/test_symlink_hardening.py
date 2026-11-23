"""
Symlink hardening tests for scaffold and installer write paths.

Zero bare assert statements (100% R4 parity under -I -B, -I -O -B, -I -B -W error).
"""
from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest

from aletheia.installer import _collect_tree, install_adapter
from aletheia.scaffold import init_workspace
from aletheia.strict_io import AletheiaError


def _req(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


class TestSymlinkHardening(unittest.TestCase):
    def test_scaffold_refuses_symlinked_subdirectory(self) -> None:
        with tempfile.TemporaryDirectory(prefix="aletheia_t_link_") as td:
            base = Path(td)
            outside = base / "outside"
            outside.mkdir()
            for force in (False, True):
                ws = base / f"ws_{force}"
                ws.mkdir()
                (ws / "cartography").symlink_to(outside, target_is_directory=True)
                try:
                    init_workspace(ws, domain="math", force=force)
                except AletheiaError as exc:
                    _req(exc.code == "SYMLINK_REFUSED", f"force={force} wrong code: {exc.code}")
                    _req("force never follows links" in exc.message, f"message lacks force note: {exc.message}")
                else:
                    raise AssertionError(f"force={force}: symlinked cartography was not refused")
                _req(not (outside / "frontier_portals.md").exists(), "scaffold wrote outside the workspace root")

    def test_scaffold_refuses_symlinked_target_file_with_force(self) -> None:
        with tempfile.TemporaryDirectory(prefix="aletheia_t_link_") as td:
            base = Path(td)
            victim = base / "victim.json"
            ws = base / "ws"
            ws.mkdir()
            (ws / "aletheia.json").symlink_to(victim)
            try:
                init_workspace(ws, domain="math", force=True)
            except AletheiaError as exc:
                _req(exc.code == "SYMLINK_REFUSED", f"wrong code: {exc.code}")
            else:
                raise AssertionError("symlinked target file was not refused")
            _req(not os.path.lexists(victim), "scaffold created the symlink victim")

    def test_installer_refuses_symlinked_subdirectory(self) -> None:
        with tempfile.TemporaryDirectory(prefix="aletheia_t_link_") as td:
            base = Path(td)
            outside = base / "outside"
            outside.mkdir()
            dest = base / "dest"
            dest.mkdir()
            (dest / ".claude").symlink_to(outside, target_is_directory=True)
            try:
                install_adapter("claude-code", dest=dest, force=True)
            except AletheiaError as exc:
                _req(exc.code == "SYMLINK_REFUSED", f"wrong code: {exc.code}")
                _req("force never follows links" in exc.message, f"message lacks force note: {exc.message}")
            else:
                raise AssertionError("symlinked install subdirectory was not refused")
            _req(list(outside.rglob("*")) == [], "installer wrote outside the destination root")

    def test_installer_refuses_broken_symlink_destination(self) -> None:
        with tempfile.TemporaryDirectory(prefix="aletheia_t_link_") as td:
            base = Path(td)
            victim = base / "victim.md"
            dest = base / "dest"
            dest.mkdir()
            (dest / "AGENTS.md").symlink_to(victim)
            plan = install_adapter("codex", dest=dest, dry_run=True)
            _req(plan["files"][0]["action"] == "CONFLICT_EXISTS", f"broken symlink must not plan CREATE: {plan['files']}")
            for force in (False, True):
                try:
                    install_adapter("codex", dest=dest, force=force)
                except AletheiaError as exc:
                    _req(exc.code == "SYMLINK_REFUSED", f"force={force} wrong code: {exc.code}")
                else:
                    raise AssertionError(f"force={force}: broken symlink destination was not refused")
            _req(not os.path.lexists(victim), "installer created the broken symlink victim")
            _req((dest / "AGENTS.md").is_symlink(), "installer replaced the destination symlink")

    def test_installer_refuses_symlinked_destination(self) -> None:
        with tempfile.TemporaryDirectory(prefix="aletheia_t_link_") as td:
            base = Path(td)
            real = base / "real"
            real.mkdir()
            link = base / "linkdest"
            link.symlink_to(real, target_is_directory=True)
            try:
                install_adapter("codex", dest=link, force=True)
            except AletheiaError as exc:
                _req(exc.code == "SYMLINK_REFUSED", f"wrong code: {exc.code}")
            else:
                raise AssertionError("symlinked destination was not refused")
            _req(not (real / "AGENTS.md").exists(), "installer wrote through the destination symlink")

    def test_collect_tree_refuses_symlinked_source(self) -> None:
        with tempfile.TemporaryDirectory(prefix="aletheia_t_link_") as td:
            base = Path(td)
            secret = base / "secret.txt"
            secret.write_text("outside the tree\n", encoding="utf-8")
            src_file = base / "src_file"
            src_file.mkdir()
            (src_file / "ok.md").write_text("ok\n", encoding="utf-8")
            (src_file / "leak.md").symlink_to(secret)
            try:
                _collect_tree(src_file)
            except AletheiaError as exc:
                _req(exc.code == "SYMLINK_REFUSED", f"file case wrong code: {exc.code}")
            else:
                raise AssertionError("symlinked source file was copied")
            outside_dir = base / "outside_dir"
            outside_dir.mkdir()
            (outside_dir / "deep.md").write_text("deep\n", encoding="utf-8")
            src_dir = base / "src_dir"
            src_dir.mkdir()
            (src_dir / "linked").symlink_to(outside_dir, target_is_directory=True)
            try:
                _collect_tree(src_dir)
            except AletheiaError as exc:
                _req(exc.code == "SYMLINK_REFUSED", f"dir case wrong code: {exc.code}")
            else:
                raise AssertionError("symlinked source directory was copied")

    def test_collect_tree_normal_flow_unchanged(self) -> None:
        with tempfile.TemporaryDirectory(prefix="aletheia_t_link_") as td:
            src = Path(td) / "src"
            (src / "sub").mkdir(parents=True)
            (src / "__pycache__").mkdir()
            (src / "a.md").write_text("a\n", encoding="utf-8")
            (src / "sub" / "b.md").write_text("b\n", encoding="utf-8")
            (src / "__pycache__" / "c.md").write_text("c\n", encoding="utf-8")
            files = _collect_tree(src)
            _req(files == [("a.md", "a\n"), ("sub/b.md", "b\n")], f"unexpected collect result: {files}")

    def test_normal_and_force_flows_still_pass(self) -> None:
        with tempfile.TemporaryDirectory(prefix="aletheia_t_link_") as td:
            base = Path(td)
            ws = base / "ws"
            result = init_workspace(ws, domain="math")
            _req(result["status"] == "INITIALIZED", f"scaffold failed: {result}")
            again = init_workspace(ws, domain="math", force=True)
            _req(again["status"] == "INITIALIZED", f"forced scaffold failed: {again}")
            dest = base / "dest"
            installed = install_adapter("codex", dest=dest)
            _req(installed["status"] == "INSTALLED", f"install failed: {installed}")
            forced = install_adapter("codex", dest=dest, force=True)
            _req(forced["files"][0]["action"] == "OVERWRITE", f"forced install must overwrite regular files: {forced['files']}")


if __name__ == "__main__":
    unittest.main()
