// Track S98: Zero-Dependency Native Rust Reference Implementation of `zone-canon-v1`
// Compiles cleanly with `rustc -O zone_canon_v1_ref.rs` (pure stdlib, zero external crates).
// Implements strict iterative (non-recursive) JSON parsing with:
//   - Hard DoS ceilings: MAX_DEPTH = 64, MAX_NODES = 4096, MAX_INT_DIGITS = 78
//   - Strict rejection of floats, exponents, -0, leading zeros, NaN/Inf, duplicate keys
//     (including Unicode-escaped duplicates), lone UTF-16 surrogates, and trailing tokens
//   - Explicit integer profiles:
//       * `mde_v0_utf8`:    raw UTF-8 strings, |n| <= 2^53 - 1
//       * `v1_utf8`:        raw UTF-8 strings, |n| <= 2^255 - 1 (256-bit signed / <=78 digits)
//       * `v1_ascii`:       ASCII-escaped strings (\uXXXX / surrogate pairs), |n| <= 2^255 - 1
//   - Domain-separated FIPS 180-4 SHA-256 over canonical bytes (`raw_sha256` & `domain_sha256`).

use std::env;
use std::io::{self, Read};

const MAX_INPUT_BYTES: usize = 1_048_576;
const MAX_DEPTH: usize = 64;
const MAX_NODES: usize = 4096;
const MAX_INT_DIGITS: usize = 78;
const JS_SAFE_INT_LIMIT: i128 = (1i128 << 53) - 1;
const INT_256_POS_MAX: &str =
    "57896044618658097711785492504343953926634992332820282019728792003956564819967";
const INT_256_NEG_MAX: &str =
    "57896044618658097711785492504343953926634992332820282019728792003956564819968";

#[derive(Clone, Copy, PartialEq, Eq)]
enum Profile {
    MdeV0Utf8,
    V1Utf8,
    V1Ascii,
}

impl Profile {
    fn from_str(s: &str) -> Result<Self, String> {
        match s {
            "mde_v0_utf8" => Ok(Profile::MdeV0Utf8),
            "v1_utf8" => Ok(Profile::V1Utf8),
            "v1_ascii" => Ok(Profile::V1Ascii),
            _ => Err(format!("UNKNOWN_PROFILE:{s}")),
        }
    }

    fn domain_prefix(self) -> &'static [u8] {
        match self {
            Profile::MdeV0Utf8 => b"zone-canon-v0:utf8:",
            Profile::V1Utf8 => b"zone-canon-v1:utf8:",
            Profile::V1Ascii => b"zone-canon-v1:ascii:",
        }
    }

    fn raw_utf8(self) -> bool {
        matches!(self, Profile::MdeV0Utf8 | Profile::V1Utf8)
    }
}

#[derive(Clone)]
enum JVal {
    Null,
    Bool(bool),
    IntStr(String),
    Str(String),
    Arr(Vec<JVal>),
    Obj(Vec<(String, JVal)>),
}

enum Frame {
    Arr(Vec<JVal>),
    Obj(Vec<(String, JVal)>, Option<String>),
}

fn decimal_gt(a: &str, b: &str) -> bool {
    if a.len() != b.len() {
        a.len() > b.len()
    } else {
        a.as_bytes() > b.as_bytes()
    }
}

fn parse_hex4(bytes: &[u8], pos: usize) -> Result<u16, String> {
    if pos + 4 > bytes.len() {
        return Err("TRUNCATED_UNICODE_ESCAPE".into());
    }
    let mut v: u16 = 0;
    for &b in &bytes[pos..pos + 4] {
        let d = match b {
            b'0'..=b'9' => (b - b'0') as u16,
            b'a'..=b'f' => (b - b'a' + 10) as u16,
            b'A'..=b'F' => (b - b'A' + 10) as u16,
            _ => return Err("BAD_HEX_ESCAPE".into()),
        };
        v = (v << 4) | d;
    }
    Ok(v)
}

