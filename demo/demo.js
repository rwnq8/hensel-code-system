/**
 * HENSEL CODE SYSTEM — JavaScript Implementation
 * ─────────────────────────────────────────────
 * Exact rational arithmetic via p-adic numbers (BigInt).
 * 
 * Theory: Ostrowski (1916) + Hensel (1904) + Krishnamurthy (1977)
 * Ported from Python hensel_system.py
 */

// ═══════════════════════════════════════════════════════════════════════════
// UTILITY: Extended Euclidean Algorithm & Modular Inverse
// ═══════════════════════════════════════════════════════════════════════════

function egcd(a, b) {
    let [r0, r1] = [a, b];
    let [s0, s1] = [1n, 0n];
    let [t0, t1] = [0n, 1n];
    while (r1 !== 0n) {
        const q = r0 / r1;
        [r0, r1] = [r1, r0 - q * r1];
        [s0, s1] = [s1, s0 - q * s1];
        [t0, t1] = [t1, t0 - q * t1];
    }
    return { gcd: r0, s: s0, t: t0 };
}

function modInverse(a, m) {
    const { gcd, s } = egcd(a, m);
    if (gcd !== 1n) throw new Error(`No inverse: gcd(${a}, ${m}) = ${gcd}`);
    return ((s % m) + m) % m;
}

function gcd(a, b) {
    a = a < 0n ? -a : a;
    b = b < 0n ? -b : b;
    while (b !== 0n) [a, b] = [b, a % b];
    return a;
}

function isqrt(n) {
    if (n < 2n) return n;
    let x = n;
    let y = (x + 1n) / 2n;
    while (y < x) {
        x = y;
        y = (x + n / x) / 2n;
    }
    return x;
}

// ═══════════════════════════════════════════════════════════════════════════
// PRIME UTILITIES
// ═══════════════════════════════════════════════════════════════════════════

function isProbablePrime(n, rounds = 20) {
    if (n < 2n) return false;
    const smallPrimes = [2n, 3n, 5n, 7n, 11n, 13n, 17n, 19n, 23n, 29n];
    for (const p of smallPrimes) {
        if (n === p) return true;
        if (n % p === 0n) return false;
    }
    let d = n - 1n;
    let s = 0n;
    while (d % 2n === 0n) { d /= 2n; s++; }
    for (const a of smallPrimes.slice(0, rounds)) {
        if (a >= n) continue;
        let x = modPow(a, d, n);
        if (x === 1n || x === n - 1n) continue;
        let cont = false;
        for (let r = 0n; r < s - 1n; r++) {
            x = (x * x) % n;
            if (x === n - 1n) { cont = true; break; }
        }
        if (cont) continue;
        return false;
    }
    return true;
}

function modPow(base, exp, mod) {
    if (mod === 1n) return 0n;
    let result = 1n;
    base = base % mod;
    while (exp > 0n) {
        if (exp % 2n === 1n) result = (result * base) % mod;
        exp /= 2n;
        base = (base * base) % mod;
    }
    return result;
}

function nextPrime(n) {
    if (n < 2n) return 2n;
    n += (n % 2n === 0n ? 1n : 0n);
    while (!isProbablePrime(n)) n += 2n;
    return n;
}

// ═══════════════════════════════════════════════════════════════════════════
// HENSEL CODE CLASS
// ═══════════════════════════════════════════════════════════════════════════

class HenselCode {
    /**
     * @param {bigint} code  - Hensel code value
     * @param {bigint} p     - Prime base
     * @param {number} k     - Precision (number of p-adic digits)
     */
    constructor(code, p, k) {
        this.p = p;
        this.k = k;
        this.modulus = p ** BigInt(k);
        this.code = ((code % this.modulus) + this.modulus) % this.modulus;
    }

    /**
     * Encode rational num/den as a Hensel code mod pᵏ.
     */
    static fromRational(num, den, p, k) {
        if (den === 0n) throw new Error("Division by zero");
        if (den % p === 0n) throw new Error(`Denominator ${den} divisible by p=${p}`);
        const modulus = p ** BigInt(k);
        const denInv = modInverse(den, modulus);
        const code = ((num * denInv) % modulus + modulus) % modulus;
        return new HenselCode(code, p, k);
    }

