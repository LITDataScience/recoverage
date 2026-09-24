"""Tier pricing. Unimported by the fixture tests."""

from __future__ import annotations


def tier_price(units: int, tier: str) -> float:
    if units < 0:
        raise ValueError("units")
    if tier == "free":
        return 0.0
    if tier == "pro":
        base = 20.0
    elif tier == "enterprise":
        base = 100.0
    else:
        raise ValueError("tier")
    if units > 100:
        return round(base * units * 0.8, 2)
    if units > 10:
        return round(base * units * 0.9, 2)
    return round(base * units, 2)
