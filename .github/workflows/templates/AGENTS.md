# .github/workflows/templates

Workflows for users to copy into their own repository. GitHub runs only files directly in
`.github/workflows/`, so these never run here.

- `lawkeep.yml`: on every pull request, run the lawkeep action and post one comment (does not
  block unless `fail-on-broken-laws: "true"`).
- `lawkeep-nightly.yml`: nightly `profile: deep`, fails the nightly job (not a pull request) when a
  law fails, and uploads the report and `laws/failing_examples.jsonl`.

Connections: both call `lawkeep/lawkeep@v0` (the moving major tag that `release.yml` moves to
each final 0.x release; users may pin `@v0.1.0` instead) and may only pass inputs
defined in the root `action.yml`. `lawkeep init --ci` does NOT copy these: it installs
`src/lawkeep/adapters/templates/lawkeep-workflow.yml` (one file with PR, push and nightly
triggers). Keep the two in line when you change the action's inputs.

Test: no test reads these files (the adapters template's inputs are checked by
`tests/test_adapters_init.py`); compare the `with:` keys against `action.yml` by hand.
