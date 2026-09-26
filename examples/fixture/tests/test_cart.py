import pytest

from shop.cart import apply_coupon, subtotal


def test_subtotal_sums_prices():
    assert subtotal([1.0, 2.5, 3.0]) == 6.5


def test_subtotal_empty_list_is_zero():
    assert subtotal([]) == 0.0


def test_subtotal_rejects_a_negative_price():
    with pytest.raises(ValueError, match="negative price"):
        subtotal([1.0, -0.5])


def test_apply_coupon_covers_each_branch():
    with pytest.raises(ValueError, match="subtotal"):
        apply_coupon(-1, None)
    assert apply_coupon(10, None) == 10
    assert apply_coupon(10, "") == 10
    assert apply_coupon(10, "SAVE10") == 9
    assert apply_coupon(50, "HALF") == 25
    with pytest.raises(ValueError, match="unknown coupon"):
        apply_coupon(10, "HALF")
    with pytest.raises(ValueError, match="unknown coupon"):
        apply_coupon(10, "NOPE")