fn parse_string(bytes: &[u8], i: &mut usize) -> Result<String, String> {
    if bytes.get(*i) != Some(&b'"') {
        return Err("EXPECTED_QUOTE".into());
    }
    *i += 1;
    let mut out = String::new();
    while *i < bytes.len() {
        let b = bytes[*i];
        if b == b'"' {
            *i += 1;
            return Ok(out);
        }
        if b < 0x20 {
            return Err("UNESCAPED_CONTROL_CHAR".into());
        }
        if b == b'\\' {
            *i += 1;
            if *i >= bytes.len() {
                return Err("TRUNCATED_ESCAPE".into());
            }
            let esc = bytes[*i];
            *i += 1;
            match esc {
                b'"' => out.push('"'),
                b'\\' => out.push('\\'),
                b'/' => out.push('/'),
                b'b' => out.push('\u{0008}'),
                b'f' => out.push('\u{000C}'),
                b'n' => out.push('\n'),
                b'r' => out.push('\r'),
                b't' => out.push('\t'),
                b'u' => {
                    let u1 = parse_hex4(bytes, *i)?;
                    *i += 4;
                    if (0xD800..=0xDBFF).contains(&u1) {
                        if *i + 6 > bytes.len() || bytes[*i] != b'\\' || bytes[*i + 1] != b'u' {
                            return Err("LONE_HIGH_SURROGATE".into());
                        }
                        *i += 2;
                        let u2 = parse_hex4(bytes, *i)?;
                        *i += 4;
                        if !(0xDC00..=0xDFFF).contains(&u2) {
                            return Err("INVALID_LOW_SURROGATE".into());
                        }
                        let cp = 0x10000 + (((u1 as u32 - 0xD800) << 10) | (u2 as u32 - 0xDC00));
                        let ch = char::from_u32(cp).ok_or_else(|| "BAD_CODEPOINT".to_string())?;
                        out.push(ch);
                    } else if (0xDC00..=0xDFFF).contains(&u1) {
                        return Err("LONE_LOW_SURROGATE".into());
                    } else if u1 == 0 {
                        return Err("NUL_FORBIDDEN".into());
                    } else {
                        let ch = char::from_u32(u1 as u32)
                            .ok_or_else(|| "BAD_CODEPOINT".to_string())?;
                        out.push(ch);
                    }
                }
                _ => return Err("INVALID_ESCAPE".into()),
            }
        } else if b < 0x80 {
            out.push(b as char);
            *i += 1;
        } else {
            let s = std::str::from_utf8(&bytes[*i..]).map_err(|_| "INVALID_UTF8".to_string())?;
            let ch = s.chars().next().ok_or_else(|| "INVALID_UTF8".to_string())?;
            out.push(ch);
            *i += ch.len_utf8();
        }
    }
    Err("UNTERMINATED_STRING".into())
}

fn parse_number(bytes: &[u8], i: &mut usize, profile: Profile) -> Result<JVal, String> {
    let start = *i;
    let neg = if bytes.get(*i) == Some(&b'-') {
        *i += 1;
        true
    } else {
        false
    };
    let dig_start = *i;
    match bytes.get(*i) {
        Some(b'0') => {
            *i += 1;
            if matches!(bytes.get(*i), Some(b'0'..=b'9')) {
                return Err("LEADING_ZERO".into());
            }
        }
        Some(b'1'..=b'9') => {
            *i += 1;
            while matches!(bytes.get(*i), Some(b'0'..=b'9')) {
                *i += 1;
            }
        }
        _ => return Err("INVALID_NUMBER".into()),
    }
    if matches!(bytes.get(*i), Some(b'.' | b'e' | b'E')) {
        return Err("FLOAT_FORBIDDEN".into());
    }
    let digits = std::str::from_utf8(&bytes[dig_start..*i]).map_err(|_| "INVALID_UTF8")?;
    if neg && digits == "0" {
        return Err("NEGATIVE_ZERO".into());
    }
    if digits.len() > MAX_INT_DIGITS {
        return Err("INT_DIGITS_EXCEEDED".into());
    }
    match profile {
        Profile::MdeV0Utf8 => {
            if digits.len() > 20 {
                return Err("INT_RANGE_EXCEEDED".into());
            }
            let txt = std::str::from_utf8(&bytes[start..*i]).map_err(|_| "INVALID_UTF8")?;
            let val: i128 = txt.parse().map_err(|_| "INT_PARSE_FAILED")?;
            if val.abs() > JS_SAFE_INT_LIMIT {
                return Err("INT_RANGE_EXCEEDED".into());
            }
        }
        Profile::V1Utf8 | Profile::V1Ascii => {
            let max_str = if neg { INT_256_NEG_MAX } else { INT_256_POS_MAX };
            if decimal_gt(digits, max_str) {
                return Err("INT_256_EXCEEDED".into());
            }
        }
    }
    let txt = std::str::from_utf8(&bytes[start..*i])
        .map_err(|_| "INVALID_UTF8")?
        .to_string();
    Ok(JVal::IntStr(txt))
}

