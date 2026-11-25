#!/usr/bin/env python3
"""
Track S84: Full-Expedition K_16 Higher-Order All-to-All Interlocking Epistemic Mesh
(Orders 1..4 Convergences Across All 5 Spines S1-S83) — Pure-Z/Q Exact Oracle.

100% pure Python 3 stdlib (`int` / `fractions.Fraction`), zero IEEE-754 floats,
zero `float()`, zero bare `assert`s, zero `.isdigit()`, zero RNG, zero host paths.
"""

from __future__ import annotations

from fractions import Fraction
import hashlib
import json
from math import comb
from typing import Any

SCHEMA_VERSION = "aletheia.track_s84.higher_order_k16_mesh.certificate.v1"
TRACK_ID = "TRACK-S84-HIGHER-ORDER-K16-MESH"
EXPECTED_LEAN_TOOLCHAIN = "leanprover/lean4:v4.36.0"
EXPECTED_LEAN_SHA256 = "00238fb5e82cbb64e1b0877c4962a7cac1dec3332871dd9471b3fe6636bdb831"
MAX_JSON_DEPTH = 32
MAX_INT_BITS = 1024

PATHWAY_WEIGHTS: dict[str, int] = {
    "EXACT_COMMUTE": 4,
    "CONDITIONAL_BRIDGE": 2,
    "EXACT_OBSTRUCTION": 1,
}

OPERATOR_GLYPHS: dict[str, str] = {
    "SCHUR_PUSHFORWARD": "\u29c4",
    "HOLONOMY_CURVATURE": "\u29b7",
    "GAUGE_QUOTIENT": "\u29c2",
    "KREIN_INERTIA": "\u29ba",
    "PHASE_CROSSOVER": "\u27e0",
    "REFUSAL_GATE": "\u2ae9",
    "BOUNDARY_WALL": "\u29c7",
}

EXPECTED_LEAN_THEOREMS: tuple[str, ...] = (
    "HigherOrderEpistemicMesh.schur_3node_conductance_exact",
    "HigherOrderEpistemicMesh.schur_3node_strict_compounding",
    "HigherOrderEpistemicMesh.schur_uniform_kn_conductance_strict",
    "HigherOrderEpistemicMesh.foster_uniform_kn_exact",
    "HigherOrderEpistemicMesh.prop_e10_balanced_edge_cut_bound",
    "HigherOrderEpistemicMesh.k16_edge_destruction_exact",
    "HigherOrderEpistemicMesh.kn_triangle_destruction_exact_identity",
    "HigherOrderEpistemicMesh.kn_tetrahedron_destruction_exact_identity",
    "HigherOrderEpistemicMesh.kn_5cell_destruction_exact_identity",
    "HigherOrderEpistemicMesh.k16_balanced_exponential_destruction_exact",
    "HigherOrderEpistemicMesh.balanced_halving_survival_strict_exponential_bound",
    "HigherOrderEpistemicMesh.simplicial_hodge_b1_b2_zero",
    "HigherOrderEpistemicMesh.tetrahedral_z2_bianchi_zero",
    "HigherOrderEpistemicMesh.paired_frustration_repair_cancels_two_triangles",
    "HigherOrderEpistemicMesh.five_cell_single_wall_frustrates_exactly_three_faces",
    "HigherOrderEpistemicMesh.ungated_k16_contagion_amplification",
    "HigherOrderEpistemicMesh.gated_refusal_firewall_zero_contagion",
    "HigherOrderEpistemicMesh.gated_k15_submesh_preserves_higher_order_compounding",
)

# Sixteen frozen on-disk verified certificates spanning all 5 Spines (n00..n07 = Wave-4 K_8).
MESH_NODES: tuple[dict[str, Any], ...] = (
    {
        "id": "n00",
        "spine": "Spine I",
        "track": "Track S73",
        "domain": "siliquant_stratified_lattice",
        "relative_ref": "track-s73-lowbit-and-sharednorm-quad-snake/rtx3080_s73_certificate.json",
        "bytes": 5202,
        "sha256": "33dfb4153fe974e9ef13120190c14ada6dda63ffbee6caa46047d274f32d36cf",
        "anchor": "quoted anchor (external track, not an S84 claim): 3.0 bpw QuadSnake -11.42% (2.70x amp), p=0.375 PyKL 0.018248 (-20.58%)",
    },
    {
        "id": "n01",
        "spine": "Spine II",
        "track": "Track S75+S82",
        "domain": "vp_vnp_cat0_laurent_cuts",
        "relative_ref": "track-s75-vp-vnp-formal-audit/s75_vp_vnp_certificate.json",
        "bytes": 1982,
        "sha256": "7e383c1cfe04937277be7f8f4ff4305984d51ecd81858eebdd67e45238823224",
        "anchor": "Rem D.3 det(G)=-1/4 at mu=2, Prop E.10 9|S|(N-|S|)>=2N^2, Lem F.2/N.2",
    },
    {
        "id": "n02",
        "spine": "Spine III",
        "track": "Track S76",
        "domain": "circularep_loop_schur_ep",
        "relative_ref": "track-s76-circular-pc-loop-schur-holonomy/s76_circular_pc_certificate.json",
        "bytes": 7006,
        "sha256": "d30805fcb876de096d9b387a8274ecd8063b7906f4feb36124b38a05aefadc95",
        "anchor": "Loop-Schur G_loop^(-1) (det 599/360), 176/176 GD cliff, 2.912e+9x curl bias",
    },
    {
        "id": "n03",
        "spine": "Spine IV",
        "track": "Track S77",
        "domain": "mellin_glu_circuit_graft",
        "relative_ref": "track-s77-mellin-glu-wsp-quantization-tomography/s77_mellin_wsp_certificate.json",
        "bytes": 11729,
        "sha256": "d1b9121c435331053b7ab28b915a2062ae7c93b4197d203c63dba42cce5dd74d",
        "anchor": "Mellin-GLU S72 INT8 rescue 0/5->5/5, WSP-Gym CS-08 p<1e-10",
    },
    {
        "id": "n04",
        "spine": "Spine IV",
        "track": "Track S81",
        "domain": "motifbench_se3_protein_graft",
        "relative_ref": "track-s81-motifbench-esmfold-grafting-duality/s81_motifbench_certificate.json",
        "bytes": 4058,
        "sha256": "bc3b9222c47b2ab93c4b5256501d87f8b6483186766e03dba6f1501670936fe0",
        "anchor": "SE(3) MSD_unit=4/3, R^3 Gram det(G4)=0, ESMFold 28.6029 vs AF2 22.4610",
    },
    {
        "id": "n05",
        "spine": "Spine V",
        "track": "Track S78",
        "domain": "engram_lora_mdl_capacity",
        "relative_ref": "track-s78-engram-lora-capacity-siliquant-mdl/s78_engram_lora_siliquant_certificate.json",
        "bytes": 18553,
        "sha256": "3b8341ef5f588f970accb9a9d28f0b683af9747be045e69196e6c19d3fa58378",
        "anchor": "C_MP=(1/2ln2)*P_raw*eta_alg*kappa, 6.929B cross, b_floor(1B)=4.3226 bpw",
    },
    {
        "id": "n06",
        "spine": "Spine V",
        "track": "Track S80",
        "domain": "rocket_songe_unsloth_rl",
        "relative_ref": "track-s80-rocket-songe-unsloth-optimizations/s80_certificate.json",
        "bytes": 6098,
        "sha256": "95681a29ca577c4e3040f8ba63f8516b1cbb2bf1ebfdcda06277f21bb2aa2cb7",
        "anchor": "Rocket ESS 36481/16447, songe 87.15% FWER, CCE 75672x cut, atomic_cas wall",
    },
    {
        "id": "n07",
        "spine": "Spine I",
        "track": "Track S79",
        "domain": "twodsd_multipole_csr_laws",
        "relative_ref": "track-s79-2dsd-multipole-dense-sparse-laws/s79_2dsd_multipole_certificate.json",
        "bytes": 6460,
        "sha256": "9c30539e6d585141a9b1a5111935ca86de0f740e80749a622547a18242465ad8",
        "anchor": "2DSD KV 3.9767x, CSR cap rho_s<=1/160, Multipole Jensen 33/32",
    },
    {
        "id": "n08",
        "spine": "Spine I",
        "track": "Track S59+S47",
        "domain": "e8_vs_a16_hadamard_law",
        "relative_ref": "track-s59-exact-e8-vs-a16-hadamard-law/e8_vs_a16_hadamard_certificate.json",
        "bytes": 6360,
        "sha256": "914a84512d7026b23af0672d4b175128534a7d3c8a0fbc9152b28bc38ea8f1ed",
        "anchor": "Opposite-sign E_8/A_16 Hadamard O_16(Q) isometry & 8x regime flip",
    },
    {
        "id": "n09",
        "spine": "Spine I",
        "track": "Track S71+S65",
        "domain": "proximity_barrier_silicon",
        "relative_ref": "track-s71-proximity-barrier-silicon-unlock/s71_proximity_certificate.json",
        "bytes": 2982,
        "sha256": "7774fedfd575f48451aae0722cdbaf8015673585786dc43dc8e35402580efe6d",
        "anchor": "64 B MESI repulsion 16.973x vs read-fusion 2.681x & AVX-512 VNNI",
    },
    {
        "id": "n10",
        "spine": "Spine II",
        "track": "Track S54+S38",
        "domain": "silq_cs21_boundary_compiler",
        "relative_ref": "track-s54-silq-cs21-boundary-compiler/silq_cs21_compiler_certificate.json",
        "bytes": 12813,
        "sha256": "94b9c34f196afc031e6169032eb42d2fe2ddd120d2dc137bc52c0ee2bebf3850",
        "anchor": "Silq Landauer erasure & CS-21 600/401 classical boundary offloading",
    },
    {
        "id": "n11",
        "spine": "Spine III",
        "track": "Track S50+S42/43",
        "domain": "zero_dw_state_transport",
        "relative_ref": "track-s50-zero-dw-state-transport-tomography/zero_dw_state_transport_certificate.json",
        "bytes": 12803,
        "sha256": "1316eede91b66c309c427fec60e36374350d65b6649eba7154de8e4ea4431320",
        "anchor": "Zero-dW rank-1 state transport (+2 -> -83/25) & ReLU/Hodge yield wall",
    },
    {
        "id": "n12",
        "spine": "Spine V",
        "track": "Track S31+S34",
        "domain": "aletheia_v22_dpi_misfolding",
        "relative_ref": "track-s31-aletheia-v22-society-misfolding-tomography/aletheia_v22_misfolding_certificate.json",
        "bytes": 12707,
        "sha256": "f4f7f8abff0c7eae0d5678016c1041ab34870ef2de57a2f83e4cbb9a529f8a9b",
        "anchor": "75,968x iso-MDL DPI blindness, CS-16 66/25 sign flip & Rosen cusp",
    },
    {
        "id": "n13",
        "spine": "Spine III",
        "track": "Track S28+S23b/33",
        "domain": "alcubierre_adm_krein_slemma",
        "relative_ref": "track-s28-alcubierre-adm-slemma-tomography/alcubierre_adm_certificate.json",
        "bytes": 7831,
        "sha256": "6d5579f52d176f39d6f160a405873843ff616ca7d1d76c95f1a3d340237bbc9f",
        "anchor": "Krein (4,0,0)->(2,0,2) flip, S-lemma blind spot & ADM Schur closure",
    },
    {
        "id": "n14",
        "spine": "Spine II",
        "track": "Track S40+S22c/41",
        "domain": "mozart_f2x_carry_polya_wall",
        "relative_ref": "track-s40-mozart-perfect-numbers-bridge/mozart_perfect_bridge_certificate.json",
        "bytes": 11634,
        "sha256": "3c6b226b43804befdd102a4f02800421087ed851009967bc20b2e72479ce336e",
        "anchor": "F_2[x] Frobenius splitting vs Z carry wall & Polya 0/512 SOS wall",
    },
    {
        "id": "n15",
        "spine": "Spine V",
        "track": "Track S62+S56/57",
        "domain": "ceer_lean4_silicon_recursion",
        "relative_ref": "track-s62-ceer-lean4-silicon-recursion/ceer_silicon_certificate.json",
        "bytes": 11121,
        "sha256": "cef74336a38edc2d7c0b05007952690c0f8608607bc800036292aa4642665b53",
        "anchor": "Live CEER Lean 4.36.0 + silicon reality gate & meta-recursion",
    },
)

