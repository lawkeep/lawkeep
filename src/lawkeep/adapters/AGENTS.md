# src/lawkeep/adapters

Thin per-agent adapters on one shared base, installed by `lawkeep init`.

- `base.py`: the shared base (AGENTS.md snippet between `lawkeep:begin/end` markers, git pre-commit
  hook, JSON merging that never overwrites invalid files, `.gitignore`), plus `all_adapters()`,
  `get_adapter()` and `detect_agents()`.
- `guard.py`: one decision function (`decide`) for every agent's pre-tool-use hook (Claude Code,
  Codex, Cursor, Copilot payloads all go through it). It denies direct writes to `laws/` (except
  `laws/drafts/` outside `proposals/`), `laws.lock`, `lawkeep.toml` and
  `.github/workflows/lawkeep.yml`, and answers "ask" when a command actually *runs*
  `lawkeep approve` (also wrapped in `uv run`, `python -m`, `sh -c`, `xargs`, `env`/`sudo`/
  `timeout`, Python `subprocess`/`cli.main`/`history.record_change`). Text that only mentions
  it (here-document bodies, `echo`, `git commit -m`, strings in code, files being written)
  is never asked about, nor is `lawkeep approve --help`. Edit tools: the target path decides (relative to the call's
  folder, `..` removed, symlinks followed). A drafting session (`LAWKEEP_DRAFTING=1`, set by
  `agent_launcher`) may write `laws/strategies.py`.
- Shell commands are judged by what they **write to**, never by what they mention:
  - `shellwords.py`: a small POSIX lexer (quotes, `$(...)`, backticks, here-documents,
    redirections with fd numbers, `;`/`&&`/`||`/`|`/newlines). Unbalanced quotes raise
    `Incomplete` (then only a text check is possible).
  - `writes.py`: walks the commands, following `cd`/`pushd`, `VAR=value`, `for x in ...`, `~`,
    `$HOME`, globs (expanded against the real folder), `$(pwd)` and
    `$(git rev-parse --show-toplevel)`, and a table of writing commands: redirections, `tee`,
    `rm`, `mv`, `cp`/`install`/`ln`/`rsync`/`scp`, `touch`, `truncate`, `chmod`/`chown`/
    `chattr`, `sed -i`, `perl -i`, `dd of=`, `git checkout`/`restore`/`rm`/`mv`/`clean`/
    `stash push`/`apply`/`am` (`git -C` too), `patch` (reads the patch file), `find -delete`/
    `-exec`, `tar`/`unzip` extraction, compressors, `curl -o`/`wget -O`, `sort -o`, editors,
    `sh`/`bash -c`, script files it can read, `source`, `eval` of fixed text, `xargs`, and
    wrappers (`sudo`, `env`, `nohup`, `time`, `timeout`, `uv run` ...). Read-only commands
    (`cat`, `grep`, `rg`, `git diff/log/show`, `ls`, `lawkeep ...`) never count.
  - `pywrites.py`: inline Python (`-c`, here-documents, piped `echo`/`cat`, readable script
    files) read from its syntax tree: `open(p, "w"/"a"/"x"/"+")`, `Path.write_text`/`unlink`/
    `rename`..., `os.remove`/`rename`..., `shutil.copy`/`move`/`rmtree`, `subprocess`/
    `os.system` commands (analysed as shell), with `sys.argv[N]` taken from the command line.
    Other languages (`node -e` ...): a quoted protected path in code that writes files counts.
  - When a write's target cannot be seen (`eval` of computed text, a path from `$(...)`/`read`,
    code piped in from another command, a script that cannot be read), the command is denied
    only if it plausibly touches the laws: some word or string literal in it is a protected-
    looking path (`laws/...`, `laws.lock`, `lawkeep.toml`, `lawkeep.yml`; prose with spaces
    such as `"update laws doc"` does not count), or it runs decoded code (`base64 -d | sh`),
    or `find -exec`/`-delete` writes over a folder holding `laws/` without a `-name` filter
    that rules every law file out. Otherwise it is allowed.
  - What it cannot see: unknown commands' own behaviour (`make`, `npm run`, your scripts in
    other languages), values only known at run time, whole-tree git operations
    (`git checkout <branch>` / `.`, `git stash pop`, `git reset --hard`, `git pull`), archive
    and patch contents it cannot read, symlinks created earlier in the same command, `case`
    patterns, and deliberate disguise beyond these forms.
- `approve_preview.py`: the "ask" question for the person. It parses the `lawkeep approve`
  arguments (`writes.ApproveRun`) with approve's own parser, lists what waits with
  `approve.collect` and picks what the run decides with `approve.select` (the real command's
  selection), then writes one plain line per item ("Loosen “…” → “…” (looser: protects less)",
  "Add new law “…”", "Accept a hand edit to laws/x.py", "REJECT: …" for `--no`), at most 5
  lines plus "…and N more". Arguments only known at run time or an unknown id say "lawkeep
  could not tell which law change this is — say no unless you are sure". No project code runs;
  it never raises (the plain `guard.APPROVE_MESSAGE` is the fallback). Codex hooks cannot ask,
  so Codex shows `codex.JUSTIFICATION_TEXT` from its rules file instead.
- `claude_code.py`, `codex.py`, `cursor.py`, `copilot.py`: each agent's hook, MCP and instruction
  files. Cursor's rule and Copilot's instructions are the AGENTS.md snippet, so they carry the
  "When no person is there" rules too; the session-start text (`commands/hook.py`) adds them
  plus lawkeep's `person_present` guess and the waiting count. They were checked against each agent's docs (2026-11-21), never inside a running agent.
- `templates/`: the files `init` writes (see `templates/AGENTS.md`), read with `base.template(name)`.
- `mcp_server.py` and `commands/{init,hook,mcp}.py` (outside this folder) are the entry points
  that use these adapters.

Gotcha: the guard also protects `laws/drafts/proposals/undo/` (inside `proposals/`), where
`approve` keeps the earlier file versions for undoing an approval made without a terminal.
Gotchas: the guard is a speed bump, not a wall; anything it misses must still show up as an
unrecorded law change in `check` (that, not the guard, is the promise). When you add a writing
command, add a row to `tests/test_adapters_guard_writes.py` (both an allowed and a denied
form). This repository's own Claude Code hook runs this code, so a guard bug can block your own
shell commands: test with `uv run pytest tests/test_adapters_guard*.py` before relying on it.
Adapters merge into the user's files and never overwrite them; keep `install` idempotent (`init --agent all` twice changes nothing).

Tests: `tests/test_adapters_*.py` (no real agent is ever started); the shell-command table is
`tests/test_adapters_guard_writes.py`.
