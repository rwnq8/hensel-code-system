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
    
    print("\n🎉 ALL TESTS PASSED")
