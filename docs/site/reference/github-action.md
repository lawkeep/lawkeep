<!-- Generated from action.yml by scripts/build_llms_docs.py; do not edit. -->

# GitHub Action inputs and outputs

The lawkeep GitHub Action is `action.yml` at the root of the lawkeep repository. This page is generated from that file. How to use it: [CI and the GitHub Action](../guides/ci.md).

## Inputs

| Input | Default | Meaning |
| --- | --- | --- |
| `working-directory` | `.` | Folder of the project (the one with lawkeep.toml). |
| `python-version` | `3.12` | Python version to run the laws with. |
| `lawkeep-spec` | `lawkeep` | What to install as lawkeep: a pip requirement such as 'lawkeep==0.1.0', a path, or a git URL. |
| `install-project` | `true` | Install the project itself first (pyproject.toml / setup.py, else requirements.txt) so laws can import it. |
| `extra-packages` | (empty) | Extra pip requirements to install, separated by spaces (for example 'lawkeep[deep]'). |
| `profile` | (empty) | lawkeep check profile ('pr' by default from lawkeep.toml; 'deep' for nightly runs). |
| `base-ref` | (empty) | Git ref to compare against for the protection report and the law change report. Defaults to the pull request's base commit. |
| `comment` | `true` | Post or update the pull-request comment ('true' or 'false'). |
| `fail-on-broken-laws` | `false` | Fail the job when some laws fail (result code 1). Off by default: lawkeep reports, your team decides. |
| `fail-on-waiting` | `false` | Fail the job when something waits for a person's decision (result code 2), such as an unrecorded law change. |
| `github-token` | `${{ github.token }}` | Token used to post the comment. |

## Outputs

| Output | Meaning |
| --- | --- |
| `result-code` | lawkeep check result code: 0 all laws hold, 1 some fail, 2 waiting for a person's decision, 3 setup problem. |
| `verdict` | ALL LAWS HOLD, SOME LAWS FAIL, WAITING FOR YOUR DECISION or SETUP PROBLEM. |
| `summary` | One plain-English line from lawkeep check. |
| `check-json` | Path of the lawkeep check JSON report. |
| `report-markdown` | Path of the Markdown report (the comment body). |
| `comment-url` | URL of the pull-request comment, when one was posted or updated. |
