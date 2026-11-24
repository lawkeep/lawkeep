# Laws

A **law** is a rule your code must always follow, for every input. It has two parts:

- **one plain-English sentence**, which is what people read and decide on: "A refund never exceeds
  the original payment";
- **a check** that lawkeep runs: a short piece of Python that tries the rule with many different
  inputs.

People decide which laws exist. Coding agents write and maintain the checks. You never have to read
the check: when a law is proposed, you see its sentence and a table of concrete examples.

## Laws are tried with many inputs

An ordinary test checks one example: "a refund of $40 on a $40 payment gives back $40". A law says
something about *every* example: "a refund never exceeds the payment". lawkeep tries it with
hundreds of generated inputs, including odd ones (a $0.01 payment, a refund of exactly the full
amount, a refund of zero). This is called property-based testing; lawkeep uses
[Hypothesis](https://hypothesis.readthedocs.io/) to do it.

When an input breaks the law, lawkeep shrinks it to the **simplest failing example**, for example
"a charge of $0.25 with no discount code", and shows it in words. That input is saved in
`laws/failing_examples.jsonl` and tried again on every later check (a **saved failing example**),
so a bug found once cannot quietly return.

## What a law looks like

Technically, a law is a pytest test written with Hypothesis and marked with `@law("sentence")`:

```python
from lawkeep import given, law, st

@law(
    "A refund never exceeds the original payment",
    inputs={"charge": "a payment the customer made", "amount": "how much they ask to get back"},
)
@given(charge=st.charges(), amount=st.money(0, 1000))
def refund_never_exceeds_payment(charge, amount):
    try:
        result = refund(charge, amount)
    except RefundTooLarge:
        return
    assert result.total <= charge.total
```

- Laws live in `laws/*.py`. Any function (or Hypothesis state machine class) marked with `@law` is
  a law, whatever its name.
- The **law id** is the file path inside `laws/` with dots, plus the function name:
  `laws/refunds.py` → `refunds.refund_never_exceeds_payment`. `@law(..., id="R7")` sets it yourself.
- `inputs=` says in plain words what each input is. People see it next to the examples.
- `st` holds the **input generators**: everything Hypothesis has, plus `st.money()`,
  `st.percentages()`, `st.non_empty_text()`, `st.ids()` and the generators your project defines in
  `laws/strategies.py` (here `st.charges()`).

More in [Writing good laws](../writing-laws/index.md) and the [Python API](../reference/python-api.md).

## Levels

lawkeep says honestly how strongly a law was checked:

| Level | Meaning |
| --- | --- |
| L1 | fixed examples only |
| L2 | a Hypothesis property: many generated inputs (what lawkeep does by default) |
| L3 | CrossHair picks inputs by reading the code (experimental, `lawkeep check --deep-check`, needs `lawkeep[deep]`); it may not try every path |
| L4 | a machine-checked proof (planned for v0.5, not available) |

Only L4 may ever be called "proven". Everything lawkeep does today is evidence from many inputs,
not proof.

## What counts as part of the laws

Everything in `laws/` (except `laws/drafts/`), `lawkeep.toml` and the lawkeep GitHub workflow. A
change to an input generator or to the number of inputs tried can weaken every law, so those
changes are recorded and permissioned like a change to a law itself. See
[Law history and lock](history-and-lock.md).
