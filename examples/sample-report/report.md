# Recoverage report

**Merge Readiness Score: 7.5 / 100**  
**Gate: `blocked`**  
**Badge: `NOT MERGEABLE`**

Not mergeable. Measured statement coverage is 16.7%, under 20%, and the Merge Readiness Score is 7.5, under 40.

Project: `fixture`  
Language: python  
Test runner: pytest  
Coverage tool: coverage.py  
LLM: off  
Generated: 2026-09-26T09:02:44+00:00

<!-- recoverage:score=7.5;gate=blocked;mutation=false -->

## Overview

| Metric | Value |
| --- | --- |
| Statement coverage | 16.7% |
| Branch coverage | 10.5% |
| Gaps | 5 |
| Mutation ran | no |

## Coverage stats

| Metric | Value |
| --- | --- |
| Project statement coverage | 16.7% |
| Tool percent_covered | 14.1% |
| Branch coverage | 10.5% |
| Branch figure is runtime-tool-only | yes |
| Tool | coverage.py |
| Measured | yes |
| Test exit code | 0 |

## Score factors

| Factor | Earned | Max | Heuristic | Detail |
| --- | --- | --- | --- | --- |
| Structural coverage | 5.69 | 40 | no | Statement coverage 16.7% and branch coverage 10.5% combine to 14.2 before the 40-point weight. Tool percent_covered is 14.1% and is not used: branch mode blends arcs into that headline. |
| Property-based resilience | 0.00 | 25 | no | Deep probes were not requested. |
| Prompt / semantic alignment | 0.26 | 15 | yes | ΔH coverage 1.7%. ΔH is the drop in Shannon entropy of specification tokens after removing tokens named by tests. This is a lexical spotlight, not transformer attention. |
| Blast radius safety | 1.57 | 10 | yes | No diff was supplied. The radius is the whole indexed graph, so union coverage collapses to coverage of those functions. |
| Execution-time efficiency | 0.00 | 10 | no | Timing was not measured. |

## Coverage by package

![coverage by package](charts/coverage_by_package.svg)

## Gap severity

![gap severity](charts/gap_severity.svg)

Mutation testing did not run.

## Authenticity scorecard

Authenticity scorecard is not the Merge Readiness Score and does not move the gate. DAR checks the workspace, the stdlib, and declared manifests. It does not query a package registry. FIRI is a static scan, not a reproduction of a flake.

| Dimension | Value | Threshold | Status |
| --- | --- | --- | --- |
| Dependency authenticity (DAR) | 100.0 | 100% | PASS |
| Statement coverage | 16.7 | ≥ 80% | FAIL |
| Branch coverage | 10.5 | ≥ 75% | FAIL |
| Mutation score (MSI) | n/a | ≥ 70% | n/a |
| Assertion strength (ASR) | 100.0 | ≥ 85% | PASS |
| Mean CRAP | 34.2 | ≤ 15 | FAIL |
| CRAP > 30 | 3 | 0 | FAIL |
| Flakiness risk (FIRI) | 0.0 | 0% | PASS |

ASR is substantive assertions divided by all assertions. Tautologies (x == x, assert True) and type-or-presence checks are not substantive. A comparison against a literal is substantive and can still be a magic-number smell. Vacuous or tautological assertions: 0. Assertion roulette: 0. Magic-number asserts: 1. AAA interleaving: 0. DAR = verified imports / imports. Verified means stdlib, a module in this workspace, or a name declared in a manifest. No registry was contacted. Phantom imports: none. FIRI = tests with direct time, random, filesystem, or network calls, divided by test functions. This does not re-run the suite.

## Property-based testing

Deep probes were not requested.

| Symbol | Trials | Passed | Failed |
| --- | --- | --- | --- |
| — | 0 | 0 | 0 |

## Prompt coverage

ΔH is the drop in Shannon entropy of specification tokens after removing tokens named by tests. This is a lexical spotlight, not transformer attention.

## Blast radius

No diff was supplied. The radius is the whole indexed graph, so union coverage collapses to coverage of those functions.

Union coverage: 15.7%.

## Execution time

Timing was not measured.

## Code graph

Tree-sitter index: yes. Entities: 5. Communities: 5.

## Risk hotspots

![risk hotspots](charts/risk_hotspots.svg)

| Function | File | Risk | Coverage | Tags |
| --- | --- | --- | --- | --- |
| `charge` | `src/shop/payments.py` | 0.90 | 0% | payment |
| `refund` | `src/shop/payments.py` | 0.85 | 0% | payment |
| `apply_coupon` | `src/shop/cart.py` | 0.45 | 10% | payment |

## Files

| File | Statements | Coverage | Functions | Gaps | Worst |
| --- | --- | --- | --- | --- | --- |
| `src/shop/cart.py` | 19 | 42.1% | 2 | 2 | medium |
| `src/shop/payments.py` | 17 | 0.0% | 2 | 2 | critical |
| `src/shop/pricing.py` | 15 | 0.0% | 1 | 1 | high |

## Findings

### critical

#### G01 · charge never ran

`src/shop/payments.py` `charge`. Kind: `untested-function`.

src/shop/payments.py:6 has 11 executable lines in range and none executed. Risk 0.90 \(payment\). A regression in this function would ship unnoticed.

Suggestion: Add a pytest test that calls charge\(amount, method, authorized\) and asserts each branch \(6 static decision points\).

#### G02 · refund never ran

`src/shop/payments.py` `refund`. Kind: `untested-function`.

