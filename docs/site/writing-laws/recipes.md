# Recipes

Patterns for laws that catch real bugs, and traps that make laws look green while checking
little. Examples use the made-up projects in the repository's
[examples/](https://github.com/lawkeep/lawkeep/tree/main/examples) folder. Every law here is a
pytest test with `@law("...")` and Hypothesis's `@given`.

Each recipe starts with the plain sentence a person would approve, because that is what people
judge. The code is for the agent and for developers.

## 1. A limit, plus its "exact" companion

> "A refund never exceeds the original payment."

```python
@law("A refund never exceeds the original payment")
@given(charge=st.charges(), amount=st.money(0, 1000))
def refund_never_exceeds_payment(charge, amount):
    try:
        result = refund(charge, amount)
    except RefundTooLarge:
        return
    assert result.total <= charge.total
```

On its own this law is weak: code that refuses every refund passes it. Pair every limit with a
law that pins down the normal case:

> "Refunding exactly what was paid gives back exactly the payment and the whole card fee."

```python
@law("Refunding exactly what was paid gives back exactly the payment and the whole card fee")
@given(charge=st.charges())
def full_refund_gives_back_exact_payment(charge):
    result = refund(charge, charge.total)
    assert result.total == charge.total
    assert result.fee_returned == charge.card_fee
```

`lawkeep strength` finds missing companions: it swaps `refund` for "always refuse" and flags
every law that still passes.

## 2. Nothing bad ever happens, over a sequence of actions

> "Two bookings never overlap."

```python
@law("Two bookings never overlap")
@given(now=st.clock_times(), requests=st.lists(st.slots(), max_size=8))
def bookings_never_overlap(now, requests):
    book = BookingBook(FixedClock(now))
    for slot in requests:
        try:
            book.book(slot, "Ana")
        except BookingError:
            pass
    accepted = book.bookings()
    for i, first in enumerate(accepted):
        for second in accepted[i + 1:]:
            assert not first.slot.overlaps(second.slot)
```

Generate a list of actions, apply them, and check the rule on the final state. Keep the input
space small (one day, 15-minute steps) so actions collide often. For longer or branching
sequences, use a Hypothesis `RuleBasedStateMachine` and put `@law` on the class.

```python
from hypothesis.stateful import RuleBasedStateMachine, invariant, rule

@law("The number of free seats never goes below zero or above the room size")
class SeatsMachine(RuleBasedStateMachine):
    def __init__(self):
        super().__init__()
        self.room = Room(seats=10)

    @rule(name=st.non_empty_text())
    def reserve(self, name):
        try:
            self.room.reserve(name)
        except RoomFull:
            pass

    @rule()
    def cancel_one(self):
        self.room.cancel_any()

    @invariant()
    def seats_stay_in_range(self):
        assert 0 <= self.room.free_seats <= 10
```

Hypothesis runs many random sequences of `reserve` and `cancel_one` and checks the invariant after
every step. A failure is shrunk to the shortest sequence that breaks it.

## 3. Undo really undoes

> "Cancelling a booking frees its slot for someone else."

Do, undo, and check you are back where you started; then check the freed resource can really be
used again (not just that a flag changed).

## 4. Time comes from a clock you control

> "A booking never starts before the current time."

Pass "now" in (a clock object or a parameter) instead of reading the system clock inside the
code. Then the law can try 09:00, 18:45 and every time in between, and the same inputs always
give the same verdict.

## 5. Bounds that hold for every input

> "A discount code never raises the price and never takes it below zero."

```python
assert 0 <= apply_discount(price, code) <= round_money(price)
```

Include the odd inputs in the generator: no code, lower-case codes, unknown codes, a $0.00 price.
Add `@example(...)` for the cases you care about most (a $3.00 item with a $5.00-off code), so
they run every time.

## 6. Round trip: there and back again

> "Saving a booking and loading it again gives the same booking."

When one function undoes another (save and load, encode and decode, format and parse), check that
going there and back gives the original:

```python
@law("Saving a booking and loading it again gives the same booking")
@given(booking=st.bookings())
def save_then_load_gives_the_same_booking(booking):
    assert load_booking(save_booking(booking)) == booking
```

Round trips catch lost fields, rounding and encoding bugs without having to know the exact output.

## 7. Compare with a simpler version

> "The fast price calculator gives the same total as the simple one."

When an optimised function has a slow, obviously correct counterpart, assert they agree on every
input. This is also how lawkeep confirms a rename kept a law's meaning.

## 8. Rounding and money

> "Rounding money gives whole cents and is never off by more than half a cent."

Use `Decimal` (`st.money()`), never floats, for amounts. Test the rounding rule with more
decimal places than the result has (`st.decimals(places=4)`), so half-cent cases come up.

## 9. More in, more out (or never less)

> "A bigger refund never returns a smaller share of the card fee."

When you cannot say exactly what the answer is, you can often say how it changes when the input
changes. Generate two inputs, order them, and compare the results.

## 10. Write it down once, keep it forever

Every failing input lawkeep finds is saved in `laws/failing_examples.jsonl` and retried on every
run. If a bug was found by hand, ask the agent to "save this case as an example": that is a
stricter change and is allowed automatically by default.

More: [Avoiding weak laws](weak-laws.md).
