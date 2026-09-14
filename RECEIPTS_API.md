# Radarboard Receipts API

Public, read-only, no key, no auth. Cached 60 seconds. `GET` only.

```
https://oiiqwunjyiygfxcyxzzs.supabase.co/functions/v1/receipts
```

This is the track record: every memecoin call the engine fired, how each one
turned out, and the parts of it that cannot be quoted. It is served whole
rather than as a highlight reel, and the fields that make it awkward — rugs,
thin books, unreadable windows — are first-class, not footnotes.

Data licensed **CC BY 4.0**. See `DATA-LICENSE.md`.

---

## The one distinction that matters

**OFFERED is not REALISED.**

`peak` is the best price that printed. `peak_close` is the best price that
closed. Both answer *what was on the screen*. Neither answers *what would you
have left with* — and the gap between those is the whole difference between a
track record and a brochure.

So every realised figure comes from one stated, mechanical exit rule applied
identically to every call, run on the same sealed candles that produced the
peak. The rule ships with the number in `realised_rule`. It is a control, not
advice: no judgement, no re-entry, and every tie inside a candle resolves
against us.

Read `expectancy_pct` and `realised_mean_pct` together or you have not read
the record.

---

## `summary`

### Headline

| field | meaning |
|---|---|
| `real_calls` | calls that set the rates — one vote per token, first alert |
| `tokens_graded` | every graded token, including the disclosed classes below |
| `median_pct` | median best close, in percent |
| `expectancy_pct` | mean best close — what was OFFERED |
| `pct_10`, `pct_30`, `pct_2x` | share that offered ≥10%, ≥30%, ≥100% |
| `no_gain_calls`, `no_gain_pct` | calls that never closed above the price they were called at |
| `liq_floor_usd` | the liquidity floor separating a call from a thin call |

### Realised

| field | meaning |
|---|---|
| `realised_n` | calls with a realised figure (needs sealed candles) |
| `realised_mean_pct` | what the published ladder would have banked |
| `realised_median_pct` | the middle of that |
| `realised_positive_pct` | share that banked more than zero |
| `realised_rule` | the ladder, as one string |

`realised_n` is smaller than `real_calls`. A call that has not sealed has no
realised figure — render the difference as *not yet sealed*, never as zero.

### Disclosed, never averaged

Counted in full, published by name, and excluded from every rate. In the same
order the engine classifies them:

| field | meaning |
|---|---|
| `rugs_found`, `rug_pct` | the move never existed at a size anyone could leave with |
| `unreadable_calls`, `unreadable_pct` | past the horizon with no candles left to seal it |
| `entry_unverified_calls`, `entry_unverified_pct` | graded off a candle open — no alert price on file |
| `thin_calls`, `thin_pct` | real, in a book too small to get in and out of |

Bad liquidity readings never arrive at all; they are held back at source.

### Provenance

| field | meaning |
|---|---|
| `sealed_shown` | rows final at the 24h horizon |
| `sealed_coarse_shown` | of those, sealed on 1h/4h bars rather than 15m |
| `ledger_records` | entries in the hash chain |
| `with_thin` | the same rates recomputed with the thin rows included, so the wider read is published beside the narrower one |
| `ledger_head` | the current chain head — check it with `verify_ledger.py` |
| `chains` | the networks read |

A coarse seal is measured on wider candles because 15-minute history only
reaches back a day. That understates a move rather than flattering it — a
wider close is harder to hit — but it is a different measurement and it says
so.

---

## `calls`

Call-class rows only, ordered by `realised_pct` descending. Rugs, thin
and unreadable rows are not in this table; they are counted in `summary`
and `distribution`, and the thin rows are served in full in `thin_calls`.

| field | meaning |
|---|---|
| `symbol`, `chain`, `called_at` | what, where, when |
| `address` | the contract. This, not the symbol, is the identity of the row |
| `reads` | how many times the grader read this row before it sealed |
| `called_mc` | market cap at the moment of the call |
| `peak_x`, `close_x` | best wick and best close, as multiples |
| `realised_pct` | what the ladder banked. `null` until sealed — a dash, never a zero |
| `window_min` | how long the move stayed tradeable |
| `verdict` | `HELD`, `RUG`, `FADED` |
| `thin`, `unreadable`, `entry_unverified` | the disclosure flags above |
| `liq_at_call` | liquidity at the moment of the call, part of the sealed read |
| `liq_now`, `liq_now_at` | liquidity today and when it was read. Read separately, never part of the sealed grade |
| `liq` | deprecated alias of `liq_at_call`, kept for older clients |
| `sealed`, `sealed_bar_min`, `sealed_coarse` | whether final, and on what bar size |

`close_x` is `null` when no close could be measured. It used to fall back to
the peak, which quietly restated a wick as something you could have sold into.
A dash is the honest answer.

---

## `peak_calls`

The same class of row as `calls`, ordered by `peak_x` descending instead of
by `realised_pct`. The two orderings disagree on purpose: the biggest climb
and the best result are rarely the same call, and a record that only
published one ordering would be choosing which of the two to show.

---

## `thin_calls`

Rows called under the liquidity floor in `summary.liq_floor_usd`. Same
fields, same seal, same grade. They are shown and never counted, because
the book was too small to get in and out of at size.

---

## `distribution`

Buckets of the graded record, including `rug`, `unreadable`, `entry
unverified` and `thin` as bands in their own right, so the counts sum to the
whole rather than to the flattering part.

## `sales`

`open`, `treasury`, `price_sol` — the front door's state. A receiving address
is public by nature.

---

## Other fields

| field | meaning |
|---|---|
| `as_of` | when the scorecard snapshot was written |
| `engine_updated` | when the engine last wrote a board |
| `provisional` | the record is young and says so |
| `days_running` | days since the first call on file |
| `horizon_hours` | the grading window: 24 |
| `method` | one paragraph stating exactly how the above was computed |

---

## Conventions

- Percentages are percent, not fractions. `12.4` is 12.4%.
- Multiples are multiples. `2.5` is 2.5×.
- `null` means *unknown* and never *zero*. This is load-bearing throughout.
- Timestamps are ISO 8601, UTC.
- One vote per token: repeat alerts on the same token do not each count.

## Errors and limits

`503` with `{"error": "unavailable"}` when the upstream snapshot cannot be
read. `405` for anything but `GET` or `OPTIONS`. CORS is open. Cached 60s at
the edge — polling faster gains you nothing.

## Verifying any of this

The summary carries `ledger_head`. Every call was sealed into a hash chain
when it fired, and `verify_ledger.py` in this repo recomputes that chain from
the raw entries and checks it against that head. It imports nothing but the
Python standard library and none of the engine.

```
python3 verify_ledger.py
```

Exit code `0` means the record you are reading is the record that was written.