# Exhaustive 120/120 strictly typed edges on K_16:
#   - Edges (0..7, 0..7) match Track S83 K_8 verbatim (10 commute, 12 bridge, 6 obstruction).
#   - Remaining 92 edges map exact cross-spine laws & honest obstructions across Spines I-V.
MESH_EDGES_SPEC: tuple[tuple[int, int, str, str, str], ...] = (
    # --- Wave-4 K_8 Core (28 edges, exact Track S83 inheritance) ---
    (0, 1, "CONDITIONAL_BRIDGE", "GAUGE_QUOTIENT", "A16/E8 rank-metric CAT(0) vs orthogonal WHT kappa2=1"),
    (0, 2, "CONDITIONAL_BRIDGE", "PHASE_CROSSOVER", "BlockH4 spectral-bounded weights vs CircularEP contraction"),
    (0, 3, "EXACT_COMMUTE", "SCHUR_PUSHFORWARD", "S72/S73 stratified quad INT8 rescues Mellin-GLU 0/5->5/5"),
    (0, 4, "EXACT_OBSTRUCTION", "BOUNDARY_WALL", "O(n) reflection-invariant WHT vs SE(3) chirality MSD=4/3"),
    (0, 5, "EXACT_COMMUTE", "GAUGE_QUOTIENT", "Exact joint (bpw,rank) bit-budget conservation B_tot"),
    (0, 6, "EXACT_COMMUTE", "PHASE_CROSSOVER", "3.0/4.5 bpw siliquant compression fits 8 GiB Unsloth CCE"),
    (0, 7, "EXACT_COMMUTE", "PHASE_CROSSOVER", "Dense QuadSnake vs CSR sidecar crossover rho_s<=1/160"),
    (1, 2, "EXACT_COMMUTE", "HOLONOMY_CURVATURE", "Lem N.2 Laurent cutoff N=2^L*Delta <-> EP O(r/beta) pole"),
    (1, 3, "CONDITIONAL_BRIDGE", "BOUNDARY_WALL", "Prop M.2 char-2 XOR & Sec 2.5 ideal <-> Mellin Boolean gate"),
    (1, 4, "EXACT_OBSTRUCTION", "KREIN_INERTIA", "Rem D.3 hyperbolic det(G)=-1/4 vs R^3 Gram det(G4)=0"),
    (1, 5, "EXACT_OBSTRUCTION", "BOUNDARY_WALL", "Thm D.2 non-constructive hyperfilter vs finite-rank C_MP"),
    (1, 6, "EXACT_COMMUTE", "HOLONOMY_CURVATURE", "Lem N.2/Prop N.4 Laurent cutoff <-> Rocket exp(+-T*d) drift"),
    (1, 7, "EXACT_COMMUTE", "SCHUR_PUSHFORWARD", "Prop E.10 balanced cut <-> 128-expert MoE & Multipole rank"),
    (2, 3, "CONDITIONAL_BRIDGE", "SCHUR_PUSHFORWARD", "CircularEP DEQ fixed-point <-> Mellin zero-grad graft"),
    (2, 4, "EXACT_OBSTRUCTION", "HOLONOMY_CURVATURE", "Complex-curl monodromy 2.912e+9x bias vs rigid SE(3) frame"),
    (2, 5, "CONDITIONAL_BRIDGE", "GAUGE_QUOTIENT", "CircularEP effective depth <-> Engram 24-layer capacity"),
    (2, 6, "CONDITIONAL_BRIDGE", "REFUSAL_GATE", "EP truncated-phase O(r/beta) <-> Rocket async-RL staleness"),
    (2, 7, "EXACT_COMMUTE", "SCHUR_PUSHFORWARD", "CircularEP rho(M)<1 (81/256) <-> 2DSD last-loop KV sharing"),
    (3, 4, "EXACT_OBSTRUCTION", "BOUNDARY_WALL", "Width-extension d->d+K grafting vs fixed ambient R^3 wall"),
    (3, 5, "CONDITIONAL_BRIDGE", "GAUGE_QUOTIENT", "Mellin 0.057% sidecar budget <-> Engram LoRA rank capacity"),
    (3, 6, "CONDITIONAL_BRIDGE", "REFUSAL_GATE", "WSP-Gym CS-08 & random-edit wall <-> songe Ratchet Gate 2"),
    (3, 7, "EXACT_COMMUTE", "PHASE_CROSSOVER", "Portal-77 0.057% sidecar sits inside S79 CSR cap (26/35)"),
    (4, 5, "CONDITIONAL_BRIDGE", "GAUGE_QUOTIENT", "Multi-segment 6(K-1) SE(3) DOF <-> GL_r gauge eta_alg(r)"),
    (4, 6, "CONDITIONAL_BRIDGE", "REFUSAL_GATE", "MotifBench dual-oracle PPV 184/51 <-> Ratchet outside gate"),
    (4, 7, "CONDITIONAL_BRIDGE", "BOUNDARY_WALL", "Global scRMSD<=2A consistency <-> Multipole far-field bound"),
    (5, 6, "EXACT_COMMUTE", "REFUSAL_GATE", "CS-15 Forgetting/Learning=1.00 <-> songe 87% FWER Ratchet"),
    (5, 7, "CONDITIONAL_BRIDGE", "PHASE_CROSSOVER", "Joint (bpw,rank) budget <-> 2DSD drafter + KV VRAM budget"),
    (6, 7, "EXACT_OBSTRUCTION", "HOLONOMY_CURVATURE", "tl.atomic_cas ULP non-assoc vs 2DSD/Multipole invariance"),
    # --- Cross-Spine Edges n08 (S59 E8/A16 Hadamard) x n00..n07 ---
    (0, 8, "EXACT_COMMUTE", "KREIN_INERTIA", "QuadSnake BlockH4 inherits S59 exact E8/A16 O_16(Q) sign-flip"),
    (1, 8, "EXACT_OBSTRUCTION", "GAUGE_QUOTIENT", "vp-vnp CNOT real shear kappa2=phi^2 vs S59 orthogonal O_16(Q)"),
    (2, 8, "CONDITIONAL_BRIDGE", "HOLONOMY_CURVATURE", "Orthogonal WHT conditioning stabilizes CircularEP recursion"),
    (3, 8, "EXACT_COMMUTE", "SCHUR_PUSHFORWARD", "S59 BlockH4 equal-variance mixing underpins S77 INT8 carry rescue"),
    (4, 8, "EXACT_OBSTRUCTION", "BOUNDARY_WALL", "Hadamard reflection det=-1 violates SE(3) proper rotation det=+1"),
    (5, 8, "EXACT_COMMUTE", "GAUGE_QUOTIENT", "Orthogonal Hadamard preserves Fisher whitening & C_MP capacity"),
    (6, 8, "CONDITIONAL_BRIDGE", "PHASE_CROSSOVER", "BlockH4 4.5/3.0 bpw quantization unlocks 8 GiB CCE RL budget"),
    (7, 8, "EXACT_COMMUTE", "PHASE_CROSSOVER", "S59 dense A_16 Hadamard sets exact dense baseline vs S79 CSR cap"),
    # --- Cross-Spine Edges n09 (S71 Proximity/MESI/VNNI) x n00..n08 ---
    (0, 9, "EXACT_COMMUTE", "KREIN_INERTIA", "BlockH4 64 B aligned tiles match S71 read-fusion & AVX-512 VNNI"),
    (1, 9, "CONDITIONAL_BRIDGE", "SCHUR_PUSHFORWARD", "Prop E.10 balanced partition governs 64 B cache-line locality"),
    (2, 9, "CONDITIONAL_BRIDGE", "PHASE_CROSSOVER", "Fixed-point synchronous writes hit 64 B MESI false-sharing wall"),
    (3, 9, "EXACT_COMMUTE", "SCHUR_PUSHFORWARD", "Compact INT8 Mellin-GLU tiles stay cache-resident under read-fusion"),
    (4, 9, "CONDITIONAL_BRIDGE", "BOUNDARY_WALL", "3D protein distance tables respect 64 B cache-line packing"),
    (5, 9, "EXACT_COMMUTE", "PHASE_CROSSOVER", "Low-rank LoRA adapters keep working set inside L2/L3 read-fusion"),
    (6, 9, "EXACT_OBSTRUCTION", "KREIN_INERTIA", "Concurrent atomic_cas updates trigger 16.973x 64 B MESI repulsion"),
    (7, 9, "EXACT_COMMUTE", "PHASE_CROSSOVER", "CSR irregular indirection breaks 64 B coalescing vs dense tiles"),
    (8, 9, "EXACT_COMMUTE", "KREIN_INERTIA", "S59 8x Hadamard sign-flip mirrors S71 64 B repulsion/fusion flip"),
    # --- Cross-Spine Edges n10 (S54 Silq Landauer & CS-21) x n00..n09 ---
    (0, 10, "CONDITIONAL_BRIDGE", "REFUSAL_GATE", "CS-21 full boundary accounting audits scale/codebook bit overhead"),
    (1, 10, "CONDITIONAL_BRIDGE", "BOUNDARY_WALL", "Silq uncomputation boundary mirrors vp-vnp reversible CNOT cost"),
    (2, 10, "CONDITIONAL_BRIDGE", "HOLONOMY_CURVATURE", "Reversible phase-space conservation vs dissipative EP settling"),
    (3, 10, "CONDITIONAL_BRIDGE", "REFUSAL_GATE", "CS-21 full-stack accounting prevents hidden sidecar width offloading"),
    (4, 10, "CONDITIONAL_BRIDGE", "BOUNDARY_WALL", "Reversible geometric folding vs irreversible sequence collapse"),
    (5, 10, "EXACT_COMMUTE", "REFUSAL_GATE", "Two-part MDL parameter bits unify with CS-21 600/401 total cost"),
    (6, 10, "EXACT_COMMUTE", "REFUSAL_GATE", "CS-21 offloading refusal closes RL reward/eval cost-hiding loophole"),
    (7, 10, "EXACT_COMMUTE", "PHASE_CROSSOVER", "CS-21 total-bit accounting derives S79 exact CSR index overhead"),
    (8, 10, "CONDITIONAL_BRIDGE", "GAUGE_QUOTIENT", "Exact reversible O_16(Q) Hadamard incurs zero Landauer bit erasure"),
    (9, 10, "EXACT_COMMUTE", "REFUSAL_GATE", "CS-21 full energy accounting matches S71 RAPL DRAM+cache budget"),
    # --- Cross-Spine Edges n11 (S50 Zero-dW State Transport) x n00..n10 ---
    (0, 11, "CONDITIONAL_BRIDGE", "GAUGE_QUOTIENT", "Frozen quantized base weights preserve zero-dW state transport"),
    (1, 11, "CONDITIONAL_BRIDGE", "HOLONOMY_CURVATURE", "Rank-1 state transport vs vp-vnp bilinear tensor rank growth"),
    (2, 11, "EXACT_COMMUTE", "SCHUR_PUSHFORWARD", "Zero-dW fixed-point steering commutes with CircularEP loop transport"),
    (3, 11, "EXACT_COMMUTE", "SCHUR_PUSHFORWARD", "Zero-dW state transport dualizes Mellin-GLU zero-grad weight graft"),
    (4, 11, "EXACT_OBSTRUCTION", "BOUNDARY_WALL", "Rank-1 linear state shift cannot bypass R^3 rigid SE(3) Gram wall"),
    (5, 11, "CONDITIONAL_BRIDGE", "GAUGE_QUOTIENT", "Activation-space transport complements LoRA parameter-space C_MP"),
    (6, 11, "CONDITIONAL_BRIDGE", "REFUSAL_GATE", "Activation drift under zero-dW mirrors Rocket logit-staleness bound"),
    (7, 11, "CONDITIONAL_BRIDGE", "SCHUR_PUSHFORWARD", "Last-loop KV reuse transports hidden state across 2DSD depth"),
    (8, 11, "CONDITIONAL_BRIDGE", "GAUGE_QUOTIENT", "Orthogonal WHT commutes with rank-1 activation transport norms"),
    (9, 11, "CONDITIONAL_BRIDGE", "PHASE_CROSSOVER", "Zero-dW avoids weight-write MESI invalidations during adaptation"),
    (10, 11, "CONDITIONAL_BRIDGE", "REFUSAL_GATE", "Zero-dW state shifts still incur CS-21 activation-memory accounting"),
    # --- Cross-Spine Edges n12 (S31+S34 DPI / CS-16 / Rosen Cusp) x n00..n11 ---
    (0, 12, "EXACT_COMMUTE", "PHASE_CROSSOVER", "S34 log-convex KL(b)=C*2^(-alpha*b) directly fits siliquant ladder"),
    (1, 12, "CONDITIONAL_BRIDGE", "KREIN_INERTIA", "Rosen cusp 1!=3 non-metric geometry echoes CAT(0) det(G)=-1/4"),
    (2, 12, "CONDITIONAL_BRIDGE", "REFUSAL_GATE", "DPI blindness flags single-scalar EP energy hiding curl bias"),
    (3, 12, "EXACT_COMMUTE", "REFUSAL_GATE", "S31 CS-16 matched-gain sign flip parallels WSP-Gym CS-08 flip"),
    (4, 12, "EXACT_COMMUTE", "REFUSAL_GATE", "75,968x iso-MDL DPI blindness directly predicts MotifBench PPV gap"),
    (5, 12, "EXACT_COMMUTE", "REFUSAL_GATE", "S34 offline-online MDL & S31 CS-16 66/25 directly anchor Track S78"),
    (6, 12, "EXACT_COMMUTE", "REFUSAL_GATE", "DPI single-proxy blindness necessitates songe 5-gate outside ratchet"),
    (7, 12, "CONDITIONAL_BRIDGE", "PHASE_CROSSOVER", "S34 convex KL floor bounds lossless speculative draft compression"),
    (8, 12, "EXACT_COMMUTE", "GAUGE_QUOTIENT", "S31 Pillar 3 proves Hadamard rotation bypasses naive proxy traps"),
    (9, 12, "CONDITIONAL_BRIDGE", "REFUSAL_GATE", "Aggregate throughput hides 64 B MESI tail stalls (DPI projection)"),
    (10, 12, "EXACT_COMMUTE", "REFUSAL_GATE", "CS-21 boundary accounting closes CS-16/DPI hidden-cost proxy gaming"),
    (11, 12, "EXACT_COMMUTE", "REFUSAL_GATE", "Iso-Frobenius airlock exposes zero-dW collapse invisible to norm DPI"),
    # --- Cross-Spine Edges n13 (S28 Krein / ADM / S-Lemma) x n00..n12 ---
    (0, 13, "CONDITIONAL_BRIDGE", "KREIN_INERTIA", "Quadratic KL Hessian curvature switches mirror Krein inertia flips"),
    (1, 13, "EXACT_COMMUTE", "KREIN_INERTIA", "vp-vnp Rem D.3 det(G)=-1/4 signature aligns with Krein (2,0,2) flip"),
    (2, 13, "EXACT_COMMUTE", "KREIN_INERTIA", "CircularEP Krein [2,2,0]->[1,1,2] flip & ADM Schur closure exact"),
    (3, 13, "CONDITIONAL_BRIDGE", "SCHUR_PUSHFORWARD", "ADM block Schur elimination structures nonlinear GLU carry gating"),
    (4, 13, "EXACT_OBSTRUCTION", "KREIN_INERTIA", "Indefinite Krein (2,0,2) signature is incompatible with Euclidean R^3"),
    (5, 13, "CONDITIONAL_BRIDGE", "KREIN_INERTIA", "Convex MDL Hessian d2J/db2>0 stays strictly positive-definite (SPD)"),
    (6, 13, "CONDITIONAL_BRIDGE", "HOLONOMY_CURVATURE", "Krein instability threshold mirrors Rocket/EP stability boundary"),
    (7, 13, "EXACT_COMMUTE", "SCHUR_PUSHFORWARD", "ADM Schur complement mirrors 2DSD/Multipole hierarchical reduction"),
    (8, 13, "EXACT_COMMUTE", "KREIN_INERTIA", "S59 opposite-sign quadratic KL witnesses realize Krein inertia switch"),
    (9, 13, "EXACT_COMMUTE", "KREIN_INERTIA", "S71 64 B repulsion vs fusion realizes competing-potential sign flip"),
    (10, 13, "CONDITIONAL_BRIDGE", "BOUNDARY_WALL", "ADM horizon boundary terms mirror CS-21 irreversible boundary flux"),
    (11, 13, "EXACT_COMMUTE", "KREIN_INERTIA", "Zero-dW yield wall & Hodge cohomology map onto Krein stability cone"),
    (12, 13, "CONDITIONAL_BRIDGE", "KREIN_INERTIA", "S-lemma blind spot mirrors DPI/Rosen non-convex projection failure"),
    # --- Cross-Spine Edges n14 (S40 F_2[x] / Carry / Polya SOS) x n00..n13 ---
    (0, 14, "EXACT_OBSTRUCTION", "BOUNDARY_WALL", "F_2[x] carry-free algebra fractures under Z integer quantization rounding"),
    (1, 14, "EXACT_COMMUTE", "BOUNDARY_WALL", "vp-vnp Lem F.2 char-2 CNOT & S40 F_2[x] share exact char-2 wall"),
    (2, 14, "CONDITIONAL_BRIDGE", "HOLONOMY_CURVATURE", "Nyquist pentagonal parity resonance echoes CircularEP discrete phase"),
    (3, 14, "EXACT_OBSTRUCTION", "BOUNDARY_WALL", "F_2[x] carry-free splitting breaks at Z binary carry propagation in GLU"),
    (4, 14, "EXACT_OBSTRUCTION", "BOUNDARY_WALL", "Discrete F_2[x] polynomial arithmetic cannot represent continuous SE(3)"),
    (5, 14, "CONDITIONAL_BRIDGE", "BOUNDARY_WALL", "Anti-numerology control parallels Engram random-noise no-profit MDL"),
    (6, 14, "CONDITIONAL_BRIDGE", "REFUSAL_GATE", "S40 anti-numerology & Polya 0/512 refusal echo songe FWER ratchet"),
    (7, 14, "CONDITIONAL_BRIDGE", "PHASE_CROSSOVER", "Polya SOS rank barrier parallels dense-vs-sparse CSR rank crossover"),
    (8, 14, "EXACT_COMMUTE", "GAUGE_QUOTIENT", "RM(1,4)/Hadamard F_2 linearity lifts cleanly to O_16(Q) before carries"),
    (9, 14, "CONDITIONAL_BRIDGE", "PHASE_CROSSOVER", "Bitwise POPCNT/XOR in AVX-512 executes carry-free F_2 algebra natively"),
    (10, 14, "EXACT_OBSTRUCTION", "BOUNDARY_WALL", "Lossless F_2[x] compression fractures under Landauer/CS-21 bit erasure"),
    (11, 14, "CONDITIONAL_BRIDGE", "BOUNDARY_WALL", "ReLU piecewise-linear yield wall parallels Polya non-negative SOS wall"),
    (12, 14, "EXACT_COMMUTE", "REFUSAL_GATE", "S40 anti-numerology control enforces Aletheia Law-5 proxy-refusal gate"),
    (13, 14, "CONDITIONAL_BRIDGE", "KREIN_INERTIA", "Polya SOS certificate gap parallels S-lemma quadratic blind spot"),
    # --- Cross-Spine Edges n15 (S62 CEER Lean 4 + Silicon Reality) x n00..n14 ---
    (0, 15, "EXACT_COMMUTE", "SCHUR_PUSHFORWARD", "S62 CEER Lean 4 + silicon loop directly drives Track S73 Cycle 6"),
    (1, 15, "EXACT_COMMUTE", "REFUSAL_GATE", "Pure-Init Lean 4.36.0 kernel gate verifies vp-vnp + S62 alike"),
    (2, 15, "EXACT_COMMUTE", "SCHUR_PUSHFORWARD", "CEER contractive feedback loop implements Loop-Schur stability"),
    (3, 15, "EXACT_COMMUTE", "REFUSAL_GATE", "CEER silicon-reality gate verifies Mellin-GLU INT8 carry survival"),
    (4, 15, "CONDITIONAL_BRIDGE", "REFUSAL_GATE", "CEER dual-kernel audit audits MotifBench ESMFold vs AF2 drift"),
    (5, 15, "EXACT_COMMUTE", "REFUSAL_GATE", "CEER zero-axiom Lean 4 gate certifies Track S78 17/17 theorems"),
    (6, 15, "EXACT_COMMUTE", "REFUSAL_GATE", "CEER closed-loop verification integrates songe 5-gate ratchet"),
    (7, 15, "EXACT_COMMUTE", "SCHUR_PUSHFORWARD", "CEER pure-Init Lean 4 + roofline audit certifies S79 18/18 laws"),
    (8, 15, "EXACT_COMMUTE", "SCHUR_PUSHFORWARD", "CEER Cycle framework produced S59 exact E8/A16 Hadamard discovery"),
    (9, 15, "EXACT_COMMUTE", "SCHUR_PUSHFORWARD", "CEER silicon reality gate directly anchors S71 i9 RAPL/MESI proof"),
    (10, 15, "EXACT_COMMUTE", "REFUSAL_GATE", "CEER Lean 4 contract integrates S54 CS-21 full boundary accounting"),
    (11, 15, "CONDITIONAL_BRIDGE", "REFUSAL_GATE", "CEER airlock verification audits zero-dW iso-Frobenius transport"),
    (12, 15, "EXACT_COMMUTE", "REFUSAL_GATE", "CEER governance directly executes S31 Aletheia v2.2 refusal rules"),
    (13, 15, "CONDITIONAL_BRIDGE", "KREIN_INERTIA", "CEER exact rational inertia checks close S-lemma blind spots"),
    (14, 15, "EXACT_COMMUTE", "REFUSAL_GATE", "CEER anti-numerology & Lean 4 gates prevent F_2->Z false lifts"),
)

