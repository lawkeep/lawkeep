<!-- Generated from the signatures and docstrings in lawkeep._law and lawkeep.strategies by scripts/build_llms_docs.py; do not edit. -->

# Python API

What a law file imports. Everything else in lawkeep is used through the `lawkeep` command, not from Python.

```python
from lawkeep import law, given, st, example, settings, assume, note, event
```

`given`, `example`, `settings`, `assume`, `note` and `event` are [Hypothesis](https://hypothesis.readthedocs.io/)'s own. `get_law`, `is_law` and `LawMeta` read the law information attached to a function. `lawkeep.__version__` is the installed version. How to use them: [Writing laws](../writing-laws/index.md).

## law

```python
law(sentence: str, *, id: str | None = None, inputs: dict[str, str] | None = None) -> Callable[[T], T]
```

Mark a pytest test (or a Hypothesis state machine) as a law with a plain sentence.

`inputs` maps each input name to a short plain-English description
(`{"codes": "the result numbers being combined"}`); people see it next to the examples.

## st

`st` is everything in `hypothesis.strategies`, plus the helpers below, plus every generator your project defines in `laws/strategies.py` (for example `st.charges()`). Names that Hypothesis already has (`times`, `dates`, `text`) always mean Hypothesis's version, so give your own generators other names.

### st.money

```python
st.money(min_value: int | float | str | Decimal = 0, max_value: int | float | str | Decimal = 1000000, *, places: int = 2) -> SearchStrategy[Decimal]
```

Money amounts as `Decimal` with `places` decimals (default 0.00 to 1,000,000.00).

Never NaN or infinity. Edge values (the minimum, the maximum, zero when in range, one cent)
come up often because Hypothesis favours boundaries.

### st.percentages

```python
st.percentages(*, places: int = 2) -> SearchStrategy[Decimal]
```

Percentages from 0 to 100 as `Decimal` (e.g. `Decimal("2.50")`).

### st.non_empty_text

```python
st.non_empty_text(*, max_size: int = 50) -> SearchStrategy[str]
```

Text with at least one non-space character.

### st.ids

```python
st.ids(*, prefix: str = '', max_value: int = 10000) -> SearchStrategy[str]
```

Readable string ids like `"user-17"` (`prefix` + number).
