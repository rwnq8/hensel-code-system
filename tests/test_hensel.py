"""
Tests for Hensel Code System.
Run: python tests/test_hensel.py
"""

import sys
sys.path.insert(0, 'src')

from hensel_system import HenselCode, BruhatTitsTree
import math


def test_encode_decode():
    """Test basic encoding and decoding of rationals."""
    p, k = 7, 30
    
    test_cases = [
        (1, 10),   # 0.1
        (1, 3),    # 1/3
        (1, 5),    # 0.2
        (3, 10),   # 0.3
        (2, 3),    # 2/3
        (7, 2),    # 3.5
        (0, 1),    # 0
        (1, 1),    # 1
        (-1, 3),   # -1/3
        (100, 11), # 100/11 (denom coprime to 7)
    ]
    
    for num, den in test_cases:
        h = HenselCode.from_rational(num, den, p, k)
        recovered = h.to_rational()
        assert recovered is not None, f"Failed to recover {num}/{den}"
        rnum, rden = recovered
        # Check equivalence (may be reduced)
        assert num * rden == den * rnum, \
            f"{num}/{den} recovered as {rnum}/{rden}"


def test_exact_arithmetic():
    """Test that Hensel arithmetic is exact."""
    p, k = 7, 30
    
    # 0.1 + 0.2 = 0.3
    h01 = HenselCode.from_rational(1, 10, p, k)
    h02 = HenselCode.from_rational(2, 10, p, k)
    h03 = HenselCode.from_rational(3, 10, p, k)
    assert (h01 + h02) == h03, "0.1 + 0.2 != 0.3 in Hensel"
    
    # 1/3 * 3 = 1
    h_third = HenselCode.from_rational(1, 3, p=5, k=20)
    h_one = HenselCode.from_rational(1, 1, p=5, k=20)
    h_three = HenselCode.from_rational(3, 1, p=5, k=20)
    assert (h_third * h_three) == h_one, "(1/3)*3 != 1 in Hensel"
    
    # 1/7 * 7 = 1
    h_seventh = HenselCode.from_rational(1, 7, p=11, k=15)
    h_seven = HenselCode.from_rational(7, 1, p=11, k=15)
    h_one = HenselCode.from_rational(1, 1, p=11, k=15)
    assert (h_seventh * h_seven) == h_one, "(1/7)*7 != 1 in Hensel"
    
    # Subtraction
    assert (h03 - h01) == h02, "0.3 - 0.1 != 0.2 in Hensel"
    
    # Division
    assert (h03 / h01) == HenselCode.from_rational(3, 1, p, k), "0.3/0.1 != 3 in Hensel"


def test_float_comparison():
    """Test that IEEE 754 float fails where Hensel succeeds."""
    # The classic 0.1 + 0.2 != 0.3 in float
    assert 0.1 + 0.2 != 0.3, "Float should fail 0.1+0.2==0.3"
    
    p, k = 7, 30
    h01 = HenselCode.from_rational(1, 10, p, k)
    h02 = HenselCode.from_rational(2, 10, p, k)
    h03 = HenselCode.from_rational(3, 10, p, k)
    assert (h01 + h02) == h03, "Hensel should pass 0.1+0.2==0.3"


def test_patriot_scenario():
    """Test accumulated error over many ticks."""
    ticks = 100000
    p, k = 7, 30
    
    # Float accumulation
    float_acc = 0.0
    for _ in range(ticks):
        float_acc += 0.1
    float_expected = ticks * 0.1
    float_error = abs(float_acc - float_expected)
    assert float_error > 1e-10, f"Float should have detectable error, got {float_error}"
    
    # Hensel accumulation
    h_tick = HenselCode.from_rational(1, 10, p, k)
    h_acc = HenselCode.from_rational(0, 1, p, k)
    for _ in range(ticks):
        h_acc = h_acc + h_tick
    h_expected = HenselCode.from_rational(ticks, 10, p, k)
    assert h_acc == h_expected, "Hensel accumulation should be exact"


