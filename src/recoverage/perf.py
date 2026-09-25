"""Mann-Whitney U on call timings. Rejects a generation only when it is actually slower."""

from __future__ import annotations

import math
from pathlib import Path

from recoverage.models import MappedFunction, ProjectProfile
from recoverage.probe import ProbeSession


def mann_whitney(sample_a: list[float], sample_b: list[float]) -> tuple[float, float]:
    """Return (U for A, two-sided p) with tie correction and a normal approximation."""
    a = list(sample_a)
    b = list(sample_b)
    n1, n2 = len(a), len(b)
    if n1 == 0 or n2 == 0:
        return 0.0, 1.0
    combined = sorted([(value, 0) for value in a] + [(value, 1) for value in b])
    ranks = [0.0] * len(combined)
    index = 0
    while index < len(combined):
        end = index
        while end < len(combined) and combined[end][0] == combined[index][0]:
            end += 1
        average = (index + 1 + end) / 2
        for cursor in range(index, end):
            ranks[cursor] = average
        index = end
    rank_a = sum(ranks[index] for index, item in enumerate(combined) if item[1] == 0)
    u_a = rank_a - n1 * (n1 + 1) / 2.0
    total = n1 + n2
    tie_term = 0
    index = 0
    values = [item[0] for item in combined]
    while index < len(values):
        end = index
        while end < len(values) and values[end] == values[index]:
            end += 1
        length = end - index
        tie_term += length**3 - length
        index = end
    if total < 2:
        return u_a, 1.0
    variance = (n1 * n2 / 12.0) * ((total + 1) - tie_term / (total * (total - 1)))
    if variance <= 0:
        return u_a, 1.0
    mean = n1 * n2 / 2.0
    z = abs(u_a - mean) / math.sqrt(variance)
    p = 2.0 * (1.0 - _phi(z))
    return u_a, max(0.0, min(1.0, p))


def _phi(z: float) -> float:
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def time_functions(profile: ProjectProfile, functions: list[MappedFunction], repeats: int = 21) -> dict:
    """Compare a direct baseline call with a heavier argument draw.

    There is one version of the source, so this cannot see a commit-to-commit
    regression. It flags a function whose heavier inputs are statistically slower.
    """
    usable = [
        function
        for function in functions
        if function.spec.is_public and not function.spec.is_method and function.spec.parameters and function.spec.file.endswith(".py")
    ][:3]
    if not usable:
        return {"ran": False, "regression": False, "p_value": None, "note": "No parameterized public functions to time."}
    regressions = []
    worst_p = 1.0
    measured = 0
    session = ProbeSession(profile, call_timeout=30.0)
    try:
        for function in usable:
            baseline = _times(session, profile, function, "baseline", repeats)
            heavy = _times(session, profile, function, "heavy", repeats)
            if baseline is None or heavy is None:
                continue
            measured += 1
            _u, p_value = mann_whitney(baseline, heavy)
            worst_p = min(worst_p, p_value)
            base_med = sorted(baseline)[len(baseline) // 2]
            heavy_med = sorted(heavy)[len(heavy) // 2]
            if p_value < 0.05 and base_med > 0 and heavy_med > base_med * 8:
                regressions.append(
                    {
                        "symbol": function.spec.qualname,
                        "p_value": round(p_value, 4),
                        "median_ratio": round(heavy_med / base_med, 2),
                    }
                )
    finally:
        session.close()
    if measured == 0:
        return {
            "ran": False,
            "regression": False,
            "p_value": None,
            "regressions": [],
            "note": "No function was successfully timed.",
        }
    note = (
        "Mann-Whitney U compared baseline inputs with heavier inputs on this same revision. "
        "A regression is recorded only when p < 0.05 and the median is more than 8x slower. "
        "This is not a cross-commit EffiBench run."
    )
    if regressions:
        names = ", ".join(f"{item['symbol']} ({item['median_ratio']}x)" for item in regressions)
        note += f" Heavier inputs were slower for {names}."
    return {
        "ran": True,
        "regression": bool(regressions),
        "p_value": None if worst_p == 1.0 and not regressions else round(worst_p, 4),
        "regressions": regressions,
        "note": note,
    }


def _times(session: ProbeSession, profile: ProjectProfile, function: MappedFunction, mode: str, repeats: int) -> list[float] | None:
    payload = session.request(
        {
            "op": "time",
            "module": _module(function.spec.file, profile.src_layout),
            "qualname": function.spec.qualname,
            "args": list(_args(function, mode)),
            "repeats": repeats,
        },
        timeout=30.0,
    )
    samples = payload.get("samples")
    if not payload.get("ok") or not isinstance(samples, list) or len(samples) != repeats:
        return None
    return [float(item) for item in samples]


def _args(function: MappedFunction, mode: str) -> tuple:
    heavy = mode == "heavy"
    values = []
    for name in function.spec.parameters:
        if name in {"prices"}:
            values.append([1.0] * (200 if heavy else 3))
        elif name in {"amount", "subtotal", "subtotal_amount", "price", "captured"}:
            values.append(1000.0 if heavy else 1.0)
        elif name in {"units", "qty"}:
            values.append(100 if heavy else 1)
        elif name in {"authorized", "enabled", "flag"}:
            values.append(True)
        elif name in {"method"}:
            values.append("card")
        elif name in {"coupon"}:
            values.append("SAVE10")
        elif name in {"tier"}:
            values.append("pro")
        else:
            values.append("x" if heavy else "a")
    return tuple(values)


def _module(relative: str, src_layout: bool) -> str:
    path = Path(relative)
    if src_layout and path.parts and path.parts[0] == "src":
        path = Path(*path.parts[1:])
    return ".".join(path.with_suffix("").parts)
