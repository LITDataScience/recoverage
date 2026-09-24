from shop.cart import subtotal


def test_subtotal_sums_prices():
    assert subtotal([1.0, 2.5, 3.0]) == 6.5
