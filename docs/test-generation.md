# Test generation

`recoverage generate` drafts pytest files from the last analysis. It does not lock observed return values. Specs come from the signature and the name.

Two files per module that produced data:

- `tests/test_<module>_recoverage.py` — one test per SBST case that did not raise. The call uses `repr` of the arguments that search kept. The assertion checks the annotated type, or a generic structured type when there is no annotation.
- `tests/test_<module>_recoverage_pbt.py` — a Hypothesis test (`max_examples=25`, `database=None`, `deadline=None`) for structural conformance and determinism. `TypeError`, `ValueError`, `KeyError`, and `OverflowError` are ignored.

JavaScript projects are not given jest/vitest drafts. Rendering is Python only.

## What search will call

SBST and PBT call the function in `probe_worker`, not in this process. A function is skipped when its file text contains one of: `subprocess`, `socket`, `requests`, `urllib`, `sqlite3`, `os.system`, `eval(`, `exec(`, `input(`, `open(`, `parse_args`, `execute_run`, `run_analysis`. SBST also skips `Popen`. This is a substring search. It is not a security boundary. An alias, `getattr`, or a call inside a helper in another file is not seen.

On a coverage stall, search asks the LLM for a JSON array of arguments when `--llm` was passed, and otherwise splices constants found in `==` / comparisons against parameters. Persisted `args` are type names. A secret-shaped string is `<redacted>`. Drafts render those stored values with `repr`, so they do not embed the source constant.

## Filters before anything is copied back

`assure_and_write` copies the project to a temporary directory (`recoverage-sandbox-*`) with `proc.temp_copy`, which skips `.git`, `.hg`, `.svn`, `.venv`, `venv`, `.tox`, `.nox`, `node_modules`, `__pycache__`, `.pytest_cache`, `.mypy_cache`, `.ruff_cache`, `.coverage`, `recoverage-out`, and `*.pyc`, and copies symlinks as links rather than following them. The directory name is historical. The copy is not a sandbox: pytest runs as the current user. The child environment is the allowlist from [security.md](security.md), not a full copy of the parent environment. The rubric says these drafts are executed 5 times in a temp copy.

With `--dry-run`, the copy is skipped and the planned files are returned as previews only.

Otherwise, for up to three attempts:

1. Each draft must parse as Python.
2. `pytest` in the temp copy must exit 0, five times in a row (180s each).
3. The draft must add covered lines versus the original analysis, or, if coverage was not measured or did not increase, kill at least one mutant the original suite left alive (up to five surviving mutants).

A failed attempt deletes test functions whose names show up as `::test_...` in the pytest output, or deletes a file that no longer parses. If nothing can be removed, the loop stops.

Survivors are copied back only as new files. `_allocate` appends `_2`, `_3`, … when that relative path already exists. If the candidate still exists at write time, `generate` raises `FileExistsError` rather than overwrite. A second `generate` leaves the files from the first one in place. Existing tests are not deleted.

`--dry-run` is the way to read the draft before those constants are written into the project. The preview is `generation-preview.md` in the output directory.
