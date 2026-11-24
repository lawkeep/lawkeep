# FAQ and known limits

## Questions

### Does lawkeep prove my code is correct?

No. lawkeep checks exactly the laws you have, against many inputs, and tells you how strongly
("tried 200 inputs, catches 5 of 6 planted bugs"). Code that no law covers is not checked; the
[protection report](concepts/protection.md) shows you where that is. Nothing in lawkeep 0.1 is
"proven": that word is reserved for machine-checked proofs (level L4, planned for v0.5).

### Can the AI get around lawkeep?

lawkeep does not claim it cannot. It makes law changes **visible**: every change is recorded, edits
made outside lawkeep are flagged as unrecorded law changes, files that could change results are
flagged as side doors, and weakening a law needs a person's yes. An agent determined to cheat could
still, for example, write code that patches the test library from inside. See the known limits below.

### Do I need to read code to use lawkeep?

No. You decide on laws by their sentence and a table of examples, and you can do everything by
talking to your coding agent. See [Using lawkeep by talking to your agent](guides/talking-to-your-agent.md).

### Does lawkeep need an API key or an account?

No. `lawkeep draft` starts a session of the coding agent you already use. lawkeep itself runs locally
and has no hosted service.

### Does lawkeep force a review process on my team?

No. It records and shows. The GitHub Action reports and does not fail the job on failing laws unless
you turn that on; making it a required check is your team's choice.

### How is this different from my normal tests?

Laws are tests too (pytest and Hypothesis), but lawkeep adds what normal tests lack when an agent
writes the code: every change to them is permissioned and recorded, the gate runs them in a clean
process with side doors switched off, lawkeep measures whether they are strong enough, and it tells you
which changed code they do not cover. Keep your normal tests; laws are the short list of rules that must
never silently change.

### Which languages are supported?

Python 3.10 and newer. Other languages are on the roadmap (TypeScript and others come last, v0.6).

### Does it work on Windows?

Not in 0.1. The hooks and the MCP launcher are POSIX shell scripts, and the law runner uses POSIX-only
features. CI runs on Linux; macOS has not been tested.

### Why did `check` say "WAITING FOR YOUR DECISION"?

Something needs a person: usually a law file changed outside lawkeep, or a proposal waits. Run
`lawkeep approve`. See [Handling an unrecorded law change](guides/unrecorded-changes.md).

### My laws pass locally but CI shows a flag. Why?

Several checks compare with git: `HEAD` locally, the pull request's base in CI. After a local commit,
plain `lawkeep check` may not show a change that CI does. Use `lawkeep check --base main`.

## Known limits

These are the honest edges of lawkeep 0.1. Each is shown to you when lawkeep can see it, but none is
made impossible.

- **The code under test is trusted.** Laws call your code in the same Python process as lawkeep's law
  runner, so code written to cheat could change the results from inside (for example by patching
  Hypothesis). lawkeep flags source files that import lawkeep, pytest or Hypothesis, read lawkeep's
  settings, raise skips, or shadow a standard-library or installed module, and results travel through
  a private channel that is closed before your code's clean-up runs. Flagged is not prevented: read
  flagged files before trusting a green result.
- **Approvals record who claimed to approve.** lawkeep cannot check who typed "yes". Approvals made
  without a terminal (for example by an agent after its permission prompt) are recorded as such and
  stay on the `lawkeep approve` list until someone in a terminal confirms or undoes them.
- **"Is a person there?" is a guess.** lawkeep reads `LAWKEEP_PERSON_PRESENT`, `CI`, whether the
  command was typed in a terminal, and two Claude Code variables; other agents' interactive sessions
  read as "nobody there". The guess never changes what lawkeep allows.
- **"Same meaning" and "stricter" are evidence, not proof.** They come from sample inputs,
  deliberately broken versions and planted bugs, plus code rules (only a consistent rename counts as
  the same meaning; a change to a law's input generators always asks).
- **Objects that lie about comparisons.** Code that returns values whose `==` or `<=` always say "yes"
  passes equality and limit laws. lawkeep flags comparison methods that always return `True`, but
  cannot catch every disguise.
- **Git decides what is "new".** Several checks compare with a git base. Once a change is committed
  locally, `lawkeep check --base main` (or CI) still shows it; plain `lawkeep check` may not.
- **Filtered inputs.** A law that throws most generated inputs away checks fewer cases than it seems;
  the report says how many were thrown away.
- **Agents other than Claude Code are untested in practice.** The Codex, Cursor and Copilot adapters
  follow those agents' documentation and were tested with simulated messages only. See
  [AI tools](agents/index.md).
- **A newly saved failing example** that is not yet committed or recorded in `laws.lock` can still be
  deleted without a flag.

## Not in 0.1

Other programming languages, laws against a real database, fake outside services, race conditions,
machine-checked proofs (Dafny, v0.5), an optional strict blocking mode (v1.0), Windows, and any hosted
service. The roadmap is in the
[plan](https://github.com/lawkeep/lawkeep/blob/main/docs/PLAN.md#roadmap).