def test_bruhat_tits_tree():
    """Test ultrametric and clustering."""
    p = 5
    tree = BruhatTitsTree(p, max_depth=5)
    
    h1 = HenselCode.from_rational(1, 2, p, k=10)
    h2 = HenselCode.from_rational(1, 3, p, k=10)
    h3 = HenselCode.from_rational(3, 4, p, k=10)
    
    codes = [h1, h2, h3]
    
    # Self-distance should be minimal (p^{-max_depth}) for finite-depth tree
    d11 = tree.ultrametric_distance(h1, h1)
    assert d11 <= p ** (-tree.max_depth) + 1e-10, f"Self-distance too large: {d11}"
    
    # Ultrametric property: d(x,z) <= max(d(x,y), d(y,z))
    d12 = tree.ultrametric_distance(h1, h2)
    d23 = tree.ultrametric_distance(h2, h3)
    d13 = tree.ultrametric_distance(h1, h3)
    assert d13 <= max(d12, d23) + 1e-10, \
        f"Ultrametric violated: d13={d13} > max(d12={d12}, d23={d23})"


def test_negative_numbers():
    """Test encoding/decoding of negative rationals."""
    p, k = 7, 20
    
    test_cases = [(-1, 3), (-2, 5), (-3, 10), (-7, 2)]
    
    for num, den in test_cases:
        h = HenselCode.from_rational(num, den, p, k)
        recovered = h.to_rational()
        assert recovered is not None, f"Failed to recover {num}/{den}"
        rnum, rden = recovered
        assert num * rden == den * rnum, \
            f"{num}/{den} recovered as {rnum}/{rden}"


def test_edge_cases():
    """Test edge cases."""
    p, k = 7, 20
    
    # Zero
    h0 = HenselCode.from_rational(0, 1, p, k)
    recovered = h0.to_rational()
    assert recovered == (0, 1), f"Zero recovered as {recovered}"
    
    # One
    h1 = HenselCode.from_rational(1, 1, p, k)
    recovered = h1.to_rational()
    assert recovered == (1, 1), f"One recovered as {recovered}"
    
    # Large denominator
    h = HenselCode.from_rational(1, 100, p, k)
    recovered = h.to_rational()
    assert recovered is not None, "Failed large denominator"
    assert recovered[0] * 100 == recovered[1], f"1/100 recovered as {recovered}"
    
    # Denom divisible by p should raise
    try:
        HenselCode.from_rational(1, 7, p, k)
        assert False, "Should have raised ValueError"
    except ValueError:
        pass  # Expected


def test_valuation():
    """Test p-adic valuation v_p(r)."""
    p, k = 7, 30
    primes = [5, 11, 13]
    
    for prime in primes:
        # p itself should have valuation 1
        h = HenselCode.from_rational(prime, 1, prime, k=20)
        assert h.valuation() == 1, f"v_{prime}({prime}) should be 1, got {h.valuation()}"
        
        # p^3 should have valuation 3
        h = HenselCode.from_rational(prime**3, 1, prime, k=20)
        assert h.valuation() == 3, f"v_{prime}({prime**3}) should be 3, got {h.valuation()}"
        
        # 1 should have valuation 0
        h = HenselCode.from_rational(1, 1, prime, k=20)
        assert h.valuation() == 0, f"v_{prime}(1) should be 0, got {h.valuation()}"
        
        # Number coprime to p should have valuation 0
        non_div = prime + 1  # coprime: p+1 mod p = 1
        h = HenselCode.from_rational(non_div, 1, prime, k=20)
        assert h.valuation() == 0, f"v_{prime}({non_div}) should be 0"
    
    # Zero → valuation = k (precision limit)
    h0 = HenselCode.from_rational(0, 1, p, k)
    assert h0.valuation() == k, f"v_p(0) should be k={k}, got {h0.valuation()}"
    
    # ord_p alias
    h = HenselCode.from_rational(7, 1, p, k)  # 7 is p=7
    assert h.ord_p() == 1, "ord_p alias should match valuation"


def test_padic_norm():
    """Test p-adic norm |r|_p = p^{-v_p(r)}."""
    p, k = 5, 20
    
    # |5|_5 = 1/5 = 0.2
    h = HenselCode.from_rational(5, 1, p, k)
    assert abs(h.padic_norm() - 0.2) < 1e-10, f"|5|_5 should be 0.2, got {h.padic_norm()}"
    
    # |25|_5 = 1/25 = 0.04
    h = HenselCode.from_rational(25, 1, p, k)
    assert abs(h.padic_norm() - 0.04) < 1e-10, f"|25|_5 should be 0.04, got {h.padic_norm()}"
    
    # |1|_5 = 1
    h = HenselCode.from_rational(1, 1, p, k)
    assert abs(h.padic_norm() - 1.0) < 1e-10, f"|1|_5 should be 1, got {h.padic_norm()}"
    
    # Ultrametric property: |x + y|_p ≤ max(|x|_p, |y|_p)
    h1 = HenselCode.from_rational(5, 1, p, k)
    h2 = HenselCode.from_rational(25, 1, p, k)
    h_sum = h1 + h2
    assert h_sum.padic_norm() <= max(h1.padic_norm(), h2.padic_norm()) + 1e-10, \
        "Ultrametric inequality violated for 5-adic norm"


