/* Universal Paper — JavaScript engine, part 1: canonical JSON, SHA-256/512, Ed25519, decimals, time.
 * A second, independent implementation of spec/01-domain.md §1–3 and spec/04-inference.md §2, §6.
 * No dependencies. Works in browsers and in Node. Licensed Apache-2.0. */
(function (root) {
  "use strict";
  var UP = root.UP || (root.UP = {});

  // ---- UTF-8 and hex ------------------------------------------------------
  var enc = typeof TextEncoder !== "undefined" ? new TextEncoder() : null;
  function utf8(s) { return enc.encode(s); }
  function hex(b) { var s = ""; for (var i = 0; i < b.length; i++) s += (b[i] < 16 ? "0" : "") + b[i].toString(16); return s; }
  function unhex(h) { var b = new Uint8Array(h.length / 2); for (var i = 0; i < b.length; i++) b[i] = parseInt(h.substr(i * 2, 2), 16); return b; }
  function concat() { var n = 0, i; for (i = 0; i < arguments.length; i++) n += arguments[i].length; var o = new Uint8Array(n), k = 0; for (i = 0; i < arguments.length; i++) { o.set(arguments[i], k); k += arguments[i].length; } return o; }

  // ---- Canonical JSON (RFC 8785, restricted per spec/01 §1.1) --------------
  var MAX_INT = 9007199254740991;
  function canonErr(m) { var e = new Error(m); e.name = "CanonError"; return e; }
  function jstr(s) {
    var out = '"';
    for (var i = 0; i < s.length; i++) {
      var c = s.charCodeAt(i), ch = s[i];
      if (c >= 0xD800 && c <= 0xDBFF) {
        var lo = i + 1 < s.length ? s.charCodeAt(i + 1) : 0;
        if (lo < 0xDC00 || lo > 0xDFFF) throw canonErr("strings must not contain lone surrogates");
        out += ch + s[i + 1]; i++; continue;
      }
      if (c >= 0xDC00 && c <= 0xDFFF) throw canonErr("strings must not contain lone surrogates");
      if (ch === '"') out += '\\"';
      else if (ch === "\\") out += "\\\\";
      else if (c === 8) out += "\\b";
      else if (c === 12) out += "\\f";
      else if (c === 10) out += "\\n";
      else if (c === 13) out += "\\r";
      else if (c === 9) out += "\\t";
      else if (c < 0x20) out += "\\u" + ("000" + c.toString(16)).slice(-4);
      else out += ch;
    }
    return out + '"';
  }
  function jcsString(v) {
    if (v === true) return "true";
    if (v === false) return "false";
    if (v === null || v === undefined) throw canonErr("null is not allowed in Universal Paper objects");
    if (typeof v === "number") {
      if (!Number.isInteger(v)) throw canonErr("non-integer JSON numbers are not allowed; use a Decimal string");
      if (Math.abs(v) > MAX_INT) throw canonErr("integer out of range: " + v);
      return String(v);
    }
    if (typeof v === "string") return jstr(v);
    if (Array.isArray(v)) return "[" + v.map(jcsString).join(",") + "]";
    if (typeof v === "object") {
      var keys = Object.keys(v);
      keys.forEach(function (k) { if (!/^[\x00-\x7f]*$/.test(k)) throw canonErr("object keys must be ASCII (spec/01-domain.md §1.1)"); });
      keys.sort();
      return "{" + keys.map(function (k) { return jstr(k) + ":" + jcsString(v[k]); }).join(",") + "}";
    }
    throw canonErr("unsupported type: " + typeof v);
  }
  function strip(o) {
    if (!o || typeof o !== "object" || Array.isArray(o)) return o;
    var r = {}; Object.keys(o).forEach(function (k) { if (k !== "sigs") r[k] = o[k]; }); return r;
  }

  // ---- SHA-256 --------------------------------------------------------------
  var K256 = new Uint32Array([
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5, 0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3,
    0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174, 0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
    0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967, 0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13,
    0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85, 0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
    0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3, 0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208,
    0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2]);
  function sha256(msg) {
    var l = msg.length, nb = ((l + 9 + 63) >> 6) << 6, m = new Uint8Array(nb);
    m.set(msg); m[l] = 0x80;
    var bits = l * 8; m[nb - 4] = bits >>> 24; m[nb - 3] = (bits >>> 16) & 255; m[nb - 2] = (bits >>> 8) & 255; m[nb - 1] = bits & 255;
    m[nb - 5] = Math.floor(l / 0x20000000) & 255;
    var h0 = 0x6a09e667, h1 = 0xbb67ae85, h2 = 0x3c6ef372, h3 = 0xa54ff53a, h4 = 0x510e527f, h5 = 0x9b05688c, h6 = 0x1f83d9ab, h7 = 0x5be0cd19;
    var w = new Uint32Array(64);
    for (var off = 0; off < nb; off += 64) {
      for (var i = 0; i < 16; i++) w[i] = (m[off + i * 4] << 24) | (m[off + i * 4 + 1] << 16) | (m[off + i * 4 + 2] << 8) | m[off + i * 4 + 3];
      for (i = 16; i < 64; i++) {
        var x = w[i - 15], y = w[i - 2];
        var s0 = ((x >>> 7) | (x << 25)) ^ ((x >>> 18) | (x << 14)) ^ (x >>> 3);
        var s1 = ((y >>> 17) | (y << 15)) ^ ((y >>> 19) | (y << 13)) ^ (y >>> 10);
        w[i] = (w[i - 16] + s0 + w[i - 7] + s1) | 0;
      }
      var a = h0, b = h1, c = h2, d = h3, e = h4, f = h5, g = h6, h = h7;
      for (i = 0; i < 64; i++) {
        var S1 = ((e >>> 6) | (e << 26)) ^ ((e >>> 11) | (e << 21)) ^ ((e >>> 25) | (e << 7));
        var t1 = (h + S1 + ((e & f) ^ (~e & g)) + K256[i] + w[i]) | 0;
        var S0 = ((a >>> 2) | (a << 30)) ^ ((a >>> 13) | (a << 19)) ^ ((a >>> 22) | (a << 10));
        var t2 = (S0 + ((a & b) ^ (a & c) ^ (b & c))) | 0;
        h = g; g = f; f = e; e = (d + t1) | 0; d = c; c = b; b = a; a = (t1 + t2) | 0;
      }
      h0 = (h0 + a) | 0; h1 = (h1 + b) | 0; h2 = (h2 + c) | 0; h3 = (h3 + d) | 0; h4 = (h4 + e) | 0; h5 = (h5 + f) | 0; h6 = (h6 + g) | 0; h7 = (h7 + h) | 0;
    }
    var out = new Uint8Array(32), hs = [h0, h1, h2, h3, h4, h5, h6, h7];
    for (i = 0; i < 8; i++) { out[i * 4] = hs[i] >>> 24; out[i * 4 + 1] = (hs[i] >>> 16) & 255; out[i * 4 + 2] = (hs[i] >>> 8) & 255; out[i * 4 + 3] = hs[i] & 255; }
    return out;
  }

  // ---- SHA-512 (BigInt; only used for Ed25519 on short inputs) --------------
  var K512 = [
    "428a2f98d728ae22", "7137449123ef65cd", "b5c0fbcfec4d3b2f", "e9b5dba58189dbbc", "3956c25bf348b538", "59f111f1b605d019", "923f82a4af194f9b", "ab1c5ed5da6d8118",
    "d807aa98a3030242", "12835b0145706fbe", "243185be4ee4b28c", "550c7dc3d5ffb4e2", "72be5d74f27b896f", "80deb1fe3b1696b1", "9bdc06a725c71235", "c19bf174cf692694",
    "e49b69c19ef14ad2", "efbe4786384f25e3", "0fc19dc68b8cd5b5", "240ca1cc77ac9c65", "2de92c6f592b0275", "4a7484aa6ea6e483", "5cb0a9dcbd41fbd4", "76f988da831153b5",
    "983e5152ee66dfab", "a831c66d2db43210", "b00327c898fb213f", "bf597fc7beef0ee4", "c6e00bf33da88fc2", "d5a79147930aa725", "06ca6351e003826f", "142929670a0e6e70",
    "27b70a8546d22ffc", "2e1b21385c26c926", "4d2c6dfc5ac42aed", "53380d139d95b3df", "650a73548baf63de", "766a0abb3c77b2a8", "81c2c92e47edaee6", "92722c851482353b",
    "a2bfe8a14cf10364", "a81a664bbc423001", "c24b8b70d0f89791", "c76c51a30654be30", "d192e819d6ef5218", "d69906245565a910", "f40e35855771202a", "106aa07032bbd1b8",
    "19a4c116b8d2d0c8", "1e376c085141ab53", "2748774cdf8eeb99", "34b0bcb5e19b48a8", "391c0cb3c5c95a63", "4ed8aa4ae3418acb", "5b9cca4f7763e373", "682e6ff3d6b2b8a3",
    "748f82ee5defb2fc", "78a5636f43172f60", "84c87814a1f0ab72", "8cc702081a6439ec", "90befffa23631e28", "a4506cebde82bde9", "bef9a3f7b2c67915", "c67178f2e372532b",
    "ca273eceea26619c", "d186b8c721c0c207", "eada7dd6cde0eb1e", "f57d4f7fee6ed178", "06f067aa72176fba", "0a637dc5a2c898a6", "113f9804bef90dae", "1b710b35131c471b",
    "28db77f523047d84", "32caab7b40c72493", "3c9ebe0a15c9bebc", "431d67c49c100d4c", "4cc5d4becb3e42b6", "597f299cfc657e2a", "5fcb6fab3ad6faec", "6c44198c4a475817"].map(function (x) { return BigInt("0x" + x); });
  var M64 = (1n << 64n) - 1n;
  function rotr(x, n) { return ((x >> n) | (x << (64n - n))) & M64; }
  function sha512(msg) {
    var l = msg.length, nb = ((l + 17 + 127) >> 7) << 7, m = new Uint8Array(nb);
    m.set(msg); m[l] = 0x80;
    var bits = BigInt(l) * 8n;
    for (var i = 0; i < 16; i++) m[nb - 1 - i] = Number((bits >> BigInt(8 * i)) & 255n);
    var H = ["6a09e667f3bcc908", "bb67ae8584caa73b", "3c6ef372fe94f82b", "a54ff53a5f1d36f1", "510e527fade682d1", "9b05688c2b3e6c1f", "1f83d9abfb41bd6b", "5be0cd19137e2179"].map(function (x) { return BigInt("0x" + x); });
    var w = new Array(80);
    for (var off = 0; off < nb; off += 128) {
      for (i = 0; i < 16; i++) { var v = 0n; for (var j = 0; j < 8; j++) v = (v << 8n) | BigInt(m[off + i * 8 + j]); w[i] = v; }
      for (i = 16; i < 80; i++) {
        var s0 = rotr(w[i - 15], 1n) ^ rotr(w[i - 15], 8n) ^ (w[i - 15] >> 7n);
        var s1 = rotr(w[i - 2], 19n) ^ rotr(w[i - 2], 61n) ^ (w[i - 2] >> 6n);
        w[i] = (w[i - 16] + s0 + w[i - 7] + s1) & M64;
      }
      var a = H[0], b = H[1], c = H[2], d = H[3], e = H[4], f = H[5], g = H[6], h = H[7];
      for (i = 0; i < 80; i++) {
        var S1 = rotr(e, 14n) ^ rotr(e, 18n) ^ rotr(e, 41n);
        var t1 = (h + S1 + ((e & f) ^ (~e & M64 & g)) + K512[i] + w[i]) & M64;
        var S0 = rotr(a, 28n) ^ rotr(a, 34n) ^ rotr(a, 39n);
        var t2 = (S0 + ((a & b) ^ (a & c) ^ (b & c))) & M64;
        h = g; g = f; f = e; e = (d + t1) & M64; d = c; c = b; b = a; a = (t1 + t2) & M64;
      }
      H = [H[0] + a, H[1] + b, H[2] + c, H[3] + d, H[4] + e, H[5] + f, H[6] + g, H[7] + h].map(function (x) { return x & M64; });
    }
    var out = new Uint8Array(64);
    for (i = 0; i < 8; i++) for (j = 0; j < 8; j++) out[i * 8 + j] = Number((H[i] >> BigInt(56 - 8 * j)) & 255n);
    return out;
  }

  // ---- Ed25519 (RFC 8032) ----------------------------------------------------
  var P = (1n << 255n) - 19n, Q = (1n << 252n) + 27742317777372353535851937790883648493n;
  function mod(a) { a %= P; return a < 0n ? a + P : a; }
  function pow(b, e) { var r = 1n; b = mod(b); while (e > 0n) { if (e & 1n) r = (r * b) % P; b = (b * b) % P; e >>= 1n; } return r; }
  function inv(x) { return pow(x, P - 2n); }
  var D = mod(-121665n * inv(121666n)), D2 = mod(2n * D), SQRTM1 = pow(2n, (P - 1n) / 4n);
  function add(p1, p2) {
    var A = mod((p1[1] - p1[0]) * (p2[1] - p2[0])), B = mod((p1[1] + p1[0]) * (p2[1] + p2[0]));
    var C = mod(p1[3] * D2 * p2[3]), Dd = mod(p1[2] * 2n * p2[2]);
    var E = B - A, F = Dd - C, G = Dd + C, H = B + A;
    return [mod(E * F), mod(G * H), mod(F * G), mod(E * H)];
  }
  var ZERO = [0n, 1n, 1n, 0n];
  function mul(s, pt) { var q = ZERO; while (s > 0n) { if (s & 1n) q = add(q, pt); pt = add(pt, pt); s >>= 1n; } return q; }
  function recoverX(y, sign) {
    if (y >= P) return null;
    var x2 = mod((y * y - 1n) * inv(D * y * y + 1n));
    if (x2 === 0n) return sign ? null : 0n;
    var x = pow(x2, (P + 3n) / 8n);
    if (mod(x * x - x2) !== 0n) x = mod(x * SQRTM1);
    if (mod(x * x - x2) !== 0n) return null;
    if (Number(x & 1n) !== sign) x = P - x;
    return x;
  }
  var GY = mod(4n * inv(5n)), GX = recoverX(GY, 0), BASE = [GX, GY, 1n, mod(GX * GY)];
  var BASE_POW = (function () { var t = [], p = BASE; for (var i = 0; i < 256; i++) { t.push(p); p = add(p, p); } return t; })();
  function mulBase(s) { var q = ZERO, i = 0; while (s > 0n) { if (s & 1n) q = add(q, BASE_POW[i]); s >>= 1n; i++; } return q; }
  function leInt(b) { var r = 0n; for (var i = b.length - 1; i >= 0; i--) r = (r << 8n) | BigInt(b[i]); return r; }
  function intLe(n, len) { var o = new Uint8Array(len); for (var i = 0; i < len; i++) { o[i] = Number(n & 255n); n >>= 8n; } return o; }
  function compress(p) { var zi = inv(p[2]), x = mod(p[0] * zi), y = mod(p[1] * zi); return intLe(y | ((x & 1n) << 255n), 32); }
  function decompress(b) {
    if (b.length !== 32) return null;
    var y = leInt(b), sign = Number(y >> 255n); y &= (1n << 255n) - 1n;
    var x = recoverX(y, sign); if (x === null) return null;
    return [x, y, 1n, mod(x * y)];
  }
  function equal(p1, p2) { return mod(p1[0] * p2[2] - p2[0] * p1[2]) === 0n && mod(p1[1] * p2[2] - p2[1] * p1[2]) === 0n; }
  function expand(secret) { var h = sha512(secret), a = leInt(h.slice(0, 32)); a &= (1n << 254n) - 8n; a |= 1n << 254n; return [a, h.slice(32)]; }
  var pubCache = new Map();
  function publicFromSecret(secret) {
    var k = hex(secret); if (pubCache.has(k)) return pubCache.get(k);
    var A = compress(mulBase(expand(secret)[0])); pubCache.set(k, A); return A;
  }
  function sign(secret, msg) {
    var ex = expand(secret), a = ex[0], A = publicFromSecret(secret);
    var r = leInt(sha512(concat(ex[1], msg))) % Q, R = compress(mulBase(r));
    var h = leInt(sha512(concat(R, A, msg))) % Q, s = (r + h * a) % Q;
    return concat(R, intLe(s, 32));
  }
  var verifyCache = new Map();
  function verify(pub, msg, sig) {
    var key = hex(pub) + hex(sig) + hex(msg);
    if (verifyCache.has(key)) return verifyCache.get(key);
    var ok = (function () {
      if (sig.length !== 64) return false;
      var A = decompress(pub); if (!A) return false;
      var Rs = sig.slice(0, 32), R = decompress(Rs); if (!R) return false;
      var s = leInt(sig.slice(32)); if (s >= Q) return false;
      var h = leInt(sha512(concat(Rs, pub, msg))) % Q;
      return equal(mulBase(s), add(R, mul(h, A)));
    })();
    if (verifyCache.size > 20000) verifyCache.clear();
    verifyCache.set(key, ok);
    return ok;
  }

  // ---- Content hashes and keys ----------------------------------------------
  function jcs(v) { return utf8(jcsString(v)); }
  function digest(o) { return sha256(jcs(strip(o))); }
  function contentHash(o) { return "sha256:" + hex(digest(o)); }

  function Key(secret) { this.secret = secret; this.public = "ed25519:" + hex(publicFromSecret(secret)); }
  Key.fromSeed = function (seed) { return new Key(sha256(utf8(seed))); };
  Key.prototype.signObj = function (obj, mandate) {
    var e = { key: this.public, sig: hex(sign(this.secret, digest(obj))) };
    if (mandate) e.mandate = mandate;
    return e;
  };
  // Strict verification (spec/01-domain.md §1.3), identical to src/universal_paper/crypto.py:
  // lowercase hex, canonical key and R encodings (y < p), key not of small order, S < L.
  var KEY_RE = /^ed25519:[0-9a-f]{64}$/, SIG_RE = /^[0-9a-f]{128}$/;
  var SMALL_ORDER_Y = [0n, 1n, P - 1n,
    0x05FC536D880238B13933C6D305ACDFD5F098EFF289F4C345B027B2C28F95E826n,
    0x7A03AC9277FDC74EC6CC392CFA53202A0F67100D760B3CBA4FD84D3D706A17C7n];
  function yOf(b) { return leInt(b) & ((1n << 255n) - 1n); }
  function validKey(pub) {
    if (typeof pub !== "string" || !KEY_RE.test(pub)) return false;
    var y = yOf(unhex(pub.slice(8)));
    return y < P && SMALL_ORDER_Y.indexOf(y) < 0;
  }
  function verifySig(pub, sigHex, obj) {
    try {
      if (!validKey(pub)) return false;
      if (typeof sigHex !== "string" || !SIG_RE.test(sigHex)) return false;
      var sig = unhex(sigHex);
      if (yOf(sig.slice(0, 32)) >= P || leInt(sig.slice(32)) >= Q) return false;
      return verify(unhex(pub.slice(8)), digest(obj), sig);
    } catch (e) { return false; }
  }
  function attach(obj) {
    var byKey = {}; (obj.sigs || []).forEach(function (s) { byKey[s.key] = s; });
    for (var i = 1; i < arguments.length; i++) byKey[arguments[i].key] = arguments[i];
    var out = Object.assign({}, obj); out.sigs = Object.keys(byKey).sort().map(function (k) { return byKey[k]; });
    return out;
  }

  // ---- Decimal (exact, BigInt-scaled) ---------------------------------------
  var DEC_RE = /^-?(0|[1-9][0-9]*)(\.[0-9]+)?$/;
  var MAX_DECIMAL_LEN = 64, MAX_PERIOD_COUNT = 10000, MAX_ROUNDING_SCALE = 18;
  function Dec(i, s) { this.i = i; this.s = s; }
  function dec(str) {
    if (typeof str !== "string" || str.length > MAX_DECIMAL_LEN || !DEC_RE.test(str)) throw new Error("not a Decimal string: " + JSON.stringify(str));
    var neg = str[0] === "-", body = neg ? str.slice(1) : str, parts = body.split(".");
    var frac = parts[1] || "", i = BigInt(parts[0] + frac);
    return new Dec(neg ? -i : i, frac.length);
  }
  function align(a, b) { var s = Math.max(a.s, b.s); return [a.i * 10n ** BigInt(s - a.s), b.i * 10n ** BigInt(s - b.s), s]; }
  Dec.prototype.add = function (b) { var x = align(this, b); return new Dec(x[0] + x[1], x[2]); };
  Dec.prototype.mul = function (b) { return new Dec(this.i * b.i, this.s + b.s); };
  Dec.prototype.cmp = function (b) { var x = align(this, b); return x[0] < x[1] ? -1 : x[0] > x[1] ? 1 : 0; };
  Dec.prototype.isZero = function () { return this.i === 0n; };
  Dec.prototype.toString = function () {
    var neg = this.i < 0n && this.i !== 0n, a = neg ? -this.i : this.i, s = a.toString();
    if (this.s > 0) { while (s.length <= this.s) s = "0" + s; s = s.slice(0, s.length - this.s) + "." + s.slice(s.length - this.s); }
    return (neg ? "-" : "") + s;
  };
  Dec.prototype.round = function (rounding) {
    var scale = rounding.scale, mode = rounding.mode;
    if (!(typeof scale === "number" && Number.isInteger(scale) && scale >= 0 && scale <= MAX_ROUNDING_SCALE))
      throw new Error("rounding scale must be an integer from 0 to " + MAX_ROUNDING_SCALE);
    if (["half-even", "half-up", "down", "up"].indexOf(mode) < 0) throw new Error("bad rounding mode " + mode);
    if (scale >= this.s) return new Dec(this.i * 10n ** BigInt(scale - this.s), scale);
    var f = 10n ** BigInt(this.s - scale), neg = this.i < 0n, a = neg ? -this.i : this.i;
    var q = a / f, r = a % f, twice = r * 2n;
    var up;
    if (mode === "down") up = false;
    else if (mode === "up") up = r !== 0n;
    else if (mode === "half-up") up = twice >= f;
    else if (mode === "half-even") up = twice > f || (twice === f && (q & 1n) === 1n);
    else throw new Error("bad rounding mode " + mode);
    if (up) q += 1n;
    return new Dec(neg ? -q : q, scale);
  };
  function decStr(d) { return d.isZero() ? new Dec(0n, d.s).toString() : d.toString(); }

  // ---- Time and Period -------------------------------------------------------
  var TIME_RE = /^([0-9]{4})-([0-9]{2})-([0-9]{2})T([0-9]{2}):([0-9]{2}):([0-9]{2})Z$/;
  // Date.UTC maps years 0-99 to 1900-1999, so dates are built with setUTCFullYear.
  function utc(y, mo, d, h, mi, s) { var r = new Date(0); r.setUTCFullYear(y, mo, d); r.setUTCHours(h, mi, s, 0); return r; }
  function parseTime(s) {
    var m = typeof s === "string" && TIME_RE.exec(s);
    if (!m) throw new Error("not a UP Time: " + JSON.stringify(s));
    var y = +m[1], mo = +m[2], da = +m[3], h = +m[4], mi = +m[5], se = +m[6];
    var d = utc(y, mo - 1, da, h, mi, se);
    if (y < 1 || mo < 1 || mo > 12 || h > 23 || mi > 59 || se > 59 || d.getUTCDate() !== da || d.getUTCMonth() !== mo - 1)
      throw new Error("not a UP Time: " + JSON.stringify(s));
    return d;
  }
  function pad(n, w) { n = String(n); while (n.length < w) n = "0" + n; return n; }
  function fmtTime(d) {
    var y = d.getUTCFullYear();
    if (!(y >= 1 && y <= 9999)) throw new Error("time out of range");
    return pad(d.getUTCFullYear(), 4) + "-" + pad(d.getUTCMonth() + 1, 2) + "-" + pad(d.getUTCDate(), 2) + "T" +
      pad(d.getUTCHours(), 2) + ":" + pad(d.getUTCMinutes(), 2) + ":" + pad(d.getUTCSeconds(), 2) + "Z";
  }
  function addMonths(d, n) {
    var m = d.getUTCMonth() + n, y = d.getUTCFullYear() + Math.floor(m / 12); m = ((m % 12) + 12) % 12;
    var last = utc(y, m + 1, 0, 0, 0, 0).getUTCDate();
    return utc(y, m, Math.min(d.getUTCDate(), last), d.getUTCHours(), d.getUTCMinutes(), d.getUTCSeconds());
  }
  function addPeriod(t, p, k) {
    if (k === undefined) k = 1;
    var d = parseTime(t), count = p.count, u = p.unit, r;
    if (!(typeof count === "number" && Number.isInteger(count) && count >= 1 && count <= MAX_PERIOD_COUNT))
      throw new Error("period count must be an integer from 1 to " + MAX_PERIOD_COUNT);
    var n = count * k;
    if (u === "day") r = new Date(d.getTime() + n * 86400000);
    else if (u === "month") r = addMonths(d, n);
    else if (u === "quarter") r = addMonths(d, 3 * n);
    else if (u === "year") r = addMonths(d, 12 * n);
    else throw new Error("bad period unit " + u);
    return fmtTime(r);
  }
  function fmtPeriod(p) {
    var n = Number(p.count), word = { day: "day", month: "calendar month", quarter: "calendar quarter", year: "year" }[p.unit];
    return n + " " + word + (n !== 1 ? "s" : "");
  }

  // ---- Seals ------------------------------------------------------------------
  var SEALED = { sealed: true, toString: function () { return "sealed"; } };
  function isSeal(x) { return !!x && typeof x === "object" && !Array.isArray(x) && Object.keys(x).length === 1 && typeof x.seal === "string"; }
  function sealOf(value, salt) {
    if (typeof salt !== "string" || !/^[0-9a-f]{64}$/.test(salt)) throw new Error("salt must be 64 hex characters");
    return { seal: "sha256:" + hex(sha256(jcs({ salt: salt, value: value }))) };
  }
  function opens(d, seal) { try { return sealOf(d.value, d.salt).seal === seal.seal && d.seal === seal.seal; } catch (e) { return false; } }
  function containsSeal(x) {
    if (isSeal(x)) return true;
    if (Array.isArray(x)) return x.some(containsSeal);
    if (x && typeof x === "object") return Object.keys(x).some(function (k) { return containsSeal(x[k]); });
    return false;
  }

  Object.assign(UP, {
    SPEC: "UP/0.1-draft", hex: hex, unhex: unhex, utf8: utf8, sha256: sha256, sha512: sha512,
    jcs: jcs, jcsString: jcsString, strip: strip, digest: digest, contentHash: contentHash,
    Key: Key, verifySig: verifySig, validKey: validKey,
    MAX_DECIMAL_LEN: MAX_DECIMAL_LEN, MAX_PERIOD_COUNT: MAX_PERIOD_COUNT, MAX_ROUNDING_SCALE: MAX_ROUNDING_SCALE, attach: attach, ed25519: { sign: sign, verify: verify, publicFromSecret: publicFromSecret },
    clearVerifyCache: function () { verifyCache.clear(); },
    dec: dec, Dec: Dec, decStr: decStr, parseTime: parseTime, fmtTime: fmtTime, addPeriod: addPeriod, fmtPeriod: fmtPeriod,
    SEALED: SEALED, isSeal: isSeal, sealOf: sealOf, opens: opens, containsSeal: containsSeal
  });
  if (typeof module !== "undefined" && module.exports) module.exports = UP;
})(typeof globalThis !== "undefined" ? globalThis : this);