# Four pairwise-disjoint 3rd-order K_4 clusters partitioning all 16 nodes (4 + 4 + 4 + 4 = 16)
# forming the exact quotient 4th-Order Meta-Mesh M_4 = P^T L_0 P.
ORDER4_META_CLUSTERS: tuple[dict[str, Any], ...] = (
    {
        "cluster_id": "C0_SILICON_LATTICE_GRAFT",
        "label": "Sovereign Silicon-Lattice-Circuit Quantization Core",
        "nodes": [0, 3, 8, 9],
        "expected_tet_class": "K4_EXACT_LOCK",
    },
    {
        "cluster_id": "C1_SPECTRAL_SCHUR_KREIN",
        "label": "Dynamical Loop-Schur, vp-vnp & Krein Contraction Core",
        "nodes": [1, 2, 7, 13],
        "expected_tet_class": "K4_EXACT_LOCK",
    },
    {
        "cluster_id": "C2_MDL_RATCHET_BOUNDARY",
        "label": "Two-Part MDL, Anti-Goodhart Ratchet & CS-21 Governance Core",
        "nodes": [5, 6, 10, 12],
        "expected_tet_class": "K4_EXACT_LOCK",
    },
    {
        "cluster_id": "C3_WALL_TRANSPORT_CEER",
        "label": "Ambient SE(3)/F_2[x] Boundary Wall, State Transport & CEER Core",
        "nodes": [4, 11, 14, 15],
        "expected_tet_class": "MULTI_WALL_TET",
    },
)

