# Schema contracts (MySQL vs SQLite)

## Why this exists

SQLite **ignores** `VARCHAR(N)` length. Inserts that blow past the column width
succeed in pytest (SQLite) and then explode in production MySQL as:

```text
(pymysql.err.DataError) (1406, "Data too long for column '…' at row 1")
```

SeasonLand hit this on `orders.original_order_id` (was `VARCHAR(64)`): kit/dino
claims build readable idem keys that exceed 64 chars once `season_id` looks like
`season-delta-YYYYMMDDHHMMSS` and kits prepend `__admin_skip_kit_limit__|`.

## Checklist for new string IDs / columns

1. **Read the SQLAlchemy length** — `Column.type.length` (or `Mapped[…] = mapped_column(String(N))`).
2. **Build the worst-case production value** (longest season_id, longest SKU, prefixes).
3. **Assert** `len(worst_case) <= Column.type.length` in `test_schema_contracts.py`
   (SQLite will not catch this for you).
4. If the value can grow (new prefix, longer season_id format), **widen the column**
   and add a boot migrate (`ALTER … MODIFY`) — do not rely on hashing unless
   readability is impossible.
5. Prefer fixtures with **long** `season_id` (e.g. `season-delta-20240715032535`),
   not short stubs like `s1`.
6. Remember kit orders store:
   `__admin_skip_kit_limit__|sp:{season}:{track}:{level}:kit:{sku}`
   — include that prefix in the length budget.

## Related files

- `test_schema_contracts.py` — static length contracts against models
- `test_season_pass.py` — claim flow with long season_id + fail-before-claimed
- `app.py` — `Order.original_order_id` + `_ensure_orders_original_order_id_width`
