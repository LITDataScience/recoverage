"""Cart totals and coupons."""

from __future__ import annotations


def subtotal(prices: list[float]) -> float:
    if not prices:
        return 0.0
    total = 0.0
    for price in prices:
        if price < 0:
            raise ValueError("negative price")
        total += price
    return round(total, 2)


def apply_coupon(subtotal_amount: float, coupon: str | None) -> float:
    if subtotal_amount < 0:
        raise ValueError("subtotal")
    if coupon is None or coupon == "":
        return round(subtotal_amount, 2)
    if coupon == "SAVE10":
        return round(subtotal_amount * 0.9, 2)
    if coupon == "HALF" and subtotal_amount >= 50:
        return round(subtotal_amount * 0.5, 2)
    raise ValueError("unknown coupon")