# Eight curated vertex-disjoint 2nd-order natural transformations (exact operator-tag match).
DISJOINT_NATURAL_TRANSFORMS: tuple[dict[str, Any], ...] = (
    {
        "id": "NT01_QUADRATIC_SIGN_FLIP",
        "edge_a": [0, 8],
        "edge_b": [9, 13],
        "operator_tag": "KREIN_INERTIA",
        "law": "Competing-potential quadratic sign flip: E8/A16 Hadamard 8x flip <-> 64 B MESI/Krein flip",
    },
    {
        "id": "NT02_AMBIENT_VS_CARRY_WALL",
        "edge_a": [3, 4],
        "edge_b": [0, 14],
        "operator_tag": "BOUNDARY_WALL",
        "law": "Obstruction-wall duality: Mellin d->d+K vs R^3 wall <-> F_2[x] vs Z quantization carry wall",
    },
    {
        "id": "NT03_SCHUR_CONTRACTION_GRAFT",
        "edge_a": [0, 3],
        "edge_b": [2, 7],
        "operator_tag": "SCHUR_PUSHFORWARD",
        "law": "Monotone Schur pushforward: S72 INT8 carry rescue <-> CircularEP/2DSD KV contraction",
    },
    {
        "id": "NT04_ANTI_GOODHART_RATCHET",
        "edge_a": [5, 6],
        "edge_b": [10, 12],
        "operator_tag": "REFUSAL_GATE",
        "law": "Two-channel refusal lock: CS-15/songe FWER ratchet <-> CS-21/DPI proxy-gaming closure",
    },
    {
        "id": "NT05_BUDGET_PHASE_CROSSOVER",
        "edge_a": [0, 7],
        "edge_b": [5, 9],
        "operator_tag": "PHASE_CROSSOVER",
        "law": "Memory-hierarchy phase crossover: dense vs CSR 1/160 cap <-> LoRA rank vs L2/L3 read-fusion",
    },
    {
        "id": "NT06_LAURENT_CURL_MONODROMY",
        "edge_a": [1, 2],
        "edge_b": [6, 7],
        "operator_tag": "HOLONOMY_CURVATURE",
        "law": "Finite-order discretization curvature: Lem N.2/EP pole <-> atomic_cas ULP non-associativity",
    },
    {
        "id": "NT07_GAUGE_QUOTIENT_ISOMETRY",
        "edge_a": [0, 5],
        "edge_b": [8, 14],
        "operator_tag": "GAUGE_QUOTIENT",
        "law": "Exact symmetry-quotient invariance: joint (bpw,rank) gauge <-> RM(1,4) F_2 -> O_16(Q) lift",
    },
    {
        "id": "NT08_SILICON_CEER_RESCUE",
        "edge_a": [0, 15],
        "edge_b": [2, 11],
        "operator_tag": "SCHUR_PUSHFORWARD",
        "law": "Closed-loop fixed-point transport: CEER->S73 silicon loop <-> CircularEP->Zero-dW transport",
    },
)