    /**
     * Encode from a float string (e.g., "0.1", "0.333...").
     */
    static fromDecimal(str, p = 7n, k = 30) {
        // Parse decimal string to rational
        const [num, den] = decimalToRational(str);
        return HenselCode.fromRational(num, den, p, k);
    }

    /**
     * Recover the rational number via EEA.
     */
    toRational(bound = null) {
        if (bound === null) {
            bound = isqrt(this.modulus / 2n);
        }

        // Special case: code == 0 → rational is 0/1
        if (this.code === 0n) return [0n, 1n];

        let [r0, r1] = [this.modulus, this.code];
        let [t0, t1] = [0n, 1n];

        while (r1 !== 0n) {
            const q = r0 / r1;
            [r0, r1] = [r1, r0 - q * r1];
            [t0, t1] = [t1, t0 - q * t1];

            // Check convergence
            const ar0 = r0 < 0n ? -r0 : r0;
            const at0 = t0 < 0n ? -t0 : t0;
            if (ar0 <= bound && at0 <= bound && t0 !== 0n) {
                let num = r0, den = t0;
                if (den < 0n) { num = -num; den = -den; }
                const g = gcd(num, den);
                num /= g; den /= g;
                // Verify
                try {
                    const check = HenselCode.fromRational(num, den, this.p, this.k);
                    if (check.code === this.code) return [num, den];
                } catch (e) { /* continue */ }
            }
        }

        // Post-loop check
        const ar0 = r0 < 0n ? -r0 : r0;
        const at0 = t0 < 0n ? -t0 : t0;
        if (ar0 <= bound && at0 <= bound && t0 !== 0n) {
            let num = r0, den = t0;
            if (den < 0n) { num = -num; den = -den; }
            const g = gcd(num, den);
            num /= g; den /= g;
            try {
                const check = HenselCode.fromRational(num, den, this.p, this.k);
                if (check.code === this.code) return [num, den];
            } catch (e) { /* continue */ }
        }

        return null;
    }

    toDecimal(precision = 50) {
        const rat = this.toRational();
        if (rat === null) return "〈unrecoverable〉";
        // For demo, return as fraction + approximate decimal
        const [num, den] = rat;
        if (den === 1n) return String(num);
        // Compute decimal to given precision
        let result = "";
        let n = num < 0n ? -num : num;
        if (num < 0n) result = "-";
        result += String(n / den);
        n = n % den;
        if (n !== 0n && precision > 0) {
            result += ".";
            for (let i = 0; i < precision && n !== 0n; i++) {
                n *= 10n;
                result += String(n / den);
                n = n % den;
            }
            if (n !== 0n) result += "…";
        }
        return result;
    }

    toFraction() {
        const rat = this.toRational();
        if (rat === null) return "???";
        return `${rat[0]}/${rat[1]}`;
    }

    // -- Arithmetic --

    add(other) {
        this._checkCompat(other);
        return new HenselCode((this.code + other.code) % this.modulus, this.p, this.k);
    }

    sub(other) {
        this._checkCompat(other);
        return new HenselCode((this.code - other.code + this.modulus) % this.modulus, this.p, this.k);
    }

    mul(other) {
        this._checkCompat(other);
        return new HenselCode((this.code * other.code) % this.modulus, this.p, this.k);
    }

    div(other) {
        this._checkCompat(other);
        if (other.code % this.p === 0n) throw new Error("Division by p-adic non-unit");
        const inv = modInverse(other.code, this.modulus);
        return new HenselCode((this.code * inv) % this.modulus, this.p, this.k);
    }

    equals(other) {
        return this.code === other.code && this.p === other.p && this.k === other.k;
    }

