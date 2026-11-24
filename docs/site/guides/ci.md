# CI and the GitHub Action

lawkeep can check your laws on every pull request and post one plain-English comment with the
verdict, the law changes and their approvals, and the protection report.

## The quickest way

```bash
lawkeep init --ci
```

This adds `.github/workflows/lawkeep.yml`. It runs on pull requests and pushes to `main` with the `pr`
profile, runs a nightly deeper search with the `deep` profile, and comments only on pull requests.
The workflow file is part of your laws (fingerprinted in `laws.lock`), so a change to it is recorded
like any other law change.

:::{important}
In lawkeep 0.1.0 the workflow written by `lawkeep init --ci` uses `lawkeep/lawkeep@v0`, but only the
tag `v0.1.0` exists so far. Until a `v0` tag is published, change that line to
`uses: lawkeep/lawkeep@v0.1.0` (or a commit SHA) in your copy, and record the edit with
`lawkeep approve --accept-unrecorded`.
:::

## By hand

```yaml
# .github/workflows/lawkeep.yml
name: lawkeep
on: pull_request
permissions:
  contents: read
  pull-requests: write   # to post the comment
jobs:
  laws:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0     # the protection report compares with the base branch
      - uses: lawkeep/lawkeep@v0.1.0
```

The action installs Python, lawkeep and your project (from `pyproject.toml` / `setup.py`, else
`requirements.txt`), runs `lawkeep check --json` and `lawkeep report` on the fresh checkout, and posts
or updates **one** comment per pull request (never a duplicate).

## It reports; your team decides

By default the job fails only on a setup problem (result code 3). Failing laws and waiting decisions
are reported in the comment but do not fail the job. To make them fail it:

```yaml
      - uses: lawkeep/lawkeep@v0.1.0
        with:
          fail-on-broken-laws: "true"   # fail on result code 1
          fail-on-waiting: "true"       # fail on result code 2 (e.g. an unrecorded law change)
```

Whether a failing lawkeep job blocks merging is your choice: make it a required check in your
branch settings only if your team wants that. lawkeep does not force a review process.

## The pull-request comment

The comment leads with the verdict, then:

- the law changes in the pull request, with who made each one, why, and who approved it;
- unrecorded law changes and other integrity issues;
- "N things wait for your decision — run `lawkeep approve`" when something waits;
- the protection report: each changed function marked Protected, Partly protected or
  Not protected — read this one.

On pull requests from forks the token is read-only, so the report goes to the job summary instead.

## Nightly deep search

Pull requests use a fixed seed so the same code always gets the same verdict. A nightly job with the
`deep` profile tries 2,000 new random inputs per law to find rare failures:

```yaml
name: lawkeep nightly
on:
  schedule:
    - cron: "23 2 * * *"
  workflow_dispatch:
permissions:
  contents: read
jobs:
  deep:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - id: lawkeep
        uses: lawkeep/lawkeep@v0.1.0
        with:
          profile: deep
          comment: "false"
          fail-on-broken-laws: "true"
      - if: always()
        uses: actions/upload-artifact@v4
        with:
          name: lawkeep-nightly
          path: |
            ${{ steps.lawkeep.outputs.check-json }}
            laws/failing_examples.jsonl
          if-no-files-found: ignore
```

When it finds a failure, the uploaded report shows the simplest failing input. Ask your coding agent
to fix the code and save that input as an example, so every later check retries it. Both templates
are in the repository under
[`.github/workflows/templates/`](https://github.com/lawkeep/lawkeep/tree/main/.github/workflows/templates).

## Inputs and outputs

All inputs (`working-directory`, `python-version`, `lawkeep-spec`, `install-project`,
`extra-packages`, `profile`, `base-ref`, `comment`, `fail-on-broken-laws`, `fail-on-waiting`,
`github-token`) and outputs (`result-code`, `verdict`, `summary`, `check-json`, `report-markdown`,
`comment-url`) are listed in [GitHub Action inputs and outputs](../reference/github-action.md).

## Other CI systems

Run `lawkeep check --json` and use the result code: 0 all laws hold, 1 some fail, 2 waiting for a
person's decision, 3 setup problem. `lawkeep report --format markdown` gives the comment text.
Output is plain text in CI (no colour).