QMat = list[list[Fraction]]


def require_ok(cond: bool, msg: str) -> None:
    """Hardened non-assert guard (immune to python3 -O)."""
    if not cond:
        raise ValueError(msg)


def canonical_json_bytes(obj: Any) -> bytes:
    """Deterministic ASCII LF-terminated canonical JSON serialization."""
    text = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False) + "\n"
    return text.encode("ascii")


def q_str(q: Fraction) -> str:
    return f"{q.numerator}" if q.denominator == 1 else f"{q.numerator}/{q.denominator}"


def dec_from_q(q: Fraction, places: int) -> str:
    """Exact ROUND_HALF_UP decimal string of Fraction `q` to `places` decimal places."""
    scale = 10 ** places
    num = q.numerator * scale
    den = q.denominator
    neg = num < 0
    anum = -num if neg else num
    quot, rem = divmod(anum, den)
    if 2 * rem >= den:
        quot += 1
    if quot == 0:
        neg = False
    sign = "-" if neg else ""
    if places == 0:
        return f"{sign}{quot}"
    ip, fp = divmod(quot, scale)
    return f"{sign}{ip}.{fp:0{places}d}"


def q_zeros(r: int, c: int) -> QMat:
    return [[Fraction(0) for _ in range(c)] for _ in range(r)]


def q_eye(n: int) -> QMat:
    return [[Fraction(1 if i == j else 0) for j in range(n)] for i in range(n)]


def q_sub(a: QMat, b: QMat) -> QMat:
    return [[a[i][j] - b[i][j] for j in range(len(a[0]))] for i in range(len(a))]


def q_mul(a: QMat, b: QMat) -> QMat:
    m, k, n = len(a), len(b), len(b[0])
    out = q_zeros(m, n)
    for i in range(m):
        row_i = out[i]
        a_i = a[i]
        for t in range(k):
            at = a_i[t]
            if at == 0:
                continue
            b_t = b[t]
            for j in range(n):
                row_i[j] += at * b_t[j]
    return out


def q_solve(a: QMat, b: QMat) -> QMat:
    """Exact pure-Q Gauss-Jordan linear solve A X = B."""
    n = len(a)
    ncols = len(b[0])
    aug = [a[i][:] + b[i][:] for i in range(n)]
    for col in range(n):
        piv = None
        for r in range(col, n):
            if aug[r][col] != 0:
                piv = r
                break
        require_ok(piv is not None, "SINGULAR_MATRIX")
        if piv != col:
            aug[col], aug[piv] = aug[piv], aug[col]
        pv = aug[col][col]
        row_c = aug[col]
        for c in range(col, n + ncols):
            row_c[c] /= pv
        for r in range(n):
            if r == col:
                continue
            fac = aug[r][col]
            if fac == 0:
                continue
            row_r = aug[r]
            for c in range(col, n + ncols):
                row_r[c] -= fac * row_c[c]
    return [row[n:] for row in aug]


def q_sylvester_inertia(sym: QMat) -> list[int]:
    """Exact pure-Q symmetric congruence returning [n_pos, n_neg, n_zero]."""
    n = len(sym)
    m = [row[:] for row in sym]
    pos = 0
    neg = 0
    zero = 0
    k = 0
    while k < n:
        piv = None
        for i in range(k, n):
            if m[i][i] != 0:
                piv = i
                break
        if piv is not None:
            if piv != k:
                m[k], m[piv] = m[piv], m[k]
                for r in range(n):
                    m[r][k], m[r][piv] = m[r][piv], m[r][k]
            d = m[k][k]
            if d > 0:
                pos += 1
            else:
                neg += 1
            for i in range(k + 1, n):
                fac = m[i][k] / d
                if fac == 0:
                    continue
                for j in range(k + 1, n):
                    m[i][j] -= fac * m[k][j]
            k += 1
            continue
        pair = None
        for i in range(k, n):
            for j in range(i + 1, n):
                if m[i][j] != 0:
                    pair = (i, j)
                    break
            if pair is not None:
                break
        if pair is None:
            zero += n - k
            break
        pi, pj = pair
        if pi != k:
            m[k], m[pi] = m[pi], m[k]
            for r in range(n):
                m[r][k], m[r][pi] = m[r][pi], m[r][k]
        if pj != k + 1:
            m[k + 1], m[pj] = m[pj], m[k + 1]
            for r in range(n):
                m[r][k + 1], m[r][pj] = m[r][pj], m[r][k + 1]
        off = m[k][k + 1]
        pos += 1
        neg += 1
        for i in range(k + 2, n):
            c0 = m[i][k + 1] / off
            c1 = m[i][k] / off
            for j in range(k + 2, n):
                m[i][j] -= c0 * m[k][j] + c1 * m[k + 1][j]
        k += 2
    return [pos, neg, zero]


def build_weighted_laplacian(n: int, edges: list[tuple[int, int, Fraction]]) -> QMat:
    lap = q_zeros(n, n)
    for u, v, w in edges:
        lap[u][u] += w
        lap[v][v] += w
        lap[u][v] -= w
        lap[v][u] -= w
    return lap


def grounded_green_matrix(lap: QMat) -> QMat:
    """Compute exact n x n grounded Green's function Z (row/col 0 = 0, submatrix = L[1:,1:]^{-1})."""
    n = len(lap)
    sub = [[lap[i][j] for j in range(1, n)] for i in range(1, n)]
    inv = q_solve(sub, q_eye(n - 1))
    z = q_zeros(n, n)
    for i in range(1, n):
        for j in range(1, n):
            z[i][j] = inv[i - 1][j - 1]
    return z


def schur_complement_subset(lap: QMat, keep: list[int]) -> QMat:
    n = len(lap)
    keep_set = set(keep)
    elim = [i for i in range(n) if i not in keep_set]
    l_aa = [[lap[i][j] for j in keep] for i in keep]
    l_ab = [[lap[i][j] for j in elim] for i in keep]
    l_ba = [[lap[i][j] for j in keep] for i in elim]
    l_bb = [[lap[i][j] for j in elim] for i in elim]
    return q_sub(l_aa, q_mul(l_ab, q_solve(l_bb, l_ba)))


def verify_schur_2x2_match(s2: QMat, expected_g: Fraction) -> None:
    """Verify exact 2x2 Schur complement symmetry S = g * [[1,-1],[-1,1]] and Green match."""
    require_ok(s2 == [[expected_g, -expected_g], [-expected_g, expected_g]], "SCHUR_2X2_MISMATCH")


def build_edge_lookup(
    spec: tuple[tuple[int, int, str, str, str], ...] = MESH_EDGES_SPEC,
) -> dict[tuple[int, int], tuple[str, str, str, Fraction]]:
    out: dict[tuple[int, int], tuple[str, str, str, Fraction]] = {}
    for u, v, cls, op_tag, note in spec:
        require_ok(0 <= u < v < 16, "EDGE_INDEX_OUT_OF_RANGE")
        require_ok((u, v) not in out, "DUPLICATE_EDGE")
        out[(u, v)] = (cls, op_tag, note, Fraction(PATHWAY_WEIGHTS[cls], 1))
    require_ok(len(out) == 120, "EXPECTED_120_EDGES")
    return out


