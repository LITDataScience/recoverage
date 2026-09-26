"""Payment capture and refunds."""

from __future__ import annotations


def charge(amount: float, method: str, authorized: bool) -> dict:
    if amount <= 0:
        raise ValueError("amount")
    if method not in {"card", "ach"}:
        raise ValueError("method")
    if not authorized:
        return {"status": "declined", "amount": amount}
    if method == "card" and amount >= 1000:
        return {"status": "review", "amount": amount}
    fee = 0.30 if method == "card" else 0.10
    return {"status": "captured", "amount": round(amount + fee, 2), "method": method}


def refund(amount: float, captured: float) -> dict:
    if amount <= 0:
        raise ValueError("amount")
    if amount > captured:
        raise ValueError("exceeds capture")
    return {"status": "refunded", "amount": amount}
