"""
STALE versus UNKNOWN classification of `audit-check --pinned-manifest` hash mismatches.

A mismatch is STALE when the pinned SHA-256 equals the bytes of an older revision of that file in the
git history holding the manifest root (the commit is reported), and UNKNOWN otherwise. Every result
says how much a miss shows: `complete`, `partial`, `untracked` or `unavailable`; `complete` needs a full
clone, at least one commit that touched the path and every listed blob read. Both statuses still fail
the manifest. Zero bare `assert` statements.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

from aletheia.audit_check import _git_revision_with_sha256, run_audit_check, validate_pinned_manifest
from aletheia.strict_io import canonical_sha256_bytes

V1 = b"pinned revision one\n"
V2 = b"revision two\n"
V3 = b"revision three\n"


def _req(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def _sha(data: bytes) -> str:
    return canonical_sha256_bytes(data)


def _git(repo: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@example.invalid",
         "-c", "commit.gpgsign=false", *args],
        capture_output=True, text=True, check=True,
    )
    return proc.stdout.strip()


def _commit(repo: Path, rel: str, data: bytes, msg: str) -> str:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    _git(repo, "add", rel)
    _git(repo, "commit", "-q", "-m", msg)
    return _git(repo, "rev-parse", "HEAD")


def _manifest(path: Path, files: dict[str, str]) -> Path:
    path.write_bytes((json.dumps({"files": files}) + "\n").encode("utf-8"))
    return path


class TestPinnedManifestHistory(unittest.TestCase):
    def test_01_stale_names_newest_matching_commit_unknown_otherwise(self) -> None:
        with tempfile.TemporaryDirectory(prefix="aletheia_t_pin_") as td:
            repo = Path(td) / "repo"
            repo.mkdir()
            _git(repo, "init", "-q")
            _commit(repo, "f.txt", V1, "v1")
            _commit(repo, "f.txt", V2, "v2")
            c3 = _commit(repo, "f.txt", V1, "v1 again")
            _commit(repo, "f.txt", V3, "v3")
            mf = _manifest(Path(td) / "MANIFEST.json", {"f.txt": _sha(V1)})
            res = validate_pinned_manifest(mf, root=repo)
            _req(not res["passed"] and res["errors"] == ["PINNED_FILE_SHA256_MISMATCH:f.txt"], f"stale pin must still fail: {res}")
            _req(len(res["mismatches"]) == 1, f"one mismatch expected: {res['mismatches']}")
            mm = res["mismatches"][0]
            _req(mm["status"] == "STALE" and mm["stale_commit"] == c3 and mm["history"] == "complete", f"{mm}")
            _req(mm["expected_sha256"] == _sha(V1) and mm["actual_sha256"] == _sha(V3), f"{mm}")

            res_unknown = validate_pinned_manifest(_manifest(Path(td) / "M2.json", {"f.txt": "0" * 64}), root=repo)
            mm2 = res_unknown["mismatches"][0]
            _req(mm2["status"] == "UNKNOWN" and mm2["stale_commit"] is None and mm2["history"] == "complete", f"{mm2}")

            res_ok = validate_pinned_manifest(_manifest(Path(td) / "M3.json", {"f.txt": _sha(V3)}), root=repo)
            _req(res_ok["passed"] and res_ok["mismatches"] == [] and res_ok["files_verified"] == 1, f"{res_ok}")

    def test_02_subdirectory_root_and_entries_format(self) -> None:
        with tempfile.TemporaryDirectory(prefix="aletheia_t_pin_") as td:
            repo = Path(td) / "repo"
            repo.mkdir()
            _git(repo, "init", "-q")
            c1 = _commit(repo, "sub/dir/g.py", V1, "v1")
            _commit(repo, "sub/dir/g.py", V2, "v2")
            sub = repo / "sub"
            mf = sub / "CORE_MANIFEST.json"
            mf.write_bytes((json.dumps({"entries": [{"path": "dir/g.py", "sha256": "sha256:" + _sha(V1)}]}) + "\n").encode("utf-8"))
            res = validate_pinned_manifest(mf)
            _req(res["errors"] == ["PINNED_FILE_SHA256_MISMATCH:dir/g.py"], f"{res}")
            mm = res["mismatches"][0]
            _req(mm["path"] == "dir/g.py" and mm["status"] == "STALE" and mm["stale_commit"] == c1, f"{mm}")

    def test_03_uncommitted_edit_is_stale_against_head(self) -> None:
        with tempfile.TemporaryDirectory(prefix="aletheia_t_pin_") as td:
            repo = Path(td) / "repo"
            repo.mkdir()
            _git(repo, "init", "-q")
            c1 = _commit(repo, "f.txt", V1, "v1")
            (repo / "f.txt").write_bytes(V2)
            res = validate_pinned_manifest(_manifest(Path(td) / "M.json", {"f.txt": _sha(V1)}), root=repo)
            mm = res["mismatches"][0]
            _req(mm["status"] == "STALE" and mm["stale_commit"] == c1, f"{mm}")

    def test_04_no_history_is_unavailable(self) -> None:
        with tempfile.TemporaryDirectory(prefix="aletheia_t_pin_") as td:
            plain = Path(td) / "plain"
            plain.mkdir()
            (plain / "f.txt").write_bytes(V2)
            # The ceiling stops git from finding a repository above the temporary directory (TMPDIR may lie
            # inside a work tree), so this case does not depend on where the tests run.
            with mock.patch.dict(os.environ, {"GIT_CEILING_DIRECTORIES": str(Path(td).resolve())}):
                res = validate_pinned_manifest(_manifest(Path(td) / "M.json", {"f.txt": _sha(V1)}), root=plain)
            mm = res["mismatches"][0]
            _req(mm["status"] == "UNKNOWN" and mm["history"] == "unavailable", f"non-git root: {mm}")

            unborn = Path(td) / "unborn"
            unborn.mkdir()
            _git(unborn, "init", "-q")
            (unborn / "f.txt").write_bytes(V2)
            res_u = validate_pinned_manifest(_manifest(Path(td) / "M2.json", {"f.txt": _sha(V1)}), root=unborn)
            mm_u = res_u["mismatches"][0]
            _req(mm_u["status"] == "UNKNOWN" and mm_u["history"] == "unavailable", f"repo with no commits: {mm_u}")

    def test_05_shallow_clone_history_is_partial(self) -> None:
        with tempfile.TemporaryDirectory(prefix="aletheia_t_pin_") as td:
            src = Path(td) / "src"
            src.mkdir()
            _git(src, "init", "-q")
            _commit(src, "f.txt", V1, "v1")
            c2 = _commit(src, "f.txt", V2, "v2")
            clone = Path(td) / "clone"
            subprocess.run(
                ["git", "clone", "-q", "--depth", "1", src.resolve().as_uri(), str(clone)],
                capture_output=True, text=True, check=True,
            )
            (clone / "f.txt").write_bytes(V3)
            # V1 lies beyond the shallow boundary: UNKNOWN, and the history is marked partial.
            res = validate_pinned_manifest(_manifest(Path(td) / "M.json", {"f.txt": _sha(V1)}), root=clone)
            mm = res["mismatches"][0]
            _req(mm["status"] == "UNKNOWN" and mm["history"] == "partial", f"shallow miss: {mm}")
            # V2 is inside the shallow history: still a measured STALE match.
            res2 = validate_pinned_manifest(_manifest(Path(td) / "M2.json", {"f.txt": _sha(V2)}), root=clone)
            mm2 = res2["mismatches"][0]
            _req(mm2["status"] == "STALE" and mm2["stale_commit"] == c2 and mm2["history"] == "partial", f"shallow hit: {mm2}")

    def test_06_run_audit_check_summary_counts(self) -> None:
        with tempfile.TemporaryDirectory(prefix="aletheia_t_pin_") as td:
            repo = Path(td) / "repo"
            repo.mkdir()
            _git(repo, "init", "-q")
            _commit(repo, "a.txt", V1, "a1")
            _commit(repo, "a.txt", V2, "a2")
            _commit(repo, "b.txt", V3, "b")
            _commit(repo, "c.txt", V1, "c1")
            _commit(repo, "c.txt", V2, "c2")
            # Two STALE and one UNKNOWN, so swapping the two counts cannot pass.
            mf = _manifest(Path(td) / "M.json", {"a.txt": _sha(V1), "b.txt": "1" * 64, "c.txt": _sha(V1)})
            res = run_audit_check(repo, pinned_manifest=mf)
            s = res["summary"]
            _req(not res["passed"], "mismatched pins must fail audit-check")
            _req((s["pinned_mismatch_stale_count"], s["pinned_mismatch_unknown_count"]) == (2, 1), f"{s}")
            no_mf = run_audit_check(repo)
            _req((no_mf["summary"]["pinned_mismatch_stale_count"], no_mf["summary"]["pinned_mismatch_unknown_count"]) == (0, 0), "defaults")

    def test_07_no_commit_for_the_path_is_untracked(self) -> None:
        with tempfile.TemporaryDirectory(prefix="aletheia_t_pin_") as td:
            # A plain directory inside an unrelated repository: git lists no commit for the path, so no
            # history of these bytes was searched and the result must not claim `complete`.
            outer = Path(td) / "outer"
            outer.mkdir()
            _git(outer, "init", "-q")
            _commit(outer, "other.txt", V1, "unrelated")
            plain = outer / "plain"
            plain.mkdir()
            (plain / "f.txt").write_bytes(V2)
            res = validate_pinned_manifest(_manifest(Path(td) / "M.json", {"f.txt": _sha(V1)}), root=plain)
            mm = res["mismatches"][0]
            _req(mm["status"] == "UNKNOWN" and mm["history"] == "untracked", f"nested plain directory: {mm}")
            # Staged but never committed: still no commit for the path.
            (outer / "staged.txt").write_bytes(V2)
            _git(outer, "add", "staged.txt")
            res_s = validate_pinned_manifest(_manifest(Path(td) / "M2.json", {"staged.txt": _sha(V1)}), root=outer)
            mm_s = res_s["mismatches"][0]
            _req(mm_s["status"] == "UNKNOWN" and mm_s["history"] == "untracked", f"staged only: {mm_s}")

    def test_08_unreadable_blob_makes_history_partial(self) -> None:
        with tempfile.TemporaryDirectory(prefix="aletheia_t_pin_") as td:
            repo = Path(td) / "repo"
            repo.mkdir()
            _git(repo, "init", "-q")
            c1 = _commit(repo, "f.txt", V1, "v1")
            c2 = _commit(repo, "f.txt", V2, "v2")
            c3 = _commit(repo, "f.txt", V3, "v3")
            (repo / "f.txt").write_bytes(V1 + V2)
            # Remove the v2 blob from the object store (a damaged or incomplete repository).
            oid = _git(repo, "rev-parse", f"{c2}:f.txt")
            (repo / ".git" / "objects" / oid[:2] / oid[2:]).unlink()

            def _mm(pin: str) -> dict:
                return validate_pinned_manifest(_manifest(Path(td) / "M.json", {"f.txt": pin}), root=repo)["mismatches"][0]

            # A miss can no longer show that the pinned bytes never existed: v2 did exist, in c2.
            for pin in (_sha(V2), "0" * 64):
                mm = _mm(pin)
                _req(mm["status"] == "UNKNOWN" and mm["stale_commit"] is None and mm["history"] == "partial", f"miss: {mm}")
            # A match behind the unreadable newer blob is still measured, but reported as partial.
            mm_behind = _mm(_sha(V1))
            _req(mm_behind["status"] == "STALE" and mm_behind["stale_commit"] == c1 and mm_behind["history"] == "partial", f"{mm_behind}")
            # A match before any unreadable blob is complete.
            mm_first = _mm(_sha(V3))
            _req(mm_first["status"] == "STALE" and mm_first["stale_commit"] == c3 and mm_first["history"] == "complete", f"{mm_first}")

    def test_09_blobless_partial_clone_is_partial_and_never_fetches(self) -> None:
        with tempfile.TemporaryDirectory(prefix="aletheia_t_pin_") as td:
            src = Path(td) / "src"
            src.mkdir()
            _git(src, "init", "-q")
            _commit(src, "f.txt", V1, "v1")
            c2 = _commit(src, "f.txt", V2, "v2")
            _git(src, "config", "uploadpack.allowFilter", "true")
            clone = Path(td) / "clone"
            subprocess.run(
                ["git", "clone", "-q", "--filter=blob:none", src.resolve().as_uri(), str(clone)],
                capture_output=True, text=True, check=True,
            )
            if subprocess.run(["git", "-C", str(clone), "config", "remote.origin.promisor"], capture_output=True).returncode != 0:
                self.skipTest("this git did not make a partial clone")
            (clone / "f.txt").write_bytes(V3)

            def _objects() -> list[str]:
                return sorted(str(q.relative_to(clone)) for q in (clone / ".git" / "objects").rglob("*") if q.is_file())

            before = _objects()
            mf = _manifest(Path(td) / "M.json", {"f.txt": _sha(V1)})
            res = validate_pinned_manifest(mf, root=clone)
            mm = res["mismatches"][0]
            _req(mm["status"] == "UNKNOWN" and mm["history"] == "partial", f"blobless clone, remote reachable: {mm}")
            _req(_objects() == before, "audit-check must not fetch missing objects from the promisor remote")
            res_hit = validate_pinned_manifest(_manifest(Path(td) / "M2.json", {"f.txt": _sha(V2)}), root=clone)
            mm_hit = res_hit["mismatches"][0]
            _req(mm_hit["status"] == "STALE" and mm_hit["stale_commit"] == c2 and mm_hit["history"] == "partial", f"{mm_hit}")
            shutil.rmtree(src)
            res_gone = validate_pinned_manifest(mf, root=clone)
            mm_gone = res_gone["mismatches"][0]
            _req(mm_gone["status"] == "UNKNOWN" and mm_gone["history"] == "partial", f"blobless clone, remote gone: {mm_gone}")

    def test_10_absent_or_non_file_revisions_are_not_unreadable(self) -> None:
        with tempfile.TemporaryDirectory(prefix="aletheia_t_pin_") as td:
            repo = Path(td) / "repo"
            repo.mkdir()
            _git(repo, "init", "-q")
            c1 = _commit(repo, "f.txt", V1, "v1")
            _git(repo, "rm", "-q", "f.txt")
            _git(repo, "commit", "-q", "-m", "delete")
            _commit(repo, "f.txt/inner.txt", V2, "f.txt as a directory")
            _git(repo, "rm", "-q", "-r", "f.txt")
            _git(repo, "commit", "-q", "-m", "delete the directory")
            _commit(repo, "f.txt", V3, "v3")
            (repo / "f.txt").write_bytes(V1 + V3)
            res = validate_pinned_manifest(_manifest(Path(td) / "M.json", {"f.txt": _sha(V1)}), root=repo)
            mm = res["mismatches"][0]
            _req(mm["status"] == "STALE" and mm["stale_commit"] == c1 and mm["history"] == "complete", f"{mm}")
            res_miss = validate_pinned_manifest(_manifest(Path(td) / "M2.json", {"f.txt": _sha(V2)}), root=repo)
            mm_miss = res_miss["mismatches"][0]
            _req(mm_miss["status"] == "UNKNOWN" and mm_miss["history"] == "complete", f"{mm_miss}")

    def test_11_no_git_binary_is_unavailable(self) -> None:
        with tempfile.TemporaryDirectory(prefix="aletheia_t_pin_") as td:
            repo = Path(td) / "repo"
            repo.mkdir()
            _git(repo, "init", "-q")
            _commit(repo, "f.txt", V1, "v1")
            _commit(repo, "f.txt", V2, "v2")
            empty_bin = Path(td) / "empty_bin"
            empty_bin.mkdir()
            with mock.patch.dict(os.environ, {"PATH": str(empty_bin)}):
                res = validate_pinned_manifest(_manifest(Path(td) / "M.json", {"f.txt": _sha(V1)}), root=repo)
            mm = res["mismatches"][0]
            _req(mm["status"] == "UNKNOWN" and mm["history"] == "unavailable", f"no git on PATH: {mm}")

    def test_12_target_outside_work_tree_and_inherited_git_env(self) -> None:
        with tempfile.TemporaryDirectory(prefix="aletheia_t_pin_") as td:
            repo = Path(td) / "repo"
            repo.mkdir()
            _git(repo, "init", "-q")
            c1 = _commit(repo, "f.txt", V1, "v1")
            _commit(repo, "f.txt", V2, "v2")
            outside = Path(td) / "outside.txt"
            outside.write_bytes(V1)
            got = _git_revision_with_sha256(repo.resolve(), outside.resolve(), _sha(V1))
            _req(got == (None, "unavailable"), f"target outside the work tree: {got}")
            # GIT_DIR / GIT_WORK_TREE inherited from a caller (e.g. a git hook) must not redirect the search.
            other = Path(td) / "other"
            other.mkdir()
            _git(other, "init", "-q")
            _commit(other, "f.txt", V3, "other")
            hook_env = {"GIT_DIR": str(other / ".git"), "GIT_WORK_TREE": str(other), "GIT_INDEX_FILE": str(other / ".git" / "index")}
            with mock.patch.dict(os.environ, hook_env):
                got_env = _git_revision_with_sha256(repo.resolve(), (repo / "f.txt").resolve(), _sha(V1))
            _req(got_env == (c1, "complete"), f"inherited git environment redirected the search: {got_env}")

    def test_13_pinned_path_is_literal_not_a_pathspec(self) -> None:
        with tempfile.TemporaryDirectory(prefix="aletheia_t_pin_") as td:
            repo = Path(td) / "repo"
            repo.mkdir()
            _git(repo, "init", "-q")
            name = ":(top)f.txt"  # read as pathspec magic, this would mean `f.txt`
            try:
                (repo / name).write_bytes(V1)
            except OSError:
                self.skipTest("this file system refuses the file name")
            _git(repo, "--literal-pathspecs", "add", "--", name)
            _git(repo, "commit", "-q", "-m", "v1")
            c1 = _git(repo, "rev-parse", "HEAD")
            (repo / name).write_bytes(V2)
            res = validate_pinned_manifest(_manifest(Path(td) / "M.json", {name: _sha(V1)}), root=repo)
            mm = res["mismatches"][0]
            _req(mm["status"] == "STALE" and mm["stale_commit"] == c1 and mm["history"] == "complete", f"{mm}")


if __name__ == "__main__":
    unittest.main()