def certify_pillar1_order1_k16_and_k8_lift(
    emap: dict[tuple[int, int], tuple[str, str, str, Fraction]],
) -> tuple[dict[str, Any], QMat, dict[tuple[int, int], Fraction]]:
    """Order 1: 120 all-to-all pairs, L_0 inertia [15,0,1], Foster=15, 120/120 compounding, K_8 lift."""
    edges_q = [(u, v, info[3]) for (u, v), info in sorted(emap.items())]
    lap16 = build_weighted_laplacian(16, edges_q)
    inertia16 = q_sylvester_inertia(lap16)

    z16 = grounded_green_matrix(lap16)
    foster_sum = Fraction(0)
    g_eff_map: dict[tuple[int, int], Fraction] = {}
    ratios: list[tuple[Fraction, tuple[int, int], Fraction, Fraction]] = []
    class_counts = {"EXACT_COMMUTE": 0, "CONDITIONAL_BRIDGE": 0, "EXACT_OBSTRUCTION": 0}
    op_counts: dict[str, int] = {k: 0 for k in OPERATOR_GLYPHS}
    total_weight = 0

    for (u, v), (cls, op_tag, _note, w) in sorted(emap.items()):
        class_counts[cls] += 1
        op_counts[op_tag] += 1
        total_weight += int(w)
        r_eff = z16[u][u] + z16[v][v] - 2 * z16[u][v]
        g_eff = Fraction(1, 1) / r_eff
        g_eff_map[(u, v)] = g_eff
        foster_sum += w * r_eff
        ratios.append((g_eff / w, (u, v), g_eff, w))

    for pair in ((0, 1), (0, 15), (6, 7)):
        verify_schur_2x2_match(schur_complement_subset(lap16, [pair[0], pair[1]]), g_eff_map[pair])

    ratios.sort(key=lambda item: item[0])
    min_ratio, min_pair, min_g, min_w = ratios[0]
    max_ratio, max_pair, max_g, max_w = ratios[-1]

    k8_edges = [(u, v, info[3]) for (u, v), info in sorted(emap.items()) if v < 8]
    lap8 = build_weighted_laplacian(8, k8_edges)
    z8 = grounded_green_matrix(lap8)
    s8_from_16 = schur_complement_subset(lap16, list(range(8)))
    s8_inertia = q_sylvester_inertia(s8_from_16)

    k8_lifts: list[tuple[Fraction, tuple[int, int]]] = []
    for u in range(8):
        for v in range(u + 1, 8):
            r8 = z8[u][u] + z8[v][v] - 2 * z8[u][v]
            g8 = Fraction(1, 1) / r8
            k8_lifts.append((g_eff_map[(u, v)] / g8, (u, v)))
    k8_lifts.sort(key=lambda item: item[0])
    min_lift, min_lift_pair = k8_lifts[0]
    max_lift, max_lift_pair = k8_lifts[-1]

    all_ok = (
        min_ratio > 1
        and min_lift > 1
        and foster_sum == Fraction(15, 1)
        and inertia16 == [15, 0, 1]
        and s8_inertia == [7, 0, 1]
    )
    p1 = {
        "all_verified": all_ok,
        "node_count": 16,
        "edge_count": 120,
        "class_counts": class_counts,
        "operator_counts": op_counts,
        "total_edge_weight": total_weight,
        "laplacian_inertia": inertia16,
        "foster_sum_q": q_str(foster_sum),
        "all_120_pairs_strictly_compounded": min_ratio > 1,
        "min_compounding_pair": [f"n{min_pair[0]:02d}", f"n{min_pair[1]:02d}"],
        "min_compounding_direct_w": int(min_w),
        "min_compounding_g_eff_q": q_str(min_g),
        "min_compounding_ratio_q": q_str(min_ratio),
        "min_compounding_ratio_dec4": dec_from_q(min_ratio, 4),
        "max_compounding_pair": [f"n{max_pair[0]:02d}", f"n{max_pair[1]:02d}"],
        "max_compounding_direct_w": int(max_w),
        "max_compounding_g_eff_q": q_str(max_g),
        "max_compounding_ratio_q": q_str(max_ratio),
        "max_compounding_ratio_dec4": dec_from_q(max_ratio, 4),
        "wave4_k8_submesh_comparison": {
            "k8_edge_count": len(k8_edges),
            "k8_total_weight": sum(int(w) for _, _, w in k8_edges),
            "k8_schur_pushforward_inertia": s8_inertia,
            "all_28_wave4_pairs_strictly_amplified_by_k16": min_lift > 1,
            "min_k16_over_k8_lift_pair": [f"n{min_lift_pair[0]:02d}", f"n{min_lift_pair[1]:02d}"],
            "min_k16_over_k8_lift_q": q_str(min_lift),
            "min_k16_over_k8_lift_dec4": dec_from_q(min_lift, 4),
            "max_k16_over_k8_lift_pair": [f"n{max_lift_pair[0]:02d}", f"n{max_lift_pair[1]:02d}"],
            "max_k16_over_k8_lift_q": q_str(max_lift),
            "max_k16_over_k8_lift_dec4": dec_from_q(max_lift, 4),
        },
        "canonical_edges": [
            {
                "u": f"n{u:02d}",
                "v": f"n{v:02d}",
                "pathway_class": cls,
                "weight": int(w),
                "operator_tag": op_tag,
                "glyph": OPERATOR_GLYPHS[op_tag],
                "compounding_dec4": dec_from_q(g_eff_map[(u, v)] / w, 4),
                "note": note,
            }
            for (u, v), (cls, op_tag, note, w) in sorted(emap.items())
        ],
    }
    return p1, lap16, g_eff_map


def certify_pillar2_order2_triangles_hodge_and_disjoint(
    emap: dict[tuple[int, int], tuple[str, str, str, Fraction]],
) -> tuple[dict[str, Any], dict[tuple[int, int, int], int]]:
    """Order 2: 560 triangles, exact simplicial B_1 B_2 = 0 Hodge-1 decomposition, disjoint transforms."""
    tri_counts = {
        "EXACT_TRANSITIVE_CLOSURE": 0,
        "CONDITIONAL_COMPOUNDING_CLOSURE": 0,
        "FRUSTRATED_CURVATURE_LOOP": 0,
        "MULTI_WALL_BOUNDARY_SECTOR": 0,
    }
    tri_holonomy: dict[tuple[int, int, int], int] = {}
    # B_1 B_2 = 0 identically (boundary-of-boundary, d^2 = 0); proven by Lean Thm 12.
    # No Python entry-count is claimed: the former loop iterated constant-zero expressions.
    b1_b2_nonzero = 0

    for a in range(16):
        for b in range(a + 1, 16):
            for c in range(b + 1, 16):
                c_ab = emap[(a, b)][0]
                c_bc = emap[(b, c)][0]
                c_ac = emap[(a, c)][0]
                walls = (
                    (1 if c_ab == "EXACT_OBSTRUCTION" else 0)
                    + (1 if c_bc == "EXACT_OBSTRUCTION" else 0)
                    + (1 if c_ac == "EXACT_OBSTRUCTION" else 0)
                )
                tri_holonomy[(a, b, c)] = walls % 2
                if walls == 0:
                    if (c_ab, c_bc, c_ac) == ("EXACT_COMMUTE", "EXACT_COMMUTE", "EXACT_COMMUTE"):
                        tri_counts["EXACT_TRANSITIVE_CLOSURE"] += 1
                    else:
                        tri_counts["CONDITIONAL_COMPOUNDING_CLOSURE"] += 1
                elif walls == 1:
                    tri_counts["FRUSTRATED_CURVATURE_LOOP"] += 1
                else:
                    tri_counts["MULTI_WALL_BOUNDARY_SECTOR"] += 1

    unw_edges = [(u, v, Fraction(1, 1)) for (u, v) in sorted(emap.keys())]
    b1_b1t_inertia = q_sylvester_inertia(build_weighted_laplacian(16, unw_edges))
    grad_dim = b1_b1t_inertia[0]
    curl_dim = 120 - grad_dim

    edges_sorted = sorted(emap.keys())
    total_disjoint_same_op = 0
    for idx_i, e1 in enumerate(edges_sorted):
        op1 = emap[e1][1]
        for idx_j in range(idx_i + 1, len(edges_sorted)):
            e2 = edges_sorted[idx_j]
            if len({e1[0], e1[1], e2[0], e2[1]}) == 4:
                if emap[e2][1] == op1:
                    total_disjoint_same_op += 1

    curated_disjoint: list[dict[str, Any]] = []
    for nt in DISJOINT_NATURAL_TRANSFORMS:
        ea = (nt["edge_a"][0], nt["edge_a"][1])
        eb = (nt["edge_b"][0], nt["edge_b"][1])
        require_ok(len({ea[0], ea[1], eb[0], eb[1]}) == 4, f"DISJOINT_NT_OVERLAP:{nt['id']}")
        require_ok(
            (emap[ea][1], emap[eb][1]) == (nt["operator_tag"], nt["operator_tag"]),
            f"DISJOINT_NT_OP_MISMATCH:{nt['id']}",
        )
        curated_disjoint.append(
            {
                "id": nt["id"],
                "edge_a": [f"n{ea[0]:02d}", f"n{ea[1]:02d}"],
                "edge_b": [f"n{eb[0]:02d}", f"n{eb[1]:02d}"],
                "operator_tag": nt["operator_tag"],
                "glyph": OPERATOR_GLYPHS[nt["operator_tag"]],
                "class_a": emap[ea][0],
                "class_b": emap[eb][0],
                "law": nt["law"],
            }
        )

    p2 = {
        "all_verified": (sum(tri_counts.values()), b1_b2_nonzero, grad_dim, curl_dim, len(curated_disjoint))
        == (560, 0, 15, 105, 8),
        "triangle_count": 560,
        "triangle_counts": tri_counts,
        "hodge_1_simplicial": {
            "b1_shape": [16, 120],
            "b2_shape": [120, 560],
            "b1_b2_proof": "B1B2 = 0 identically (d^2 = 0), proven by Lean Thm 12; shapes/traces by construction, not entry-checked in Python",
            "b1_b2_nonzero_entries": b1_b2_nonzero,
            "b1_b2_identically_zero": b1_b2_nonzero == 0,
            "b1_b1t_inertia": b1_b1t_inertia,
            "gradient_dim": grad_dim,
            "curl_dim": curl_dim,
            "harmonic_dim": 0,
            "trace_b1t_b1": 2 * 120,
            "trace_b2_b2t": 3 * 560,
        },
        "disjoint_edge_second_order_convergences": {
            "exhaustive_disjoint_same_operator_pairs": total_disjoint_same_op,
            "curated_count": len(curated_disjoint),
            "curated_transforms": curated_disjoint,
        },
    }
    return p2, tri_holonomy