def test_is_unit():
    """Test p-adic unit detection."""
    p, k = 5, 15
    
    # Numbers not divisible by p are units
    h = HenselCode.from_rational(1, 1, p, k)
    assert h.is_unit(), "1 should be a unit"
    
    h = HenselCode.from_rational(2, 1, p, k)
    assert h.is_unit(), "2 should be a unit"
    
    h = HenselCode.from_rational(6, 1, p, k)  # 6 mod 5 = 1
    assert h.is_unit(), "6 should be a unit"
    
    # Numbers divisible by p are NOT units
    h = HenselCode.from_rational(5, 1, p, k)
    assert not h.is_unit(), "5 should not be a unit"
    
    h = HenselCode.from_rational(10, 1, p, k)
    assert not h.is_unit(), "10 should not be a unit"


def test_pev():
    """Test Prime Exponent Vector (PEV) representation."""
    p, k = 7, 30
    
    # 108 = 2^2 * 3^3
    h = HenselCode.from_rational(108, 1, p, k)
    pev = h.pev()
    assert pev.get(2) == 2, f"PEV of 108: v_2 should be 2, got {pev.get(2)}"
    assert pev.get(3) == 3, f"PEV of 108: v_3 should be 3, got {pev.get(3)}"
    
    # 1/10 = 2^{-1} * 5^{-1}
    h = HenselCode.from_rational(1, 10, p, k)
    pev = h.pev()
    assert pev.get(2) == -1, f"PEV of 1/10: v_2 should be -1, got {pev.get(2)}"
    assert pev.get(5) == -1, f"PEV of 1/10: v_5 should be -1, got {pev.get(5)}"
    
    # pev_str
    s = h.pev_str()
    assert "2" in s and "5" in s, f"PEV string should contain primes: {s}"


def test_gcd_lcm():
    """Test GCD and LCM operations on Hensel codes."""
    p, k = 7, 20
    
    # gcd(12, 18) = 6
    h12 = HenselCode.from_rational(12, 1, p, k)
    h18 = HenselCode.from_rational(18, 1, p, k)
    h_gcd = h12.gcd(h18)
    r = h_gcd.to_rational()
    assert r == (6, 1), f"gcd(12,18) should be 6/1, got {r}"
    
    # lcm(12, 18) = 36
    h_lcm = h12.lcm(h18)
    r = h_lcm.to_rational()
    assert r == (36, 1), f"lcm(12,18) should be 36/1, got {r}"
    
    # gcd × lcm = |a × b| (for integers)
    h_prod_gcd_lcm = h_gcd * h_lcm
    h_prod_ab = h12 * h18
    # Recover rationals
    r1 = h_prod_gcd_lcm.to_rational()
    r2 = h_prod_ab.to_rational()
    assert r1[0] * r2[1] == r2[0] * r1[1], \
        f"gcd*lcm should equal |a*b|: {r1} vs {r2}"
    
    # Test with rationals: gcd(1/2, 1/3) = 1/6
    h_half = HenselCode.from_rational(1, 2, p=5, k=20)
    h_third = HenselCode.from_rational(1, 3, p=5, k=20)
    h_gcd2 = h_half.gcd(h_third)
    r = h_gcd2.to_rational()
    assert r is not None, f"gcd(1/2, 1/3) should recover"
    assert r[0] * 6 == r[1], f"gcd(1/2, 1/3) should be 1/6, got {r}"


