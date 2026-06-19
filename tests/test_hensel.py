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
    
    print(f"\n🎉 ALL {17} TESTS PASSED")
