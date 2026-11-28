# EXP-Q42b — Prior-Tilt Logit-Bias Obstruction and Fixed-Scale Lattice Remainder Contraction

## Claim & Exact Witness

A single additive constant shift on unbalanced comparable-pair cohorts produces positive net improvement on both raw and flipped objectives without resolving label imbalance:

- **Canonical Prior-Tilt Witness:** `pos_errors = 264`, `neg_errors = 167` (`imbalance = 97 > 0`), `feedback_pos = 18`, `feedback_neg = 7` (`feedback_diff = 11 > 0`), `comparable_pairs = 406`; real net gain `75 + 2 = 77` (`rate = 11/58`, `gcd(77, 406) = 7`), flipped net gain `0 + 52 = 52` (`rate = 26/203`).
- **Balanced-Cohort Gate:** Equal cohort weighting (`n_pos = n_neg = 20`, weight `1/40`, `f_pos = r_neg = 5`) gives exact cleared numerator `balancedNumerator = f_pos * n_neg - r_neg * n_pos = 0`, whereas the imbalanced witness yields `18 * 167 - 7 * 264 = 1158 > 0`.
- **Fixed-Scale Remainder Contraction (`b = 1/50`, `p = 45/60 = 3/4`):** `factor = (3 * b^2) / p = 1/625` (`3 * 1 * 60 < 45 * 2500`), contracting `(390625, 625, 1, 0)` in `3` steps under exact cleared grid bounds `-scale <= 2 * (x - m * scale) <= scale`.

## Lean Package (`lean/PriorTilt`, Lean 4.36.0 Pure `Init`, Zero External Packages)

6 package files (`lakefile.toml`, `lean-toolchain`, `lake-manifest.json`, `PriorTilt.lean`, `PriorTilt/Basic.lean`, `AxiomAudit.lean`; `3` Lean source modules totaling `101` LoC), `9` public theorems in cleared-integer form:

- `netGain_pos_of_gt`, `prior_tilt_imbalance_gain`, `prior_tilt_witness_77_vs_52`
- `balanced_numerator_zero_of_equal`, `balanced_prior_gate_sufficiency`
- `fixed_grid_defect_bound`, `contraction_factor_1_625`, `fixed_grid_remainder_contraction`, `fixed_grid_remainder_two_steps`

`AxiomAudit.lean` prints axioms for all `9` theorems (`propext`, `Quot.sound`), and `verify_s160_q42b_prior_tilt.py` statically enforces zero `sorry`, `admit`, `axiom`, `native_decide`, `Classical`, `#eval`, or `IO.`.

## Verifier, Certificate, & Fail-Closed Guarantees

- **Verifier:** `verify_s160_q42b_prior_tilt.py` (`0` `BoolOp`, `0` `Assert`, `0` float literals, stdlib `int`/`Fraction` only, `dir_fd` `O_DIRECTORY | O_NOFOLLOW | O_NONBLOCK` ancestor + leaf open, `S_ISREG` + `1 MiB` streaming read, UTF-8/BOM/CRLF/LF checks, duplicate-key & non-JSON constant rejection, `MAX_DEPTH = 32`, `MAX_INT_DIGITS = 256`, `RC=2` single-line JSON verifier errors).
- **Certificate:** `s160_q42b_prior_tilt_certificate.json` (`schema = s160.q42b.prior_tilt.v1`, canonical compact `payload_sha256 = 8631c9dfe63b50eec230e749a634d9a779d55b2340de24799e6efeadfc1a3584`).
- **Deterministic Gates:** `3× -I` (`-I -B`, `-I -O -B`, `-I -B -W error`) `--check --json` bit-identical (`SHA-256 = 4c06a6dda40908d4f8bc2b744492723c560f50f9dd4c7d4a3429d84cc9dab050`), `--live-lean --check --json` (`RC=0`, same digest), `test_s160_q42b_r5.py` (`10/10 OK ×3`), `aletheia audit-check --lean-audit --allow-project-import PriorTilt --strict-ancestors --safety-scan --strict-unseeded` (`PASS`, `10` files, `2/2` R4, `3` Lean, `0` findings), and dual `aletheia mutate` **`113/113 = 100.0%` (`default`) & `113/113 = 100.0%` (`--guards require_ok`), `0` survived** (`0` `ast.BoolOp` sites).