fn skip_ws(bytes: &[u8], i: &mut usize) {
    while matches!(bytes.get(*i), Some(b' ' | b'\n' | b'\t' | b'\r')) {
        *i += 1;
    }
}

fn parse_strict_iterative(input: &str, profile: Profile) -> Result<JVal, String> {
    let bytes = input.as_bytes();
    let mut i: usize = 0;
    let mut nodes: usize = 0;
    let mut stack: Vec<Frame> = Vec::new();
    let mut expect_value = true;
    let mut completed: Option<JVal> = None;

    loop {
        skip_ws(bytes, &mut i);
        if expect_value {
            nodes += 1;
            if nodes > MAX_NODES {
                return Err("MAX_NODES_EXCEEDED".into());
            }
            let b = *bytes.get(i).ok_or_else(|| "UNEXPECTED_EOF".to_string())?;
            match b {
                b'{' => {
                    if stack.len() + 1 > MAX_DEPTH {
                        return Err("MAX_DEPTH_EXCEEDED".into());
                    }
                    i += 1;
                    skip_ws(bytes, &mut i);
                    if bytes.get(i) == Some(&b'}') {
                        i += 1;
                        completed = Some(JVal::Obj(Vec::new()));
                        expect_value = false;
                    } else {
                        let key = parse_string(bytes, &mut i)?;
                        skip_ws(bytes, &mut i);
                        if bytes.get(i) != Some(&b':') {
                            return Err("EXPECTED_COLON".into());
                        }
                        i += 1;
                        stack.push(Frame::Obj(Vec::new(), Some(key)));
                        expect_value = true;
                    }
                }
                b'[' => {
                    if stack.len() + 1 > MAX_DEPTH {
                        return Err("MAX_DEPTH_EXCEEDED".into());
                    }
                    i += 1;
                    skip_ws(bytes, &mut i);
                    if bytes.get(i) == Some(&b']') {
                        i += 1;
                        completed = Some(JVal::Arr(Vec::new()));
                        expect_value = false;
                    } else {
                        stack.push(Frame::Arr(Vec::new()));
                        expect_value = true;
                    }
                }
                b'"' => {
                    let s = parse_string(bytes, &mut i)?;
                    completed = Some(JVal::Str(s));
                    expect_value = false;
                }
                b'-' | b'0'..=b'9' => {
                    let n = parse_number(bytes, &mut i, profile)?;
                    completed = Some(n);
                    expect_value = false;
                }
                b't' => {
                    if bytes[i..].starts_with(b"true") {
                        i += 4;
                        completed = Some(JVal::Bool(true));
                        expect_value = false;
                    } else {
                        return Err("BAD_LITERAL".into());
                    }
                }
                b'f' => {
                    if bytes[i..].starts_with(b"false") {
                        i += 5;
                        completed = Some(JVal::Bool(false));
                        expect_value = false;
                    } else {
                        return Err("BAD_LITERAL".into());
                    }
                }
                b'n' => {
                    if bytes[i..].starts_with(b"null") {
                        i += 4;
                        completed = Some(JVal::Null);
                        expect_value = false;
                    } else {
                        return Err("BAD_LITERAL".into());
                    }
                }
                _ => return Err("BAD_TOKEN".into()),
            }
        } else {
            let val = completed.take().ok_or_else(|| "INTERNAL_STATE".to_string())?;
            if let Some(frame) = stack.last_mut() {
                match frame {
                    Frame::Arr(items) => {
                        items.push(val);
                        skip_ws(bytes, &mut i);
                        match bytes.get(i) {
                            Some(b',') => {
                                i += 1;
                                expect_value = true;
                            }
                            Some(b']') => {
                                i += 1;
                                if let Some(Frame::Arr(done)) = stack.pop() {
                                    completed = Some(JVal::Arr(done));
                                }
                                expect_value = false;
                            }
                            _ => return Err("EXPECTED_COMMA_OR_RBRACKET".into()),
                        }
                    }
                    Frame::Obj(pairs, cur_key) => {
                        let k = cur_key.take().ok_or_else(|| "MISSING_KEY".to_string())?;
                        if pairs.iter().any(|(ek, _)| ek == &k) {
                            return Err("DUPLICATE_KEY".into());
                        }
                        pairs.push((k, val));
                        skip_ws(bytes, &mut i);
                        match bytes.get(i) {
                            Some(b',') => {
                                i += 1;
                                skip_ws(bytes, &mut i);
                                let next_key = parse_string(bytes, &mut i)?;
                                skip_ws(bytes, &mut i);
                                if bytes.get(i) != Some(&b':') {
                                    return Err("EXPECTED_COLON".into());
                                }
                                i += 1;
                                *cur_key = Some(next_key);
                                expect_value = true;
                            }
                            Some(b'}') => {
                                i += 1;
                                if let Some(Frame::Obj(done, _)) = stack.pop() {
                                    completed = Some(JVal::Obj(done));
                                }
                                expect_value = false;
                            }
                            _ => return Err("EXPECTED_COMMA_OR_RBRACE".into()),
                        }
                    }
                }
            } else {
                skip_ws(bytes, &mut i);
                if i != bytes.len() {
                    return Err("TRAILING_DATA".into());
                }
                return Ok(val);
            }
        }
    }
}

