"""Heuristic gap analysis. Labels say so when a conclusion is not a measurement."""

from __future__ import annotations

import re
from pathlib import Path

from recoverage.models import SEVERITY_ORDER, Gap, MappedFunction, ProjectProfile
from recoverage.sources import SourceCache


def find_gaps(
    profile: ProjectProfile,
    functions: list[MappedFunction],
    extra: list[Gap] | None = None,
    *,
    cache: SourceCache | None = None,
) -> list[Gap]:
    gaps: list[Gap] = []
    runner = profile.test_runner
    if not profile.test_runner:
        gaps.append(
            Gap(
                id="",
                severity="critical",
                kind="no-test-runner",
                title="No test runner detected",
                why="Recoverage could not find pytest, unittest, jest, or vitest. There is no executable check on this tree.",
                file="",
                symbol=None,
                suggestion="Add a runner Recoverage can see: pytest (pyproject/pytest.ini) or jest/vitest (package.json), then re-run.",
                heuristic=False,
            )
        )
    if profile.flake_markers:
        gaps.append(
            Gap(
                id="",
                severity="low",
                kind="flake-marker",
                title="Flake markers are present",
                why=(
                    "Static scan found markers that usually mean a test was already considered flaky: "
                    + "; ".join(profile.flake_markers)
                    + ". Recoverage did not re-run those tests, so this is not a flake reproduction."
                ),
                file=profile.flake_markers[0].split(":", 1)[0],
                symbol=None,
                suggestion="Quarantine or fix the marked tests before treating a green run as stable.",
                heuristic=True,
            )
        )
    test_names = _test_identifiers(profile, cache)
    measured = _any_measured(functions)
    for function in functions:
        gap = _function_gap(function, test_names, runner, measured=measured)
        if gap is not None:
            gaps.append(gap)
    if profile.skipped_projects:
        listed = ", ".join(profile.skipped_projects[:12])
        more = len(profile.skipped_projects) - 12
        if more > 0:
            listed = f"{listed}, and {more} more"
        gaps.append(
            Gap(
                id="",
                severity="high" if not profile.source_files else "low",
                kind="skipped-workspaces",
                title=f"{len(profile.skipped_projects)} nested projects were not analyzed",
                why=(
                    "Each of these directories has its own manifest, so this run did not read them: "
                    f"{listed}. A workspace root is not the product."
                ),
                file="",
                symbol=None,
                suggestion="Run recoverage on each nested directory.",
                heuristic=False,
            )
        )
    gaps.extend(extra or [])
    gaps.sort(key=lambda gap: (SEVERITY_ORDER.get(gap.severity, 9), gap.file, gap.symbol or "", gap.kind))
    for index, gap in enumerate(gaps, start=1):
        gap.id = f"G{index:02d}"
    return gaps


def _any_measured(functions: list[MappedFunction]) -> bool:
    return any(item.file_measured or item.coverage_ratio is not None for item in functions)


def _function_gap(function: MappedFunction, test_names: frozenset[str], runner: str | None, *, measured: bool) -> Gap | None:
    spec = function.spec
    if spec.name.startswith("_"):
        return None
    # Set membership, not one regex scan of the whole test corpus per function.
    referenced = spec.name in test_names
    ratio = function.coverage_ratio
    tags = ", ".join(spec.risk_tags) if spec.risk_tags else "no special risk tags"
    location = f"{spec.file}:{spec.lineno}"

    if not measured or ratio is None and not function.file_measured:
        if spec.risk_score < 0.55 and spec.branch_count < 3:
            return None
        return Gap(
            id="",
            severity="high" if spec.risk_score >= 0.55 else "medium",
            kind="unmeasured-function",
            title=f"{spec.qualname} was not measured",
            why=(
                f"{location} has risk {spec.risk_score:.2f} ({tags}) and {spec.branch_count} static decision points. "
                "Runtime coverage did not run, so this is an unverified hotspot, not a proof that the lines are untested."
            ),
            file=spec.file,
            symbol=spec.qualname,
            suggestion=f"Install a coverage tool and add {_a_test(runner)} that calls {spec.qualname} at each branch.",
            heuristic=True,
        )

    if ratio == 0:
        if spec.risk_score >= 0.7:
            severity = "critical"
        elif spec.risk_score >= 0.45 or spec.is_public:
            severity = "high"
        else:
            severity = "medium"
        return Gap(
            id="",
            severity=severity,
            kind="untested-function",
            title=f"{spec.qualname} never ran",
            why=(
                f"{location} has {function.executable_lines} executable lines in range and none executed. "
                f"Risk {spec.risk_score:.2f} ({tags}). A regression in this function would ship unnoticed."
            ),
            file=spec.file,
            symbol=spec.qualname,
            suggestion=(
                f"Add {_a_test(runner)} that calls {spec.name}({', '.join(spec.parameters) or ''}) "
                f"and asserts each branch ({spec.branch_count} static decision points)."
            ),
            heuristic=False,
        )

    if ratio is not None and ratio < 0.8 and spec.branch_count >= 1:
        severity = "high" if spec.risk_score >= 0.55 else "medium"
        missing = ", ".join(str(line) for line in function.missing_lines[:12])
        return Gap(
            id="",
            severity=severity,
            kind="partial-branch",
            title=f"{spec.qualname} is only partly covered",
            why=(
                f"{location} executed {function.covered_lines}/{function.executable_lines} statement lines "
                f"({ratio:.0%}). Missing lines: {missing or 'see the coverage map'}. "
                f"Risk {spec.risk_score:.2f} ({tags})."
            ),
            file=spec.file,
            symbol=spec.qualname,
            suggestion=f"Extend {_the_tests(runner)} so the uncovered branches in {spec.qualname} actually run.",
            heuristic=False,
        )

    if spec.risk_score >= 0.55 and not referenced:
        return Gap(
            id="",
            severity="medium",
            kind="missing-critical-path-test",
            title=f"{spec.qualname} is covered without a direct test",
            why=(
                f"{location} has runtime coverage but no test file names {spec.name}. "
                "Incidental coverage can disappear without a failing test. This check is a name scan, not a call graph."
            ),
            file=spec.file,
            symbol=spec.qualname,
            suggestion=f"Name {spec.name} in {_a_test(runner)} and assert the outcome you care about.",
            heuristic=True,
        )
    return None


def parse_error_gaps(errors: list[tuple[str, str]]) -> list[Gap]:
    gaps = []
    for path, message in errors:
        gaps.append(
            Gap(
                id="",
                severity="medium",
                kind="parse-error",
                title=f"Could not parse {path}",
                why=message,
                file=path,
                symbol=None,
                suggestion="Fix the syntax error so structure and coverage can include this file.",
                heuristic=False,
            )
        )
    return gaps


def _a_test(runner: str | None) -> str:
    return f"a {runner} test" if runner else "a test"


def _the_tests(runner: str | None) -> str:
    return f"the {runner} tests" if runner else "the tests"


_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def _test_identifiers(profile: ProjectProfile, cache: SourceCache | None) -> frozenset[str]:
    """Every identifier token named in any test file. Built once, O(total test bytes)."""
    cache = cache or SourceCache(Path(profile.root))
    names: set[str] = set()
    for relative in profile.test_files:
        text = cache.text(relative)
        if text:
            names.update(_IDENTIFIER.findall(text))
    return frozenset(names)
