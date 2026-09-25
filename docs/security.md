# Security

Recoverage is a local analysis tool for a checkout you already trust. It is not a scanner for a hostile repository. `production-ready` on a report is a score gate, not a claim that this package or the project under test is safe to ship.

## Default run

`recoverage run` without `--dynamic` does not import project code and does not start a test runner. It walks the tree, parses what it can, and writes a report whose coverage is unmeasured.

## `--dynamic` and `--deep`

`--dynamic` runs the project's tests as you. `--deep` implies `--dynamic` and also runs property trials, mutation, timing, and search. The CLI prints that there is no OS sandbox.

What that opt-in does:

- Test runners and mutation pytest are child processes. The environment is an allowlist (`PATH`, `SYSTEMROOT`, `TEMP`, `HOME`, `VIRTUAL_ENV`, and a few other process basics). API keys, cloud credentials, CI tokens, SSH keys, and `RECOVERAGE_LLM_API_KEY` are not copied.
- A timeout kills the child process tree. Coverage and pytest timeouts record exit 124.
- Property trials, search, and timing call project functions in `probe_worker`, a separate interpreter. A call dies at 2 seconds. A timing batch dies at 30 seconds. The worker is killed on timeout.
- `generate` copies the tree to a temp directory and runs pytest there. That copy limits edits to your source tree. It does not drop privileges, disable the network, or hide your home directory. It is a temp copy, not a sandbox.

Import-time code in the child runs before the target function is called. A project you do not trust can still read files you can read, write files you can write, and use the network, because the child is your user. Do not pass `--dynamic` on an untrusted tree.

## Reports

`analysis.json` is scrubbed before write. Docstrings are blanked. Absolute paths become a basename. Secret-shaped strings are redacted. Search arguments are type names, or `<redacted>` when the string looks like a secret. Test stdout and stderr tails are not stored. Markdown escapes gap title, why, and suggestion. HTML escapes those fields too.

The directory name is what the Markdown project line prints. Uploading `analysis.json` still publishes function names, relative paths, and gap text. Drop it from a CI artifact if the artifact store is wider than the people who can read the repo.

## LLM

The CLI does not call the network unless you pass `--llm`. The payload is gap metadata or a symbol plus parameter names, not the whole file. `RECOVERAGE_LLM_BASE_URL` must be `https`, except `http` on loopback. The bearer key is sent to that URL. The response is capped at 1_000_000 bytes. Redirects are refused, so the key is not forwarded. Library `llm_mode` `"auto"` and `"off"` stay offline. Only `"on"` builds a client.

## What is in place

- Default `run` is static.
- Child commands are argument arrays, not a shell string.
- Child environment is an allowlist. Timeouts kill the process tree.
- Probes run out of process.
- HTML and Markdown gap text are escaped.
- `show` binds to `127.0.0.1` and only serves the report file.
- The gate treats a nonzero test exit, and a missing exit code on a measured run, as `blocked`. A numeric `--threshold` fails when the tests failed.
- `analysis.json` must match this package version, must contain the analysis keys, and must be at most 100_000_000 bytes.

## What is not in place

There is no OS container, no network namespace, and no read-only filesystem for `--dynamic`. A symlink that resolves outside the project root is not indexed. Directory symlinks are not followed. That is not a substitute for isolation.
