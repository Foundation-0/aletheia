# Executable `CS-24` Gate: Mock-Anchor Silicon Divergence & Non-Commutativity Obstruction

- **Identifier:** `TRACK-S56-CS24-MOCK-ANCHOR-GATE`
- **Schema Version:** `aletheia.track_s56.cs24_mock_anchor.v1`
- **Oracle Class:** `exact` (100% pure Python 3 stdlib: `int`, `fractions.Fraction`, `hashlib`, `hmac`, `json`; **`0`** IEEE-754 floats on trust paths, **`0`** AST float literals, **`0`** `float()` calls, **`0`** bare `assert`s, **`0`** `.isdigit()` calls, **`0`** mathematical RNG calls, **`0`** external dependencies)
- **Novelty Classification:** **`N1`** (executable zero-float `CS-24` governance gate, empirical non-commutativity witness suite anchored to live `UX582HS` hardware receipts, and fail-closed certificate auditor; all classical test-double, hardware-in-the-loop, `pciutils`, and NVML/KMD prior art explicitly quarantined as **`N0`**)
- **Canonical Certificate Digests (`cs24_mock_anchor_certificate.json`, `0o600`, LF-only, `5,837` B):**
  - File / `--standalone --json` SHA-256: `26cc2265d301a6871c618351707ce6e470e6e710d918c5cb8cab42e88fa9ac00`
  - `payload_sha256`: `37ce0870d9a07700fe5ea1f54206e424484dab8e0239074e618528ce22962a25`
  - `certificate_sha256`: `378a5fe8088c0bf7ba331fddf93b7380d0792f72486dd3243ecf1d3e5fcad4d4`
  - Zero-arg / `--check` stdout SHA-256: `9564dd8ff1d277019612e4de3d439c64e83b9416ceb4307d213be2bd68999fe7`

---

## 1. Formal Scope & Non-Commutativity Obstruction

Mocking OS utilities, kernel drivers, or GPU telemetry inside unit tests validates only the author's mental model of a system interface — not the live hardware/kernel contract. Formally, let $\mathcal{M}$ denote the **subprocess-mock projection** and $\mathcal{K}$ denote **unmocked live-silicon execution** emitting a SHA-256-pinned hardware receipt. For any verification witness $w$, let $V_{\mathrm{mock}}(w) \in \{0, 1\}$ indicate whether mocked unit tests pass (`passed == total > 0`) and $V_{\mathrm{silicon}}(w) \in \{0, 1\}$ indicate conformance with real hardware/driver behavior. The exact integer **commutator defect** is:

$$\Delta_{\mathrm{comm}}(w) = V_{\mathrm{mock}}(\mathcal{M}(w)) - V_{\mathrm{silicon}}(\mathcal{K}(w)) \in \{-1, 0, +1\},$$

and the exact rational **false-green divergence rate** over a witness corpus of size $N$ is:

$$R_{\mathrm{div}} = \frac{\#\{w : V_{\mathrm{mock}}(w) = 1 \wedge V_{\mathrm{silicon}}(w) = 0\}}{N} \in \mathbb{Q} \cap [0, 1].$$

Across all four live empirical `UX582HS` hardware/driver defects documented below, $V_{\mathrm{mock}} = 1$ while $V_{\mathrm{silicon}} = 0$, giving $\Delta_{\mathrm{comm}} = +1$ on `4/4` witnesses ($R_{\mathrm{div}} = 1$), constructively proving $\mathcal{M} \circ \mathcal{K} \neq \mathcal{K} \circ \mathcal{M}$.

---

## 2. Prior-Art Quarantine (`N0`) vs. Implementation Scope (`N1`)

| Component | Class | Attribution & Scope |
|---|---|---|
| Fragile test doubles & mock-drift taxonomy | **`N0`** | G. Meszaros (2007), *xUnit Test Patterns* — test-double over-specification and drift against real collaborators. |
| Hardware-in-the-Loop (HIL) validation | **`N0`** | Standard embedded/systems engineering discipline separating simulated tests from physical target verification. |
| Linux `pciutils` `lspci(8)` CLI semantics | **`N0`** | Linux `pciutils` manual: `-s [[[[<domain>]:]<bus>]:][<slot>][.[<func>]]` requires a slot argument (`-Dnn` lists all PCI devices with domain & numeric IDs; `-Dnns` without a slot errors). |
| NVIDIA Linux KMD internal VRAM accounting | **`N0`** | NVIDIA Linux kernel mode driver (`615.78.08`, `GA104M`) internal metadata retention (`2 MiB`) with zero graphics/compute processes. |
| Executable zero-float `CS-24` gate, empirical `UX582HS` commutator witness corpus, & hardened auditor | **`N1`** | Original pure-$\mathbb{Z}/\mathbb{Q}$ implementation in `cs24_mock_anchor_oracle.py`, `cs24_mock_anchor_audit.py`, and `test_cs24_mock_anchor_r5.py`. |

---

## 3. Exact Certified Results

### 3.1 Pillar 1 — Empirical `UX582HS` Non-Commutativity Witnesses & Power-State Commutator

| Witness ID | Subsystem | Mocked Pass | $V_{\mathrm{mock}}$ | $V_{\mathrm{silicon}}$ | $\Delta_{\mathrm{comm}}$ | Live Silicon Reality |
|---|---|---:|---:|---:|---:|---|
| `W1_LSPCI_DNNS_FLAG` | `ml_os.probe.lspci` | `16/16` | `1` | `0` | **`+1`** | Real Linux `pciutils` rejects `-Dnns` without `-s <slot>` (`igpu_model=null`); fix requires `lspci -Dnn` for `0000:00:02.0 [8086:9a60]`. |
| `W2_NVIDIA_KMD_2MIB_BASELINE` | `ml_os.stamp_run.vram_baseline` | `16/16` | `1` | `0` | **`+1`** | NVIDIA Linux driver `615.78.08` (`GA104M`) retains `2 MiB` internal KMD metadata with `0` graphics/compute processes. |
| `W3_UX582HS_DP3_ELAN9009_LUA` | `aletheia_shell.display_hud` | `7/7` | `1` | `0` | **`+1`** | Live `UX582HS` exposes `DP-3` + `elan9009:00-04f3:2c23` and Omarchy `4.5.0` Lua `hl.dsp.exec_cmd` dispatch contract. |
| `W4_AC110W_VS_BAT55W_ROOFLINE` | `siliquant.rtx3080_roofline` | `18/18` | `1` | `0` | **`+1`** | Battery `55 W` `SwPowerCap` vs. AC `110 W` `P0` shifts BF16 GEMM from `31.880` to `35.031` TFLOPS (`+9.8839%`). |

- **Exact Power-State Roofline Ratios (Pure $\mathbb{Q}$):**
  - Power cap ratio: $110 / 55 = \mathbf{2}$
  - BF16 throughput ratio: $35031 / 31880$
  - Exact relative BF16 uplift: $(35031 - 31880) / 31880 = \mathbf{3151/31880}$ (`9.8839%`)

### 3.2 Pillars 2 & 3 — Executable `CS-24` Gate Matrix (`12` Certified Claims + Live Float Probe)

`evaluate_cs24_mock_anchor_gate(claim)` enforces strict schema keysets, strict `int`/`bool`/`str` typing (rejecting `bool`-in-`int` and runtime `float` values as `CS24_RECEIPT_TYPE_CONTAMINATION`), constant-time `hmac.compare_digest` receipt SHA-256 pinning (forbidding all-zero digests), non-mocked subprocess attestation (`subprocess_mocked == False`), `clean_hardware_run == True` / `exit_code == 0` / `anomalies == []` / `determinism_zone == "B"`, verified Linux KMD baseline (`0 <= memory_used_mib <= linux_kmd_baseline_vram_mib <= 4` with `gpu_processes_queried == True` and `graphics_processes_count == 0`, or `0 MiB` on non-Linux), exact power-regime alignment, and non-empty PCI/DRM/CUDA witness strings.

| Group | Claim ID | Domain | Verdict | `CS-24` Reason Code |
|---|---|---|---|---|
| **Mock-Only Divergence (4/4)** | `W1_LSPCI_DNNS_FLAG` | `hardware_probe` | **`DENY`** | `CS24_MOCK_ANCHOR_UNVERIFIED` |
| **Mock-Only Divergence (4/4)** | `W2_NVIDIA_KMD_2MIB_BASELINE` | `driver_isolation` | **`DENY`** | `CS24_MOCK_ANCHOR_UNVERIFIED` |
| **Mock-Only Divergence (4/4)** | `W3_UX582HS_DP3_ELAN9009_LUA` | `display_shell` | **`DENY`** | `CS24_MOCK_ANCHOR_UNVERIFIED` |
| **Mock-Only Divergence (4/4)** | `W4_AC110W_VS_BAT55W_ROOFLINE` | `silicon_roofline` | **`DENY`** | `CS24_MOCK_ANCHOR_UNVERIFIED` |
| **Benign Live Control (3/3)** | `C1_MLOS_PR7_UX582HS_STAMP` | `hardware_probe` | **`ALLOW`** | `[]` (`4ba28f3e…70516a`) |
| **Benign Live Control (3/3)** | `C2_RTX3080_ZONEB_RECEIPT` | `silicon_roofline` | **`ALLOW`** | `[]` (`de1a1b18…51102d`) |
| **Benign Live Control (3/3)** | `C3_SHELL_PR8_DP3_LUA_CONTROL` | `display_shell` | **`ALLOW`** | `[]` (`6f05ea43…7f83b53`) |
| **Forged Receipt Attack (5/5)** | `F1_KMD_ZERO_PROCESS_SPOOF` | `driver_isolation` | **`DENY`** | `CS24_KMD_BASELINE_SPOOFED` |
| **Forged Receipt Attack (5/5)** | `F2_UNPINNED_ZERO_SHA` | `hardware_probe` | **`DENY`** | `CS24_RECEIPT_SHA_UNPINNED` |
| **Forged Receipt Attack (5/5)** | `F3_BATTERY_MASKED_AC_ROOFLINE` | `silicon_roofline` | **`DENY`** | `CS24_POWER_REGIME_MISMATCH` |
| **Forged Receipt Attack (5/5)** | `F4_MOCKED_SUBPROCESS_RECEIPT` | `display_shell` | **`DENY`** | `CS24_SUBPROCESS_MOCKED_IN_RECEIPT` |
| **Forged Receipt Attack (5/5)** | `F5_BOOL_INT_FLOAT_CONTAMINATION` | `driver_isolation` | **`DENY`** | `CS24_RECEIPT_TYPE_CONTAMINATION` |

- **Live Runtime Float Probe (`F5B_RUNTIME_FLOAT_CONTAMINATION`):** Injecting a runtime float via `json.loads("2.0")` into `memory_used_mib` returns **`DENY`** (`["CS24_RECEIPT_TYPE_CONTAMINATION"]`) while keeping zero floats in source AST and zero floats in the JSON certificate.

### 3.3 Pillar 4 — Exact Contingency Matrix & Arithmetic Bounds

- `true_positives = 9`, `true_negatives = 3`, `false_positives = 0`, `false_negatives = 0`, `total_evaluated = 12`
- Exact `sensitivity = 1`, `specificity = 1`, `precision = 1`, `accuracy = 1`
- Binding bounds: `MAX_KMD_BASELINE_MIB = 4`, `MAX_INT_BITS = 3,321` (paired with `MAX_INT_DIGITS = 1,000` decimal pre-parse cap for immunity against Python's `4,300`-digit conversion limit).

---

## 4. Security Architecture & Honest Threat Boundary

- **Atomic `dir_fd` I/O & Cross-Platform Safety:** `read_regular_bytes_capped` and `write_regular_bytes_safe` traverse ancestor chains via `O_RDONLY | O_DIRECTORY | O_NOFOLLOW`, verify root-owned macOS `/var`, `/tmp`, `/etc` -> `/private/*` aliases without resolving user symlinks (`_normalize_darwin_system_prefix`), validate logical `$PWD` without symlinks when its `(st_dev, st_ino)` matches `.`, enforce NUL/lone-surrogate string hygiene on direct `evaluate_cs24_mock_anchor_gate` calls, wrap deleted-CWD `OSError` as `CWD_UNAVAILABLE`, stream reads in `65,536`-byte chunks (`max_bytes <= 64 MiB`), reject non-regular files (tested with scratch `os.mkfifo` inside `TemporaryDirectory`, zero device-path writes), and write atomically via `0o600` `O_CREAT | O_EXCL | O_NOFOLLOW | O_NONBLOCK` temp files with `threading.Lock` + monotonic sequence + CSPRNG token + `os.fsync(fd)` + pre-replace `fstat(fd).st_nlink == 1` + target `st_nlink <= 1` + `os.replace(..., dir_fd)` + `os.fsync(dfd)`.
- **Honest Same-UID POSIX Boundary:** POSIX provides no atomic kernel primitive combining `renameat` with simultaneous link-count enforcement; full isolation against a malicious same-UID writer requires OS directory isolation (`0700` owned directory or distinct UIDs).
- **Honest Verification Boundary:** `verify_certificate_dict(..., full_replay=True)` enforces canonical ASCII+LF framing, constant-time `hmac.compare_digest` over both `payload_sha256` and `certificate_sha256`, iterative JSON-tree validation (`_validate_json_tree`), bijective schema/keyset/length/leaf verification across all `24` dicts, `18` lists, and `146` leaves plus independent division-free algebraic cross-checks inside `secondary_audit_payload` (active under both `full_replay=False` and direct calls), AND full deterministic oracle replay. Because the auditor imports the oracle, `--check` is deterministic replay plus intra-package secondary cross-checking rather than a zero-shared-code independent audit.

---

## 5. Post-Last-Edit Verification Receipts & Frozen Manifest

All verification checks ran strictly sequentially (`OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1`):

| Gate | Scope | Exact Result |
|---|---|---|
| **Unit & Adversarial Regression Suite** | `test_cs24_mock_anchor_r5.py` (`9` test methods, incl. exhaustive `24`-dict / `18`-list / `146`-leaf / container-to-scalar tamper sweep, Darwin alias tests, & Linux-guarded `renameat2`) | **`9/9` PASS** (`~0.45s`, `0` bare `assert`s, `0` AST floats/`float()`, `0` `.isdigit()`, `0` device-path writes) |
| **R4 3-Mode Isolated + Hash-Seed Parity** | `-I -B`, `-I -O -B`, `-I -B -W error`, plus `PYTHONHASHSEED=42 -B` (non-isolated) | **`4/4` bit-identical** (`26cc2265d301a6871c618351707ce6e470e6e710d918c5cb8cab42e88fa9ac00`), `--check` `9564dd8f…` ×4, unit suite `9/9 OK` ×4 (plus `umask 077` `OK`) |
| **Refusal-Site Mutation Suite (Exhaustive)** | `cs24_mock_anchor_oracle.py` + `cs24_mock_anchor_audit.py` | **`51/51` + `110/110` = `161/161` (`100.0%`, `survived=0`, `truncated=False`)** |
| **Exhaustive `SWAP + SUBCOND_DEL` AST `BoolOp`** | `cs24_mock_anchor_oracle.py` + `cs24_mock_anchor_audit.py` | **`33/33` + `30/30` = `63/63` (`100.0%`, `survivors=[]`)** |
| **4-Surface Adversarial Zone-B Fuzzing** | CLI (`25`) + `full_replay=True` (`19`) + `full_replay=False` (`19`) + direct `secondary_audit_payload` (`19`) | **`82/82` (`100.0%`, `bypasses=0`, `crashes=0`)** |
| **Concurrency & Kernel Races** | `16T` distinct + `16T` same + `80T` burst + `550` `renameat2(RENAME_EXCHANGE)` (Linux) + `500` hardlink race | **`0` errors, `0` leaks, `0` clobbers, `0` leftover `.tmp` files** |
| **Static Hygiene & Path-Safety Gate** | Strict ancestor permissions, safety scan, zero-float / zero-assert / zero-CRLF / zero-leak verification | **`PASS`** (`5` files, `2/2` scripts, `0` findings, `0` `.pyc`) |

### Frozen 5-File Manifest

| File | Lines | Bytes | Mode | SHA-256 |
|---|---:|---:|---:|---|
| `cs24_mock_anchor_oracle.py` | `697` | `28,858` | `0o644` | `192ea7c3cc45c87ae0ca5eb63bf38e8f4e542cdd8fe2c3a6f5911721db05f0d1` |
| `cs24_mock_anchor_audit.py` | `809` | `35,711` | `0o644` | `da37c0aa02eb6c389e9a06de27254ac2651fefedc116a86b55ec3fe00e60f042` |
| `test_cs24_mock_anchor_r5.py` | `1,020` | `52,700` | `0o644` | `e551edcd630a46d4157a026ee216e2ef05777811f50075e64aec2dd20b7c917f` |
| `cs24_mock_anchor_certificate.json` | `1` | `5,837` | `0o600` | `26cc2265d301a6871c618351707ce6e470e6e710d918c5cb8cab42e88fa9ac00` |
| `CS24_MOCK_ANCHOR_REPORT.md` | (this report) | — | `0o644` | See directory manifest on freeze |
