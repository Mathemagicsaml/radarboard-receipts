# Radarboard — public record

A memecoin scanner publishes a track record. Anyone can publish a track
record; the question is whether you can check it.

This repository is the checking half. It contains the API contract for the
public receipts endpoint and a standalone verifier for the hash chain the
record is sealed into. It contains no part of the engine.

```
python3 verify_ledger.py
```

Exit code `0` means the record being served is the record that was written.

---

## Why a chain at all

The claim is "here is our track record, losses included". A JSON file the
publisher can edit does not support that claim, however sincerely it is meant.

So every call is sealed the moment it fires. Each entry carries the hash of
the entry before it:

```
genesis       = "0" * 64
canonical(x)  = JSON, keys sorted, separators "," and ":", non-ASCII unescaped
sealed(entry) = {"kind": entry.kind, "utc": entry.utc, "data": entry.data}
hash(entry)   = sha256(prev_hash + canonical(sealed(entry)))
head          = the hash of the last entry
```

Change one past entry and every hash after it breaks. You cannot quietly
improve history; you can only append to it.

Note what the seal covers. The entry's **kind** and its **timestamp** are
inside the hash alongside the data, so backdating a call or relabelling it
breaks the chain exactly like editing its numbers does.

Only facts known at the moment of the call are sealed. Outcomes are
deliberately **not** sealed into the alert record — a result can never rewrite
the call it came from. Instead a **settlement** entry is appended when a call
reaches its 24-hour horizon, carrying the grade and linked into the same
chain. Settlements begin with the v2 format described below; entries 1–559 are
alerts only.

**Entries 1–559 are published as hashes only: the chain verifies end to end
through them, but their contents were sealed in a format that cannot be
redacted, so content verifiability starts at entry 560.**

Those early entries sealed the whole internal row, signal names included, and
serving them would publish the method rather than the record. From 560 the
seal is split — an allowlisted `public` payload plus a `private_hash`
committing to the rest — so the entry hash can be recomputed from exactly what
the endpoint returns:

```
hash(entry) = sha256(prev_hash + canonical({kind, utc, public, private_hash}))
```

Redaction therefore costs nothing in verifiability. The verifier reports both
counts separately and never treats a check it could not perform as a pass.

No wallet address appears in any public entry, in any field, ever. `address`
is the token contract — the thing a receipt is about. This is asserted by the
engine's own test suite rather than promised here.

## Why the verifier is MIT and short

A verifier written by the party being verified is worth exactly as much as
your ability to read all of it. So it is one file, standard library only, no
dependencies, and you are invited to reimplement it in whatever language you
trust more.

That is not a rhetorical invitation. On its first run against the live chain
this verifier **disagreed with the engine and was wrong** — it hashed `data`
alone instead of `{kind, utc, data}`, and rejected a chain that was correct.
An independent reimplementation is the only thing that finds a wrong
specification. It found ours before anyone else had to.

```
python3 verify_ledger.py --selftest
```

runs it against known-good chains and against tampered ones: edited contents,
broken links, a deleted middle entry, a backdated timestamp, a relabelled
kind. All must fail, and it reports which entry is the first to disagree.

## What is here

```
verify_ledger.py    the verifier — stdlib only, no engine imports
RECEIPTS_API.md     the public API contract
LICENSE             MIT, for the code
DATA-LICENSE.md     CC BY 4.0, for the record
```

## What is not here, and will not be

The engine is private. The scanner, the scoring, the signal set and the
alerting logic are not in this repository and are not covered by the data
licence.

**The record is open. How it was produced is not.** Those are separate
questions and only the first one needs to be checkable by strangers.

## Reading the record honestly

Two numbers, and taking one without the other misreads everything:

- **`expectancy_pct`** — what was *offered*. The average best close.
- **`realised_mean_pct`** — what a stated, mechanical exit rule would have
  *banked* from the same candles. The rule ships with the number.

They disagree, substantially and by design. An unrealised figure is a
screenshot; it goes to zero on the way to being money. Publishing only the
first is how a track record becomes a brochure, so both are in the summary and
neither is the headline on its own.

The disclosed classes matter for the same reason. Rugs, thin books,
unreadable windows and unverified entries are counted in full, named, and
excluded from every rate — never quietly dropped. A record that hides its duds
is not a record.

## The bar moved on 2026-09-12

The rules that decide what becomes a call are not fixed, and a record made
under two different bars is two records unless it says so.

On **2026-09-12** the wallet-agreement bar was raised: a token needed
**2** tracked wallets to be pinned and **3** distinct actors to earn a signal
arrow; it now needs **5** of each. A **holder floor** was added at the same
time — a call now requires at least **50 holders**, and on chains where holder
addresses are obtainable, at least 50 that are not traceable to one another
through a shared funder. Tokens whose holder base cannot be read are refused
rather than assumed.

Every call dated before 2026-09-12 was made under the older, looser bar. They
are left in the record exactly as they were graded — removing them would be
the more flattering choice and the less honest one — but they were not held to
the rule the current ones are.

## Status

The record is young and says so: `provisional` is `true` in the summary, and
`days_running` tells you how young. Treat it accordingly.