def test_comparison():
    """Test comparison operators on Hensel codes."""
    p, k = 7, 20
    
    h_half = HenselCode.from_rational(1, 2, p, k)
    h_one = HenselCode.from_rational(1, 1, p, k)
    h_ten = HenselCode.from_rational(10, 1, p, k)
    h_neg = HenselCode.from_rational(-3, 1, p, k)
    
    assert h_half < h_one, "1/2 should be < 1"
    assert h_half <= h_one, "1/2 should be <= 1"
    assert h_one > h_half, "1 should be > 1/2"
    assert h_one >= h_half, "1 should be >= 1/2"
    assert h_one <= h_one, "1 should be <= 1"
    assert h_one >= h_one, "1 should be >= 1"
    assert h_neg < h_half, "-3 should be < 1/2"
    assert h_ten > h_one, "10 should be > 1"


def test_power():
    """Test exact exponentiation."""
    p, k = 7, 20
    
    # 3^4 = 81
    h3 = HenselCode.from_rational(3, 1, p, k)
    h81 = HenselCode.from_rational(81, 1, p, k)
    assert h3 ** 4 == h81, "3^4 should be 81"
    
    # (1/2)^3 = 1/8
    h_half = HenselCode.from_rational(1, 2, p, k)
    h_eighth = HenselCode.from_rational(1, 8, p, k)
    assert h_half ** 3 == h_eighth, "(1/2)^3 should be 1/8"
    
    # x^0 = 1
    h_one = HenselCode.from_rational(1, 1, p, k)
    assert h3 ** 0 == h_one, "x^0 should be 1"
    
    # Negative exponent (for units): 2^{-1} = 1/2
    h2 = HenselCode.from_rational(2, 1, p, k)
    h_inv = h2 ** (-1)
    h_half2 = HenselCode.from_rational(1, 2, p, k)
    assert h_inv == h_half2, "2^{-1} should be 1/2"
    
    # Non-unit negative exponent should raise
    h_p = HenselCode.from_rational(p, 1, p, k)  # p=7, divisible by p
    try:
        _ = h_p ** (-1)
        assert False, "Should have raised ValueError for non-unit inverse"
    except ValueError:
        pass


def test_abs():
    """Test absolute value."""
    p, k = 7, 20
    
    h_neg = HenselCode.from_rational(-5, 3, p, k)
    h_pos = abs(h_neg)
    r = h_pos.to_rational()
    assert r[0] >= 0, "abs(negative) should be positive"
    assert r[0] * 3 == r[1] * 5, f"abs(-5/3) should be 5/3, got {r}"
    
    h_pos2 = HenselCode.from_rational(5, 3, p, k)
    assert h_pos == h_pos2, "abs(-5/3) should equal 5/3"


def test_simplify():
    """Test rational simplification."""
    p, k = 7, 20
    
    # 6/8 = 3/4
    h = HenselCode.from_rational(6, 8, p, k)
    h_simple = h.simplify()
    r = h_simple.to_rational()
    assert r == (3, 4), f"6/8 should simplify to 3/4, got {r}"
    
    # 100/10 = 10/1
    h = HenselCode.from_rational(100, 10, p, k)
    h_simple = h.simplify()
    r = h_simple.to_rational()
    assert r == (10, 1), f"100/10 should simplify to 10/1, got {r}"


def test_int_arithmetic():
    """Test arithmetic between Hensel codes and Python ints."""
    p, k = 7, 20
    
    h5 = HenselCode.from_rational(5, 1, p, k)
    
    # int + Hensel
    h_sum = 3 + h5
    r = h_sum.to_rational()
    assert r == (8, 1), f"3 + 5 should be 8, got {r}"
    
    # int * Hensel
    h_prod = 3 * h5
    r = h_prod.to_rational()
    assert r == (15, 1), f"3 * 5 should be 15, got {r}"
    
    # int - Hensel
    h_diff = 10 - h5
    r = h_diff.to_rational()
    assert r == (5, 1), f"10 - 5 should be 5, got {r}"


# ═══════════════════════════════════════════════════════════════════════════════
# PROPERTY-BASED TESTS — verify algebraic laws hold
# ═══════════════════════════════════════════════════════════════════════════════

def test_property_commutativity():
    """Test a + b = b + a and a * b = b * a."""
    p, k = 7, 30
    cases = [
        (1, 10), (1, 3), (2, 3), (7, 2), (100, 11),
        (-1, 3), (22, 7), (355, 113),
    ]
    
    for num1, den1 in cases:
        for num2, den2 in cases:
            if den1 % p == 0 or den2 % p == 0:
                continue
            h1 = HenselCode.from_rational(num1, den1, p, k)
            h2 = HenselCode.from_rational(num2, den2, p, k)
            
            assert h1 + h2 == h2 + h1, \
                f"Addition not commutative: {num1}/{den1} + {num2}/{den2}"
            assert h1 * h2 == h2 * h1, \
                f"Multiplication not commutative: {num1}/{den1} * {num2}/{den2}"


