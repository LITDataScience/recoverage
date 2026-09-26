import pytest

from shop.payments import charge, refund


def test_charge_covers_each_branch():
    with pytest.raises(ValueError, match="amount"):
        charge(0, "card", True)
    with pytest.raises(ValueError, match="method"):
        charge(10, "cash", True)
    assert charge(10, "card", False) == {"status": "declined", "amount": 10}
    assert charge(1000, "card", True) == {"status": "review", "amount": 1000}
    assert charge(10, "card", True) == {"status": "captured", "amount": 10.3, "method": "card"}
    assert charge(10, "ach", True) == {"status": "captured", "amount": 10.1, "method": "ach"}


def test_refund_covers_each_branch():
    with pytest.raises(ValueError, match="amount"):
        refund(0, 10)
    with pytest.raises(ValueError, match="exceeds capture"):
        refund(11, 10)
    assert refund(4, 10) == {"status": "refunded", "amount": 4}
