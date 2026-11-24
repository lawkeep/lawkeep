# Changing a law

Laws change. A rule was wrong, the business changed, or a function was renamed. In lawkeep, every
law change goes through `lawkeep propose`, so it is recorded, its direction is judged from evidence,
and weakening waits for a person.

## Through your agent

Ask your agent, for example:

> No card fee on refunds under $1.

If that conflicts with a law, a well-behaved agent does not edit the law. It tells you which law,
shows the example that fails, and proposes the change. lawkeep works out the direction and shows you:

```text
+-  Proposed law change  ----------------------------------------------+
| ! Looser — the law would allow more, so it protects less.            |
|                                                                      |
| Law now:      “Fee is always 2%”                                     |
| Would become: “Fee is 2%, or $0 for refunds under $1”                |
| Why:          your request "no fees on tiny refunds"                 |
|                                                                      |
| Input           What the code did     Old law OK?   New law OK?      |
| refund $0.50    fee() gave 0.00       NO            Yes              |
|                                                                      |
| ! Think twice: this makes the law protect less. Say yes only if you  |
|   asked for this change or agree with the reason.                    |
+----------------------------------------------------------------------+
```

Say yes or no. Either way, the decision is recorded.

## By hand

1. Copy the law's file into `laws/drafts/` and edit the copy:

   ```bash
   cp laws/fees.py laws/drafts/fees.py
   $EDITOR laws/drafts/fees.py
   ```

2. Propose it:

   ```bash
   lawkeep propose fees.fee_is_two_percent --file laws/drafts/fees.py \
     --reason "no card fee on refunds under \$1 (support ticket 812)"
   ```

3. lawkeep runs the old and the new version on the same inputs and on deliberately broken versions
   of the code, then applies your permissions:

   | Result | Result code | What happens |
   | --- | --- | --- |
   | stricter or same, allowed by `auto` | 0 | applied now, and recorded |
   | looser, unclear, or a permission set to `ask` | 2 | waits; it prints an id like `h-1a2b3c4d` |
   | the new version is broken | 1 | rejected |

4. If it waits, a person decides:

   ```bash
   lawkeep approve h-1a2b3c4d
   ```

The draft file is removed once the proposal is applied or parked, so it does not show up again as a
new draft.

## Deleting a law

```bash
lawkeep propose fees.fee_is_two_percent --delete --reason "fees were removed from the product"
```

Deleting is always looser, so it always waits for a person's yes.

## Things that also count as weakening

Lowering `examples` in `lawkeep.toml`, adding `@settings(max_examples=1)`, adding a `skip` marker, or
throwing most inputs away with `assume()`. lawkeep records these as looser changes (or flags them),
so they need a person's yes too.
