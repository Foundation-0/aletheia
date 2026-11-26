# `Bend 2`, `sm_86` PTX/SASS & `siliconcordat/loom` Compiler & Hardware-Physics Tomography (`18/18` Pure-`Init` Lean `4.36.0`)

Self-contained Aletheia evidence bundle combining primary-source `Bend 2` (`bendlang/bend`) compiler tomography, offline CPU `ptxas --gpu-name=sm_86` + `nvdisasm` (CUDA `13.4`) SASS determinism proofs, and `siliconcordat/loom` roofline analysis with **`18/18` pure-`Init` Lean `4.36.0` theorems** (`17` universal `∀` theorems + `1` 21-clause ground witness suite; `0` imports, `0` warnings, `4` `[]` + `14` `[propext]`, `0` `Quot.sound`, `0` `Classical.choice`, `0` `sorryAx`):

1. **Pillar 1 — `Bend 2` (`bendlang/bend @ 6180be5b...`) TCB & Semantics Tomography:** Measures the exact `4465/1287` (`3.4693x`) untrusted TypeScript (`13,395` L) vs Lean kernel (`3,861` L, `228` theorems, `17` `partial` defs, `400,000,000` fuel) split, confirms HVM removal (`BendRT` + CUDA `cuMemAllocManaged` `nvidia_uvm`), and formalizes the dead-part `Type : Type` Girard caveat alongside predicative level acyclicity.
2. **Pillar 2 — Offline CPU `sm_86` PTX/SASS Determinism Audit:** Verifies `s101_atomic_cas_reduce_f32` (`ATOMG.E.CAS.STRONG.GPU` + `RED.E.ADD.F32.FTZ.RN.STRONG.GPU` + `BSSY`/`BSYNC`/`YIELD`), `s101_det_warp_shfl_reduce_f32` (`5`-stage `SHFL.BFLY` + `FADD`, `0` atomics, `16` regs/thread -> `48/48 = 100.00%` `sm_86` warp occupancy), and `s101_fused_blockh4_dp4a_int32` (`LDG.E.128`, `IADD3`, `PRMT`, `IDP.4A.S8.S8`, `IMAD`, `0` float/atomic instructions, `0 B` spill).
3. **Pillar 3 — `siliconcordat/loom` × Zero-PyTorch `libcuda.so` Roofline:** Proves exact rational launch-overhead collapses (`2,592x` at `4B N=3`, `43,008x` at `27B N=8`), `nvidia_uvm` fault tax (`7,560x` / `125,440x`), symbolic-vs-dense crossovers (`356.6 KB` Graph vs `4.28 MB` Eager vs `12.48 MB` UVM), steady-state PCIe bandwidth obstruction (`1783/60 = 29.7167x`), tridiagonal `det_2 = 0 -> det_3 < 0` inertia obstruction, and `35x` residual gate-contract escape reduction.
4. **Pillar 4 — Pure-`Init` Lean `4.36.0` Companion & R12 Verification Gate:** `CompilerAndLoomTomography.lean` (`18/18` theorems) verified by field-complete `SEC`/`FR0`/`FR1` replay, R12 static + live scrubbed `lean --stdin` verifier, and zero-skip R5 test suite.

## Honest Scope & Novelty Classification (`N1`)

- **Novelty Classification:** **`N1`** (`n2_claims = 0`). `Bend 2` / `BendTT`, NVIDIA `sm_86` PTX/SASS, and `siliconcordat/loom` are established upstream systems (`N0`); this bundle's contribution is a reproducible exact-$\mathbb{Q}$, offline SASS, and pure-`Init` Lean `4.36.0` verification suite unifying those measurements under fail-closed R12 gates.

## Files

- `CompilerAndLoomTomography.lean` — `18/18` pure-`Init` Lean `4.36.0` theorems (`0` external imports, `0` warnings)
- `lean-toolchain` / `lakefile.toml` — Pinned `leanprover/lean4:v4.36.0` build specification
- `s101_compiler_loom_oracle.py` — Pure-$\mathbb{Z}/\mathbb{Q}$ exact oracle and canonical certificate builder
- `verify_s101_compiler_loom.py` — Zone-B hardened standalone verifier, field-complete `SEC`/`FR0`/`FR1` auditor, offline CPU `ptxas`/`nvdisasm` gate, R12 static Lean scanner, and live scrubbed `lean --stdin` kernel verifier
- `s101_compiler_loom_audit.py` — `*_audit.py` CLI wrapper for `evidence-tracks` CI discovery
- `s101_compiler_loom_certificate.json` — Committed canonical zero-float certificate (`11,107` bytes)
- `test_s101_r5.py` — Assertion-free verification, tamper, Zone-B, R12 Lean gate, and live Lean/PTX test suite (`0` skips)
- `REPORT.md` — Complete 4-pillar tomography ledger, theorem table, and file manifest

## Quickstart

```bash
# Verify certificate, full deterministic replay, and live Lean 4.36.0 kernel (18/18 theorems)
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 \
  python3 -I -B verify_s101_compiler_loom.py --check s101_compiler_loom_certificate.json --json

# Run CI audit wrapper
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 \
  python3 -I -B s101_compiler_loom_audit.py --check s101_compiler_loom_certificate.json

# Run full test suite across all three isolated Python modes
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 python3 -I -B test_s101_r5.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 python3 -I -O -B test_s101_r5.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 python3 -I -B -W error test_s101_r5.py
```