def test_property_associativity():
    """Test (a+b)+c = a+(b+c) and (a*b)*c = a*(b*c)."""
    p, k = 5, 20
    cases = [(1, 2), (1, 3), (2, 3), (3, 4), (-1, 2), (5, 1)]
    
    for num1, den1 in cases:
        for num2, den2 in cases:
            for num3, den3 in cases:
                if den1 % p == 0 or den2 % p == 0 or den3 % p == 0:
                    continue
                h1 = HenselCode.from_rational(num1, den1, p, k)
                h2 = HenselCode.from_rational(num2, den2, p, k)
                h3 = HenselCode.from_rational(num3, den3, p, k)
                
                assert (h1 + h2) + h3 == h1 + (h2 + h3), "Addition not associative"
                assert (h1 * h2) * h3 == h1 * (h2 * h3), "Multiplication not associative"


def test_property_distributivity():
    """Test a*(b+c) = a*b + a*c."""
    p, k = 5, 20
    cases = [(1, 2), (1, 3), (2, 3), (5, 1)]
    
    for num1, den1 in cases:
        for num2, den2 in cases:
            for num3, den3 in cases:
                if den1 % p == 0 or den2 % p == 0 or den3 % p == 0:
                    continue
                h1 = HenselCode.from_rational(num1, den1, p, k)
                h2 = HenselCode.from_rational(num2, den2, p, k)
                h3 = HenselCode.from_rational(num3, den3, p, k)
                
                left = h1 * (h2 + h3)
                right = (h1 * h2) + (h1 * h3)
                assert left == right, \
                    f"Distributivity failed: {num1}/{den1} * ({num2}/{den2} + {num3}/{den3})"


def test_property_identities():
    """Test additive and multiplicative identities."""
    p, k = 7, 20
    cases = [(1, 10), (1, 3), (5, 1), (-2, 3), (100, 11)]
    
    h_zero = HenselCode.from_rational(0, 1, p, k)
    h_one = HenselCode.from_rational(1, 1, p, k)
    
    for num, den in cases:
        if den % p == 0:
            continue
        h = HenselCode.from_rational(num, den, p, k)
        
        assert h + h_zero == h, f"Additive identity failed for {num}/{den}"
        assert h * h_one == h, f"Multiplicative identity failed for {num}/{den}"
        assert h - h == h_zero, f"a - a should be 0 for {num}/{den}"
    
    h5 = HenselCode.from_rational(5, 1, p, k)
    assert h5 / h5 == h_one, "a / a should be 1"


def test_property_gcd_lcm_identity():
    """Test gcd(a,b) * lcm(a,b) = a * b for integers."""
    p, k = 5, 20
    
    test_pairs = [(12, 18), (8, 12), (15, 25), (7, 13), (100, 10)]
    
    for a_int, b_int in test_pairs:
        ha = HenselCode.from_rational(a_int, 1, p, k)
        hb = HenselCode.from_rational(b_int, 1, p, k)
        
        h_gcd = ha.gcd(hb)
        h_lcm = ha.lcm(hb)
        
        product1 = h_gcd * h_lcm
        product2 = ha * hb
        
        r1 = product1.to_rational()
        r2 = product2.to_rational()
        assert r1 is not None and r2 is not None, "Recovery failed in gcd*lcm test"
        assert r1[0] * r2[1] == r2[0] * r1[1], \
            f"gcd({a_int},{b_int}) * lcm({a_int},{b_int}) != {a_int} * {b_int}"


# Stress, edge case, regression, and cross-verification tests for Hensel Code System

def test_stress_large_rationals():
    """Test encoding/decoding of large rationals."""
    p, k = 7, 40
    large_cases = [
        (10**12, 1), (10**12, 3), (2**50, 1),
        (1, 10**6), (10**10, 10**10 + 1), (123456789, 987654321),
    ]
    for num, den in large_cases:
        if den % p == 0:
            continue
        h = HenselCode.from_rational(num, den, p, k)
        r = h.to_rational()
        assert r is not None, f"Failed to recover large rational {num}/{den}"
        rnum, rden = r
        assert num * rden == den * rnum, \
            f"Large rational {num}/{den} recovered as {rnum}/{rden}"


