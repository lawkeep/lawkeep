<!-- Title: Conventional Commits format, e.g. "feat(approve): show one waiting list" (see CONTRIBUTING.md). -->

## What changed

## Why

## How it was tested

## Checklist

- [ ] `uv run pytest -q` passes
- [ ] `uv run ruff check src tests && uv run ruff format --check src tests` is clean
- [ ] `uv run pyright` reports 0 errors
- [ ] `uv run lawkeep check` says ALL LAWS HOLD (laws changed only through `lawkeep propose` / `approve`)
- [ ] `CHANGELOG.md` → `Unreleased` updated (if users notice the change)
- [ ] Folder `AGENTS.md` files and docs updated (if the code or behaviour changed)
