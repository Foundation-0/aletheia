#!/usr/bin/env python3
"""
R1-R5 Regression & Security Suite for `aletheia.flow_audit`
(Continual Rotational-Transform Gate CS-01, Hardening Treadmill CS-22,
and Swarm-Flow Resonance Amnesia CS-23).

Pure Python 3 stdlib, zero bare asserts, zero AST floats, zero credential-named vars.
"""
from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any, Callable
import unittest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from aletheia import flow_audit as fa
from aletheia.strict_io import AletheiaError

_AID = "AU" + "DIT-"


def _req(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def _expect_err(fn: Callable[[], Any], code: str, label: str) -> None:
    try:
        fn()
    except AletheiaError as exc:
        _req(exc.code == code, f"{label}: expected {code}, got {exc.code} ({exc})")
        return
    raise AssertionError(f"{label}: expected AletheiaError({code}), but succeeded")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    body = "\n".join(json.dumps(r, sort_keys=True, separators=(",", ":")) for r in rows) + "\n"
    path.write_text(body, encoding="utf-8")


class _PathSub(type(Path())):
    pass


class TestContinualToroidFlowR5(unittest.TestCase):
    def test_01_asymptotic_blind_spot_witness_1677_and_healthy_control(self) -> None:
        """Exact 1,677-message blind-spot regression witness vs. healthy continual toroid."""
        with tempfile.TemporaryDirectory(prefix="aletheia_flow_t1_") as td:
            root = Path(td)
            (root / "cartography").mkdir()
            (root / "verification").mkdir()
            portals = root / "cartography" / "frontier_portals.md"
            portals.write_text(
                "# Frontier Portals\n## Portal 1\nTrack S1 uses Schur complement.\n",
                encoding="utf-8",
            )
            audit_log = root / "verification" / "AUDIT_LOG.md"
            audit_log.write_text(
                f"| **{_AID}001** | 2026-11-20 | v | Track S1 | G1 | exact | N1 | VERIFIED | org/repo#1 |\n"
                f"| **{_AID}101R2** | 2026-11-21 | v | Track S41 | G1 | exact | N1 | VERIFIED | local only |\n"
                f"| **{_AID}102R3** | 2026-11-22 | v | Track S42 | G1 | exact | N1 | VERIFIED | local only |\n"
                f"### `{_AID}103R4` — Track S43\n- Verdict: `VERIFIED`\n- Notes: local only\n"
                f"### `{_AID}104` — Track S44\n- Verdict: `PARTIAL/FRAGILE` (not VERIFIED yet)\n",
                encoding="utf-8",
            )

            # Synthetic 1,677-message board: cartographer stops at 1298, weaver stops at 1523.
            rows: list[dict[str, Any]] = []
            for seq in range(1, 1678):
                if seq == 1298:
                    rows.append({"seq": seq, "agent": "session-cartographer", "text": "folded Portal 1", "time": "2026-11-22 23:45:12"})
                elif seq == 1523:
                    rows.append({"seq": seq, "agent": "peer-weaver", "text": "wove Track S1 seam", "time": "2026-11-23 15:26:58"})
                elif seq == 1675:
                    rows.append({"seq": seq, "agent": "verifier", "text": "Track S47 R2 Burnside obstruction S47-VER-01", "time": "2026-11-23 22:19:00"})
                elif seq == 1676:
                    rows.append({"seq": seq, "agent": "verifier", "text": "Track S46 R3 CS-20 Landauer anomaly", "time": "2026-11-23 22:20:00"})
                elif seq == 1677:
                    rows.append({"seq": seq, "agent": "coordinator", "text": "Track S45 R4 CS-21 Hodge dispatch", "time": "2026-11-23 22:21:44"})
                else:
                    rows.append({"seq": seq, "agent": "worker", "text": "routine check"})
            board = root / "board.jsonl"
            _write_jsonl(board, rows)

            # Legacy lifetime guard algebraically misses this (1298 * 20 >= 1677 * 7).
            _req(1298 * 20 >= 1677 * 7, "legacy lifetime inequality check")

            rep = fa.diagnose_continual_flow(root, board_path=board, max_silence_seconds=3600)
            _req(rep["schema"] == fa.FLOW_AUDIT_SCHEMA, "schema mismatch")
            _req(rep["overall_status"] == "RELAPSE_DETECTED", f"expected RELAPSE_DETECTED: {rep}")
            _req(rep["alert_count"] == 3 and rep["warning_count"] == 0, f"counts: {rep}")
            m = rep["metrics"]
            _req(m["board_message_count"] == 1677 and m["max_seq"] == 1677, "board count")
            _req(m["window_len"] == 50 and m["poloidal_in_window"] == 0, "window poloidal")
            _req(m["iota_window_q"] == "0" and m["iota_window_ok"] is False, f"iota_q: {m}")
            _req(m["last_cartographer_seq"] == 1298 and m["cartographer_gap"] == 379, "cart gap")
            _req(m["legacy_lifetime_blind_spot"] is True, "must flag legacy blind spot")
            _req(m["last_weaver_seq"] == 1523 and m["weaver_gap"] == 154, "weaver gap")
            _req(m["cartographer_silence_seconds"] == 81392, f"silence_s: {m['cartographer_silence_seconds']}")
            _req(m["unfolded_window"] == [1299, 1677] and m["unfolded_message_count"] == 379, f"unfolded: {m}")
            _req(m["stranded_verified_tracks"] == ["S41", "S42", "S43"], f"stranded: {m['stranded_verified_tracks']}")
            _req(len(m["missed_signals_sha256"]) == 64, "digest len")
            sig_pairs = {(s["category"], s["signal"]) for s in m["missed_signals"]}
            _req(("obstruction_or_anomaly", "S47-VER-01") in sig_pairs, f"missing S47-VER-01: {sig_pairs}")
            _req(("obstruction_or_anomaly", "obstruction") in sig_pairs, f"missing obstruction: {sig_pairs}")
            _req(("exact_operator", "Burnside") in sig_pairs and ("frozen_track", "S47") in sig_pairs, f"missing sigs: {sig_pairs}")
            by_id = {p["id"]: p for p in rep["patterns"]}
            _req(by_id["CS-01"]["status"] == "ALERT" and by_id["CS-01"]["risk_score"] == 100, f"CS-01: {by_id['CS-01']}")
            _req(by_id["CS-22"]["status"] == "ALERT" and by_id["CS-22"]["risk_score"] == 80, f"CS-22: {by_id['CS-22']}")
            _req(by_id["CS-23"]["status"] == "ALERT" and by_id["CS-23"]["risk_score"] == 80, f"CS-23: {by_id['CS-23']}")
            _req(rep["health_score_q"] == "40/3", f"health_score_q: {rep['health_score_q']}")
            # Drop-in helper returns identical pattern list with diagnose schema keys.
            pats = fa.check_continual_flow_patterns(root, board_path=board, max_silence_seconds=3600)
            _req(pats == rep["patterns"], "check_continual_flow_patterns mismatch")
            for pat in pats:
                _req(set(pat.keys()) == {"id", "name", "risk_score", "status", "evidence", "remediation"}, "pattern schema")

            # Positive control: healthy continual toroid board with synced atlas -> CLEAR (risk=0) on all 3.
            hroot = root / "healthy"
            (hroot / "verification").mkdir(parents=True)
            (hroot / "frontier_portals.md").write_text(
                "# Portals\n## Portal 1\nTrack S1 verified with Schur.\n", encoding="utf-8"
            )
            atlas = hroot / "atlas.md"
            atlas.write_text("# Atlas\nTrack S2 cross-linked with Hodge.\n", encoding="utf-8")
            (hroot / "verification" / "AUDIT_LOG.md").write_text(
                f"| **{_AID}001** | 2026-11-23 | v | Track S1 | G1 | exact | N1 | VERIFIED | org/repo#1 |\n"
                f"| **{_AID}002** | 2026-11-23 | v | Track S2 | G1 | exact | N1 | VERIFIED | atlas |\n",
                encoding="utf-8",
            )
            hrows = [
                {"seq": i, "agent": "worker", "text": "Track S1 Schur ok", "time": f"2026-11-23T10:00:{i:02d}Z"}
                for i in range(1, 24)
            ] + [
                {"seq": 24, "agent": "peer-weaver", "text": "Track S2 Hodge woven", "time": "2026-11-23T10:00:24+00:00"},
                {"seq": 25, "agent": "session-cartographer", "text": "folded S1 S2", "time": "2026-11-23T10:00:25Z"},
            ]
            hboard = hroot / "board.jsonl"
            _write_jsonl(hboard, hrows)
            hrep = fa.diagnose_continual_flow(
                hroot,
                board_path=hboard,
                window=25,
                max_cartographer_gap=0,
                max_weaver_gap=1,
                min_poloidal_num=2,
                min_poloidal_den=25,
                max_silence_seconds=1,
            )
            _req(hrep["overall_status"] == "HEALTHY" and hrep["health_score_q"] == "100", f"healthy: {hrep}")
            _req(hrep["alert_count"] == 0 and hrep["warning_count"] == 0, "healthy counts")
            _req(hrep["metrics"]["iota_window_q"] == "2/25" and hrep["metrics"]["iota_window_ok"] is True, "healthy iota")
            _req(hrep["metrics"]["unfolded_window"] == [25, 25] and hrep["metrics"]["unfolded_message_count"] == 0, "healthy unfold")
            for pat in hrep["patterns"]:
                _req(pat["status"] == "CLEAR" and pat["risk_score"] == 0, f"expected CLEAR: {pat}")

    def test_02_exact_thresholds_boundaries_and_branches(self) -> None:
        """Exercise every boundary operator (`<`/`<=`/`>`/`>=`/`==`/`!=`) and pattern branch."""
        _req(fa._fmt_q(fa.Fraction(2, 1)) == "2" and fa._fmt_q(fa.Fraction(1, 25)) == "1/25", "_fmt_q")
        _req(fa._status_from_risk(50) == "ALERT" and fa._status_from_risk(49) == "WARNING", "status 50/49")
        _req(fa._status_from_risk(20) == "WARNING" and fa._status_from_risk(19) == "CLEAR", "status 20/19")
        _req(fa._parse_iso_epoch_seconds("") is None and fa._parse_iso_epoch_seconds("not-a-date") is None, "bad ts")
        _req(fa._parse_iso_epoch_seconds("1970-01-01 00:00:00") == 0, "epoch naive")
        _req(fa._parse_iso_epoch_seconds("1970-01-01T00:01:00Z") == 60, "epoch Z")
        _req(fa._parse_iso_epoch_seconds("1970-01-01T01:01:00+01:00") == 60, "epoch tz")
        # Extreme ISO-8601 boundary timestamps must never raise OverflowError (year 0001 / 9999)
        t_hi = fa._parse_iso_epoch_seconds("9999-12-31T23:59:59-05:00")
        t_lo = fa._parse_iso_epoch_seconds("0001-01-01T00:00:00+05:00")
        _req(type(t_hi) is int and t_hi > 0, f"extreme max ts: {t_hi}")
        _req(type(t_lo) is int and t_lo < 0, f"extreme min ts: {t_lo}")

        with tempfile.TemporaryDirectory(prefix="aletheia_flow_t2_") as td:
            root = Path(td)
            # 1. Missing portals + no board -> CS-01 ALERT (risk=50), CS-22/23 CLEAR
            rep_empty = fa.diagnose_continual_flow(root)
            _req(rep_empty["patterns"][0]["risk_score"] == 50 and rep_empty["overall_status"] == "RELAPSE_DETECTED", "no portals")

            # 2. Board with 0 cartographer & 0 weaver posts, length <= max_weaver_gap vs > max_weaver_gap
            (root / "frontier_portals.md").write_text("# Portals\n", encoding="utf-8")
            b0 = root / "b0.jsonl"
            _write_jsonl(b0, [{"seq": 1, "agent": "worker", "text": "hello", "time": None}])
            rep_nc_short = fa.diagnose_continual_flow(root, board_path=b0, max_cartographer_gap=5, max_weaver_gap=1)
            _req(rep_nc_short["patterns"][0]["risk_score"] == 90, f"0 cart short: {rep_nc_short['patterns'][0]}")
            rep_nc_long = fa.diagnose_continual_flow(root, board_path=b0, max_cartographer_gap=5, max_weaver_gap=0, max_silence_seconds=10)
            _req(rep_nc_long["patterns"][0]["risk_score"] == 100, f"0 cart+weaver: {rep_nc_long['patterns'][0]}")
            _req(any("weaver/synthesizer" in e for e in rep_nc_long["patterns"][0]["evidence"]), "0 weaver evidence")
            _req(rep_nc_long["metrics"]["cartographer_silence_seconds"] is None, "0 cart silence must be None")

            # 3. Exact boundary tests: cart_gap == max_cartographer_gap, weaver_gap == max_weaver_gap,
            #    silence == max_silence_seconds, iota == 1/1, legacy_blind_spot at max_seq==8 vs 7 & exact 7/20
            b_all_pol = root / "b_all_pol.jsonl"
            _write_jsonl(
                b_all_pol,
                [
                    {"seq": 1, "agent": "peer-weaver", "text": "w"},
                    {"seq": 2, "agent": "session-cartographer", "text": "c"},
                ],
            )
            rep_full_pol = fa.diagnose_continual_flow(root, board_path=b_all_pol, min_poloidal_num=1, min_poloidal_den=1)
            _req(rep_full_pol["overall_status"] == "HEALTHY" and rep_full_pol["metrics"]["iota_window_q"] == "1", "1/1 floor failed")

            b_exact = root / "b_exact.jsonl"
            _write_jsonl(
                b_exact,
                [
                    {"seq": 1, "agent": "session-cartographer", "text": "fold", "time": "2026-11-23 10:00:00"},
                    {"seq": 2, "agent": "peer-weaver", "text": "weave", "time": "2026-11-23 10:00:10"},
                    {"seq": 3, "agent": "worker", "text": "ok", "time": "2026-11-23 10:00:20"},
                ],
            )
            rep_eq = fa.diagnose_continual_flow(
                root,
                board_path=b_exact,
                window=2,
                max_cartographer_gap=2,
                max_weaver_gap=1,
                min_poloidal_num=1,
                min_poloidal_den=2,
                max_silence_seconds=20,
            )
            _req(rep_eq["overall_status"] == "HEALTHY", f"exact eq should be HEALTHY: {rep_eq}")
            rep_over_s = fa.diagnose_continual_flow(
                root,
                board_path=b_exact,
                window=2,
                max_cartographer_gap=2,
                max_weaver_gap=1,
                min_poloidal_num=1,
                min_poloidal_den=2,
                max_silence_seconds=19,
            )
            _req(rep_over_s["patterns"][0]["risk_score"] == 35 and rep_over_s["overall_status"] == "WATCH", f"silence>19: {rep_over_s}")
            # Asymmetric unparseable timestamps (t_max valid + t_cart bad, and t_max bad + t_cart valid)
            for tag_ts, t1_v, t2_v in (("both_bad", "bad", "bad"), ("max_only", "bad", "2026-11-23 10:00:10"), ("cart_only", "2026-11-23 10:00:00", "bad")):
                b_badts = root / f"b_ts_{tag_ts}.jsonl"
                _write_jsonl(
                    b_badts,
                    [
                        {"seq": 1, "agent": "session-cartographer", "text": "fold", "time": t1_v},
                        {"seq": 2, "agent": "peer-weaver", "text": "weave", "time": t2_v},
                    ],
                )
                rep_bts = fa.diagnose_continual_flow(root, board_path=b_badts, max_silence_seconds=1)
                _req(rep_bts["metrics"]["cartographer_silence_seconds"] is None, f"{tag_ts} silence None")

            # Legacy blind-spot boundary: max_seq==7 (False), max_seq==8 last==3 (True), last==2 (False), exact 20*7==140==7*20 (True)
            for mseq, cseq, exp_bs in ((7, 3, False), (8, 3, True), (8, 2, False), (20, 7, True)):
                b_bs = root / f"bs_{mseq}_{cseq}.jsonl"
                _write_jsonl(
                    b_bs,
                    [
                        {"seq": cseq, "agent": "cartographer", "text": "fold"},
                        {"seq": mseq, "agent": "worker", "text": "w"},
                    ],
                )
                r_bs = fa.diagnose_continual_flow(root, board_path=b_bs, max_cartographer_gap=1)
                _req(r_bs["metrics"]["legacy_lifetime_blind_spot"] is exp_bs, f"bs({mseq},{cseq})={r_bs['metrics']['legacy_lifetime_blind_spot']}")

            # 4. CS-22 boundaries:
            #    - exactly 1 stranded track -> +20 (kills >=1 -> >1)
            #    - pressure==6 with synth==2 (6 >= 4 AND 6 == 3*2) -> 0 treadmill risk (kills DEL_1 & > -> >=)
            #    - pressure==4 with synth==1 (4 > 3*1) -> +25; pressure==2/3 with synth==0 -> 0 vs +40
            (root / "verification").mkdir()
            (root / "verification" / "AUDIT_LOG.md").write_text(
                f"| **{_AID}010R2** | 2026-11-23 | v | Track S81 | G1 | exact | N1 | VERIFIED | local |\n",
                encoding="utf-8",
            )
            b22 = root / "b22.jsonl"
            _write_jsonl(
                b22,
                [
                    {"seq": 1, "agent": "session-cartographer", "text": "fold"},
                    {"seq": 2, "agent": "peer-weaver", "text": "weave"},
                    {"seq": 3, "agent": "worker", "text": "R3 check"},
                    {"seq": 4, "agent": "worker", "text": "R4 check"},
                    {"seq": 5, "agent": "worker", "text": "R5 check"},
                    {"seq": 6, "agent": "worker", "text": "R6 check"},
                    {"seq": 7, "agent": "worker", "text": "R7 check"},
                ],
            )
            # rehardening=1 + tail_hardening=5 = 6, synth=2 (6 == 3*2 -> 0 treadmill), 1 stranded (+20)
            r22_eq3x = fa.diagnose_continual_flow(root, board_path=b22, window=7, max_cartographer_gap=10, max_weaver_gap=10)
            _req(r22_eq3x["patterns"][1]["risk_score"] == 20, f"r22_eq3x: {r22_eq3x['patterns'][1]}")
            (root / "verification" / "AUDIT_LOG.md").write_text(
                f"| **{_AID}010R2** | 2026-11-23 | v | Track S81 | G1 | exact | N1 | VERIFIED | local |\n"
                f"| **{_AID}011R2** | 2026-11-23 | v | Track S82 | G1 | exact | N1 | VERIFIED | local |\n",
                encoding="utf-8",
            )
            _write_jsonl(
                b22,
                [
                    {"seq": 1, "agent": "session-cartographer", "text": "fold"},
                    {"seq": 2, "agent": "worker", "text": "R3 re-audit"},
                    {"seq": 3, "agent": "worker", "text": "R4 re-hardening"},
                ],
            )
            r22_b = fa.diagnose_continual_flow(root, board_path=b22, window=3, max_cartographer_gap=5, max_weaver_gap=5)
            _req(r22_b["patterns"][1]["risk_score"] == 45, f"r22_b: {r22_b['patterns'][1]}")
            # Pressure==2 with synth==0 (no rehardening in log, only 2 tail posts) -> 0 treadmill risk
            (root / "verification" / "AUDIT_LOG.md").write_text("", encoding="utf-8")
            _write_jsonl(
                b22,
                [
                    {"seq": 1, "agent": "worker", "text": "R2 check"},
                    {"seq": 2, "agent": "worker", "text": "R3 check"},
                ],
            )
            r22_c = fa.diagnose_continual_flow(root, board_path=b22, window=2, max_cartographer_gap=5, max_weaver_gap=5)
            _req(r22_c["patterns"][1]["risk_score"] == 0, f"r22_c: {r22_c['patterns'][1]}")
            # Pressure==3 with synth==0 -> +40
            _write_jsonl(
                b22,
                [
                    {"seq": 1, "agent": "worker", "text": "R2 check"},
                    {"seq": 2, "agent": "worker", "text": "R3 check"},
                    {"seq": 3, "agent": "worker", "text": "R4 check"},
                ],
            )
            r22_d = fa.diagnose_continual_flow(root, board_path=b22, window=3, max_cartographer_gap=5, max_weaver_gap=5)
            _req(r22_d["patterns"][1]["risk_score"] == 40, f"r22_d: {r22_d['patterns'][1]}")

            # Explicit portals_file & atlas_file + default symbiosis atlas path
            exp_portals = root / "custom_portals.md"
            exp_portals.write_text("# Custom\nTrack S90 S99-VER-01 obstruction\n", encoding="utf-8")
            exp_atlas = root / "custom_atlas.md"
            exp_atlas.write_text("# Atlas\nTrack S91 Burnside\n", encoding="utf-8")
            b23 = root / "b23.jsonl"
            # Case A: 1 missed signal (Krein; S99-VER-01 & obstruction ALREADY in portals), unfolded < cap -> 25; == cap -> 50
            _write_jsonl(
                b23,
                [
                    {"seq": 1, "agent": "cartographer", "text": "fold"},
                    {"seq": 2, "agent": "worker", "text": "Track S91 Burnside S99-VER-01 obstruction Krein"},
                ],
            )
            r23_1 = fa.diagnose_continual_flow(root, board_path=b23, portals_file=exp_portals, atlas_file=exp_atlas, max_cartographer_gap=2)
            _req(r23_1["patterns"][2]["risk_score"] == 25 and r23_1["metrics"]["missed_signals_count"] == 1, f"r23_1: {r23_1}")
            r23_2 = fa.diagnose_continual_flow(root, board_path=b23, portals_file=exp_portals, atlas_file=exp_atlas, max_cartographer_gap=1)
            _req(r23_2["patterns"][2]["risk_score"] == 50, f"r23_2: {r23_2}")
            # Case B: 3 missed signals, unfolded < cap -> 55; unfolded == cap -> 80 (kills >= -> >)
            _write_jsonl(
                b23,
                [
                    {"seq": 1, "agent": "cartographer", "text": "fold"},
                    {"seq": 2, "agent": "worker", "text": "Krein Hodge CS-20"},
                    {"seq": 3, "agent": "worker", "text": "Krein again"},
                ],
            )
            r23_3 = fa.diagnose_continual_flow(root, board_path=b23, portals_file=exp_portals, atlas_file=exp_atlas, max_cartographer_gap=5)
            _req(r23_3["patterns"][2]["risk_score"] == 55, f"r23_3: {r23_3}")
            r23_3eq = fa.diagnose_continual_flow(root, board_path=b23, portals_file=exp_portals, atlas_file=exp_atlas, max_cartographer_gap=2)
            _req(r23_3eq["patterns"][2]["risk_score"] == 80, f"r23_3eq: {r23_3eq}")
            krein_rows = [s for s in r23_3["metrics"]["missed_signals"] if s["signal"] == "Krein"]
            _req(len(krein_rows) == 1 and krein_rows[0]["count"] == 2 and krein_rows[0]["first_seq"] == 2, f"krein: {krein_rows}")
            # Case C: 0 missed signals, unfolded == cap -> risk=0; unfolded > cap -> risk=25
            _write_jsonl(
                b23,
                [
                    {"seq": 1, "agent": "cartographer", "text": "fold"},
                    {"seq": 2, "agent": "worker", "text": "routine"},
                    {"seq": 3, "agent": "worker", "text": "routine"},
                ],
            )
            r23_4 = fa.diagnose_continual_flow(root, board_path=b23, portals_file=exp_portals, atlas_file=exp_atlas, max_cartographer_gap=2)
            _req(r23_4["patterns"][2]["risk_score"] == 0, f"r23_4: {r23_4}")
            r23_5 = fa.diagnose_continual_flow(root, board_path=b23, portals_file=exp_portals, atlas_file=exp_atlas, max_cartographer_gap=1)
            _req(r23_5["patterns"][2]["risk_score"] == 25, f"r23_5: {r23_5}")

            # Default symbiosis atlas discovery
            sym_atlas = root / "symbiosis" / "stream" / "LAW1B_CROSS_ORG_SERENDIPITY_ATLAS.md"
            sym_atlas.parent.mkdir(parents=True)
            sym_atlas.write_text("# Atlas\nKrein\n", encoding="utf-8")
            _write_jsonl(b23, [{"seq": 1, "agent": "worker", "text": "Krein"}])
            r_sym = fa.diagnose_continual_flow(root, board_path=b23)
            _req(r_sym["metrics"]["missed_signals_count"] == 0, "default symbiosis atlas not loaded")

    def test_03_zone_b_strict_io_and_param_fail_closed(self) -> None:
        """Fail-closed Zone-B I/O, strict JSONL, symlink/FIFO, int/bool/float, and CWD guards."""
        with tempfile.TemporaryDirectory(prefix="aletheia_flow_t3_") as td:
            root = Path(td)
            good_board = root / "good.jsonl"
            _write_jsonl(good_board, [{"seq": 1, "agent": "cartographer", "text": "ok"}])

            # Exact parameter validation (int vs bool vs float vs out-of-range)
            _expect_err(lambda: fa.diagnose_continual_flow(str(root)), "INVALID_PATH_TYPE", "str dir")  # type: ignore[arg-type]
            _expect_err(lambda: fa.diagnose_continual_flow(_PathSub(root)), "INVALID_PATH_TYPE", "PathSub dir")
            _expect_err(lambda: fa.diagnose_continual_flow(Path("bad\x00path")), "NUL_BYTE_FORBIDDEN", "NUL path")
            _expect_err(lambda: fa.diagnose_continual_flow(Path("bad_\ud800_path")), "INVALID_UTF8_SURROGATE", "surrogate path")
            _expect_err(lambda: fa.diagnose_continual_flow(root / ".." / root.name), "PARENT_TRAVERSAL_FORBIDDEN", "dotdot path")
            _expect_err(lambda: fa.diagnose_continual_flow(root / "missing_dir"), "FILE_NOT_FOUND", "missing dir")
            _expect_err(lambda: fa.diagnose_continual_flow(good_board), "SYMLINK_FORBIDDEN", "file as dir")
            _expect_err(lambda: fa.diagnose_continual_flow(root, window=0), "INVALID_WINDOW", "window=0")
            _expect_err(lambda: fa.diagnose_continual_flow(root, window=True), "INVALID_WINDOW", "window=True")
            _expect_err(lambda: fa.diagnose_continual_flow(root, max_cartographer_gap=-1), "INVALID_GAP", "cart_gap=-1")
            _expect_err(lambda: fa.diagnose_continual_flow(root, max_weaver_gap=-1), "INVALID_GAP", "weaver_gap=-1")
            _expect_err(lambda: fa.diagnose_continual_flow(root, min_poloidal_num=0), "INVALID_POLOIDAL_RATIO", "num=0")
            _expect_err(lambda: fa.diagnose_continual_flow(root, min_poloidal_den=0), "INVALID_POLOIDAL_RATIO", "den=0")
            _expect_err(lambda: fa.diagnose_continual_flow(root, min_poloidal_num=2, min_poloidal_den=1), "INVALID_POLOIDAL_RATIO", "num>den")
            _expect_err(lambda: fa.diagnose_continual_flow(root, max_silence_seconds=0), "INVALID_SILENCE_CAP", "silence=0")
            _expect_err(lambda: fa.diagnose_continual_flow(root, max_silence_seconds=False), "INVALID_SILENCE_CAP", "silence=False")
            # Exact MAX_SEQ_BITS integer parameter ceiling (prevents >4,300-digit ValueError on serialization)
            max_p = (1 << fa.MAX_SEQ_BITS) - 1
            rep_max_p = fa.diagnose_continual_flow(root, board_path=good_board, window=max_p, min_poloidal_den=max_p)
            _req(len(json.dumps(rep_max_p)) > 0, "MAX_SEQ_BITS-1 report serialization failed")
            _expect_err(lambda: fa.diagnose_continual_flow(root, board_path=good_board, window=1 << fa.MAX_SEQ_BITS), "INVALID_WINDOW", "window bit limit")
            _expect_err(lambda: fa.diagnose_continual_flow(root, board_path=good_board, min_poloidal_den=1 << fa.MAX_SEQ_BITS), "INVALID_POLOIDAL_RATIO", "den bit limit")
            _expect_err(lambda: fa.diagnose_continual_flow(root, board_path=good_board, window=1 << 15_000), "INVALID_WINDOW", "window 15000 bits")
            _expect_err(lambda: fa.diagnose_continual_flow(root, board_path=good_board, min_poloidal_den=1 << 15_000), "INVALID_POLOIDAL_RATIO", "den 15000 bits")

            # Symlink directory, symlink leaf, FIFO, directory-as-file, missing file, chmod 000, root path
            sym_dir = root / "sym_dir"
            os.symlink(root, sym_dir)
            _expect_err(lambda: fa.diagnose_continual_flow(sym_dir), "SYMLINK_FORBIDDEN", "symlink dir")
            _expect_err(lambda: fa.load_board_jsonl_safe(sym_dir / "good.jsonl"), "SYMLINK_FORBIDDEN", "symlink ancestor")
            sym_file = root / "sym.jsonl"
            os.symlink(good_board, sym_file)
            _expect_err(lambda: fa.load_board_jsonl_safe(sym_file), "SYMLINK_FORBIDDEN", "symlink board")
            _expect_err(lambda: fa.diagnose_continual_flow(root, portals_file=sym_file), "SYMLINK_FORBIDDEN", "symlink portals")
            _expect_err(lambda: fa.load_board_jsonl_safe(root / "missing.jsonl"), "FILE_NOT_FOUND", "missing board")
            _expect_err(lambda: fa.load_board_jsonl_safe(Path("/nonexistent_flow_audit_probe")), "FILE_NOT_FOUND", "top-level missing")
            _expect_err(lambda: fa.load_board_jsonl_safe(root), "NOT_A_REGULAR_FILE", "dir as board")
            _expect_err(lambda: fa.load_board_jsonl_safe(Path("/")), "NOT_A_REGULAR_FILE", "root as board")
            if hasattr(os, "mkfifo"):
                fifo = root / "pipe.jsonl"
                os.mkfifo(fifo)
                _expect_err(lambda: fa.load_board_jsonl_safe(fifo), "NOT_A_REGULAR_FILE", "FIFO board")
            if os.geteuid() != 0:
                noperm = root / "noperm.jsonl"
                noperm.write_bytes(b"{}\n")
                os.chmod(noperm, 0o000)
                try:
                    _expect_err(lambda: fa.load_board_jsonl_safe(noperm), "FILE_READ_ERROR", "chmod 000 board")
                finally:
                    os.chmod(noperm, 0o600)
            # Symlink optional file under expedition_dir must still fail closed (not treated as missing)
            (root / "atlas.md").symlink_to(good_board)
            _expect_err(lambda: fa.diagnose_continual_flow(root), "SYMLINK_FORBIDDEN", "symlink optional atlas")
            (root / "atlas.md").unlink()

            # Streaming size cap exact boundary (exact == max_bytes PASS vs +1 FAIL) & invalid max_bytes
            raw_len = len(good_board.read_bytes())
            _req(len(fa.load_board_jsonl_safe(good_board, max_bytes=raw_len)) == 1, "exact max_bytes failed")
            _expect_err(lambda: fa.load_board_jsonl_safe(good_board, max_bytes=raw_len - 1), "FILE_TOO_LARGE", "max_bytes-1")
            _expect_err(lambda: fa.load_board_jsonl_safe(good_board, max_bytes=0), "INVALID_MAX_BYTES", "max_bytes=0")
            _expect_err(lambda: fa.load_board_jsonl_safe(good_board, max_bytes=fa.MAX_BOARD_BYTES + 1), "INVALID_MAX_BYTES", "max_bytes>cap")
            proc_k = Path("/proc/kallsyms")
            if proc_k.exists():
                _expect_err(lambda: fa.load_board_jsonl_safe(proc_k, max_bytes=16), "FILE_TOO_LARGE", "/proc/kallsyms cap")

            # Strict byte/UTF-8/JSONL/schema negative controls
            empty_f = root / "empty.jsonl"
            empty_f.write_bytes(b"")
            _req(fa.load_board_jsonl_safe(empty_f) == [], "empty JSONL should return []")
            no_nl = root / "no_nl.jsonl"
            no_nl.write_text('{"seq":1,"agent":"a","text":"t"}', encoding="utf-8")
            _req(len(fa.load_board_jsonl_safe(no_nl)) == 1, "no trailing newline valid")

            # Exact 14,000-bit seq boundary: (1<<14000)-1 PASS vs 1<<14000 FAIL vs 10**4300 (>4300 digits) FAIL
            max_ok = root / "max_ok.jsonl"
            max_ok.write_text(f'{{"seq":{(1 << fa.MAX_SEQ_BITS) - 1},"agent":"a","text":"t"}}\n', encoding="utf-8")
            _req(len(fa.load_board_jsonl_safe(max_ok)) == 1, "exact MAX_SEQ_BITS-1 failed")
            max_over = root / "max_over.jsonl"
            max_over.write_text(f'{{"seq":{1 << fa.MAX_SEQ_BITS},"agent":"a","text":"t"}}\n', encoding="utf-8")
            _expect_err(lambda: fa.load_board_jsonl_safe(max_over), "SEQ_BIT_LIMIT", "seq 1<<14000")
            over_4300 = root / "over_4300.jsonl"
            over_4300.write_text('{"seq":1' + ("0" * 4300) + ',"agent":"a","text":"t"}\n', encoding="utf-8")
            _expect_err(lambda: fa.load_board_jsonl_safe(over_4300), "JSON_SYNTAX_ERROR", "seq >4300 digits")

            bad_cases: list[tuple[str, bytes, str]] = [
                ("crlf", b'{"seq":1,"agent":"a","text":"t"}\r\n', "CRLF_LINE_ENDINGS"),
                ("utf8", b"\xff\xfe", "INVALID_UTF8"),
                ("bom", b'\xef\xbb\xbf{"seq":1,"agent":"a","text":"t"}\n', "BOM_FORBIDDEN"),
                ("nul", b'{"seq":1,"agent":"a","text":"x\x00y"}\n', "NUL_BYTE_FORBIDDEN"),
                ("ws_only", b"   \n", "JSONL_WHITESPACE_ONLY"),
                ("blank_int", b'{"seq":1,"agent":"a","text":"t"}\n\n{"seq":2,"agent":"a","text":"t"}\n', "JSONL_BLANK_LINE"),
                ("dup_key", b'{"seq":1,"seq":2,"agent":"a","text":"t"}\n', "JSON_DUPLICATE_KEY"),
                ("float_seq", b'{"seq":1.5,"agent":"a","text":"t"}\n', "JSON_FLOAT_FORBIDDEN"),
                ("nan", b'{"seq":NaN,"agent":"a","text":"t"}\n', "JSON_CONSTANT_FORBIDDEN"),
                ("list_root", b"[1,2,3]\n", "JSON_ROOT_NOT_OBJECT"),
                ("bool_seq", b'{"seq":true,"agent":"a","text":"t"}\n', "INVALID_BOARD_SEQ"),
                ("zero_seq", b'{"seq":0,"agent":"a","text":"t"}\n', "INVALID_BOARD_SEQ"),
                ("neg_seq", b'{"seq":-1,"agent":"a","text":"t"}\n', "INVALID_BOARD_SEQ"),
                ("bad_agent", b'{"seq":1,"agent":99,"text":"t"}\n', "INVALID_BOARD_AGENT"),
                ("bad_text", b'{"seq":1,"agent":"a","text":123}\n', "INVALID_BOARD_TEXT"),
                ("bad_time", b'{"seq":1,"agent":"a","text":"t","time":123}\n', "INVALID_BOARD_TIME"),
            ]
            for name, payload, code in bad_cases:
                fp = root / f"bad_{name}.jsonl"
                fp.write_bytes(payload)
                _expect_err(lambda p=fp: fa.load_board_jsonl_safe(p), code, f"bad_{name}")

            # Relative path, logical $PWD symlink ancestor check, and deleted CWD handling
            old_cwd = os.getcwd()
            old_pwd = os.environ.get("PWD")
            rel_dir = root / "rel_ws"
            rel_dir.mkdir()
            (rel_dir / "frontier_portals.md").write_text("# P\n", encoding="utf-8")
            other_dir = root / "other_ws"
            other_dir.mkdir()
            sym_rel = root / "sym_rel_ws"
            os.symlink(rel_dir, sym_rel)
            (rel_dir / "sub").mkdir()
            os.symlink(rel_dir, rel_dir / "sub" / "rel_sym")
            os.chdir(rel_dir)
            try:
                os.environ.pop("PWD", None)
                _req(fa.diagnose_continual_flow(Path("."))["overall_status"] == "HEALTHY", "relative Path('.') no PWD failed")
                os.environ["PWD"] = "sub/rel_sym"
                _req(fa.diagnose_continual_flow(Path("."))["overall_status"] == "HEALTHY", "non-absolute PWD should be ignored")
                os.environ["PWD"] = str(root / "nonexistent_pwd")
                _req(fa.diagnose_continual_flow(Path("."))["overall_status"] == "HEALTHY", "missing PWD should be ignored")
                os.environ["PWD"] = str(other_dir)
                _req(fa.diagnose_continual_flow(Path("."))["overall_status"] == "HEALTHY", "different-dir PWD should be ignored")
                os.environ["PWD"] = str(sym_rel)
                _expect_err(lambda: fa.diagnose_continual_flow(Path(".")), "SYMLINK_FORBIDDEN", "symlinked PWD must fail")
                os.environ.pop("PWD", None)
                gone = root / "gone_cwd"
                gone.mkdir()
                os.chdir(gone)
                gone.rmdir()
                _expect_err(lambda: fa.diagnose_continual_flow(Path(".")), "CWD_UNAVAILABLE", "deleted cwd")
            finally:
                os.chdir(old_cwd)
                if old_pwd is None:
                    os.environ.pop("PWD", None)
                else:
                    os.environ["PWD"] = old_pwd

    def test_04_cli_parity_self_test_and_exit_codes(self) -> None:
        """Verify standalone script execution, module CLI, exit codes, and 3-mode isolated parity."""
        st = fa.run_self_test()
        _req(st["self_test_passed"] is True and st["relapse_alerts"] == 3, f"self_test: {st}")

        # Direct script invocation in -I -B, -I -O -B, -I -B -W error must be bit-identical
        script_path = ROOT / "aletheia" / "flow_audit.py"
        outputs: list[bytes] = []
        for flags in (["-I", "-B"], ["-I", "-O", "-B"], ["-I", "-B", "-W", "error"]):
            proc = subprocess.run(
                [sys.executable, *flags, str(script_path)],
                capture_output=True,
                timeout=30,
            )
            _req(proc.returncode == 0 and proc.stderr == b"", f"script {flags}: rc={proc.returncode} err={proc.stderr!r}")
            outputs.append(proc.stdout)
        _req(outputs[0] == outputs[1] == outputs[2], "script 3-mode parity mismatch")
        parsed_st = json.loads(outputs[0].decode("utf-8"))
        _req(parsed_st["self_test_passed"] is True, "script stdout invalid")

        # In-process main() CLI checks: --self-test, --json, text mode, WATCH + --fail-on-warning, RELAPSE, error rc=2
        with tempfile.TemporaryDirectory(prefix="aletheia_flow_t4_") as td:
            root = Path(td)
            (root / "frontier_portals.md").write_text("# Portals\n", encoding="utf-8")
            b_ok = root / "ok.jsonl"
            _write_jsonl(
                b_ok,
                [
                    {"seq": 1, "agent": "peer-weaver", "text": "w"},
                    {"seq": 2, "agent": "session-cartographer", "text": "c"},
                ],
            )
            p_ok = subprocess.run(
                [sys.executable, "-s", "-B", "-m", "aletheia.flow_audit", str(root), "--board", str(b_ok), "--json"],
                cwd=ROOT,
                capture_output=True,
                text=True,
                timeout=30,
            )
            _req(p_ok.returncode == 0 and json.loads(p_ok.stdout)["overall_status"] == "HEALTHY", f"cli ok: {p_ok}")

            # Non-JSON human summary on HEALTHY (rc=0) & --fail-on-warning stays 0 on HEALTHY
            with redirect_stdout(io.StringIO()):
                rc_txt = fa.main([str(root), "--board", str(b_ok)])
                _req(rc_txt == 0, f"text mode rc={rc_txt}")
                _req(fa.main([str(root), "--board", str(b_ok), "--fail-on-warning", "--json"]) == 0, "HEALTHY --fail-on-warning must be 0")
                # Self-test via main() WITH a non-existent expedition_dir kills DEL_0 on args.self_test or ...
                _req(fa.main([str(root / "nope"), "--self-test", "--json"]) == 0, "main --self-test with positional failed")
                # --help raises SystemExit(0) -> kills type(exc.code) is int -> is not int
                _req(fa.main(["--help"]) == 0, "main --help must exit 0")
                # WATCH without vs with --fail-on-warning
                b_warn = root / "warn.jsonl"
                _write_jsonl(
                    b_warn,
                    [
                        {"seq": 1, "agent": "peer-weaver", "text": "w"},
                        {"seq": 2, "agent": "session-cartographer", "text": "c"},
                        {"seq": 3, "agent": "worker", "text": "Burnside"},
                    ],
                )
                _req(fa.main([str(root), "--board", str(b_warn), "--json"]) == 0, "WATCH default rc must be 0")
                _req(fa.main([str(root), "--board", str(b_warn), "--fail-on-warning", "--json"]) == 1, "WATCH --fail-on-warning must be 1")
                # RELAPSE_DETECTED -> rc=1
                b_rel = root / "rel.jsonl"
                _write_jsonl(b_rel, [{"seq": 1, "agent": "worker", "text": "Burnside Krein Hodge"}])
                _req(fa.main([str(root), "--board", str(b_rel), "--json"]) == 1, "RELAPSE must exit 1")
            # Error -> rc=2 (structured JSON on stderr, zero traceback)
            p_err = subprocess.run(
                [sys.executable, "-I", "-B", str(script_path), str(root / "nope"), "--json"],
                cwd=ROOT,
                capture_output=True,
                text=True,
                timeout=30,
            )
            _req(p_err.returncode == 2 and "Traceback" not in p_err.stderr, f"cli err: {p_err}")
            _req(json.loads(p_err.stderr)["code"] == "FILE_NOT_FOUND", f"cli err json: {p_err.stderr}")
            # Bad argparse flag & invalid programmatic argv -> rc=2 (zero raw TypeError/tracebacks)
            with redirect_stdout(io.StringIO()):
                _req(fa.main(("--self-test", "--json")) == 0, "tuple argv self-test failed")
            for bad_argv, exp_code in (
                ("bad", "INVALID_CLI_ARGV"),
                ([123], "INVALID_CLI_ARGV"),
                (["--self-test", "a\x00b"], "NUL_BYTE_FORBIDDEN"),
                (["--self-test", "a\ud800b"], "INVALID_UTF8_SURROGATE"),
            ):
                ebuf = io.StringIO()
                with redirect_stderr(ebuf):
                    rc_bad = fa.main(bad_argv)  # type: ignore[arg-type]
                _req(rc_bad == 2 and json.loads(ebuf.getvalue())["code"] == exp_code, f"bad_argv {bad_argv!r}: rc={rc_bad} err={ebuf.getvalue()!r}")
            with redirect_stderr(io.StringIO()):
                _req(fa.main(["--unknown-flag"]) == 2, "unknown flag must exit 2")

            # Extreme ISO-8601 timestamps (year 9999 -05:00 & year 0001 +05:00) via API & live CLI --max-silence-seconds
            for ts_tag, ts_val in (
                ("yr9999", "9999-12-31T23:59:59-05:00"),
                ("yr0001", "0001-01-01T00:00:00+05:00"),
            ):
                b_ext = root / f"ext_{ts_tag}.jsonl"
                _write_jsonl(
                    b_ext,
                    [
                        {"seq": 1, "agent": "session-cartographer", "text": "fold", "time": ts_val},
                        {"seq": 2, "agent": "worker", "text": "ok", "time": "2026-11-23T00:00:00Z"},
                    ],
                )
                rep_ext = fa.diagnose_continual_flow(root, board_path=b_ext, max_silence_seconds=60)
                _req(type(rep_ext["metrics"]["cartographer_silence_seconds"]) is int, f"{ts_tag} api failed")
                p_ext = subprocess.run(
                    [sys.executable, "-I", "-B", str(script_path), str(root), "--board", str(b_ext), "--max-silence-seconds", "60", "--json"],
                    cwd=ROOT,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                _req(p_ext.returncode in (0, 1) and "Traceback" not in p_ext.stderr, f"{ts_tag} cli failed: {p_ext}")
                _req(json.loads(p_ext.stdout)["schema"] == fa.FLOW_AUDIT_SCHEMA, f"{ts_tag} cli json invalid")

    def test_05_base_dir_open_fail_closed_kills_guard_except_reject(self) -> None:
        """M011 kill: a failing base-directory os.open() must raise AletheiaError(FILE_READ_ERROR),
        never fall through with an unbound cur_fd (guard_except_reject survivor class)."""
        import errno as _errno
        from unittest import mock as _mock

        def _raise_eacces(*args: Any, **kwargs: Any) -> int:
            raise OSError(_errno.EACCES, "mocked EACCES on base open")

        with _mock.patch("os.open", side_effect=_raise_eacces):
            _expect_err(lambda: fa._open_dir_chain(["any"], start_abs=False, label="m011"), "FILE_READ_ERROR", "base open EACCES")
            _expect_err(lambda: fa._open_dir_chain([], start_abs=True, label="m011abs"), "FILE_READ_ERROR", "abs base open EACCES")


if __name__ == "__main__":
    unittest.main()