def test_stress_chained_operations():
    """Test many chained arithmetic operations."""
    p, k = 7, 30
    h = HenselCode.from_rational(1, 1, p, k)
    h_tick = HenselCode.from_rational(1, 1000, p, k)
    for _ in range(1000):
        h = h + h_tick
    r = h.to_rational()
    assert r == (2, 1), f"1000 * 0.001 + 1 should be 2, got {r}"
    
    h = HenselCode.from_rational(1, 1, p, k)
    h2 = HenselCode.from_rational(2, 1, p, k)
    for _ in range(10):
        h = h * h2
    r = h.to_rational()
    assert r == (1024, 1), f"2^10 should be 1024, got {r}"


def test_stress_many_encodings():
    """Test encoding many different rationals in the same space."""
    p, k = 7, 30
    for num in range(-20, 21):
        for den in range(1, 21):
            if num == 0:
                continue
            if den % p == 0:
                continue
            h = HenselCode.from_rational(num, den, p, k)
            r = h.to_rational()
            assert r is not None, f"Failed {num}/{den}"
            rnum, rden = r
            assert num * rden == den * rnum, \
                f"{num}/{den} recovered as {rnum}/{rden}"


def test_stress_multiple_primes():
    """Test that all operations work across multiple prime bases."""
    test_primes = [5, 7, 11, 13, 17, 19, 23, 29, 31, 37]
    for p_base in test_primes:
        k = 15
        if 10 % p_base == 0:
            continue
        h1 = HenselCode.from_rational(1, 10, p_base, k)
        h2 = HenselCode.from_rational(2, 10, p_base, k)
        h3 = HenselCode.from_rational(3, 10, p_base, k)
        assert h1 + h2 == h3, f"0.1+0.2 != 0.3 in p={p_base}"
        r = h1.to_rational()
        assert r is not None, f"Recovery failed for p={p_base}"
        assert r[0] * 10 == r[1], f"1/10 recovery wrong for p={p_base}"


def test_edge_zero_operations():
    """Test zero handling in all operations."""
    p, k = 7, 20
    h0 = HenselCode.from_rational(0, 1, p, k)
    h1 = HenselCode.from_rational(1, 1, p, k)
    h5 = HenselCode.from_rational(5, 1, p, k)
    
    assert h0 + h5 == h5, "0 + a should be a"
    assert h5 + h0 == h5, "a + 0 should be a"
    assert h0 * h5 == h0, "0 * a should be 0"
    assert h0 - h5 == HenselCode.from_rational(-5, 1, p, k), "0 - 5 should be -5"
    assert h5 - h0 == h5, "a - 0 should be a"
    assert (h0 / h5) == h0, "0 / 5 should be 0"
    assert abs(h0) == h0, "abs(0) should be 0"
    assert h0 ** 3 == h0, "0^3 should be 0"
    assert h0.valuation() == k, f"valuation of 0 should be k={k}"
    assert h0.gcd(h5) == h5, "gcd(0,5) should be 5"


def test_edge_code_zero():
    """Test edge cases where code is 0."""
    p, k = 7, 20
    h0 = HenselCode.from_rational(0, 1, p, k)
    r = h0.to_rational()
    assert r == (0, 1), f"Code 0 should recover as 0/1, got {r}"
    
    h_big = HenselCode.from_rational(7**20, 1, p, k)
    assert h_big.code == 0, "p^k should map to code 0"
    
    h_mixed = HenselCode.from_rational(7**20 * 2, 1, p, k)
    assert h_mixed.code == 0, "2*p^k should also map to code 0"


def test_edge_exponent_boundaries():
    """Test exponentiation edge cases."""
    p, k = 7, 20
    h2 = HenselCode.from_rational(2, 1, p, k)
    h_one = HenselCode.from_rational(1, 1, p, k)
    
    assert h2 ** 0 == h_one, "x^0 should be 1"
    assert h_one ** 100 == h_one, "1^100 should be 1"
    assert h2 ** 1 == h2, "x^1 should be x"
    
    h_inv = h2 ** (-1)
    assert (h2 * h_inv) == h_one, "x * x^(-1) should be 1"
    
    h_inv2 = h2 ** (-2)
    assert (h2 ** 2) * h_inv2 == h_one, "x^2 * x^(-2) should be 1"


