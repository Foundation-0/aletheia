#!/usr/bin/env python3
"""Amended exact-operator modules for Track S108 (PREREG-S108 + Amendment 1).

Implements all three amended H8 tracks with strict Law-5 / CS-08 / Amendment-1 compliance:
  - H8a: Unit-normalized factor embeddings (||A_r||=||B_p||=1) with fixed positive block weights
         (gamma_k, gamma_a, gamma_b), gamma_k^2 + gamma_a^2 + gamma_b^2 = 1, plus block-structured
         projection preventing side-block zeroing; alongside Flat-BPE, Flat-BPE-Sphere,
         Rank1-Kron (S104 Thm 8 obstruction), and seeded Random-Pair adversarial null.
  - H8b: Zero-arccos 2nd-order discrete geodesic turning angle via closed-form spherical parallel
         transport (c_t = (1 - <v_t, P(v_{t-1})>)/2, exact 0 on great circles), head-to-head
         against H-Net 1st-order cosine routing (s_t = (1 - <u_t, u_{t-1}>)/2, N0 anchor),
         BLT auxiliary byte-LM entropy patching, Fixed-4B patching, and BPE on identical raw
         UTF-8 byte windows (strict BPB); plus optional Portal-2 Turing D!=dI vs D=dI diagnostic.
  - H8c: Exact per-batch capacity-limited adaptive loop pacing (r_bar = 2.0, sum r(p) == 2*N)
         on a safe antipodal-proof Hopf-looped core, Markov-coupled MTP-8 vs independent parallel
         MTP-8 vs causal local AR byte decoder (masked variable patch lengths 1..12, primary BPB
         strictly from loop-exit chain-rule head), and unconfounded nullmodem Block-8 E8
         RAM==WIRE==HASH sphere-lattice cell bus at equal wire bits with frozen judge and
         counterfactual latent-edit audit decoder.

Zero bare assert statements; zero arccos calls; CPU-only safe and RTX-3080 ready.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
import struct
from typing import Any, Sequence

import torch
import torch.nn as nn
import torch.nn.functional as F

PREREG_S108_SHA256 = "f0343be88c9f0702855b0631abcf68199bebae93b36e4690aa5ada7eab3628a8"
AMENDMENT1_SHA256 = "5a9ddf089adb378c339d6f0e85b40cab673e80e6161f0f6725aef52728483194"


def safe_l2_normalize(x: torch.Tensor, dim: int = -1, eps: float = 1e-6) -> torch.Tensor:
    """Smooth bounded-gradient L2 normalization safe at ||x|| == 0."""
    norm = torch.sqrt(torch.sum(x * x, dim=dim, keepdim=True) + eps * eps)
    return x / norm


def safe_clamped_unit(x: torch.Tensor, dim: int = -1, floor: float = 1e-4) -> torch.Tensor:
    """Unit projection with hard norm floor preventing antipodal Norm(0) -> NaN."""
    norm = torch.linalg.vector_norm(x, dim=dim, keepdim=True).clamp_min(floor)
    return x / norm


# ---------------------------------------------------------------------------
# Deterministic Byte-Level BPE Codec & Morph-Structural Pair Factorizer (H8a)
# ---------------------------------------------------------------------------


class DeterministicByteBPE:
    """Lossless byte-level BPE tokenizer trained strictly on train bytes (decode(encode(x)) == x)."""

    def __init__(self, vocab_size: int = 512) -> None:
        if vocab_size < 256:
            raise ValueError(f"vocab_size must be >= 256, got {vocab_size}")
        self.target_vocab_size = int(vocab_size)
        self.merges: list[tuple[int, int]] = []
        self.merge_rank: dict[tuple[int, int], int] = {}
        self.id_to_bytes: list[bytes] = [bytes([i]) for i in range(256)]

    @property
    def vocab_size(self) -> int:
        return len(self.id_to_bytes)

    def fit(self, train_bytes: bytes, max_sample_bytes: int = 120_000) -> "DeterministicByteBPE":
        sample = train_bytes[:max_sample_bytes]
        ids = list(sample)
        self.merges = []
        self.merge_rank = {}
        self.id_to_bytes = [bytes([i]) for i in range(256)]
        num_merges = self.target_vocab_size - 256
        for step in range(num_merges):
            if len(ids) < 2:
                break
            counts: dict[tuple[int, int], int] = {}
            for a, b in zip(ids, ids[1:]):
                pair = (a, b)
                counts[pair] = counts.get(pair, 0) + 1
            if not counts:
                break
            best_pair, best_cnt = max(counts.items(), key=lambda kv: (kv[1], -kv[0][0], -kv[0][1]))
            if best_cnt < 2:
                break
            new_id = 256 + step
            self.merges.append(best_pair)
            self.merge_rank[best_pair] = step
            self.id_to_bytes.append(self.id_to_bytes[best_pair[0]] + self.id_to_bytes[best_pair[1]])
            merged: list[int] = []
            i = 0
            n = len(ids)
            pa, pb = best_pair
            while i < n:
                if i + 1 < n and ids[i] == pa and ids[i + 1] == pb:
                    merged.append(new_id)
                    i += 2
                else:
                    merged.append(ids[i])
                    i += 1
            ids = merged
        return self

    def encode(self, data: bytes) -> list[int]:
        if not data:
            return []
        ids = list(data)
        if not self.merges:
            return ids
        while len(ids) >= 2:
            best_rank = len(self.merges)
            best_pair: tuple[int, int] | None = None
            for a, b in zip(ids, ids[1:]):
                r = self.merge_rank.get((a, b))
                if r is not None and r < best_rank:
                    best_rank = r
                    best_pair = (a, b)
            if best_pair is None:
                break
            new_id = 256 + best_rank
            pa, pb = best_pair
            out: list[int] = []
            i = 0
            n = len(ids)
            while i < n:
                if i + 1 < n and ids[i] == pa and ids[i + 1] == pb:
                    out.append(new_id)
                    i += 2
                else:
                    out.append(ids[i])
                    i += 1
            ids = out
        return ids

    def decode(self, token_ids: Sequence[int]) -> bytes:
        return b"".join(self.id_to_bytes[int(t)] for t in token_ids)


class FastByteLevelBPE:
    """Lossless Rust-backed ByteLevel BPE (via `tokenizers`) with exact raw-byte round-trip.

    Falls back cleanly to pure-Python DeterministicByteBPE if `tokenizers` is unavailable.
    Trained strictly on train bytes; exposes `id_to_bytes` for MorphStructPairCodec.
    """

    def __init__(self, vocab_size: int = 4096) -> None:
        if vocab_size < 256:
            raise ValueError(f"vocab_size must be >= 256, got {vocab_size}")
        self.target_vocab_size = int(vocab_size)
        self._tok: Any = None
        self._fallback: DeterministicByteBPE | None = None
        self.id_to_bytes: list[bytes] = []
        # GPT-2 byte-to-unicode bijection used by HuggingFace ByteLevel pre-tokenizer
        bs = list(range(ord("!"), ord("~") + 1)) + list(range(ord("¡"), ord("¬") + 1)) + list(range(ord("®"), ord("ÿ") + 1))
        cs = list(bs)
        n = 0
        for b in range(256):
            if b not in bs:
                bs.append(b)
                cs.append(256 + n)
                n += 1
        self._byte_to_char = {b: chr(c) for b, c in zip(bs, cs)}
        self._char_to_byte = {chr(c): b for b, c in zip(bs, cs)}

    @property
    def vocab_size(self) -> int:
        return len(self.id_to_bytes)

    def fit(self, train_bytes: bytes) -> "FastByteLevelBPE":
        if self.target_vocab_size <= 512:
            self._fallback = DeterministicByteBPE(vocab_size=self.target_vocab_size).fit(train_bytes)
            self.id_to_bytes = list(self._fallback.id_to_bytes)
            return self
        try:
            from tokenizers import Tokenizer, decoders, models, pre_tokenizers, trainers
        except ImportError:
            self._fallback = DeterministicByteBPE(vocab_size=self.target_vocab_size).fit(train_bytes)
            self.id_to_bytes = list(self._fallback.id_to_bytes)
            return self

        tok = Tokenizer(models.BPE())
        tok.pre_tokenizer = pre_tokenizers.ByteLevel(add_prefix_space=False)
        tok.decoder = decoders.ByteLevel()
        trainer = trainers.BpeTrainer(
            vocab_size=self.target_vocab_size,
            min_frequency=2,
            initial_alphabet=pre_tokenizers.ByteLevel.alphabet(),
            show_progress=False,
        )
        # Feed raw UTF-8 text chunks (valid UTF-8 guaranteed by caller; surrogate-free)
        text = train_bytes.decode("utf-8", errors="strict")
        lines = [ln + "\n" for ln in text.splitlines()]
        tok.train_from_iterator(lines, trainer=trainer)
        self._tok = tok
        vocab_map = tok.get_vocab()
        vsize = tok.get_vocab_size()
        id_to_b = [b""] * vsize
        for piece, tid in vocab_map.items():
            id_to_b[int(tid)] = bytes(self._char_to_byte[ch] for ch in piece)
        self.id_to_bytes = id_to_b
        return self

    def encode(self, data: bytes) -> list[int]:
        if self._fallback is not None:
            return self._fallback.encode(data)
        if not data:
            return []
        text = data.decode("utf-8", errors="strict")
        return list(self._tok.encode(text, add_special_tokens=False).ids)

    def decode(self, token_ids: Sequence[int]) -> bytes:
        if self._fallback is not None:
            return self._fallback.decode(token_ids)
        return b"".join(self.id_to_bytes[int(t)] for t in token_ids)


class MorphStructPairCodec:
    """Deterministic injective factorization t -> (root_id, pattern_id) + seeded random-pair null."""

    def __init__(self, id_to_bytes: Sequence[bytes], n_roots: int, n_patterns: int, seed: int = 42) -> None:
        vocab_size = len(id_to_bytes)
        if n_roots * n_patterns < vocab_size:
            raise ValueError(f"n_roots*n_patterns ({n_roots*n_patterns}) must be >= vocab_size ({vocab_size})")
        self.vocab_size = vocab_size
        self.n_roots = int(n_roots)
        self.n_patterns = int(n_patterns)
        self.seed = int(seed)

        # Deterministic morphological/structural assignment (injective collision resolution)
        used: set[tuple[int, int]] = set()
        roots: list[int] = []
        pats: list[int] = []
        for tid, raw in enumerate(id_to_bytes):
            r_pref, p_pref = self._morph_hint(raw, tid)
            r, p = r_pref % self.n_roots, p_pref % self.n_patterns
            if (r, p) in used:
                # Deterministic quadratic/linear probe preserving script/prefix locality
                found = False
                for delta in range(1, self.n_roots * self.n_patterns + 1):
                    p_try = (p + delta) % self.n_patterns
                    r_try = (r + (delta // self.n_patterns)) % self.n_roots
                    if (r_try, p_try) not in used:
                        r, p = r_try, p_try
                        found = True
                        break
                if not found:
                    raise RuntimeError("injective pair table exhausted")
            used.add((r, p))
            roots.append(r)
            pats.append(p)
        self.morph_roots = roots
        self.morph_patterns = pats

        # Adversarial null: SHA-256-seeded Fisher-Yates bijection onto same (n_roots, n_patterns) grid
        grid = [(r, p) for r in range(self.n_roots) for p in range(self.n_patterns)]
        for i in range(len(grid) - 1, 0, -1):
            digest = hashlib.sha256(f"s108_randpair:{self.seed}:{i}".encode("ascii")).digest()
            j = int.from_bytes(digest[:8], "little") % (i + 1)
            grid[i], grid[j] = grid[j], grid[i]
        self.rand_roots = [grid[t][0] for t in range(vocab_size)]
        self.rand_patterns = [grid[t][1] for t in range(vocab_size)]

    def _morph_hint(self, raw: bytes, tid: int) -> tuple[int, int]:
        if not raw:
            return 0, 0
        # Script / structural class from leading UTF-8 byte + suffix/length signature
        b0 = raw[0]
        if b0 < 0x80:
            script = 0 if (65 <= b0 <= 90 or 97 <= b0 <= 122) else (1 if 48 <= b0 <= 57 else 2)
        elif 0xD8 <= b0 <= 0xDB:
            script = 3  # Arabic UTF-8 lead bytes
        elif b0 == 0xE2:
            script = 4  # Mathematical/calculus symbols (U+2xxx)
        else:
            script = 5
        stem = raw[:2] if len(raw) >= 2 else raw
        suffix = raw[-1:]
        r_hash = int.from_bytes(hashlib.sha256(b"R:" + bytes([script]) + stem).digest()[:4], "little")
        p_hash = int.from_bytes(
            hashlib.sha256(b"P:" + bytes([script, min(len(raw), 15)]) + suffix).digest()[:4], "little"
        )
        return r_hash, p_hash

    def verify_injective(self) -> tuple[bool, bool]:
        morph_ok = len(set(zip(self.morph_roots, self.morph_patterns))) == self.vocab_size
        rand_ok = len(set(zip(self.rand_roots, self.rand_patterns))) == self.vocab_size
        return morph_ok, rand_ok


# ---------------------------------------------------------------------------
# H8a Embeddings: Amended Unit-Normalized Block-Weighted Hybrid Kronecker
# ---------------------------------------------------------------------------


class BlockStructuredProj(nn.Module):
    """Maps [kron, root, pattern] blocks into disjoint slices of d_model with fixed energy weights.

    Prevents gradient descent from zeroing out the A_r or B_p side blocks (AMENDMENT1 §4).
    """

    def __init__(
        self,
        d_k_in: int,
        d_a_in: int,
        d_b_in: int,
        d_model: int,
        gammas: tuple[float, float, float],
    ) -> None:
        super().__init__()
        if d_model < 6:
            raise ValueError(f"d_model must be >= 6, got {d_model}")
        d_a_out = max(2, d_model // 4)
        d_b_out = max(2, d_model // 4)
        d_k_out = d_model - d_a_out - d_b_out
        if d_k_out < 2:
            raise ValueError(f"d_model={d_model} too small for 3 disjoint blocks")
        self.d_k_out = d_k_out
        self.d_a_out = d_a_out
        self.d_b_out = d_b_out
        self.proj_k = nn.Linear(d_k_in, d_k_out, bias=False)
        self.proj_a = nn.Linear(d_a_in, d_a_out, bias=False)
        self.proj_b = nn.Linear(d_b_in, d_b_out, bias=False)
        gk, ga, gb = gammas
        g_norm = math.sqrt(gk * gk + ga * ga + gb * gb)
        if gk <= 0.0 or ga <= 0.0 or gb <= 0.0:
            raise ValueError("block weights (gamma_k, gamma_a, gamma_b) must all be strictly positive")
        self.register_buffer("gamma_k", torch.tensor(gk / g_norm, dtype=torch.float32))
        self.register_buffer("gamma_a", torch.tensor(ga / g_norm, dtype=torch.float32))
        self.register_buffer("gamma_b", torch.tensor(gb / g_norm, dtype=torch.float32))

    def forward(self, bk: torch.Tensor, ba: torch.Tensor, bb: torch.Tensor) -> torch.Tensor:
        yk = safe_l2_normalize(self.proj_k(bk), dim=-1) * self.gamma_k
        ya = safe_l2_normalize(self.proj_a(ba), dim=-1) * self.gamma_a
        yb = safe_l2_normalize(self.proj_b(bb), dim=-1) * self.gamma_b
        return torch.cat([yk, ya, yb], dim=-1)


class HybridKronSphereEmbedding(nn.Module):
    """Amended H8a embedding: unit-normalized factors + fixed positive block weights + block-structured proj."""

    def __init__(
        self,
        root_ids: Sequence[int],
        pattern_ids: Sequence[int],
        n_roots: int,
        n_patterns: int,
        d_a: int,
        d_b: int,
        d_model: int,
        gammas: tuple[float, float, float] = (math.sqrt(0.5), math.sqrt(0.25), math.sqrt(0.25)),
        use_block_proj: bool = True,
    ) -> None:
        super().__init__()
        gk, ga, gb = gammas
        if gk <= 0.0 or ga <= 0.0 or gb <= 0.0:
            raise ValueError("gammas must be strictly positive")
        g_norm = math.sqrt(gk * gk + ga * ga + gb * gb)
        self.register_buffer("gamma_k", torch.tensor(gk / g_norm, dtype=torch.float32))
        self.register_buffer("gamma_a", torch.tensor(ga / g_norm, dtype=torch.float32))
        self.register_buffer("gamma_b", torch.tensor(gb / g_norm, dtype=torch.float32))
        self.register_buffer("root_table", torch.tensor(list(root_ids), dtype=torch.long))
        self.register_buffer("pat_table", torch.tensor(list(pattern_ids), dtype=torch.long))
        self.A = nn.Embedding(n_roots, d_a)
        self.B = nn.Embedding(n_patterns, d_b)
        nn.init.normal_(self.A.weight, mean=0.0, std=1.0 / math.sqrt(d_a))
        nn.init.normal_(self.B.weight, mean=0.0, std=1.0 / math.sqrt(d_b))
        self.d_a = d_a
        self.d_b = d_b
        self.d_raw = d_a * d_b + d_a + d_b
        self.d_model = d_model
        self.use_block_proj = use_block_proj
        if use_block_proj:
            self.proj: nn.Module | None = BlockStructuredProj(
                d_a * d_b, d_a, d_b, d_model, (gk / g_norm, ga / g_norm, gb / g_norm)
            )
        else:
            if self.d_raw != d_model:
                raise ValueError(f"when use_block_proj=False, d_a*d_b+d_a+d_b ({self.d_raw}) must equal d_model ({d_model})")
            self.proj = None

    def raw_blocks(self, token_ids: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        r_idx = self.root_table[token_ids]
        p_idx = self.pat_table[token_ids]
        a_hat = safe_l2_normalize(self.A(r_idx), dim=-1)
        b_hat = safe_l2_normalize(self.B(p_idx), dim=-1)
        kron = (a_hat.unsqueeze(-1) * b_hat.unsqueeze(-2)).reshape(*token_ids.shape, self.d_a * self.d_b)
        return kron, a_hat, b_hat

    def raw_hybrid(self, token_ids: torch.Tensor) -> torch.Tensor:
        kron, a_hat, b_hat = self.raw_blocks(token_ids)
        return torch.cat([kron * self.gamma_k, a_hat * self.gamma_a, b_hat * self.gamma_b], dim=-1)

    def forward(self, token_ids: torch.Tensor) -> torch.Tensor:
        kron, a_hat, b_hat = self.raw_blocks(token_ids)
        if self.proj is not None:
            return self.proj(kron, a_hat, b_hat)
        return torch.cat([kron * self.gamma_k, a_hat * self.gamma_a, b_hat * self.gamma_b], dim=-1)


class Rank1KronEmbedding(nn.Module):
    """Pure rank-1 A_r (x) B_p baseline (word2ket / S104 Thm 8 obstruction control)."""

    def __init__(
        self,
        root_ids: Sequence[int],
        pattern_ids: Sequence[int],
        n_roots: int,
        n_patterns: int,
        d_a: int,
        d_b: int,
        d_model: int,
    ) -> None:
        super().__init__()
        self.register_buffer("root_table", torch.tensor(list(root_ids), dtype=torch.long))
        self.register_buffer("pat_table", torch.tensor(list(pattern_ids), dtype=torch.long))
        self.A = nn.Embedding(n_roots, d_a)
        self.B = nn.Embedding(n_patterns, d_b)
        nn.init.normal_(self.A.weight, mean=0.0, std=1.0 / math.sqrt(d_a))
        nn.init.normal_(self.B.weight, mean=0.0, std=1.0 / math.sqrt(d_b))
        self.d_a = d_a
        self.d_b = d_b
        self.proj = nn.Linear(d_a * d_b, d_model, bias=False) if d_a * d_b != d_model else nn.Identity()

    def raw_kron(self, token_ids: torch.Tensor) -> torch.Tensor:
        r_idx = self.root_table[token_ids]
        p_idx = self.pat_table[token_ids]
        a_hat = safe_l2_normalize(self.A(r_idx), dim=-1)
        b_hat = safe_l2_normalize(self.B(p_idx), dim=-1)
        return (a_hat.unsqueeze(-1) * b_hat.unsqueeze(-2)).reshape(*token_ids.shape, self.d_a * self.d_b)

    def forward(self, token_ids: torch.Tensor) -> torch.Tensor:
        return safe_l2_normalize(self.proj(self.raw_kron(token_ids)), dim=-1)


class FlatSphereEmbedding(nn.Module):
    """Flat embedding table with row L2 normalization (verifies C_row=1 is not hybrid-only)."""

    def __init__(self, vocab_size: int, d_model: int, normalize_rows: bool = True) -> None:
        super().__init__()
        self.emb = nn.Embedding(vocab_size, d_model)
        nn.init.normal_(self.emb.weight, mean=0.0, std=1.0 / math.sqrt(d_model))
        self.normalize_rows = normalize_rows

    def forward(self, token_ids: torch.Tensor) -> torch.Tensor:
        out = self.emb(token_ids)
        return safe_l2_normalize(out, dim=-1) if self.normalize_rows else out


# ---------------------------------------------------------------------------
# H8b Operators: Causal Byte Encoder, H-Net Cosine, 2nd-Order Parallel-Transport
# Geodesic Curvature (ZERO arccos), BLT Entropy, & Portal-2 Turing Diagnostic
# ---------------------------------------------------------------------------


class CausalByteEncoder(nn.Module):
    """Strictly causal lightweight byte encoder mapping raw UTF-8 bytes onto S^{d_b - 1}."""

    def __init__(self, d_b: int, kernel_size: int = 4) -> None:
        super().__init__()
        self.d_b = d_b
        self.kernel_size = kernel_size
        self.byte_emb = nn.Embedding(256, d_b)
        self.conv1 = nn.Conv1d(d_b, d_b, kernel_size=kernel_size, groups=d_b)
        self.pw1 = nn.Linear(d_b, d_b)
        self.conv2 = nn.Conv1d(d_b, d_b, kernel_size=kernel_size, groups=d_b)
        self.pw2 = nn.Linear(d_b, d_b)

    def forward(self, byte_ids: torch.Tensor) -> torch.Tensor:
        # byte_ids: [B, L] in 0..255
        x = self.byte_emb(byte_ids)  # [B, L, d_b]
        pad = self.kernel_size - 1
        h = x.transpose(1, 2)
        h = F.pad(h, (pad, 0))
        h = F.silu(self.conv1(h)).transpose(1, 2)
        x = x + self.pw1(h)
        h2 = x.transpose(1, 2)
        h2 = F.pad(h2, (pad, 0))
        h2 = F.silu(self.conv2(h2)).transpose(1, 2)
        x = x + self.pw2(h2)
        return safe_l2_normalize(x, dim=-1)


def hnet_first_order_cosine_score(u: torch.Tensor) -> torch.Tensor:
    """H-Net N0 control: 1st-order smooth cosine step distance s_t = (1 - <u_t, u_{t-1}>)/2 in [0, 1].

    Strictly monotone-equivalent to arccos(<u_t, u_{t-1}>)/pi with bounded gradient everywhere.
    """
    # u: [B, L, d] unit vectors
    b, seq_len, _ = u.shape
    scores = torch.zeros((b, seq_len), dtype=u.dtype, device=u.device)
    if seq_len <= 1:
        return scores
    cos_sim = torch.sum(u[:, 1:, :] * u[:, :-1, :], dim=-1).clamp(-1.0, 1.0)
    scores[:, 1:] = 0.5 * (1.0 - cos_sim)
    return scores


def geodesic_second_order_turning_score(u: torch.Tensor, eps: float = 1e-6) -> torch.Tensor:
    """Amended H8b 2nd-order discrete geodesic curvature via closed-form spherical parallel transport.

    ZERO arccos calls; smooth bounded gradients everywhere (including u_t == u_{t-1} and antipodal).
    Exact 0.0 along any constant-speed great-circle geodesic of arbitrary step size delta; strictly
    positive on genuine directional turns of consecutive tangents.
    """
    b, seq_len, _ = u.shape
    scores = torch.zeros((b, seq_len), dtype=u.dtype, device=u.device)
    if seq_len <= 2:
        return scores
    # Outgoing unit tangent v_{t} in T_{u_{t-1}} S^{d-1} pointing from u_{t-1} toward u_{t}:
    # v_step[:, k] is at base point u[:, k] pointing toward u[:, k+1], for k = 0 .. L-2.
    u_prev = u[:, :-1, :]
    u_next = u[:, 1:, :]
    dot_step = torch.sum(u_next * u_prev, dim=-1, keepdim=True)
    raw_v = u_next - dot_step * u_prev
    v_unit = raw_v / torch.sqrt(torch.sum(raw_v * raw_v, dim=-1, keepdim=True) + eps * eps)

    # Parallel transport v_{k} from T_{u_k} to T_{u_{k+1}} along minimal geodesic u_k -> u_{k+1}:
    # P(w) = w - (<w, u_{k+1}> / (1 + <u_k, u_{k+1}> + eps)) * (u_k + u_{k+1})
    u_a = u[:, :-2, :]        # u_{t-2}
    u_b = u[:, 1:-1, :]       # u_{t-1}
    v_prev = v_unit[:, :-1, :]  # tangent at u_{t-2} toward u_{t-1}
    v_curr = v_unit[:, 1:, :]   # tangent at u_{t-1} toward u_t

    denom = (1.0 + torch.sum(u_a * u_b, dim=-1, keepdim=True)).clamp_min(eps)
    v_prev_pt = v_prev - (torch.sum(v_prev * u_b, dim=-1, keepdim=True) / denom) * (u_a + u_b)
    v_prev_pt = v_prev_pt / torch.sqrt(torch.sum(v_prev_pt * v_prev_pt, dim=-1, keepdim=True) + eps * eps)

    turn_cos = torch.sum(v_curr * v_prev_pt, dim=-1).clamp(-1.0, 1.0)
    scores[:, 2:] = 0.5 * (1.0 - turn_cos)
    return scores


class BLTAuxEntropyRouter(nn.Module):
    """Lightweight causal auxiliary byte-LM producing next-byte Shannon entropy H(b_t | b_{<t})."""

    def __init__(self, d_aux: int = 32, kernel_size: int = 4) -> None:
        super().__init__()
        self.d_aux = d_aux
        self.kernel_size = kernel_size
        self.emb = nn.Embedding(256, d_aux)
        self.conv = nn.Conv1d(d_aux, d_aux, kernel_size=kernel_size, groups=d_aux)
        self.proj = nn.Linear(d_aux, 256)

    def forward(self, byte_ids: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        # Returns (aux_logits [B, L, 256] predicting byte_ids[:, t] from byte_ids[:, <t],
        #          normalized_entropy [B, L] in [0, 1])
        b, seq_len = byte_ids.shape
        # Causal shift right by 1 (prepend byte 0) so position t sees strictly bytes < t
        shifted = torch.zeros_like(byte_ids)
        if seq_len > 1:
            shifted[:, 1:] = byte_ids[:, :-1]
        x = self.emb(shifted).transpose(1, 2)
        h = F.silu(self.conv(F.pad(x, (self.kernel_size - 1, 0)))).transpose(1, 2)
        logits = self.proj(h)
        log_p = F.log_softmax(logits.float(), dim=-1)
        probs = log_p.exp()
        entropy_bits = -(probs * log_p).sum(dim=-1) / math.log(2.0)  # in [0, 8]
        return logits, (entropy_bits / 8.0).to(logits.dtype)


def hnet_ratio_balance_loss(boundary_probs: torch.Tensor, target_rate: float) -> torch.Tensor:
    """Differentiable H-Net-style load-balance + rate regularization targeting mean rate 1/C*."""
    # boundary_probs: [B, L] in [0, 1], with position 0 forced to 1.0
    hard = (boundary_probs >= 0.5).to(boundary_probs.dtype)
    f_frac = hard.mean()
    g_mean = boundary_probs.mean()
    # Balanced ratio term + smooth target-rate anchor
    ratio_term = (1.0 - target_rate) * (1.0 - f_frac) * (1.0 - g_mean) + target_rate * f_frac * g_mean
    rate_anchor = (g_mean - target_rate) ** 2
    return ratio_term + 4.0 * rate_anchor


def turing_boundary_nucleation_diagnostic(
    seq_len: int,
    d_u: float = 1.0,
    d_v: float = 10.0,
    steps: int = 1000,
    dt: float = 0.02,
    seed: int = 42,
) -> dict[str, Any]:
    """Portal-2 diagnostic: discrete path-graph reaction-diffusion M = I (x) J - L (x) D.

    Uses Portal 2's exact witness J = [[7, 15], [-21/2, -10]] (tr=-3, det=87.5):
      - Differential D = diag(1, 10): unstable band (5/2, 7/2), predicted ring/path period in [2.60, 3.45].
      - Equal D = diag(d, d): exact zero Turing instability (O2.1 obstruction null).
    """
    if seq_len < 6:
        raise ValueError(f"seq_len must be >= 6, got {seq_len}")
    gen = torch.Generator(device="cpu")
    gen.manual_seed(seed)
    u = torch.randn((seq_len,), generator=gen, dtype=torch.float64) * 1e-2
    v = torch.randn((seq_len,), generator=gen, dtype=torch.float64) * 1e-2
    u = u - u.mean()
    v = v - v.mean()
    init_norm = float(torch.sqrt((u * u + v * v).sum()).item())

    j11, j12, j21, j22 = 7.0, 15.0, -10.5, -10.0
    for _ in range(steps):
        # Path Laplacian L x
        lu = torch.zeros_like(u)
        lv = torch.zeros_like(v)
        lu[1:] += u[1:] - u[:-1]
        lu[:-1] += u[:-1] - u[1:]
        lv[1:] += v[1:] - v[:-1]
        lv[:-1] += v[:-1] - v[1:]
        du_dt = j11 * u + j12 * v - d_u * lu
        dv_dt = j21 * u + j22 * v - d_v * lv
        u = u + dt * du_dt
        v = v + dt * dv_dt

    final_norm = float(torch.sqrt((u * u + v * v).sum()).item())
    growth_ratio = final_norm / max(init_norm, 1e-12)
    # Count local peaks of activator u as nucleated patch boundaries
    peaks = [
        i
        for i in range(1, seq_len - 1)
        if float(u[i].item()) > float(u[i - 1].item()) and float(u[i].item()) >= float(u[i + 1].item())
    ]
    mean_period = float((peaks[-1] - peaks[0]) / max(len(peaks) - 1, 1)) if len(peaks) >= 2 else float(seq_len)
    return {
        "seq_len": seq_len,
        "d_u": d_u,
        "d_v": d_v,
        "equal_diffusion": abs(d_u - d_v) < 1e-12,
        "growth_ratio": round(growth_ratio, 6),
        "nucleated": growth_ratio > 1.0,
        "num_peaks": len(peaks),
        "mean_boundary_period": round(mean_period, 4),
    }


# ---------------------------------------------------------------------------
# Shared Causal Transformer Core & Safe Hopf-Looped Core (H8a, H8b, H8c)
# ---------------------------------------------------------------------------


class CausalSelfAttnBlock(nn.Module):
    """Standard pre-norm causal multi-head self-attention + SwiGLU/GELU MLP block."""

    def __init__(self, d_model: int, n_heads: int, mlp_mult: int = 4) -> None:
        super().__init__()
        if d_model % n_heads != 0:
            raise ValueError(f"d_model ({d_model}) must be divisible by n_heads ({n_heads})")
        self.d_model = d_model
        self.n_heads = n_heads
        self.head_dim = d_model // n_heads
        self.norm1 = nn.RMSNorm(d_model)
        self.qkv = nn.Linear(d_model, 3 * d_model, bias=False)
        self.out_proj = nn.Linear(d_model, d_model, bias=False)
        self.norm2 = nn.RMSNorm(d_model)
        d_ff = d_model * mlp_mult
        self.fc1 = nn.Linear(d_model, d_ff, bias=False)
        self.fc2 = nn.Linear(d_ff, d_model, bias=False)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        b, t, d = x.shape
        h = self.norm1(x)
        qkv = self.qkv(h).reshape(b, t, 3, self.n_heads, self.head_dim)
        q, k, v = qkv[:, :, 0].transpose(1, 2), qkv[:, :, 1].transpose(1, 2), qkv[:, :, 2].transpose(1, 2)
        attn = F.scaled_dot_product_attention(q, k, v, is_causal=True)
        attn = attn.transpose(1, 2).reshape(b, t, d)
        x = x + self.out_proj(attn)
        x = x + self.fc2(F.gelu(self.fc1(self.norm2(x))))
        return x


class SafeHopfLoopCore(nn.Module):
    """Antipodal-safe Clifford-torus / Hopf-phase looped core (COLLAB-INKLING2 B1-B5 repairs).

    - Clamped alpha_r = sigmoid(alpha_raw) * (pi / 2)
    - Hard norm floor 1e-4 preventing Norm(0) -> NaN on exact antipodal F(h) = -h
    - Explicit non-aliased irrational/declared Hopf 2x2 block phase applied to state update
      between consecutive passes (never cancelling in QK)
    - Per-pass KV recompute (no stale cross-pass KV reuse)
    """

    def __init__(self, d_model: int, n_heads: int, n_inner_layers: int = 2, max_loops: int = 4) -> None:
        super().__init__()
        if d_model % 2 != 0:
            raise ValueError(f"d_model must be even for 2x2 Hopf phase blocks, got {d_model}")
        self.d_model = d_model
        self.n_inner_layers = n_inner_layers
        self.max_loops = max_loops
        self.blocks = nn.ModuleList([CausalSelfAttnBlock(d_model, n_heads, mlp_mult=2) for _ in range(n_inner_layers)])
        self.alpha_raw = nn.Parameter(torch.full((max_loops,), -0.6))
        # Explicit declared per-pass phase frequencies (golden-ratio spaced to avoid R_test aliasing)
        freqs = torch.arange(1, d_model // 2 + 1, dtype=torch.float32) * (math.pi * (math.sqrt(5.0) - 1.0))
        self.register_buffer("hopf_freqs", freqs)

    def apply_hopf_phase(self, x: torch.Tensor, pass_idx: int) -> torch.Tensor:
        theta = self.hopf_freqs * float(pass_idx + 1) * 0.25
        c = torch.cos(theta).to(x.dtype)
        s = torch.sin(theta).to(x.dtype)
        x_even = x[..., 0::2]
        x_odd = x[..., 1::2]
        out_even = x_even * c - x_odd * s
        out_odd = x_even * s + x_odd * c
        return torch.stack([out_even, out_odd], dim=-1).reshape_as(x)

    def slerp_step(self, h: torch.Tensor, delta: torch.Tensor, pass_idx: int) -> torch.Tensor:
        alpha = torch.sigmoid(self.alpha_raw[pass_idx % self.max_loops]) * (0.5 * math.pi)
        rot_delta = self.apply_hopf_phase(safe_clamped_unit(delta, dim=-1, floor=1e-4), pass_idx)
        mixed = torch.cos(alpha) * h + torch.sin(alpha) * rot_delta
        return safe_clamped_unit(mixed, dim=-1, floor=1e-4)

    def run_pass(self, h: torch.Tensor, pass_idx: int) -> torch.Tensor:
        y = h
        for blk in self.blocks:
            y = blk(y)
        return self.slerp_step(h, y - h, pass_idx)

    def forward_with_depths(
        self,
        h0: torch.Tensor,
        depths: torch.Tensor,
        ste_weights: torch.Tensor | None = None,
    ) -> tuple[torch.Tensor, dict[str, float]]:
        """Execute up to max_loops passes and gather per-position exit state h^{(r(p))}.

        h0: [B, P, d] unit-norm inputs
        depths: [B, P] integer tensor in {1, ..., max_loops}
        ste_weights: optional [B, P, max_loops] differentiable straight-through weights
        """
        h = safe_clamped_unit(h0, dim=-1, floor=1e-4)
        states: list[torch.Tensor] = []
        diffs: list[torch.Tensor] = []
        max_r = int(depths.max().item()) if depths.numel() > 0 else 1
        max_r = max(1, min(max_r, self.max_loops))
        for r in range(max_r):
            h_next = self.run_pass(h, r)
            diffs.append(torch.linalg.vector_norm(h_next - h, dim=-1).mean())
            states.append(h_next)
            h = h_next
        while len(states) < self.max_loops:
            states.append(states[-1])
        stacked = torch.stack(states, dim=2)  # [B, P, max_loops, d]
        if ste_weights is not None:
            out = torch.sum(stacked * ste_weights.unsqueeze(-1), dim=2)
        else:
            idx = (depths.clamp(1, self.max_loops) - 1).unsqueeze(-1).unsqueeze(-1).expand(-1, -1, 1, self.d_model)
            out = torch.gather(stacked, dim=2, index=idx).squeeze(2)
        norms = torch.linalg.vector_norm(out, dim=-1)
        rho_vals = [
            float((diffs[i] / diffs[i - 1].clamp_min(1e-8)).item()) for i in range(1, len(diffs))
        ]
        diag = {
            "max_unit_norm_drift": float((norms - 1.0).abs().max().item()),
            "mean_empirical_rho": float(sum(rho_vals) / len(rho_vals)) if rho_vals else 0.0,
        }
        return out, diag


# ---------------------------------------------------------------------------
# H8c Part 1: Exact Per-Batch Capacity-Limited Adaptive Loop Pacer (r_bar = 2.0)
# ---------------------------------------------------------------------------


def allocate_exact_loop_budget(
    scores: torch.Tensor,
    target_mean_r: float = 2.0,
    min_r: int = 1,
    max_r: int = 4,
) -> torch.Tensor:
    """Deterministic exact per-batch loop depth allocator: sum(r) == round(target_mean_r * B * P).

    scores: [B, P, max_r - min_r] marginal utility scores for extra loop passes (2, 3, ..., max_r).
    Guarantees monotonic nesting (a patch cannot get pass 3 without pass 2) by descending sort
    over cumulative utility or per-step diminishing scores, achieving exact per-batch CS-08 FLOP parity.
    """
    if scores.ndim != 3:
        raise ValueError(f"scores must be 3D [B, P, max_r - min_r], got shape {tuple(scores.shape)}")
    b, p, k_extra = scores.shape
    if k_extra != max_r - min_r:
        raise ValueError(f"scores last dim ({k_extra}) must equal max_r - min_r ({max_r - min_r})")
    total_slots = b * p
    target_total = int(round(target_mean_r * total_slots))
    extra_budget = target_total - min_r * total_slots
    if extra_budget < 0 or extra_budget > k_extra * total_slots:
        raise ValueError(f"infeasible target_mean_r={target_mean_r} for [{min_r}, {max_r}]")

    # Enforce diminishing marginal scores across extra passes so greedy top-k is automatically nested
    # (pass 2 score >= pass 3 score >= pass 4 score per token).
    mono_scores = scores.detach().clone()
    for step in range(1, k_extra):
        mono_scores[:, :, step] = torch.minimum(
            mono_scores[:, :, step],
            mono_scores[:, :, step - 1] - 1e-6,
        )
    flat = mono_scores.reshape(-1)
    depths = torch.full((b, p), min_r, dtype=torch.long, device=scores.device)
    if extra_budget == 0:
        return depths
    _, top_idx = torch.topk(flat, k=extra_budget, largest=True, sorted=False)
    selected = torch.zeros_like(flat, dtype=torch.long)
    selected[top_idx] = 1
    depths = depths + selected.reshape(b, p, k_extra).sum(dim=-1)
    return depths


class AdaptiveLoopPacer(nn.Module):
    """Causal loop-depth router with exact per-batch capacity budgeting and STE gradients.

    Takes ONLY causal current patch representation + previous-step surprisal (ZERO current-target leakage!).
    """

    def __init__(self, d_model: int, max_r: int = 4, target_mean_r: float = 2.0) -> None:
        super().__init__()
        self.d_model = d_model
        self.max_r = max_r
        self.target_mean_r = target_mean_r
        self.router = nn.Sequential(
            nn.Linear(d_model + 1, d_model // 2),
            nn.SiLU(),
            nn.Linear(d_model // 2, max_r - 1),
        )

    def forward(
        self,
        patch_x: torch.Tensor,
        prev_surprisal: torch.Tensor,
        mode: str = "adaptive",
        seed: int | None = None,
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """Return (exact_depths [B, P], ste_weights [B, P, max_r], anti_collapse_loss)."""
        b, p, _ = patch_x.shape
        if mode == "uniform":
            r_int = int(round(self.target_mean_r))
            depths = torch.full((b, p), r_int, dtype=torch.long, device=patch_x.device)
            weights = F.one_hot(depths - 1, num_classes=self.max_r).to(patch_x.dtype)
            return depths, weights, torch.zeros((), dtype=patch_x.dtype, device=patch_x.device)

        if mode == "random":
            gen = torch.Generator(device="cpu")
            if seed is not None:
                gen.manual_seed(seed)
            rand_scores = torch.randn((b, p, self.max_r - 1), generator=gen, dtype=patch_x.dtype).to(patch_x.device)
            depths = allocate_exact_loop_budget(rand_scores, target_mean_r=self.target_mean_r, min_r=1, max_r=self.max_r)
            weights = F.one_hot(depths - 1, num_classes=self.max_r).to(patch_x.dtype)
            return depths, weights, torch.zeros((), dtype=patch_x.dtype, device=patch_x.device)

        if mode != "adaptive":
            raise ValueError(f"unknown pacing mode: {mode!r}")

        feat = torch.cat([patch_x, prev_surprisal.unsqueeze(-1)], dim=-1)
        extra_logits = self.router(feat)  # [B, P, max_r - 1]
        depths = allocate_exact_loop_budget(extra_logits, target_mean_r=self.target_mean_r, min_r=1, max_r=self.max_r)
        hard_one_hot = F.one_hot(depths - 1, num_classes=self.max_r).to(patch_x.dtype)
        # Soft distribution over {1..max_r} for STE gradient flow + anti-collapse entropy bonus
        full_logits = torch.cat(
            [torch.zeros((b, p, 1), dtype=patch_x.dtype, device=patch_x.device), extra_logits], dim=-1
        )
        soft_probs = F.softmax(full_logits, dim=-1)
        ste_weights = hard_one_hot - soft_probs.detach() + soft_probs
        # Expected depth anchor + diversity encouragement preventing collapse to uniform r=2
        expected_r = torch.sum(
            soft_probs * torch.arange(1, self.max_r + 1, dtype=patch_x.dtype, device=patch_x.device), dim=-1
        ).mean()
        mean_dist = soft_probs.mean(dim=(0, 1)).clamp_min(1e-6)
        entropy = -(mean_dist * torch.log(mean_dist)).sum()
        aux_loss = (expected_r - self.target_mean_r) ** 2 - 0.05 * entropy
        return depths, ste_weights, aux_loss


# ---------------------------------------------------------------------------
# H8c Part 2: Markov-Coupled MTP-8 vs Parallel MTP-8 vs Local AR Byte Decoder
# ---------------------------------------------------------------------------


def pad_variable_patches_to_blocks(
    byte_seq: torch.Tensor,
    patch_starts: Sequence[int],
    block_size: int = 8,
) -> tuple[torch.Tensor, torch.Tensor, list[int]]:
    """Pack variable-length patches (including length > block_size via sub-blocks) into fixed [K, block_size].

    Returns (target_bytes [K, block_size], valid_mask [K, block_size], parent_patch_idx [K]).
    Patch k predicts patch k+1 (strictly causal: never predicts its own bytes).
    """
    seq_len = int(byte_seq.numel())
    starts = list(patch_starts) + [seq_len]
    targets: list[list[int]] = []
    masks: list[list[float]] = []
    parents: list[int] = []
    for k in range(len(starts) - 2):
        # Patch k predicts bytes of patch k+1
        s_next, e_next = starts[k + 1], starts[k + 2]
        raw = [int(x) for x in byte_seq[s_next:e_next].tolist()]
        if not raw:
            continue
        for off in range(0, len(raw), block_size):
            chunk = raw[off : off + block_size]
            pad_len = block_size - len(chunk)
            targets.append(chunk + [0] * pad_len)
            masks.append([1.0] * len(chunk) + [0.0] * pad_len)
            parents.append(k)
    if not targets:
        return (
            torch.zeros((0, block_size), dtype=torch.long, device=byte_seq.device),
            torch.zeros((0, block_size), dtype=torch.float32, device=byte_seq.device),
            [],
        )
    return (
        torch.tensor(targets, dtype=torch.long, device=byte_seq.device),
        torch.tensor(masks, dtype=torch.float32, device=byte_seq.device),
        parents,
    )


class MarkovMTP8Head(nn.Module):
    """Low-rank Markov-coupled 8-byte patch decoder (supporting both teacher-forced & unrolled eval)."""

    def __init__(self, d_model: int, block_size: int = 8, markov_rank: int = 64) -> None:
        super().__init__()
        self.d_model = d_model
        self.block_size = block_size
        self.markov_rank = markov_rank
        self.init_proj = nn.Linear(d_model, markov_rank)
        self.step_cond = nn.ModuleList([nn.Linear(d_model, markov_rank, bias=False) for _ in range(block_size)])
        self.byte_emb = nn.Embedding(256, markov_rank)
        self.state_step = nn.Linear(markov_rank, markov_rank)
        self.out_head = nn.Linear(markov_rank, 256)

    def forward(
        self,
        h_exit: torch.Tensor,
        target_bytes: torch.Tensor | None = None,
        unroll: bool = False,
    ) -> torch.Tensor:
        """h_exit: [N, d_model]; returns logits [N, block_size, 256]."""
        state = torch.tanh(self.init_proj(h_exit))
        logits_steps: list[torch.Tensor] = []
        prev_byte: torch.Tensor | None = None
        for j in range(self.block_size):
            if j == 0:
                s_in = state + self.step_cond[j](h_exit)
            else:
                if unroll or target_bytes is None:
                    b_in = prev_byte if prev_byte is not None else torch.zeros(h_exit.shape[0], dtype=torch.long, device=h_exit.device)
                else:
                    b_in = target_bytes[:, j - 1]
                s_in = self.state_step(state) + self.byte_emb(b_in) + self.step_cond[j](h_exit)
            state = torch.tanh(s_in)
            step_logits = self.out_head(state)
            logits_steps.append(step_logits)
            prev_byte = step_logits.argmax(dim=-1)
        return torch.stack(logits_steps, dim=1)


class ParallelMTP8Head(nn.Module):
    """Independent parallel 8-byte patch decoder (explicit intra-patch coupling obstruction baseline)."""

    def __init__(self, d_model: int, block_size: int = 8) -> None:
        super().__init__()
        self.block_size = block_size
        self.heads = nn.ModuleList([nn.Linear(d_model, 256) for _ in range(block_size)])

    def forward(
        self,
        h_exit: torch.Tensor,
        target_bytes: torch.Tensor | None = None,
        unroll: bool = False,
    ) -> torch.Tensor:
        _ = (target_bytes, unroll)
        return torch.stack([head(h_exit) for head in self.heads], dim=1)


class LocalARByteDecoder(nn.Module):
    """Causal 1-layer autoregressive local byte decoder conditioned on loop-exit patch state."""

    def __init__(self, d_model: int, d_dec: int = 64, n_heads: int = 4, block_size: int = 8) -> None:
        super().__init__()
        self.block_size = block_size
        self.cond_proj = nn.Linear(d_model, d_dec)
        self.byte_emb = nn.Embedding(256, d_dec)
        self.pos_emb = nn.Embedding(block_size, d_dec)
        self.block = CausalSelfAttnBlock(d_dec, n_heads, mlp_mult=2)
        self.out_head = nn.Linear(d_dec, 256)

    def forward(
        self,
        h_exit: torch.Tensor,
        target_bytes: torch.Tensor | None = None,
        unroll: bool = False,
    ) -> torch.Tensor:
        n = h_exit.shape[0]
        cond = self.cond_proj(h_exit).unsqueeze(1)  # [N, 1, d_dec]
        pos = torch.arange(self.block_size, device=h_exit.device)
        if not unroll and target_bytes is not None:
            shifted = torch.zeros_like(target_bytes)
            if self.block_size > 1:
                shifted[:, 1:] = target_bytes[:, :-1]
            x = self.byte_emb(shifted) + self.pos_emb(pos).unsqueeze(0) + cond
            return self.out_head(self.block(x))
        # Autoregressive unrolled decode
        gen_bytes = torch.zeros((n, self.block_size), dtype=torch.long, device=h_exit.device)
        logits_steps: list[torch.Tensor] = []
        for j in range(self.block_size):
            x = self.byte_emb(gen_bytes[:, : j + 1]) + self.pos_emb(pos[: j + 1]).unsqueeze(0) + cond
            step_logits = self.out_head(self.block(x))[:, -1, :]
            logits_steps.append(step_logits)
            if j + 1 < self.block_size:
                gen_bytes[:, j + 1] = step_logits.argmax(dim=-1)
        return torch.stack(logits_steps, dim=1)


# ---------------------------------------------------------------------------
# H8c Part 3: Unconfounded Block-8 E8 nullmodem RAM==WIRE==HASH Cell Bus
# ---------------------------------------------------------------------------


def build_e8_root_codebook() -> torch.Tensor:
    """Construct exact 240 unit-normalized E8 root vectors (raw squared norm == 2 -> unit norm on S^7)."""
    roots: list[list[float]] = []
    # 112 Type-I roots: permutations of (+-1, +-1, 0, 0, 0, 0, 0, 0)
    for i in range(8):
        for j in range(i + 1, 8):
            for si in (-1.0, 1.0):
                for sj in (-1.0, 1.0):
                    vec = [0.0] * 8
                    vec[i] = si
                    vec[j] = sj
                    roots.append(vec)
    # 128 Type-II roots: (+-1/2)^8 with even number of minus signs
    for mask in range(256):
        neg = bin(mask).count("1")
        if neg % 2 == 0:
            vec = [-0.5 if ((mask >> bit) & 1) else 0.5 for bit in range(8)]
            roots.append(vec)
    if len(roots) != 240:
        raise RuntimeError(f"expected 240 E8 roots, built {len(roots)}")
    mat = torch.tensor(roots, dtype=torch.float32)
    return mat / math.sqrt(2.0)


@dataclass(frozen=True)
class NullModemCell:
    """Self-verifying RAM == WIRE == HASH binary cell for Block-8 E8 sphere-lattice states."""

    magic: bytes
    version: int
    n_blocks: int
    indices: bytes
    sha256_digest: bytes

    HEADER_FMT = "!4sBBH"  # magic(4) + version(1) + n_blocks(1) + reserved(2) = 8 bytes
    HASH_BYTES = 32

    @classmethod
    def pack(cls, indices: Sequence[int]) -> bytes:
        n_blocks = len(indices)
        if n_blocks <= 0 or n_blocks > 255:
            raise ValueError(f"n_blocks must be in 1..255, got {n_blocks}")
        for idx in indices:
            if not (0 <= int(idx) < 240):
                raise ValueError(f"E8 root index out of range 0..239: {idx}")
        header = struct.pack(cls.HEADER_FMT, b"NM8S", 1, n_blocks, 0)
        payload = bytes(int(i) for i in indices)
        digest = hashlib.sha256(header + payload).digest()
        return header + payload + digest

    @classmethod
    def verify_and_unpack(cls, wire: bytes) -> "NullModemCell":
        min_len = struct.calcsize(cls.HEADER_FMT) + 1 + cls.HASH_BYTES
        if len(wire) < min_len:
            raise ValueError(f"cell too short: {len(wire)} < {min_len}")
        hdr_len = struct.calcsize(cls.HEADER_FMT)
        magic, version, n_blocks, reserved = struct.unpack(cls.HEADER_FMT, wire[:hdr_len])
        if magic != b"NM8S" or version != 1 or reserved != 0:
            raise ValueError(f"invalid cell header: {(magic, version, reserved)!r}")
        expected_len = hdr_len + n_blocks + cls.HASH_BYTES
        if len(wire) != expected_len:
            raise ValueError(f"wire length mismatch: {len(wire)} != {expected_len}")
        payload = wire[hdr_len : hdr_len + n_blocks]
        digest = wire[hdr_len + n_blocks :]
        recomputed = hashlib.sha256(wire[: hdr_len + n_blocks]).digest()
        if digest != recomputed:
            raise ValueError("cell RAM==WIRE==HASH SHA-256 verification failed")
        for b in payload:
            if b >= 240:
                raise ValueError(f"invalid E8 index byte >= 240: {b}")
        return cls(magic=magic, version=version, n_blocks=n_blocks, indices=payload, sha256_digest=digest)


class BlockE8SphereCodec(nn.Module):
    """Explicit Block-8 E8 sphere-lattice quantizer/dequantizer for z in S^{8K - 1}."""

    def __init__(self, d_latent: int) -> None:
        super().__init__()
        if d_latent % 8 != 0 or d_latent <= 0:
            raise ValueError(f"d_latent must be a positive multiple of 8, got {d_latent}")
        self.d_latent = d_latent
        self.n_blocks = d_latent // 8
        self.register_buffer("codebook", build_e8_root_codebook())  # [240, 8]

    def encode_indices(self, z: torch.Tensor) -> torch.Tensor:
        # z: [..., d_latent]
        blocks = z.reshape(*z.shape[:-1], self.n_blocks, 8)
        blocks = safe_l2_normalize(blocks, dim=-1)
        sims = torch.matmul(blocks, self.codebook.T)  # [..., n_blocks, 240]
        return sims.argmax(dim=-1)

    def decode_indices(self, idx: torch.Tensor) -> torch.Tensor:
        vecs = self.codebook[idx]  # [..., n_blocks, 8]
        return safe_l2_normalize(vecs.reshape(*idx.shape[:-1], self.d_latent), dim=-1)

    def pack_cell(self, z_single: torch.Tensor) -> bytes:
        idx = self.encode_indices(z_single).tolist()
        return NullModemCell.pack(idx)

    def unpack_cell(self, wire: bytes) -> torch.Tensor:
        cell = NullModemCell.verify_and_unpack(wire)
        if cell.n_blocks != self.n_blocks:
            raise ValueError(f"cell n_blocks ({cell.n_blocks}) != codec n_blocks ({self.n_blocks})")
        idx = torch.tensor(list(cell.indices), dtype=torch.long, device=self.codebook.device)
        return self.decode_indices(idx)


# ---------------------------------------------------------------------------
# Exact FLOP & Parameter Accounting (CS-08)
# ---------------------------------------------------------------------------


def count_model_params(model: nn.Module) -> dict[str, int]:
    total = 0
    embed = 0
    for name, p in model.named_parameters():
        if not p.requires_grad:
            continue
        n = p.numel()
        total += n
        if any(k in name for k in ("emb", "embed", ".A.", ".B.", "A.weight", "B.weight")):
            embed += n
    return {"total_params": total, "embed_params": embed, "non_embed_params": total - embed}


def estimate_transformer_fwd_flops_per_token(
    d_model: int,
    n_layers: int,
    seq_len: int,
    vocab_out: int,
    mlp_mult: int = 4,
    extra_per_token_flops: int = 0,
) -> int:
    """Analytic forward FLOPs/token (2 FLOPs per MAC: QKV, Out, Attention, MLP, LM head; lookup = 0)."""
    qkv_out = 2 * (4 * d_model * d_model)
    attn_qk_v = 2 * (2 * seq_len * d_model)
    mlp = 2 * (2 * d_model * (d_model * mlp_mult))
    per_layer = qkv_out + attn_qk_v + mlp
    lm_head = 2 * d_model * vocab_out
    return int(n_layers * per_layer + lm_head + extra_per_token_flops)
