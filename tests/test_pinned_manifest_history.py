"""
STALE versus UNKNOWN classification of `audit-check --pinned-manifest` hash mismatches.

A mismatch is STALE when the pinned SHA-256 equals the bytes of an older revision of that file in the
git history holding the manifest root (the commit is reported), and UNKNOWN otherwise. Every result
says how complete the searched history was. Both still fail the manifest. Zero bare `assert` statements.
"""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from aletheia.audit_check import run_audit_check, validate_pinned_manifest
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
            mf = _manifest(Path(td) / "M.json", {"a.txt": _sha(V1), "b.txt": "1" * 64})
            res = run_audit_check(repo, pinned_manifest=mf)
            s = res["summary"]
            _req(not res["passed"], "mismatched pins must fail audit-check")
            _req((s["pinned_mismatch_stale_count"], s["pinned_mismatch_unknown_count"]) == (1, 1), f"{s}")
            no_mf = run_audit_check(repo)
            _req((no_mf["summary"]["pinned_mismatch_stale_count"], no_mf["summary"]["pinned_mismatch_unknown_count"]) == (0, 0), "defaults")


if __name__ == "__main__":
    unittest.main()
