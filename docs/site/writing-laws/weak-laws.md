# Avoiding weak laws

A weak law passes while checking little. It looks green and protects nothing. lawkeep flags weak laws
(see [Law strength](../concepts/strength.md)); this page shows how to write laws that are not weak in
the first place.

## Traps

| Trap | Why it is a problem | Instead |
| --- | --- | --- |
| A limit law with no companion | passes when the code refuses everything | add the "exact" case (recipe 1) |
| `try: ... except Exception: pass` around the whole check | swallows the failure you wanted to see | catch only the specific, allowed refusal |
| A law written from what the code does today | it confirms the bug instead of catching it | write the sentence from what the person asked for; `lawkeep draft` deliberately does not show the law agent the code being changed |
| A generator that rarely reaches the interesting cases (huge ranges, heavy `.filter()`) | 200 inputs, none near the edge | narrow the ranges, build valid inputs directly, add `@example`s |
| Naming your generator like a Hypothesis one (`times`, `dates`, `text`) | `st.times()` means Hypothesis's version, not yours | pick another name (`clock_times`) |
| Reading the real clock, network or randomness inside the code under test | flaky verdicts | pass them in (recipe 4); outside services come in v0.3 |
| Floats for money | `0.1 + 0.2 != 0.3` | `Decimal` and `st.money()` |
| Lowering `examples`, adding `@settings(max_examples=1)`, or `skip` to get green | it weakens the law | lawkeep records it as a looser change that needs a person's yes |

## The exact-answer companion

The most common weak law is a limit on its own: "a refund never exceeds the payment" passes when the
code refuses every refund. Pair each limit with a law that pins down the normal case: "refunding
exactly what was paid gives back exactly the payment and the whole card fee". See
[recipe 1](recipes.md#1-a-limit-plus-its-exact-companion). lawkeep calls a limit without a companion
**one-sided**, and `lawkeep strength` finds it by swapping the function for "always refuse".

## Too many inputs thrown away

`assume(...)` and `.filter(...)` throw away inputs that do not fit. If most inputs are thrown away, a
law that "tried 200 inputs" really checked only a few. lawkeep reports how many were thrown away and
flags weak test data. Build valid inputs directly instead (for example `st.money(1, 100)` rather than
`st.money()` plus `assume(amount > 0)`). `assume()` called from your code instead of from a law counts
as an error.

## Checking your laws

- `lawkeep strength` (quick): swaps each function a law uses for deliberately broken versions (always
  nothing, always 0, always the input, always an error) and flags laws that still pass as weak.
- `lawkeep strength --full`: plants every small bug lawkeep can make in the functions your laws run and
  reports, per law, how many it caught and which it missed.
- Both report functions no law touches. Those, and anything the
  [protection report](../concepts/protection.md) marks "not protected", are where a person still needs
  to read the code.