def test_edge_simplify_idempotent():
    """Test that simplify is idempotent."""
    p, k = 7, 20
    h = HenselCode.from_rational(3, 5, p, k)
    h_simple = h.simplify()
    assert h == h_simple, "Simplifying 3/5 should give 3/5"
    
    h2 = HenselCode.from_rational(6, 8, p, k)
    h_simple1 = h2.simplify()
    h_simple2 = h_simple1.simplify()
    assert h_simple1 == h_simple2, "simplify should be idempotent"


def test_edge_negative_rationals_all_ops():
    """Test all operations with negative rationals."""
    p, k = 7, 20
    h_neg = HenselCode.from_rational(-3, 1, p, k)
    h_pos = HenselCode.from_rational(5, 1, p, k)
    
    r = (h_neg + h_pos).to_rational()
    assert r == (2, 1), f"-3 + 5 should be 2, got {r}"
    
    r = (h_neg * h_pos).to_rational()
    assert r == (-15, 1), f"-3 * 5 should be -15, got {r}"
    
    r = (h_neg - h_pos).to_rational()
    assert r == (-8, 1), f"-3 - 5 should be -8, got {r}"
    
    assert abs(h_neg).to_rational() == (3, 1), "abs(-3) should be 3"
    
    h_neg2 = HenselCode.from_rational(-7, 1, p, k)
    assert h_neg2 < h_neg, "-7 should be < -3"


def test_regression_one_tenth():
    """Original bug: 1/10 with p=7, k=30 must recover correctly."""
    p, k = 7, 30
    h = HenselCode.from_rational(1, 10, p, k)
    r = h.to_rational()
    assert r is not None, "0.1 recovery should not be None"
    assert r == (1, 10), f"0.1 should recover as 1/10, got {r}"


def test_regression_fraction_termination():
    """Test fractions that terminate in decimal vs Hensel."""
    p, k = 7, 30
    h = HenselCode.from_rational(1, 2, p, k)
    r = h.to_rational()
    assert r == (1, 2), f"1/2 recovery failed"
    
    h = HenselCode.from_rational(1, 4, p, k)
    r = h.to_rational()
    assert r == (1, 4), f"1/4 recovery failed"
    
    h = HenselCode.from_rational(1, 3, p, k)
    r = h.to_rational()
    assert r == (1, 3), f"1/3 recovery failed"


def test_regression_pev_edge_cases():
    """Test PEV for special numbers."""
    p, k = 7, 30
    h = HenselCode.from_rational(1, 1, p, k)
    pev = h.pev()
    assert pev == {}, f"PEV of 1 should be empty, got {pev}"
    
    h = HenselCode.from_rational(17, 1, p, k)
    pev = h.pev()
    assert pev == {17: 1}, f"PEV of 17 should be {{17: 1}}, got {pev}"
    
    h = HenselCode.from_rational(1, 6, p=5, k=20)
    pev = h.pev()
    assert pev.get(2) == -1 and pev.get(3) == -1, \
        f"PEV of 1/6 should have 2^-1 and 3^-1, got {pev}"


def test_regression_incompatible_codes():
    """Test that incompatible Hensel codes raise errors."""
    p1, k1 = 7, 20
    p2, k2 = 5, 20
    p3, k3 = 7, 30
    
    h1 = HenselCode.from_rational(1, 3, p1, k1)
    h2 = HenselCode.from_rational(1, 3, p2, k2)
    h3 = HenselCode.from_rational(1, 3, p3, k3)
    
    try:
        _ = h1 + h2
        assert False, "Should raise for incompatible p"
    except ValueError:
        pass
    
    try:
        _ = h1 + h3
        assert False, "Should raise for incompatible k"
    except ValueError:
        pass
    
    h_p = HenselCode.from_rational(p1, 1, p1, k1)
    try:
        _ = h1 / h_p
        assert False, "Should raise for division by non-unit"
    except ValueError:
        pass


def test_cross_verify_roundtrip():
    """Test that encode-arithmetic-decode preserves exact values."""
    p, k = 7, 30
    h01 = HenselCode.from_rational(1, 10, p, k)
    h02 = HenselCode.from_rational(2, 10, p, k)
    h_sum = h01 + h02
    
    r = h_sum.to_rational()
    assert r == (3, 10), f"Chain recovery failed: got {r}"
    
    h03 = HenselCode.from_rational(3, 10, p, k)
    assert h_sum == h03, "Chain equality failed"
    assert 0.1 + 0.2 != 0.3, "IEEE 754 should fail this test"