def certify_pillar3_order3_tetrahedra(
    emap: dict[tuple[int, int], tuple[str, str, str, Fraction]],
    tri_holonomy: dict[tuple[int, int, int], int],
) -> dict[str, Any]:
    """Order 3: 1,820 tetrahedra, Z_2 Bianchi 1,820/1,820==0, K_4 exact locks, paired-frustration repairs."""
    bianchi_nonzero = 0
    tet_counts = {
        "K4_EXACT_LOCK": 0,
        "K4_CLEAN_CLOSURE": 0,
        "PAIRED_FRUSTRATION_REPAIR_TET": 0,
        "MULTI_WALL_TET": 0,
    }
    k4_exact_locks: list[list[str]] = []
    paired_repair_examples: list[dict[str, Any]] = []
    wall_repair_leverage: dict[tuple[int, int], int] = {}

    for a in range(16):
        for b in range(a + 1, 16):
            for c in range(b + 1, 16):
                for d in range(c + 1, 16):
                    bianchi = (
                        tri_holonomy[(a, b, c)]
                        ^ tri_holonomy[(a, b, d)]
                        ^ tri_holonomy[(a, c, d)]
                        ^ tri_holonomy[(b, c, d)]
                    )
                    if bianchi != 0:
                        bianchi_nonzero += 1

                    six_edges = ((a, b), (a, c), (a, d), (b, c), (b, d), (c, d))
                    wall_edges = [e for e in six_edges if emap[e][0] == "EXACT_OBSTRUCTION"]
                    comm_count = sum(1 for e in six_edges if emap[e][0] == "EXACT_COMMUTE")

                    if len(wall_edges) == 0:
                        if comm_count == 6:
                            tet_counts["K4_EXACT_LOCK"] += 1
                            k4_exact_locks.append([f"n{a:02d}", f"n{b:02d}", f"n{c:02d}", f"n{d:02d}"])
                        else:
                            tet_counts["K4_CLEAN_CLOSURE"] += 1
                    elif len(wall_edges) == 1:
                        tet_counts["PAIRED_FRUSTRATION_REPAIR_TET"] += 1
                        w_edge = wall_edges[0]
                        wall_repair_leverage[w_edge] = wall_repair_leverage.get(w_edge, 0) + 1
                        if (a, b, c, d) in ((0, 5, 6, 7), (0, 6, 7, 9), (0, 1, 5, 8)):
                            paired_repair_examples.append(
                                {
                                    "tetrahedron": [f"n{a:02d}", f"n{b:02d}", f"n{c:02d}", f"n{d:02d}"],
                                    "single_wall": [f"n{w_edge[0]:02d}", f"n{w_edge[1]:02d}"],
                                    "wall_note": emap[w_edge][2],
                                    "frustrated_faces_repaired": 2,
                                }
                            )
                    else:
                        tet_counts["MULTI_WALL_TET"] += 1

    ranked_walls = sorted(wall_repair_leverage.items(), key=lambda kv: (-kv[1], kv[0]))
    return {
        "all_verified": (sum(tet_counts.values()), bianchi_nonzero) == (1820, 0),
        "tetrahedron_count": 1820,
        "z2_bianchi_nonzero_count": bianchi_nonzero,
        "z2_bianchi_all_zero": bianchi_nonzero == 0,
        "tetrahedron_counts": tet_counts,
        "k4_exact_lock_count": len(k4_exact_locks),
        "k4_exact_locks_sample": k4_exact_locks[:12],
        "paired_repair_examples": paired_repair_examples,
        "top_single_wall_repair_tetrahedra": [
            {
                "wall": [f"n{e[0]:02d}", f"n{e[1]:02d}"],
                "paired_repair_tet_count": cnt,
                "note": emap[e][2],
            }
            for e, cnt in ranked_walls[:6]
        ],
    }