src/shop/payments.py:19 has 6 executable lines in range and none executed. Risk 0.85 \(payment\). A regression in this function would ship unnoticed.

Suggestion: Add a pytest test that calls refund\(amount, captured\) and asserts each branch \(2 static decision points\).

### high

#### G03 · tier\_price never ran

`src/shop/pricing.py` `tier_price`. Kind: `untested-function`.

src/shop/pricing.py:6 has 15 executable lines in range and none executed. Risk 0.00 \(no special risk tags\). A regression in this function would ship unnoticed.

Suggestion: Add a pytest test that calls tier\_price\(units, tier\) and asserts each branch \(6 static decision points\).

### medium

#### G04 · apply\_coupon is only partly covered

`src/shop/cart.py` `apply_coupon`. Kind: `partial-branch`.

src/shop/cart.py:17 executed 1/10 statement lines \(10%\). Missing lines: 18, 19, 20, 21, 22, 23, 24, 25, 26. Risk 0.45 \(payment\).

Suggestion: Extend the pytest tests so the uncovered branches in apply\_coupon actually run.

#### G05 · subtotal is only partly covered

`src/shop/cart.py` `subtotal`. Kind: `partial-branch`.

src/shop/cart.py:6 executed 7/9 statement lines \(78%\). Missing lines: 8, 12. Risk 0.00 \(no special risk tags\).

Suggestion: Extend the pytest tests so the uncovered branches in subtotal actually run.

## Suggestions

- Read the findings from the top. Critical and high items are the ones that move the gate.
- `recoverage generate` keeps a draft only after a temp-copy compile and 5 passing runs, and only if it adds covered lines or kills a mutant the current suite left alive.
- Recoverage will not delete or overwrite an existing test file.
- Prompt coverage is a lexical entropy proxy unless an attention model was queried. The report names which one ran.
- Mutation counts come from temp-copy mutants. If that section says mutation did not run, it did not.
- `charge` CRAP 56.0 with complexity 7. Above 30, add tests or split the function.
- `charge` (critical): Add a pytest test that calls charge(amount, method, authorized) and asserts each branch (6 static decision points).
- `refund` (critical): Add a pytest test that calls refund(amount, captured) and asserts each branch (2 static decision points).
- `tier_price` (high): Add a pytest test that calls tier_price(units, tier) and asserts each branch (6 static decision points).
- `apply_coupon` (medium): Extend the pytest tests so the uncovered branches in apply_coupon actually run.
- `subtotal` (medium): Extend the pytest tests so the uncovered branches in subtotal actually run.
- Re-run after editing tests: `recoverage run . --no-llm --threshold merge-ready`

## Recoverage score rubric

The score is the Merge Readiness Score (MRS), 0–100. It is the PRD's weighted sum, not a line-coverage percentage.

| Factor | Points | How it is measured |
| --- | --- | --- |
| Structural coverage | 40 | 60% project statement coverage + 40% branch coverage. Unmeasured runtime coverage scores 0. coverage.py's own `percent_covered` is reported beside it and is not the score: with `--branch` that headline blends arcs into statements. |
| Property-based resilience | 25 | Share of property trials that held. The properties are structural conformance, determinism, and entity substitution. The engine runs at least 1,000 inputs when pure functions exist. Failing inputs are shrunk. This is not a frozen expected-output check. |
| Prompt / semantic alignment | 15 | ΔH, the drop in Shannon entropy of specification tokens once tokens named by tests are removed. Offline this is a lexical spotlight, not transformer attention. No spec text scores 0. |
| Blast radius safety | 10 | Union coverage of the call-graph radius. With no diff, the radius is the whole indexed graph and the report says so. |
| Execution-time efficiency | 10 | Mann-Whitney U between baseline inputs and heavier inputs on this revision. Points are lost only when p < 0.05 and the median is more than 8× slower. This is not a cross-commit benchmark. |

Mutation testing is a separate measurement. When it runs, mutants are applied on a temp copy and the kill count is printed. It is not silently folded into MRS. If it does not run, the report says it did not run.

Flake markers found by a static scan subtract 2 points, floored at 0. That scan is not a reproduction. Drafts that `recoverage generate` keeps are executed 5 times in a temp copy before they are copied back.

### Gates

MRS is mapped onto four gates so a CI job can fail below a named bar. The PRD badge uses the same threshold, default 85.

| Gate | Rule |
| --- | --- |
| blocked | No test runner, or measured project statement coverage is below 20%, or MRS is below 40, or the test run did not exit 0. Badge: NOT MERGEABLE. |
| needs-review | A runner exists and MRS is at least 40, but the merge bar is not met. Unmeasured runtime coverage cannot be graded above this gate. |
| merge-ready | MRS ≥ 70, statement coverage ≥ 60%, runtime coverage was measured, and there is no critical gap. Badge: MERGEABLE. |
| production-ready | MRS ≥ 85 (the PRD threshold), statement coverage ≥ 60%, runtime coverage was measured, and there is no critical gap. Badge: PRODUCTION READY. |

`--threshold` accepts a gate name or a number. A gate threshold passes only when the result gate ranks at least that high: blocked < needs-review < merge-ready < production-ready. A numeric threshold passes when MRS is greater than or equal to the number.

### Separate from MRS

CRAP, assertion strength, dependency authenticity, static flakiness risk, and the mutation score are reported on an authenticity scorecard. They are not added into the 100 points and they do not move the gate. A generated draft is kept when it adds covered lines or kills a mutant the existing suite left alive. That filter is there because a coverage bump with a vacuous assertion is not evidence. Drafts still do not lock in an observed return value.
