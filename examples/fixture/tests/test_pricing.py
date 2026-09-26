import pytest

from shop.pricing import tier_price


def test_tier_price_covers_each_branch():
    with pytest.raises(ValueError, match="units"):
        tier_price(-1, "pro")
    assert tier_price(3, "free") == 0.0
    assert tier_price(2, "pro") == 40.0
    assert tier_price(11, "pro") == 198.0
    assert tier_price(101, "enterprise") == 8080.0
    with pytest.raises(ValueError, match="tier"):
        tier_price(1, "hobby")
