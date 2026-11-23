"""
Symlink hardening tests for scaffold and installer write paths.

Zero bare assert statements (100% R4 parity under -I -B, -I -O -B, -I -B -W error).
"""
from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest

from aletheia.installer import VALID_TARGETS, _build_install_plan, _collect_tree, install_adapter
from aletheia.scaffold import init_workspace
from aletheia.strict_io import AletheiaError


def _req(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def _expect_symlink_refused(fn: object, *args: object, **kwargs: object) -> None:
    if not callable(fn):
        raise AssertionError("fn must be callable")
    try:
        fn(*args, **kwargs)
    except AletheiaError as exc:
        _req(exc.code == "SYMLINK_REFUSED", f"expected SYMLINK_REFUSED, got {exc.code}: {exc.message}")
        _req("force never follows links" in exc.message, f"message lacks force note: {exc.message}")
        return
    raise AssertionError("expected AletheiaError(SYMLINK_REFUSED), but call succeeded")


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

    def test_al15_01_scaffold_refuses_symlinked_target_and_relative_parent(self) -> None:
        with tempfile.TemporaryDirectory(prefix="aletheia_t_al15_01_") as td:
            base = Path(td).resolve()
            outside = base / "outside"
            outside.mkdir()

            # (a) Absolute live symlink target_dir
            ws_link = base / "ws_link"
            ws_link.symlink_to(outside, target_is_directory=True)
            for force in (False, True):
                _expect_symlink_refused(init_workspace, ws_link, domain="math", force=force)
            _req(not (outside / "aletheia.json").exists(), "wrote through live ws_link")

            # (b) Broken symlink target_dir
            broken_ws = base / "broken_ws"
            broken_ws.symlink_to(base / "nonexistent_target", target_is_directory=True)
            _expect_symlink_refused(init_workspace, broken_ws, domain="math", force=True)
            _req(not os.path.lexists(base / "nonexistent_target"), "created broken symlink target")

            # (c) Relative target_dir traversing a symlinked parent + clean relative positive control
            outside2 = base / "outside2"
            outside2.mkdir()
            (base / "rel_link").symlink_to(outside2, target_is_directory=True)
            old_cwd = os.getcwd()
            try:
                os.chdir(base)
                for force in (False, True):
                    _expect_symlink_refused(init_workspace, Path("rel_link/ws"), domain="math", force=force)
                _req(not (outside2 / "ws").exists(), "wrote through relative symlink parent")

                ok = init_workspace(Path("clean_sub/ws"), domain="math")
                _req(ok["status"] == "INITIALIZED", f"clean relative init failed: {ok}")
                _req((base / "clean_sub" / "ws" / "aletheia.json").is_file(), "clean relative workspace missing")
            finally:
                os.chdir(old_cwd)

    def test_al15_02_installer_antigravity_default_dest_refuses_symlinks(self) -> None:
        with tempfile.TemporaryDirectory(prefix="aletheia_t_al15_02_") as td:
            base = Path(td).resolve()
            outside = base / "outside"
            outside.mkdir()

            # Case 1: cwd/.agents is a symlink
            cwd1 = base / "cwd1"
            cwd1.mkdir()
            (cwd1 / ".agents").symlink_to(outside, target_is_directory=True)
            old_cwd = os.getcwd()
            try:
                os.chdir(cwd1)
                for dry_run in (False, True):
                    for force in (False, True):
                        _expect_symlink_refused(install_adapter, "antigravity", dest=None, dry_run=dry_run, force=force)
                _req(list(outside.rglob("*")) == [], "wrote through cwd/.agents symlink")

                # Case 2: cwd/.agents/plugins is a symlink
                cwd2 = base / "cwd2"
                (cwd2 / ".agents").mkdir(parents=True)
                (cwd2 / ".agents" / "plugins").symlink_to(outside, target_is_directory=True)
                os.chdir(cwd2)
                _expect_symlink_refused(install_adapter, "antigravity", dest=None, force=True)
                _req(list(outside.rglob("*")) == [], "wrote through cwd/.agents/plugins symlink")

                # Case 3: cwd/.agents/plugins/aletheia-research is a broken symlink
                cwd3 = base / "cwd3"
                (cwd3 / ".agents" / "plugins").mkdir(parents=True)
                (cwd3 / ".agents" / "plugins" / "aletheia-research").symlink_to(base / "dangling_ag")
                os.chdir(cwd3)
                _expect_symlink_refused(install_adapter, "antigravity", dest=None, force=True)
                _req(not os.path.lexists(base / "dangling_ag"), "created broken antigravity target")

                # Case 4: clean cwd positive control + relative explicit dest refusal
                cwd4 = base / "cwd4"
                cwd4.mkdir()
                (cwd4 / "rel_dest_link").symlink_to(outside, target_is_directory=True)
                os.chdir(cwd4)
                _expect_symlink_refused(install_adapter, "codex", dest=Path("rel_dest_link/sub"), force=True)
                ok = install_adapter("antigravity", dest=None)
                _req(ok["status"] == "INSTALLED", f"clean antigravity default install failed: {ok}")
                _req((cwd4 / ".agents" / "plugins" / "aletheia-research" / "plugin.json").is_file(), "plugin.json missing")
            finally:
                os.chdir(old_cwd)

    def test_al15_03_installer_refuses_source_symlinks_and_broken_source_links(self) -> None:
        with tempfile.TemporaryDirectory(prefix="aletheia_t_al15_03_") as td:
            base = Path(td).resolve()
            outside = base / "outside"
            (outside / "plugins" / "aletheia-research").mkdir(parents=True)
            (outside / "AGENTS.md").write_text("SECRET_ON_MAIN\n", encoding="utf-8")
            (outside / "GEMINI.md").write_text("SECRET_GEMINI\n", encoding="utf-8")
            (outside / "aletheia-research.mdc").write_text("SECRET_CURSOR\n", encoding="utf-8")
            (outside / "plugins" / "aletheia-research" / "plugin.json").write_text('{"stolen":true}\n', encoding="utf-8")
            dest = base / "dest"
            dest.mkdir()

            # (a) Symlinked source_dir itself (absolute & relative)
            real_repo = base / "real_repo"
            real_repo.mkdir()
            src_link = base / "src_link"
            src_link.symlink_to(real_repo, target_is_directory=True)
            _expect_symlink_refused(install_adapter, "codex", dest=dest, source_dir=src_link)
            old_cwd = os.getcwd()
            try:
                os.chdir(base)
                _expect_symlink_refused(install_adapter, "codex", dest=dest, source_dir=Path("src_link/sub"))
            finally:
                os.chdir(old_cwd)

            # (b) Symlinked intermediate source dir for codex (adapters/codex -> outside)
            repo_codex = base / "repo_codex"
            (repo_codex / "adapters").mkdir(parents=True)
            (repo_codex / "adapters" / "codex").symlink_to(outside, target_is_directory=True)
            _expect_symlink_refused(install_adapter, "codex", dest=dest, source_dir=repo_codex)
            _req(not (dest / "AGENTS.md").exists(), "exfiltrated codex secret")

            # (c) Symlinked intermediate source dir for antigravity (.agents -> outside)
            repo_ag = base / "repo_ag"
            repo_ag.mkdir()
            (repo_ag / ".agents").symlink_to(outside, target_is_directory=True)
            _expect_symlink_refused(install_adapter, "antigravity", dest=dest, source_dir=repo_ag)
            _req(not (dest / "plugin.json").exists(), "exfiltrated antigravity secret")

            # (d) Symlinked intermediate source dirs for claude-code, cursor, gemini-cli
            repo_cc = base / "repo_cc"
            repo_cc.mkdir()
            (repo_cc / "adapters").symlink_to(outside, target_is_directory=True)
            _expect_symlink_refused(install_adapter, "claude-code", dest=dest, source_dir=repo_cc)
            _expect_symlink_refused(install_adapter, "gemini-cli", dest=dest, source_dir=repo_cc)

            repo_cur = base / "repo_cur"
            (repo_cur / "adapters" / "cursor" / ".cursor").mkdir(parents=True)
            (repo_cur / "adapters" / "cursor" / ".cursor" / "rules").symlink_to(outside, target_is_directory=True)
            _expect_symlink_refused(install_adapter, "cursor", dest=dest, source_dir=repo_cur)

            # (e) Broken leaf/dir source symlinks must raise SYMLINK_REFUSED instead of silently falling back
            repo_broken = base / "repo_broken"
            (repo_broken / "adapters" / "codex").mkdir(parents=True)
            (repo_broken / "adapters" / "codex" / "AGENTS.md").symlink_to(base / "no_such_file")
            (repo_broken / "AGENTS.md").write_text("FALLBACK\n", encoding="utf-8")
            _expect_symlink_refused(install_adapter, "codex", dest=dest, source_dir=repo_broken)

            repo_broken_root = base / "repo_broken_root"
            repo_broken_root.mkdir()
            (repo_broken_root / "AGENTS.md").symlink_to(base / "no_such_root_agents")
            _expect_symlink_refused(install_adapter, "codex", dest=dest, source_dir=repo_broken_root)
            _expect_symlink_refused(install_adapter, "repo", dest=dest, source_dir=repo_broken_root)

            repo_broken_gem = base / "repo_broken_gem"
            (repo_broken_gem / "adapters" / "gemini-cli").mkdir(parents=True)
            (repo_broken_gem / "adapters" / "gemini-cli" / "GEMINI.md").symlink_to(base / "no_such_gem")
            _expect_symlink_refused(install_adapter, "gemini-cli", dest=dest, source_dir=repo_broken_gem)

            # (f) Clean empty source_dir + repo_root=None embedded fallbacks across all 6 targets
            empty_repo = base / "empty_repo"
            empty_repo.mkdir()
            for idx, target in enumerate(VALID_TARGETS):
                t_dest = base / f"empty_dest_{idx}"
                res = install_adapter(target, dest=t_dest, source_dir=empty_repo)
                _req(res["status"] == "INSTALLED", f"empty source_dir fallback failed for {target}: {res}")
                emb = _build_install_plan(target, None)
                _req(len(emb) >= 1, f"embedded plan empty for {target}")

            # (g) Clean real source files across all 6 targets still load from source_dir
            full_repo = base / "full_repo"
            (full_repo / ".agents" / "plugins" / "aletheia-research").mkdir(parents=True)
            (full_repo / ".agents" / "plugins" / "aletheia-research" / "plugin.json").write_text('{"ok":true}\n', encoding="utf-8")
            (full_repo / "adapters" / "claude-code" / "commands").mkdir(parents=True)
            (full_repo / "adapters" / "claude-code" / "commands" / "aletheia.md").write_text("# cmd\n", encoding="utf-8")
            (full_repo / "adapters" / "codex").mkdir(parents=True)
            (full_repo / "adapters" / "codex" / "AGENTS.md").write_text("# codex\n", encoding="utf-8")
            (full_repo / "adapters" / "cursor" / ".cursor" / "rules").mkdir(parents=True)
            (full_repo / "adapters" / "cursor" / ".cursor" / "rules" / "aletheia-research.mdc").write_text("# cur\n", encoding="utf-8")
            (full_repo / "adapters" / "gemini-cli").mkdir(parents=True)
            (full_repo / "adapters" / "gemini-cli" / "GEMINI.md").write_text("# gem\n", encoding="utf-8")
            (full_repo / "AGENTS.md").write_text("# root-agents\n", encoding="utf-8")
            for idx, target in enumerate(VALID_TARGETS):
                t_dest = base / f"full_dest_{idx}"
                res = install_adapter(target, dest=t_dest, source_dir=full_repo)
                _req(res["status"] == "INSTALLED", f"full source_dir install failed for {target}: {res}")
            _req((base / "full_dest_2" / "AGENTS.md").read_text(encoding="utf-8") == "# codex\n", "codex loaded wrong text")
            _req((base / "full_dest_5" / "AGENTS.md").read_text(encoding="utf-8") == "# root-agents\n", "repo loaded wrong text")

            # (h) Fallback from missing adapters/codex/AGENTS.md to clean repo_root/AGENTS.md
            root_only_repo = base / "root_only_repo"
            root_only_repo.mkdir()
            (root_only_repo / "AGENTS.md").write_text("# root-fallback\n", encoding="utf-8")
            rdest = base / "root_only_dest"
            res_r = install_adapter("codex", dest=rdest, source_dir=root_only_repo)
            _req(res_r["status"] == "INSTALLED", "codex root fallback failed")
            _req((rdest / "AGENTS.md").read_text(encoding="utf-8") == "# root-fallback\n", "codex root fallback content wrong")


if __name__ == "__main__":
    unittest.main()