fn encode_string(s: &str, raw_utf8: bool, out: &mut Vec<u8>) {
    out.push(b'"');
    for ch in s.chars() {
        match ch {
            '"' => out.extend_from_slice(b"\\\""),
            '\\' => out.extend_from_slice(b"\\\\"),
            '\u{0008}' => out.extend_from_slice(b"\\b"),
            '\u{000C}' => out.extend_from_slice(b"\\f"),
            '\n' => out.extend_from_slice(b"\\n"),
            '\r' => out.extend_from_slice(b"\\r"),
            '\t' => out.extend_from_slice(b"\\t"),
            c if (c as u32) < 0x20 => {
                out.extend_from_slice(format!("\\u{:04x}", c as u32).as_bytes());
            }
            c if raw_utf8 || (c as u32) < 0x7F => {
                let mut buf = [0u8; 4];
                out.extend_from_slice(c.encode_utf8(&mut buf).as_bytes());
            }
            c => {
                let cp = c as u32;
                if cp <= 0xFFFF {
                    out.extend_from_slice(format!("\\u{:04x}", cp).as_bytes());
                } else {
                    let adj = cp - 0x10000;
                    let hi = 0xD800 + (adj >> 10);
                    let lo = 0xDC00 + (adj & 0x3FF);
                    out.extend_from_slice(format!("\\u{:04x}\\u{:04x}", hi, lo).as_bytes());
                }
            }
        }
    }
    out.push(b'"');
}