    _checkCompat(other) {
        if (this.p !== other.p || this.k !== other.k) {
            throw new Error("Incompatible Hensel codes");
        }
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// DECIMAL → RATIONAL PARSER
// ═══════════════════════════════════════════════════════════════════════════

function decimalToRational(str) {
    str = str.trim();
    let sign = 1n;
    if (str.startsWith("-")) { sign = -1n; str = str.slice(1); }
    
    if (str.includes("/")) {
        const parts = str.split("/");
        return [sign * BigInt(parts[0]), BigInt(parts[1])];
    }
    if (str.includes(".")) {
        const [intPart, fracPart] = str.split(".");
        let num = BigInt(intPart || "0");
        let den = 1n;
        for (let i = 0; i < fracPart.length; i++) {
            num = num * 10n + BigInt(fracPart[i]);
            den *= 10n;
        }
        return [sign * num, den];
    }
    return [sign * BigInt(str), 1n];
}

// ═══════════════════════════════════════════════════════════════════════════
// BRUHAT-TITS TREE (for visualization data)
// ═══════════════════════════════════════════════════════════════════════════

class BruhatTitsTree {
    constructor(p, maxDepth = 5) {
        this.p = p;
        this.maxDepth = maxDepth;
    }

    path(code, k) {
        const nodes = [];
        let modulus = 1n;
        for (let level = 0; level <= this.maxDepth; level++) {
            modulus *= this.p;
            nodes.push({ level, residue: code % modulus });
        }
        return nodes;
    }

    lcaLevel(codeA, codeB) {
        let modulus = 1n;
        for (let level = 0; level <= this.maxDepth; level++) {
            if ((codeA % modulus) !== (codeB % modulus)) return level - 1;
            modulus *= this.p;
        }
        return this.maxDepth;
    }

    ultrametricDistance(codeA, codeB) {
        const level = this.lcaLevel(codeA, codeB);
        return level >= 0 ? Number(this.p) ** (-level) : Infinity;
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// PRECOMPUTED EXAMPLES
// ═══════════════════════════════════════════════════════════════════════════

const DEMO_PRIME = 7n;
const DEMO_PRECISION = 30;

function runClassicDemo() {
    const p = DEMO_PRIME;
    const k = DEMO_PRECISION;

    const h01 = HenselCode.fromDecimal("0.1", p, k);
    const h02 = HenselCode.fromDecimal("0.2", p, k);
    const h03 = HenselCode.fromDecimal("0.3", p, k);
    const hSum = h01.add(h02);

    const results = {
        hensExact: hSum.toFraction(),
        hensDecimal: hSum.toDecimal(),
        hensEquals03: hSum.equals(h03),
        float01_02: 0.1 + 0.2,
        floatEquals03: (0.1 + 0.2) === 0.3,
        floatError: Math.abs((0.1 + 0.2) - 0.3),
        h01Fraction: h01.toFraction(),
        h02Fraction: h02.toFraction(),
        h03Fraction: h03.toFraction(),
    };

    // Patriot scenario (reduced to avoid browser hang)
    const ticks = 36000; // 1 hour at 0.1s ticks
    let floatAcc = 0;
    for (let i = 0; i < ticks; i++) floatAcc += 0.1;
    const floatExpected = ticks * 0.1;
    
    let hTicks = HenselCode.fromDecimal("0.1", p, k);
    let hAcc = HenselCode.fromDecimal("0", p, k);
    for (let i = 0; i < ticks; i++) hAcc = hAcc.add(hTicks);
    const hExpected = HenselCode.fromRational(BigInt(ticks), 10n, p, k);

    results.patriotFloat = floatAcc;
    results.patriotExpected = floatExpected;
    results.patriotError = Math.abs(floatAcc - floatExpected);
    results.patriotHensel = hAcc.toFraction();
    results.patriotExact = hAcc.equals(hExpected);

    return results;
}

// Make available globally
if (typeof window !== 'undefined') {
    window.HenselCode = HenselCode;
    window.BruhatTitsTree = BruhatTitsTree;
    window.decimalToRational = decimalToRational;
    window.modInverse = modInverse;
    window.runClassicDemo = runClassicDemo;
    window.DEMO_PRIME = DEMO_PRIME;
    window.DEMO_PRECISION = DEMO_PRECISION;
}
