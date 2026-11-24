# Permissions by direction

Every change to a law has a **direction**:

| Direction | Means | Examples |
| --- | --- | --- |
| stricter | the law demands more | a new law, a new example, a tighter limit |
| same | the meaning did not change | a law updated after a function was renamed |
| looser | the law demands less | a wider limit, deleting a law, skipping it, trying fewer inputs |
| unclear | lawkeep cannot tell | a law rewritten to check something different |

Your **permissions** in `lawkeep.toml` say, for each kind of change, whether an agent may go ahead
(`auto`: go ahead and tell me) or must wait for a person (`ask`: wait for my yes):

```toml
[permissions]
add_law       = "auto"   # add a new law (stricter)
add_example   = "auto"   # add an example or a saved failing case (stricter)
rename_target = "auto"   # update a law after a rename, when lawkeep confirms the meaning is the same
change_law    = "ask"    # change what a law checks (unclear)
weaken_law    = "ask"    # loosen, delete or skip a law, or try fewer cases (always "ask")
```

`weaken_law` is always `ask`. Setting it to `auto` is ignored with a warning: **weakening a law
always needs a person's yes.**

## How lawkeep decides the direction

lawkeep does not trust the agent's description of its own change. It decides from evidence:

- it runs the old and the new version of the law on the **same inputs** and compares which inputs
  each one accepts;
- it runs both against **deliberately broken versions** of your code and planted bugs, and compares
  which ones each catches;
- it reads a few things from the code directly: a moved limit in an `assert` (`<= b` →
  `<= b + c`, `<` ↔ `<=`) is read as stricter or looser; deleting, skipping or trying fewer inputs is
  always looser; a change to the law's input generators always asks; "same meaning" requires a
  consistent rename and identical generators.

The comparison uses a fixed seed and a fixed number of inputs, so the same change always gets the
same direction. When the evidence is mixed, the direction is `unclear` and the change waits.

This is evidence from samples, not proof. When lawkeep is not sure, it asks.

## Where changes come from

- `lawkeep propose <law-id> --file laws/drafts/<file>.py --reason "<why>"`: an agent (or you)
  submits a complete new version of a law's file. See [Changing a law](../guides/changing-a-law.md).
- `lawkeep propose <law-id> --delete --reason "<why>"`: deleting a law is always looser.
- A new law through `propose` must also pass the quick strength check before it goes in without
  asking; a weak new law waits for a person.
- Edits the drafting agent of `lawkeep draft` makes to approved files always wait, even when stricter.