enum EmitOp<'a> {
    Val(&'a JVal),
    Raw(&'static [u8]),
    Key(&'a str),
}

fn encode_canonical_iterative(root: &JVal, profile: Profile) -> Vec<u8> {
    let raw_utf8 = profile.raw_utf8();
    let mut out = Vec::new();
    let mut ops: Vec<EmitOp> = vec![EmitOp::Val(root)];
    while let Some(op) = ops.pop() {
        match op {
            EmitOp::Raw(b) => out.extend_from_slice(b),
            EmitOp::Key(k) => encode_string(k, raw_utf8, &mut out),
            EmitOp::Val(v) => match v {
                JVal::Null => out.extend_from_slice(b"null"),
                JVal::Bool(true) => out.extend_from_slice(b"true"),
                JVal::Bool(false) => out.extend_from_slice(b"false"),
                JVal::IntStr(s) => out.extend_from_slice(s.as_bytes()),
                JVal::Str(s) => encode_string(s, raw_utf8, &mut out),
                JVal::Arr(items) => {
                    out.push(b'[');
                    ops.push(EmitOp::Raw(b"]"));
                    for idx in (0..items.len()).rev() {
                        ops.push(EmitOp::Val(&items[idx]));
                        if idx > 0 {
                            ops.push(EmitOp::Raw(b","));
                        }
                    }
                }
                JVal::Obj(pairs) => {
                    let mut idxs: Vec<usize> = (0..pairs.len()).collect();
                    idxs.sort_by(|&a, &b| pairs[a].0.cmp(&pairs[b].0));
                    out.push(b'{');
                    ops.push(EmitOp::Raw(b"}"));
                    for pos in (0..idxs.len()).rev() {
                        let (ref k, ref val) = pairs[idxs[pos]];
                        ops.push(EmitOp::Val(val));
                        ops.push(EmitOp::Raw(b":"));
                        ops.push(EmitOp::Key(k));
                        if pos > 0 {
                            ops.push(EmitOp::Raw(b","));
                        }
                    }
                }
            },
        }
    }
    out
}

// Pure-stdlib FIPS 180-4 SHA-256
const K256: [u32; 64] = [
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
    0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
    0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
    0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
    0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
    0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
    0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
    0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2,
];

fn sha256_hex(chunks: &[&[u8]]) -> String {
    let mut msg = Vec::new();
    for c in chunks {
        msg.extend_from_slice(c);
    }
    let bit_len = (msg.len() as u64)
        .checked_mul(8)
        .expect("sha256 message length overflow");
    msg.push(0x80);
    while (msg.len() % 64) != 56 {
        msg.push(0);
    }
    msg.extend_from_slice(&bit_len.to_be_bytes());

    let mut h: [u32; 8] = [
        0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a,
        0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19,
    ];
    for block in msg.chunks_exact(64) {
        let mut w = [0u32; 64];
        for i in 0..16 {
            w[i] = u32::from_be_bytes([
                block[4 * i],
                block[4 * i + 1],
                block[4 * i + 2],
                block[4 * i + 3],
            ]);
        }
        for i in 16..64 {
            let s0 = w[i - 15].rotate_right(7) ^ w[i - 15].rotate_right(18) ^ (w[i - 15] >> 3);
            let s1 = w[i - 2].rotate_right(17) ^ w[i - 2].rotate_right(19) ^ (w[i - 2] >> 10);
            w[i] = w[i - 16]
                .wrapping_add(s0)
                .wrapping_add(w[i - 7])
                .wrapping_add(s1);
        }
        let [mut a, mut b, mut c, mut d, mut e, mut f, mut g, mut hh] = h;
        for i in 0..64 {
            let s1 = e.rotate_right(6) ^ e.rotate_right(11) ^ e.rotate_right(25);
            let ch = (e & f) ^ ((!e) & g);
            let t1 = hh
                .wrapping_add(s1)
                .wrapping_add(ch)
                .wrapping_add(K256[i])
                .wrapping_add(w[i]);
            let s0 = a.rotate_right(2) ^ a.rotate_right(13) ^ a.rotate_right(22);
            let maj = (a & b) ^ (a & c) ^ (b & c);
            let t2 = s0.wrapping_add(maj);
            hh = g;
            g = f;
            f = e;
            e = d.wrapping_add(t1);
            d = c;
            c = b;
            b = a;
            a = t1.wrapping_add(t2);
        }
        h[0] = h[0].wrapping_add(a);
        h[1] = h[1].wrapping_add(b);
        h[2] = h[2].wrapping_add(c);
        h[3] = h[3].wrapping_add(d);
        h[4] = h[4].wrapping_add(e);
        h[5] = h[5].wrapping_add(f);
        h[6] = h[6].wrapping_add(g);
        h[7] = h[7].wrapping_add(hh);
    }
    let mut out = String::with_capacity(64);
    for word in h {
        out.push_str(&format!("{:08x}", word));
    }
    out
}

fn hex_encode(bytes: &[u8]) -> String {
    let mut out = String::with_capacity(bytes.len() * 2);
    for &b in bytes {
        out.push_str(&format!("{:02x}", b));
    }
    out
}

fn main() {
    let args: Vec<String> = env::args().collect();
    if args.len() != 3 || args[1] != "--profile" {
        eprintln!("usage: zone_canon_v1_ref --profile <mde_v0_utf8|v1_utf8|v1_ascii>");
        std::process::exit(2);
    }
    let profile = match Profile::from_str(&args[2]) {
        Ok(p) => p,
        Err(e) => {
            eprintln!("ERR:{e}");
            std::process::exit(2);
        }
    };
    let mut raw_bytes = Vec::new();
    let mut handle = io::stdin().take((MAX_INPUT_BYTES + 1) as u64);
    if handle.read_to_end(&mut raw_bytes).is_err() {
        println!("REJECT STDIN_READ_FAILED");
        std::process::exit(1);
    }
    if raw_bytes.len() > MAX_INPUT_BYTES {
        println!("REJECT INPUT_TOO_LARGE");
        std::process::exit(1);
    }
    let input = match std::str::from_utf8(&raw_bytes) {
        Ok(s) => s,
        Err(_) => {
            println!("REJECT INVALID_UTF8");
            std::process::exit(1);
        }
    };
    match parse_strict_iterative(input, profile) {
        Ok(val) => {
            let canon = encode_canonical_iterative(&val, profile);
            let raw_sha = sha256_hex(&[&canon]);
            let dom_sha = sha256_hex(&[profile.domain_prefix(), &canon]);
            println!("OK {} {} {}", hex_encode(&canon), raw_sha, dom_sha);
        }
        Err(code) => {
            println!("REJECT {code}");
            std::process::exit(1);
        }
    }
}
