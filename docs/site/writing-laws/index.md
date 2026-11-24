# Writing good laws

Most laws are written by your coding agent, and you judge them by their sentence and examples. This
section is for anyone who wants to write or review the checks themselves, or to ask the agent for
better ones.

## Start from the sentence

Write the sentence first, from what the person wants, not from what the code does today:

> A refund never exceeds the original payment.

A good sentence is short, says something about **every** input ("never", "always", "every"), and
could be checked by someone who has not seen the code. Then write the check that tries it.

## Writing a law

```python
from decimal import Decimal

from lawkeep import example, given, law, st

@law(
    "A discount code never raises the price and never takes it below zero",
    inputs={"price": "the price before the discount", "code": "the discount code typed in"},
)
@given(price=st.money(0, 1000), code=st.discount_codes())
@example(price=Decimal("3.00"), code="FIVEOFF")       # a fixed case that always runs
def discount_stays_between_zero_and_price(price, code):
    assert 0 <= apply_discount(price, code) <= round_money(price)
```

- `@law` goes on any pytest test (above or below `@given`) or on a Hypothesis
  `RuleBasedStateMachine`. The law id is the file path inside `laws/` plus the function name:
  `laws/discounts.py::discount_stays_between_zero_and_price` → `discounts.discount_stays_between_zero_and_price`.
- `inputs=` (optional) says in plain words what each input is; people see it next to the example
  table when they approve the law. Without it lawkeep writes something like "a sample discount code
  that lawkeep made up for testing". `lawkeep draft` asks the agent to always fill it in.
- `st` is `hypothesis.strategies` plus `st.money()`, `st.percentages()`, `st.non_empty_text()`,
  `st.ids()`, and anything you define in `laws/strategies.py`. Names that Hypothesis already has (for
  example `times`, `dates`, `text`) always mean Hypothesis's version; give your own generators
  different names (`clock_times`, not `times`).
- `@example(...)` adds fixed cases that run every time, next to the generated ones.
- Use `Decimal` and `st.money()` for money, never floats.

## Your own input generators

Put generators for your project's types in `laws/strategies.py`. Every function there becomes
available as `st.<name>()` in law files:

```python
# laws/strategies.py
from hypothesis import strategies as hs

from billing.models import Charge
from lawkeep import st

def charges():
    """A payment with an optional discount code."""
    return hs.builds(
        Charge,
        price=st.money(0, 500),
        discount_code=hs.none() | hs.sampled_from(["SAVE10", "FIVEOFF"]),
    )
```

`laws/strategies.py` is part of your laws: a change to an existing generator can weaken every law that
uses it, so lawkeep always asks a person about such changes. Adding a new generator is fine.

## Laws over a sequence of actions

For rules about state ("two bookings never overlap", "cancelling frees the slot"), either generate a
list of actions and check the final state, or put `@law` on a Hypothesis `RuleBasedStateMachine`
class. See [recipe 2](recipes.md#2-nothing-bad-ever-happens-over-a-sequence-of-actions).

## Rules for law files

- Laws live in `laws/` (sub-folders are fine). `laws/drafts/` holds drafts and is ignored by the gate.
- Only lawkeep's own plugin runs: no `conftest.py` outside `laws/`; fixtures go in `laws/conftest.py`.
- Do not use `skip`/`xfail` markers or lower `max_examples` in a law: lawkeep flags these as weakening.
- Laws are normal pytest tests, so plain `pytest laws/` also runs them (name them `test_*` if you want
  pytest's default collection to find them).

## Next

- [Recipes](recipes.md): patterns that catch real bugs.
- [Avoiding weak laws](weak-laws.md): traps that make laws look green while checking little.
- [Python API](../reference/python-api.md): `@law` and the `st` helpers.
