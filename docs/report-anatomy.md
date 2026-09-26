# Report anatomy

`report.html` is one file. Charts are inline SVG drawn by Recoverage. The page has no stylesheet link, no script source, and a Content-Security-Policy that allows only the hashes of its own style and script. It still reads with JavaScript disabled. The filters, theme toggle, file rows, and copy buttons need the script.

## Overview

The gauge is the Merge Readiness Score. The badge is the gate: blocked, needs-review, merge-ready, or production-ready. The sentence under it is `explain_gate`. It only names causes that applied. Four cards show statement coverage, branch coverage, gap count, and whether mutation ran.

The factor table is the same weighted split as the rubric: structural coverage, property trials, prompt coverage, blast radius, and timing.

## Coverage

The table distinguishes project statement coverage from the tool's own percent. "not measured" is not 0%. Module bars are gray when the run was static. Severity bars count gaps. They are not a coverage number.

## Findings

One card per gap, ordered critical to low. Filters hide cards in the browser. They do not change the score. A suggestion that contains a URL is text. The page does not request it.

## Files

One row per file that has a mapped function or a gap. Coverage is covered executable lines over executable lines in that file. Expanding a row lists functions and missing line numbers. A file with no mapped functions shows the gap and no function list.

## Hotspots

Risk is the heuristic from the function name, body, and complexity. Color is coverage: red uncovered, amber partial, green covered, gray unmeasured. Risk is not a vulnerability finding.

## Authenticity

CRAP, assertion strength, dependency authenticity (DAR), and the static flake scan (FIRI). These do not move the Merge Readiness Score. DAR does not contact a package registry. FIRI does not reproduce a flake.

## Analytics

Property trials, mutation, lexical prompt coverage, blast radius, and timing. Each card is the note the engine wrote, including when that engine did not run. With no diff, blast radius is the whole indexed graph and the report says so.

## Suggestions and rubric

Suggestions are the next commands and the symbol-level gaps. The rubric at the bottom is the same text embedded in the README. The PDF is a shorter projection of the same view, compiled by Typst when that binary is installed. A missing Typst binary does not fail the run.