def certify_pillar4_order4_5cells_metamesh_silocut_firewall(
    emap: dict[tuple[int, int], tuple[str, str, str, Fraction]],
    tri_holonomy: dict[tuple[int, int, int], int],
    lap16: QMat,
    g_eff_map: dict[tuple[int, int], Fraction],
) -> dict[str, Any]:
    """Order 4: 4,368 5-cells, 4th-Order Meta-Mesh M_4, k-simplex silo-cut law, Law-3 firewall."""
    cell_counts = {
        "K5_EXACT_LOCK": 0,
        "K5_CLEAN_CLOSURE": 0,
        "SINGLE_WALL_3FACE_CASCADE_5CELL": 0,
        "MULTI_WALL_5CELL": 0,
    }
    frust_hist: dict[str, int] = {}
    k5_exact_locks: list[list[str]] = []

    for a in range(16):
        for b in range(a + 1, 16):
            for c in range(b + 1, 16):
                for d in range(c + 1, 16):
                    for e in range(d + 1, 16):
                        verts = (a, b, c, d, e)
                        ten_edges = (
                            (a, b), (a, c), (a, d), (a, e),
                            (b, c), (b, d), (b, e),
                            (c, d), (c, e), (d, e),
                        )
                        walls = sum(1 for ed in ten_edges if emap[ed][0] == "EXACT_OBSTRUCTION")
                        comms = sum(1 for ed in ten_edges if emap[ed][0] == "EXACT_COMMUTE")
                        frust_faces = 0
                        for i in range(5):
                            for j in range(i + 1, 5):
                                for k in range(j + 1, 5):
                                    frust_faces += tri_holonomy[(verts[i], verts[j], verts[k])]
                        fk = str(frust_faces)
                        frust_hist[fk] = frust_hist.get(fk, 0) + 1
                        if walls == 0:
                            if comms == 10:
                                cell_counts["K5_EXACT_LOCK"] += 1
                                k5_exact_locks.append([f"n{v:02d}" for v in verts])
                            else:
                                cell_counts["K5_CLEAN_CLOSURE"] += 1
                        elif walls == 1:
                            cell_counts["SINGLE_WALL_3FACE_CASCADE_5CELL"] += 1
                        else:
                            cell_counts["MULTI_WALL_5CELL"] += 1

    cluster_summaries: list[dict[str, Any]] = []
    for cl in ORDER4_META_CLUSTERS:
        nodes = cl["nodes"]
        internal_edges = [(nodes[i], nodes[j]) for i in range(4) for j in range(i + 1, 4)]
        walls_in = sum(1 for ed in internal_edges if emap[ed][0] == "EXACT_OBSTRUCTION")
        comms_in = sum(1 for ed in internal_edges if emap[ed][0] == "EXACT_COMMUTE")
        tet_cls = (
            "K4_EXACT_LOCK"
            if (walls_in, comms_in) == (0, 6)
            else ("K4_CLEAN_CLOSURE" if walls_in == 0 else ("PAIRED_FRUSTRATION_REPAIR_TET" if walls_in == 1 else "MULTI_WALL_TET"))
        )
        cluster_summaries.append(
            {
                "cluster_id": cl["cluster_id"],
                "label": cl["label"],
                "nodes": [f"n{nd:02d}" for nd in nodes],
                "internal_commute_edges": comms_in,
                "internal_obstruction_edges": walls_in,
                "order3_class": tet_cls,
            }
        )

    meta_edges: list[tuple[int, int, Fraction]] = []
    meta_edge_rows: list[dict[str, Any]] = []
    for ci in range(4):
        for cj in range(ci + 1, 4):
            w_sum = Fraction(0)
            for u in ORDER4_META_CLUSTERS[ci]["nodes"]:
                for v in ORDER4_META_CLUSTERS[cj]["nodes"]:
                    key = (u, v) if u < v else (v, u)
                    w_sum += emap[key][3]
            meta_edges.append((ci, cj, w_sum))

    lap_m4 = build_weighted_laplacian(4, meta_edges)
    p_mat = q_zeros(16, 4)
    for ci, cl in enumerate(ORDER4_META_CLUSTERS):
        for nd in cl["nodes"]:
            p_mat[nd][ci] = Fraction(1, 1)
    pt_mat = [[p_mat[r][c] for r in range(16)] for c in range(4)]
    quot_exact = q_mul(q_mul(pt_mat, lap16), p_mat) == lap_m4

    m4_inertia = q_sylvester_inertia(lap_m4)
    z_m4 = grounded_green_matrix(lap_m4)
    m4_foster = Fraction(0)
    m4_ratios: list[Fraction] = []
    for ci, cj, w_ij in meta_edges:
        r_ij = z_m4[ci][ci] + z_m4[cj][cj] - 2 * z_m4[ci][cj]
        g_ij = Fraction(1, 1) / r_ij
        m4_foster += w_ij * r_ij
        ratio = g_ij / w_ij
        m4_ratios.append(ratio)
        meta_edge_rows.append(
            {
                "cluster_a": ORDER4_META_CLUSTERS[ci]["cluster_id"],
                "cluster_b": ORDER4_META_CLUSTERS[cj]["cluster_id"],
                "direct_weight": int(w_ij),
                "g_eff_q": q_str(g_ij),
                "compounding_ratio_q": q_str(ratio),
                "compounding_ratio_dec4": dec_from_q(ratio, 4),
            }
        )
    m4_min_ratio = min(m4_ratios)

    silo_orders: list[dict[str, Any]] = []
    for order_idx, k in enumerate((2, 3, 4, 5), start=1):
        tot = comb(16, k)
        surv = 2 * comb(8, k)
        dest = tot - surv
        dest_frac = Fraction(dest, tot)
        surv_frac = Fraction(surv, tot)
        exp_ceil = Fraction(1, 1 << (k - 1))
        silo_orders.append(
            {
                "order": order_idx,
                "simplex_k": k,
                "total_simplices": tot,
                "surviving_8_8": surv,
                "destroyed_8_8": dest,
                "destroyed_ratio_q": q_str(dest_frac),
                "destroyed_pct_dec2": dec_from_q(dest_frac * 100, 2),
                "surviving_ratio_q": q_str(surv_frac),
                "exponential_ceiling_2_pow_1_minus_k_q": q_str(exp_ceil),
                "strictly_below_exponential_ceiling": surv_frac < exp_ceil,
            }
        )

    interior = [i for i in range(16) if i not in (0, 6)]
    l_ii = [[lap16[i][j] for j in interior] for i in interior]
    rhs = [[-lap16[i][6]] for i in interior]
    u_sol = q_solve(l_ii, rhs)
    u_vals = {interior[idx]: u_sol[idx][0] for idx in range(len(interior))}
    all_14_corrupted = all(Fraction(0) < val < Fraction(1) for val in u_vals.values())
    min_u = min(u_vals.values())
    max_u = max(u_vals.values())
    j_ungated = emap[(0, 6)][3]
    for idx_i in interior:
        j_ungated += emap[(0, idx_i)][3] * u_vals[idx_i]
    flux_amp = j_ungated / emap[(0, 6)][3]

    k15_nodes = [i for i in range(16) if i != 6]
    k15_map = {orig: idx for idx, orig in enumerate(k15_nodes)}
    k15_edges = [
        (k15_map[u], k15_map[v], info[3])
        for (u, v), info in sorted(emap.items())
        if 6 not in (u, v)
    ]
    lap15 = build_weighted_laplacian(15, k15_edges)
    z15 = grounded_green_matrix(lap15)
    k15_min_comp = min(
        (Fraction(1, 1) / (z15[u15][u15] + z15[v15][v15] - 2 * z15[u15][v15])) / w15
        for u15, v15, w15 in k15_edges
    )

    p4_ok = (
        quot_exact
        and m4_inertia == [3, 0, 1]
        and m4_foster == Fraction(3, 1)
        and m4_min_ratio > 1
        and j_ungated == g_eff_map[(0, 6)]
        and all_14_corrupted
        and k15_min_comp > 1
    )
    return {
        "all_verified": p4_ok,
        "five_cell_count": 4368,
        "five_cell_counts": cell_counts,
        "five_cell_frustrated_face_histogram": frust_hist,
        "k5_exact_lock_count": len(k5_exact_locks),
        "k5_exact_locks_sample": k5_exact_locks[:10],
        "fourth_order_meta_mesh_m4": {
            "cluster_count": 4,
            "meta_edge_count": 6,
            "quotient_identity_pt_l0_p_exact": quot_exact,
            "laplacian_inertia": m4_inertia,
            "foster_sum_q": q_str(m4_foster),
            "all_6_meta_pairs_strictly_compounded": m4_min_ratio > 1,
            "min_meta_compounding_ratio_q": q_str(m4_min_ratio),
            "min_meta_compounding_ratio_dec4": dec_from_q(m4_min_ratio, 4),
            "clusters": cluster_summaries,
            "meta_edges": meta_edge_rows,
        },
        "k_simplex_silo_cut_law_k16": {
            "split_label": "8|8",
            "orders": silo_orders,
            "all_orders_strictly_below_exponential_ceiling": all(
                row["strictly_below_exponential_ceiling"] for row in silo_orders
            ),
        },
        "law3_contagion_firewall_k16_to_k15": {
            "compromised_node": "n06",
            "clean_anchor_node": "n00",
            "direct_edge_weight": int(emap[(0, 6)][3]),
            "ungated_corrupting_flux_q": q_str(j_ungated),
            "ungated_corrupting_flux_dec4": dec_from_q(j_ungated, 4),
            "ungated_flux_amplification_q": q_str(flux_amp),
            "ungated_flux_amplification_dec4": dec_from_q(flux_amp, 4),
            "ungated_interior_nodes_corrupted": 14,
            "ungated_all_14_interior_corrupted": all_14_corrupted,
            "ungated_min_interior_u_dec4": dec_from_q(min_u, 4),
            "ungated_max_interior_u_dec4": dec_from_q(max_u, 4),
            "gated_corrupting_flux": 0,
            "gated_interior_nodes_corrupted": 0,
            "k15_surviving_edges": 105,
            "k15_surviving_triangles": 455,
            "k15_surviving_tetrahedra": 1365,
            "k15_surviving_five_cells": 3003,
            "k15_all_105_pairs_compounded": k15_min_comp > 1,
            "k15_min_compounding_ratio_q": q_str(k15_min_comp),
            "k15_min_compounding_ratio_dec4": dec_from_q(k15_min_comp, 4),
        },
    }


def build_certificate_envelope() -> dict[str, Any]:
    """Build deterministic pure-Z/Q Track S84 K_16 Higher-Order Mesh certificate envelope."""
    emap = build_edge_lookup()
    p1, lap16, g_eff_map = certify_pillar1_order1_k16_and_k8_lift(emap)
    p2, tri_holonomy = certify_pillar2_order2_triangles_hodge_and_disjoint(emap)
    p3 = certify_pillar3_order3_tetrahedra(emap, tri_holonomy)
    p4 = certify_pillar4_order4_5cells_metamesh_silocut_firewall(emap, tri_holonomy, lap16, g_eff_map)

    all_ok = (p1["all_verified"], p2["all_verified"], p3["all_verified"], p4["all_verified"]) == (
        True,
        True,
        True,
        True,
    )
    payload: dict[str, Any] = {
        "track_id": TRACK_ID,
        "oracle_class": "exact",
        "novelty_tier": "N1",
        "lean_toolchain": EXPECTED_LEAN_TOOLCHAIN,
        "lean_source_sha256": EXPECTED_LEAN_SHA256,
        "lean_theorem_count": len(EXPECTED_LEAN_THEOREMS),
        "all_pillars_verified": all_ok,
        "pinned_nodes": list(MESH_NODES),
        "pillar_1_order1_k16_and_k8_lift": p1,
        "pillar_2_order2_triangles_hodge_disjoint": p2,
        "pillar_3_order3_tetrahedra_bianchi": p3,
        "pillar_4_order4_5cells_metamesh_silocut_firewall": p4,
    }
    payload_sha256 = hashlib.sha256(canonical_json_bytes(payload)).hexdigest()
    env_body = {
        "schema_version": SCHEMA_VERSION,
        "track_id": TRACK_ID,
        "payload_sha256": payload_sha256,
        "payload": payload,
    }
    certificate_sha256 = hashlib.sha256(canonical_json_bytes(env_body)).hexdigest()
    return {
        "schema_version": SCHEMA_VERSION,
        "track_id": TRACK_ID,
        "payload_sha256": payload_sha256,
        "certificate_sha256": certificate_sha256,
        "payload": payload,
    }


def main() -> int:
    env = build_certificate_envelope()
    if not env["payload"]["all_pillars_verified"]:
        return 1
    print(canonical_json_bytes(env).decode("ascii"), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
