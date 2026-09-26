# Scoring

The score is the Merge Readiness Score (MRS), 0–100. Weights are fixed. It is not a line-coverage percentage. The same text is shipped as `src/recoverage/RUBRIC.md` and printed at the bottom of every Markdown report.

| Factor | Points | How it is measured |
| --- | --- | --- |
| Structural coverage | 40 | `0.6 * statement% + 0.4 * branch%`, then scaled to 40. Unmeasured runtime coverage scores 0. If any source file was missing from the tool report, the branch figure mixes tool arcs with static decision counts and the factor is marked heuristic. |
| Property-based resilience | 25 | `passed / trials` across structural conformance, determinism, and entity substitution. At least 1,000 inputs when pure public functions exist (capped at 4 functions). Failing inputs are shrunk. |
| Prompt / semantic alignment | 15 | ΔH: Shannon entropy of spec tokens (docstrings, signatures, `README.md`) minus the entropy after dropping tokens that appear in tests. No spec text scores 0. Labeled lexical, not attention. |
| Blast radius safety | 10 | Statement coverage of functions inside a 2-hop undirected radius of the changed symbols. With no diff, the radius is the whole indexed graph and the report says so. |
| Execution-time efficiency | 10 | Mann-Whitney U between a small input and a heavier input on this revision, 21 repeats, up to 3 functions. Points drop to 0 only when p < 0.05 and the median is more than 8× slower after scaling for a larger list. A list of 200 items versus 3 is more work, not a regression by itself. |

Flake markers found by a static scan subtract 2 points, floored at 0. That scan is not a reproduction.

## Gates

| Gate | Rule |
| --- | --- |
| blocked | No test runner, or measured statement coverage is below 20%, or MRS is below 40, or the test run did not exit 0. Badge: NOT MERGEABLE. |
| needs-review | A runner exists and MRS is at least 40, but the merge bar is not met. Unmeasured runtime coverage cannot be graded above this gate. |
| merge-ready | MRS ≥ 70, statement coverage ≥ 60%, runtime coverage was measured, the test run exited 0, and there is no critical gap. Badge: MERGEABLE. |
| production-ready | MRS ≥ 85, statement coverage ≥ 60%, runtime coverage was measured, the test run exited 0, and there is no critical gap. Badge: PRODUCTION READY. |

`production-ready` is not a security audit. The gate sentence names only the causes that fired. A pytest run that exited 0 is not described as having no test runner. A measured run that exited nonzero is `blocked` even when coverage and MRS would otherwise clear `production-ready`, and the sentence says `the test run exited N`.

`--threshold` on a gate name passes when the result gate ranks at least that high. A number passes when MRS ≥ that number, even if the named gate is `blocked`. Use a gate name when a red suite must fail the job.

## Outside MRS

CRAP, assertion strength (ASR), dependency authenticity (DAR), static flakiness risk (FIRI), and the mutation score (MSI) are an authenticity scorecard. They do not move the 100 points or the gate.

- CRAP = complexity² × (1 − coverage)³ + complexity. Unmeasured coverage counts as 0. Above 30 is called out.
- ASR = substantive assertions / all assertions. `assert True`, `x == x`, and `isinstance` / `hasattr` checks are not substantive.
- DAR = imports that resolve to the stdlib, this workspace, or a name in a manifest, over all imports. No registry is contacted.
- FIRI = test functions that call time, random, filesystem, or network directly, over test functions. Not a re-run.
- Mutation flips one operator (`not`, or a comparison) inside up to 5 public functions, on a temp copy, 120s per suite. A timeout counts as killed. Baseline must already exit 0 or no mutant is scored. This is not mutmut or cosmic-ray.

## Known weaknesses

These are in the score today. They are tracked in [ROADMAP.md](ROADMAP.md). Do not treat MRS as a merge gate until they are fixed if the factor in question is load-bearing for you.

- Property trials count `TypeError`, `ValueError`, `KeyError`, and `OverflowError` as a pass. An input that never evaluated the property still earns the 25-point factor. The properties are shape, determinism, and type-stability, not a behavioral contract.
- Timing sets `ran=True` after the target list is non-empty, including when every import or every call failed and no sample was kept. `_timing` then awards 10/10 whenever `ran` is true and no regression was recorded. No samples is not a measurement.
- With no diff, blast-radius points are a second copy of whole-graph coverage, marked heuristic.
- PageRank's dangling-node step loops every sink across every node (40 iterations). Large graphs with many sinks are quadratic.
- PBT, mutation, timing, and SBST run on every `run`, in this process, with no per-call deadline on the direct function calls.
