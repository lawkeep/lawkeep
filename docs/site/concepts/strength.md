# Law strength

A law can pass and still check very little. "A refund never exceeds the payment" passes if the code
refuses every refund. `lawkeep strength` grades the laws themselves.

```bash
lawkeep strength            # quick check
lawkeep strength --full     # plant every small bug lawkeep can make (slower)
lawkeep strength --drafts   # also measure drafts that are not approved yet
```

## How it works

- **Quick check with deliberately broken versions.** For each function a law calls, lawkeep swaps in
  dumb versions: one that always returns nothing, one that returns 0, one that returns its first
  input, one that always raises an error. A strong law notices them. A law that still passes is
  flagged as weak.
- **Planted bugs.** lawkeep makes small changes to a copy of your code in memory (for example `<`
  becomes `<=`, `+` becomes `-`) and checks whether any law notices each one. `--full` plants all of
  them; the report lists the bugs no law caught.
- **Other warnings:**
  - a law that checks nothing at all;
  - a *one-sided* law: it checks a limit ("never more than") but not the right answer, so code that
    refuses everything passes;
  - weak test data: most generated inputs are thrown away (by `assume()`), so far fewer cases are
    tried than it seems;
  - public functions that no law runs.

The result looks like this in words: "Strong law — lawkeep made 3 deliberately broken versions of
the code and this law caught all 3", or, in yellow, "Weak law — ... caught only 2".

## Where strength is used

- `lawkeep approve` and `lawkeep draft` show it for every new law, with "Think twice" when it is
  weak.
- A new law proposed through `lawkeep propose` must pass the quick check before it goes in without
  asking. A weak one waits for a person.
- The [protection report](protection.md) uses planted bugs to judge changed functions.

`lawkeep strength` returns 0 when no law is flagged and 1 when some law is flagged (or fails today).
How to fix weak laws: [Avoiding weak laws](../writing-laws/weak-laws.md).