def test_cross_verify_new_ops_consistency():
    """Test that new operations are consistent with each other."""
    p, k = 7, 30
    h72 = HenselCode.from_rational(72, 1, p, k)
    h108 = HenselCode.from_rational(108, 1, p, k)
    
    h_gcd = h72.gcd(h108)
    h_lcm = h72.lcm(h108)
    h_prod = h72 * h108
    gxl = h_gcd * h_lcm
    assert gxl == h_prod, "gcd * lcm should equal a * b"
    
    assert h72.valuation() == 0, "72 should have 7-adic valuation 0"
    assert h108.valuation() == 0, "108 should have 7-adic valuation 0"
    
    h_68 = HenselCode.from_rational(6, 8, p, k)
    h_simple = h_68.simplify()
    r = h_simple.to_rational()
    assert r == (3, 4), "simplify(6/8) should give 3/4"


if __name__ == "__main__":
    test_encode_decode()
    print("✓ test_encode_decode passed")
    
    test_exact_arithmetic()
    print("✓ test_exact_arithmetic passed")
    
    test_float_comparison()
    print("✓ test_float_comparison passed")
    
    test_patriot_scenario()
    print("✓ test_patriot_scenario passed")
    
    test_bruhat_tits_tree()
    print("✓ test_bruhat_tits_tree passed")
    
    test_negative_numbers()
    print("✓ test_negative_numbers passed")
    
    test_edge_cases()
    print("✓ test_edge_cases passed")
    
    test_valuation()
    print("✓ test_valuation passed")
    
    test_padic_norm()
    print("✓ test_padic_norm passed")
    
    test_is_unit()
    print("✓ test_is_unit passed")
    
    test_pev()
    print("✓ test_pev passed")
    
    test_gcd_lcm()
    print("✓ test_gcd_lcm passed")
    
    test_comparison()
    print("✓ test_comparison passed")
    
    test_power()
    print("✓ test_power passed")
    
    test_abs()
    print("✓ test_abs passed")
    
    test_simplify()
    print("✓ test_simplify passed")
    
    test_int_arithmetic()
    print("✓ test_int_arithmetic passed")
    
    test_property_commutativity()
    print("✓ test_property_commutativity passed")
    
    test_property_associativity()
    print("✓ test_property_associativity passed")
    
    test_property_distributivity()
    print("✓ test_property_distributivity passed")
    
    test_property_identities()
    print("✓ test_property_identities passed")
    
    test_property_gcd_lcm_identity()
    print("✓ test_property_gcd_lcm_identity passed")
    
    test_stress_large_rationals()
    print("✓ test_stress_large_rationals passed")
    
    test_stress_chained_operations()
    print("✓ test_stress_chained_operations passed")
    
    test_stress_many_encodings()
    print("✓ test_stress_many_encodings passed")
    
    test_stress_multiple_primes()
    print("✓ test_stress_multiple_primes passed")
    
    test_edge_zero_operations()
    print("✓ test_edge_zero_operations passed")
    
    test_edge_code_zero()
    print("✓ test_edge_code_zero passed")
    
    test_edge_exponent_boundaries()
    print("✓ test_edge_exponent_boundaries passed")
    
    test_edge_simplify_idempotent()
    print("✓ test_edge_simplify_idempotent passed")
    
    test_edge_negative_rationals_all_ops()
    print("✓ test_edge_negative_rationals_all_ops passed")
    
    test_regression_one_tenth()
    print("✓ test_regression_one_tenth passed")
    
    test_regression_fraction_termination()
    print("✓ test_regression_fraction_termination passed")
    
    test_regression_pev_edge_cases()
    print("✓ test_regression_pev_edge_cases passed")
    
    test_regression_incompatible_codes()
    print("✓ test_regression_incompatible_codes passed")
    
    test_cross_verify_roundtrip()
    print("✓ test_cross_verify_roundtrip passed")
    
    test_cross_verify_new_ops_consistency()
    print("✓ test_cross_verify_new_ops_consistency passed")
    
    print(f"\n🎉 ALL {37} TESTS PASSED")
