# Recoverage report

**Merge Readiness Score: 95.0 / 100**  
**Gate: `production-ready`**  
**Badge: `PRODUCTION READY`**

Production ready under this rubric: Merge Readiness Score at least 85, measured coverage, and no critical gap. This is not a security audit.

Project: `fixture`  
Language: python  
Test runner: pytest  
Coverage tool: coverage.py  
LLM: off  
Generated: 2026-09-26T09:53:19+00:00


- Host budget: 4 cores, 8.0 GB RAM. Baseline caps: walk 20000 files / 200 MB, cache 64 MB, run 600s, parse workers 1.

<!-- recoverage:score=95.0;gate=production-ready;mutation=true -->

## Overview

| Metric | Value |
| --- | --- |
| Statement coverage | 100.0% |
| Branch coverage | 100.0% |
| Gaps | 0 |
| Mutation ran | yes |

## Coverage stats

| Metric | Value |
| --- | --- |
| Project statement coverage | 100.0% |
| Tool percent_covered | 100.0% |
| Branch coverage | 100.0% |
| Branch figure is runtime-tool-only | yes |
| Tool | coverage.py |
| Measured | yes |
| Test exit code | 0 |

## Score factors

| Factor | Earned | Max | Heuristic | Detail |
| --- | --- | --- | --- | --- |
| Structural coverage | 40.00 | 40 | no | Statement coverage 100.0% and branch coverage 100.0% combine to 100.0 before the 40-point weight. |
| Property-based resilience | 25.00 | 25 | no | Ran 349 property trials across structural conformance, determinism, and entity substitution. Failing inputs were shrunk toward simpler values. |
| Prompt / semantic alignment | 10.00 | 15 | yes | ΔH coverage 66.7%. ΔH is the drop in Shannon entropy of specification tokens after removing tokens named by tests. This is a lexical spotlight, not transformer attention. |
| Blast radius safety | 10.00 | 10 | yes | No diff was supplied. The radius is the whole indexed graph, so union coverage collapses to coverage of those functions. |
| Execution-time efficiency | 10.00 | 10 | no | Mann-Whitney U compared baseline inputs with heavier inputs on this same revision. A regression is recorded only when p < 0.05 and the median is more than 8x slower after allowing for a larger list input. This is not a cross-commit EffiBench run. |

## Coverage by package

![coverage by package](charts/coverage_by_package.svg)

## Gap severity

![gap severity](charts/gap_severity.svg)

Killed 5/5 viable mutants on a temp copy (0 timeouts counted as killed, 0 unviable excluded). MSI 100.0. MSI_total 100.0 keeps unviable mutants in the denominator. This is a sampled operator flip, not a mutmut or cosmic-ray campaign. Project files were not edited.

## Authenticity scorecard

Authenticity scorecard is not the Merge Readiness Score and does not move the gate. DAR checks the workspace, the stdlib, and declared manifests. It does not query a package registry. FIRI is a static scan, not a reproduction of a flake.

| Dimension | Value | Threshold | Status |
| --- | --- | --- | --- |
| Dependency authenticity (DAR) | 100.0 | 100% | PASS |
| Statement coverage | 100.0 | ≥ 80% | PASS |
| Branch coverage | 100.0 | ≥ 75% | PASS |
| Mutation score (MSI) | 100.0 | ≥ 70% | PASS |
| Assertion strength (ASR) | 100.0 | ≥ 85% | PASS |
| Mean CRAP | 5.6 | ≤ 15 | PASS |
| CRAP > 30 | 0 | 0 | PASS |
| Flakiness risk (FIRI) | 0.0 | 0% | PASS |

ASR is substantive assertions divided by all assertions. Tautologies (x == x, assert True) and type-or-presence checks are not substantive. A comparison against a literal is substantive and can still be a magic-number smell. Vacuous or tautological assertions: 0. Assertion roulette: 3. Magic-number asserts: 15. AAA interleaving: 0. DAR = verified imports / imports. Verified means stdlib, a module in this workspace, or a name declared in a manifest. No registry was contacted. Phantom imports: none. FIRI = tests with direct time, random, filesystem, or network calls, divided by test functions. This does not re-run the suite.

## Property-based testing

Ran 349 property trials across structural conformance, determinism, and entity substitution. Failing inputs were shrunk toward simpler values.

| Symbol | Trials | Passed | Failed |
| --- | --- | --- | --- |
| `subtotal` | 191 | 191 | 0 |
| `apply_coupon` | 40 | 40 | 0 |
| `charge` | 34 | 34 | 0 |
| `refund` | 84 | 84 | 0 |

## Prompt coverage

ΔH is the drop in Shannon entropy of specification tokens after removing tokens named by tests. This is a lexical spotlight, not transformer attention.

## Blast radius

No diff was supplied. The radius is the whole indexed graph, so union coverage collapses to coverage of those functions.

Union coverage: 100.0%.

## Execution time

Mann-Whitney U compared baseline inputs with heavier inputs on this same revision. A regression is recorded only when p < 0.05 and the median is more than 8x slower after allowing for a larger list input. This is not a cross-commit EffiBench run.

## Code graph

Tree-sitter index: yes. Entities: 5. Communities: 5.

## Risk hotspots

![risk hotspots](charts/risk_hotspots.svg)

| Function | File | Risk | Coverage | Tags |
| --- | --- | --- | --- | --- |
| `charge` | `src/shop/payments.py` | 0.90 | 100% | payment |
| `refund` | `src/shop/payments.py` | 0.85 | 100% | payment |
| `apply_coupon` | `src/shop/cart.py` | 0.45 | 100% | payment |

## Files

| File | Statements | Coverage | Functions | Gaps | Worst |
| --- | --- | --- | --- | --- | --- |
| `src/shop/cart.py` | 19 | 100.0% | 2 | 0 | — |
| `src/shop/payments.py` | 17 | 100.0% | 2 | 0 | — |
| `src/shop/pricing.py` | 15 | 100.0% | 1 | 0 | — |

## Findings

No gaps recorded.

## Suggestions

- Read the findings from the top. Critical and high items are the ones that move the gate.
- `recoverage generate` keeps a draft only after a temp-copy compile and 5 passing runs, and only if it adds covered lines or kills a mutant the current suite left alive.
- Recoverage will not delete or overwrite an existing test file.
- Prompt coverage is a lexical entropy proxy unless an attention model was queried. The report names which one ran.
- Mutation counts come from temp-copy mutants. If that section says mutation did not run, it did not.
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
