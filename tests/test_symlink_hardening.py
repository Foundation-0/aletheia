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
from aletheia.scaffold import _lstat_refuse_symlink, _require_no_symlink_target, init_workspace
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
                expected_rels = [rel for rel, _ in emb]
                actual_rels = [item["relative_path"] for item in res["files"]]
                _req(
                    actual_rels == expected_rels,
                    f"empty source_dir fallback for {target} wrote {actual_rels}, expected {expected_rels}",
                )
                for rel, expected_content in emb:
                    out_file = t_dest / rel
                    _req(out_file.is_file(), f"embedded fallback file missing for {target}: {rel}")
                    _req(
                        out_file.read_text(encoding="utf-8") == expected_content,
                        f"embedded fallback content mismatch for {target}: {rel}",
                    )
            _req(
                (base / "empty_dest_0" / "plugin.json").is_file(),
                "antigravity empty source_dir fallback must materialize plugin.json",
            )
            _req(
                (base / "empty_dest_1" / ".claude-plugin" / "plugin.json").is_file(),
                "claude-code empty source_dir fallback must materialize .claude-plugin/plugin.json",
            )

            # (g) Clean real source files across all 6 targets still load from source_dir
            full_repo = base / "full_repo"
            (full_repo / ".agents" / "plugins" / "aletheia-research").mkdir(parents=True)
            (full_repo / ".agents" / "plugins" / "aletheia-research" / "plugin.json").write_text('{"ok":true}\n', encoding="utf-8")
            (full_repo / "adapters" / "claude-code" / "commands").mkdir(parents=True)
            (full_repo / "adapters" / "claude-code" / "commands" / "aletheia.md").write_text("# cmd\n", encoding="utf-8")
            (full_repo / "adapters" / "claude-code" / "agents").mkdir(parents=True)
            (full_repo / "adapters" / "claude-code" / "agents" / "probe.md").write_text("# agent\n", encoding="utf-8")
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
            _req(
                (base / "full_dest_0" / "plugin.json").read_text(encoding="utf-8") == '{"ok":true}\n',
                "antigravity must materialize on-disk source_dir plugin.json rather than embedded fallback",
            )
            _req(
                not (base / "full_dest_0" / "rules" / "AGENTS.md").exists(),
                "antigravity populated source_dir install must not fall back to embedded rules/AGENTS.md",
            )
            _req((base / "full_dest_1" / ".claude" / "commands" / "aletheia.md").read_text(encoding="utf-8") == "# cmd\n", "claude-code command wrong text")
            _req((base / "full_dest_1" / ".claude" / "agents" / "probe.md").read_text(encoding="utf-8") == "# agent\n", "claude-code agent wrong text")
            _req((base / "full_dest_2" / "AGENTS.md").read_text(encoding="utf-8") == "# codex\n", "codex loaded wrong text")
            _req((base / "full_dest_3" / ".cursor" / "rules" / "aletheia-research.mdc").read_text(encoding="utf-8") == "# cur\n", "cursor loaded wrong text")
            _req((base / "full_dest_4" / "GEMINI.md").read_text(encoding="utf-8") == "# gem\n", "gemini-cli loaded wrong text")
            _req((base / "full_dest_5" / "AGENTS.md").read_text(encoding="utf-8") == "# root-agents\n", "repo loaded wrong text")

            # (h) Fallback from missing adapters/codex/AGENTS.md to clean repo_root/AGENTS.md
            root_only_repo = base / "root_only_repo"
            root_only_repo.mkdir()
            (root_only_repo / "AGENTS.md").write_text("# root-fallback\n", encoding="utf-8")
            rdest = base / "root_only_dest"
            res_r = install_adapter("codex", dest=rdest, source_dir=root_only_repo)
            _req(res_r["status"] == "INSTALLED", "codex root fallback failed")
            _req((rdest / "AGENTS.md").read_text(encoding="utf-8") == "# root-fallback\n", "codex root fallback content wrong")

    def test_absolute_symlinked_ancestors_refused_across_scaffold_and_installer(self) -> None:
        with tempfile.TemporaryDirectory(prefix="aletheia_t_abs_anc_") as td:
            base = Path(td).resolve()
            outside = base / "outside"
            outside.mkdir()
            link = base / "link"
            link.symlink_to(outside, target_is_directory=True)

            # (a) Exact issue #25 reproducer on init_workspace (missing leaf, existing leaf, deep nested, force=False/True)
            for force in (False, True):
                _expect_symlink_refused(init_workspace, link / "ws", domain="math", force=force)
                _expect_symlink_refused(init_workspace, link / "nested" / "ws", domain="math", force=force)
            _req(list(outside.iterdir()) == [], f"init_workspace wrote into outside via symlinked parent: {list(outside.iterdir())}")

            (outside / "preexisting_ws").mkdir()
            _expect_symlink_refused(init_workspace, link / "preexisting_ws", domain="math", force=True)
            _req(not (outside / "preexisting_ws" / "aletheia.json").exists(), "init_workspace wrote into preexisting dir via symlinked parent")

            # (b) install_adapter(dest=...) through an absolute symlinked parent (dry_run & live, force=False/True)
            dest_outside = base / "dest_outside"
            dest_outside.mkdir()
            dest_link = base / "dest_link"
            dest_link.symlink_to(dest_outside, target_is_directory=True)
            for target in ("antigravity", "codex", "claude-code"):
                for dry_run in (False, True):
                    for force in (False, True):
                        _expect_symlink_refused(
                            install_adapter,
                            target,
                            dest=dest_link / f"sub_{target}",
                            dry_run=dry_run,
                            force=force,
                        )
            _req(list(dest_outside.rglob("*")) == [], "install_adapter wrote into dest_outside via symlinked parent")

            # (c) install_adapter(source_dir=...) through an absolute symlinked parent (dry_run & live)
            src_outside = base / "src_outside"
            (src_outside / "repo" / "adapters" / "codex").mkdir(parents=True)
            (src_outside / "repo" / "adapters" / "codex" / "AGENTS.md").write_text("EXFIL_VIA_PARENT\n", encoding="utf-8")
            src_link = base / "src_parent_link"
            src_link.symlink_to(src_outside, target_is_directory=True)
            clean_dest = base / "clean_dest"
            for dry_run in (False, True):
                _expect_symlink_refused(
                    install_adapter,
                    "codex",
                    dest=clean_dest,
                    source_dir=src_link / "repo",
                    dry_run=dry_run,
                )
            _req(not (clean_dest / "AGENTS.md").exists(), "install_adapter read source_dir through symlinked parent")

            # (d) Dot-dot normalization & compound stack-walk bypasses (nonexistent/reg_file before link_sub/..)
            (outside / "sub").mkdir()
            link_sub = base / "link_sub"
            link_sub.symlink_to(outside / "sub", target_is_directory=True)
            reg_file = base / "reg_file.txt"
            reg_file.write_text("not a dir\n", encoding="utf-8")
            (outside / "evil_src" / "adapters" / "codex").mkdir(parents=True)
            (outside / "evil_src" / "adapters" / "codex" / "AGENTS.md").write_text("PWNED_FROM_OUTSIDE\n", encoding="utf-8")

            _expect_symlink_refused(init_workspace, link / ".." / "escaped_ws", domain="math", force=True)
            _expect_symlink_refused(init_workspace, base / "no_such" / ".." / "link" / "ws", domain="math", force=True)
            _expect_symlink_refused(init_workspace, base / "no_such" / ".." / "link_sub" / ".." / "esc_ws", domain="math", force=True)
            _expect_symlink_refused(init_workspace, reg_file / ".." / "link_sub" / ".." / "esc_reg", domain="math", force=True)
            _expect_symlink_refused(
                install_adapter, "codex", dest=base / "no_such" / ".." / "dest_link" / "sub", force=True
            )
            _expect_symlink_refused(
                install_adapter, "codex", dest=base / "no_such" / ".." / "link_sub" / ".." / "esc_dest", force=True
            )
            _expect_symlink_refused(
                install_adapter, "codex", dest=clean_dest, source_dir=base / "no_such" / ".." / "src_parent_link" / "repo"
            )
            _expect_symlink_refused(
                install_adapter, "codex", dest=clean_dest, source_dir=base / "no_such" / ".." / "link_sub" / ".." / "evil_src"
            )
            _req(not (outside / "esc_ws").exists(), "escaped via no_such/../link_sub/../esc_ws")
            _req(not (outside / "esc_reg").exists(), "escaped via reg_file/../link_sub/../esc_reg")
            _req(not (outside / "esc_dest").exists(), "escaped dest via no_such/../link_sub/../esc_dest")
            _req(not (clean_dest / "AGENTS.md").exists(), "read source_dir via no_such/../link_sub/../evil_src")

            ws_leaf_link = base / "ws_leaf_link"
            ws_leaf_link.symlink_to(outside, target_is_directory=True)
            old_cwd = os.getcwd()
            try:
                os.chdir(base)
                _expect_symlink_refused(init_workspace, Path("no_such/../link/ws"), domain="math", force=True)
                _expect_symlink_refused(init_workspace, Path("no_such/../link_sub/../esc_rel"), domain="math", force=True)
                _expect_symlink_refused(init_workspace, Path("no_such/../ws_leaf_link"), domain="math", force=True)
                _req(not (outside / "esc_rel").exists(), "escaped via relative no_such/../link_sub/../esc_rel")
                # Clean dot-dot traversal with no symlinks still works (including popping at root)
                ok_dd = init_workspace(Path("clean_sub/../clean_dd_ws"), domain="math")
                _req(ok_dd["status"] == "INITIALIZED", f"clean dot-dot init failed: {ok_dd}")
                _req((base / "clean_dd_ws" / "aletheia.json").is_file(), "clean dot-dot workspace missing")
                root_dd_ws = Path("/..") / base.relative_to("/") / "root_dd_ws"
                ok_root_dd = init_workspace(root_dd_ws, domain="math")
                _req(ok_root_dd["status"] == "INITIALIZED", f"root dot-dot init failed: {ok_root_dd}")
            finally:
                os.chdir(old_cwd)

            # (e) Symlink loop (ELOOP) must fail closed with SYMLINK_REFUSED (direct, init_workspace, & compound dot-dot)
            loop_a = base / "loop_a"
            loop_b = base / "loop_b"
            loop_a.symlink_to(loop_b, target_is_directory=True)
            loop_b.symlink_to(loop_a, target_is_directory=True)
            try:
                _lstat_refuse_symlink(loop_a / "ws", role="workspace", detail="target")
            except AletheiaError as exc:
                _req(exc.code == "SYMLINK_REFUSED", f"expected SYMLINK_REFUSED on ELOOP, got {exc.code}")
                _req("symlink loop" in exc.message, f"expected symlink loop detail, got {exc.message}")
            else:
                raise AssertionError("ELOOP path was not refused by _lstat_refuse_symlink")
            try:
                init_workspace(loop_a / "ws", domain="math")
            except AletheiaError as exc:
                _req(exc.code == "SYMLINK_REFUSED", f"expected SYMLINK_REFUSED on init_workspace ELOOP, got {exc.code}")
                _req("symlink loop" in exc.message, f"expected symlink loop message from init_workspace, got {exc.message}")
            else:
                raise AssertionError("init_workspace did not refuse ELOOP path")
            _expect_symlink_refused(init_workspace, base / "no_such" / ".." / "loop_a" / ".." / "esc_eloop", domain="math", force=True)

    def test_macos_style_top_level_system_links_allowed_while_deeper_links_refused(self) -> None:
        with tempfile.TemporaryDirectory(prefix="aletheia_t_macos_top_") as td:
            base = Path(td).resolve()
            fake_root = base / "fake_root"
            (fake_root / "private" / "var" / "folders" / "work").mkdir(parents=True)
            (fake_root / "private" / "tmp" / "work").mkdir(parents=True)
            (fake_root / "var").symlink_to(fake_root / "private" / "var", target_is_directory=True)
            (fake_root / "tmp").symlink_to(fake_root / "private" / "tmp", target_is_directory=True)

            # Depth-1 OS-style strict ancestors (/var -> /private/var, /tmp -> /private/tmp) are allowed
            ok_var = _require_no_symlink_target(
                fake_root / "var" / "folders" / "work" / "ws",
                role="workspace",
                anchor_root=fake_root,
            )
            _req(
                ok_var == (fake_root / "private" / "var" / "folders" / "work" / "ws").resolve(),
                f"unexpected resolved path via top-level /var: {ok_var}",
            )
            # Clean dot-dot staying below depth-1 /var is allowed (kills len(stack)==1 -> !=1)
            ok_var_dd = _require_no_symlink_target(
                fake_root / "var" / "no_such" / ".." / "folders" / "work" / "ws",
                role="workspace",
                anchor_root=fake_root,
            )
            _req(
                ok_var_dd == (fake_root / "private" / "var" / "folders" / "work" / "ws").resolve(),
                f"unexpected resolved path via /var/no_such/../folders: {ok_var_dd}",
            )
            ok_tmp = _require_no_symlink_target(
                fake_root / "tmp" / "work" / "dest",
                role="destination",
                anchor_root=fake_root,
            )
            _req(
                ok_tmp == (fake_root / "private" / "tmp" / "work" / "dest").resolve(),
                f"unexpected resolved path via top-level /tmp: {ok_tmp}",
            )
            # Empty relative parts (root itself) succeeds cleanly without IndexError
            ok_root = _require_no_symlink_target(fake_root, role="workspace", anchor_root=fake_root)
            _req(ok_root == fake_root.resolve(), f"root path resolution mismatch: {ok_root}")

            # Symlink leaf even at depth 1 (directly or after dot-dot) is still refused
            _expect_symlink_refused(_require_no_symlink_target, fake_root / "var", role="workspace", anchor_root=fake_root)
            _expect_symlink_refused(_require_no_symlink_target, fake_root / "tmp", role="destination", anchor_root=fake_root)
            _expect_symlink_refused(
                _require_no_symlink_target,
                fake_root / "var" / "no_such" / "..",
                role="workspace",
                anchor_root=fake_root,
            )

            # Traversing .. out of depth-1 symlink (/var/.. -> /private) is refused
            outside = base / "outside"
            outside.mkdir()
            (fake_root / "private" / "evil_in_priv").symlink_to(outside, target_is_directory=True)
            _expect_symlink_refused(
                _require_no_symlink_target,
                fake_root / "var" / "no_such" / ".." / ".." / "evil_in_priv" / "ws",
                role="workspace",
                anchor_root=fake_root,
            )

            # Symlink at exact depth 2 below OS top-level link (kills len(stack) >= 2 -> > 2) and deeper links are refused
            (fake_root / "private" / "var" / "depth2_link").symlink_to(outside, target_is_directory=True)
            _expect_symlink_refused(
                _require_no_symlink_target,
                fake_root / "var" / "depth2_link" / "ws",
                role="workspace",
                anchor_root=fake_root,
            )
            (fake_root / "private" / "var" / "folders" / "work" / "evil_link").symlink_to(outside, target_is_directory=True)
            (fake_root / "private" / "tmp" / "work" / "evil_link").symlink_to(outside, target_is_directory=True)
            _expect_symlink_refused(
                _require_no_symlink_target,
                fake_root / "var" / "folders" / "work" / "evil_link" / "ws",
                role="workspace",
                anchor_root=fake_root,
            )
            _expect_symlink_refused(
                _require_no_symlink_target,
                fake_root / "tmp" / "work" / "evil_link" / "dest",
                role="destination",
                anchor_root=fake_root,
            )

            # Unresolved TemporaryDirectory path (which sits under /var/folders/... on macOS) works end-to-end
            raw_td = Path(td)
            ws_raw = raw_td / "raw_ws"
            res_ws = init_workspace(ws_raw, domain="math")
            _req(res_ws["status"] == "INITIALIZED", f"unresolved tempdir init failed: {res_ws}")
            dest_raw = raw_td / "raw_dest"
            res_ins = install_adapter("antigravity", dest=dest_raw)
            _req(res_ins["status"] == "INSTALLED", f"unresolved tempdir install failed: {res_ins}")
            _req((dest_raw / "plugin.json").is_file(), "unresolved tempdir install missing plugin.json")


if __name__ == "__main__":
    unittest.main()
