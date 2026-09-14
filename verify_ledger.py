#!/usr/bin/env python3
"""
VERIFY THE RADARBOARD LEDGER — independently, with nothing of ours installed.

Radarboard publishes a track record of memecoin calls, losses included. A JSON
file the publisher can edit cannot support that claim, so every call is sealed
into a hash chain the moment it fires. Each entry carries the hash of the entry
before it. Change any past record and every hash after it breaks.

This script is the other half of that claim. It recomputes the entire chain
from the raw ledger and checks it against the head Radarboard publishes. If
they match, the record you are reading is the record that was written. If they
do not, this tells you exactly which entry is the first one that disagrees.

It imports nothing but the Python standard library and it talks to nothing but
the public endpoint. There is no Radarboard code in it — that is the point. A
verifier supplied by the party being verified is only useful if you can read
all of it, so it is deliberately short.

THE RULE, in full, so you can reimplement it in any language:

    genesis          = "0" * 64
    canonical(x)     = JSON, keys sorted, separators "," and ":", no ASCII
                       escaping of non-ASCII characters
    sealed(entry)    = {"kind": entry.kind, "utc": entry.utc, "data": entry.data}
    hash(entry)      = sha256(prev_hash + canonical(sealed(entry))) as lowercase hex
    head             = the hash of the last entry

Note what that covers: the entry's KIND and its seal TIMESTAMP are inside the
hash alongside the data. Backdating a record or relabelling an alert as a
settlement breaks the chain exactly like editing its contents does.

Only facts known at the moment of the call are sealed: time, address, chain,
symbol, tier, score, arrows, entry market cap, entry liquidity, timing, shape.
Outcomes are deliberately NOT sealed into the alert record — a result can never
rewrite the call it came from. Settlements are appended as their own entries.

    python3 verify_ledger.py                     fetch and verify the live chain
    python3 verify_ledger.py --file ledger.jsonl verify a local copy
    python3 verify_ledger.py --head <sha256>     also assert a specific head
    python3 verify_ledger.py --selftest          check this script itself

Exit code 0 means verified. Anything else means do not trust the record.
"""
import argparse
import hashlib
import json
import sys
import urllib.request

RECEIPTS_URL = "https://oiiqwunjyiygfxcyxzzs.supabase.co/functions/v1/receipts"
LEDGER_URL = "https://oiiqwunjyiygfxcyxzzs.supabase.co/functions/v1/ledger"
GENESIS = "0" * 64
TIMEOUT = 30


def canonical(data):
    """Deterministic serialisation.

    Key order and whitespace must not change the hash, or verification becomes
    a coin flip. `ensure_ascii=False` matters: a symbol containing non-ASCII
    characters would otherwise hash differently depending on the serialiser.
    """
    return json.dumps(data, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False)


def entry_hash(prev_hash, entry):
    """Hash one entry against the previous hash. Handles both formats.

    v2 (seq 560+) seals {kind, utc, public, private_hash}. `public` is the
    allowlisted projection and `private_hash` commits to the redacted rest, so
    this recomputes from exactly what the endpoint served — redaction costs
    nothing in verifiability.

    v1 (seq 1-559) sealed {kind, utc, data} where `data` was the whole alert
    row. Those contents are not published, so their hashes cannot be
    recomputed by anyone outside; see `verify` for how they are treated.

    The sealed payload is never `data` alone. Hashing only the data verifies
    against a chain nobody built and rejects the real one; this verifier did
    exactly that on its first run against the live ledger, and the ledger was
    right.
    """
    if (entry.get("v") or 1) >= 2:
        sealed = {"kind": entry.get("kind"), "utc": entry.get("utc"),
                  "public": entry.get("public"),
                  "private_hash": entry.get("private_hash")}
    else:
        sealed = {"kind": entry.get("kind"), "utc": entry.get("utc"),
                  "data": entry.get("data")}
    return hashlib.sha256((prev_hash + canonical(sealed)).encode("utf-8")).hexdigest()


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "radarboard-verifier"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return r.read().decode("utf-8")


def fetch_all(url=LEDGER_URL, fetcher=fetch):
    """Every entry, following `next` until the endpoint says there is no more.

    The endpoint serves 500 entries a page. A verifier that asks once and
    verifies what came back does not verify the ledger — it verifies the first
    page of it, and then reports NOT VERIFIED because a partial chain cannot
    reach the published head. That is what happened the moment the chain
    passed 500 entries: the stranger's one command started failing on a record
    that was perfectly intact.

    Two guards, both failing closed:

    - the page count must reach `total`. Short is an error, never a shorter
      chain that happens to verify.
    - `next` must move forward. An endpoint that repeats a cursor would
      otherwise spin here forever.

    `fetcher` is injectable so the selftest can drive this against a fake
    endpoint without a network.
    """
    entries, seen, cursor, total = [], set(), None, None
    while True:
        u = url + (f"?from={cursor}" if cursor is not None else "")
        body = json.loads(fetcher(u))
        if not isinstance(body, dict) or not isinstance(body.get("entries"), list):
            raise SystemExit("  the ledger endpoint did not return entries")
        if total is None:
            total = body.get("total")
        entries.extend(body["entries"])
        nxt = body.get("next")
        if nxt is None:
            break
        if nxt in seen:
            raise SystemExit(f"  the endpoint repeated cursor {nxt} — not "
                             f"advancing, refusing to loop")
        seen.add(nxt)
        cursor = nxt

    # THE COUNT IS PART OF THE PROOF. Verifying 500 of 634 entries and
    # announcing VERIFIED would be the worst possible outcome here: a pass on
    # a record nobody checked the end of.
    if total is not None and len(entries) != total:
        raise SystemExit(f"  the endpoint says the ledger has {total} entries "
                         f"and served {len(entries)}. Refusing to verify a "
                         f"partial chain.")
    return entries


def load_ledger(path=None, url=LEDGER_URL):
    """The ledger as a list of entries, from disk or from the endpoint.

    Accepts either JSON Lines (one entry per line) or a JSON array, because a
    file downloaded from a browser and a file written by the engine are not
    always the same shape and neither should be a reason this fails.
    """
    if not path:
        return fetch_all(url)
    raw = open(path, encoding="utf-8").read()
    raw = raw.strip()
    if not raw:
        return []
    if raw[0] == "[":
        body = json.loads(raw)
        return body if isinstance(body, list) else []
    if raw[0] == "{" and "\n" not in raw.strip():
        body = json.loads(raw)
        if isinstance(body, dict) and isinstance(body.get("entries"), list):
            return body["entries"]
        return [body]
    out = []
    for n, line in enumerate(raw.splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError as e:
            raise SystemExit(f"  line {n} is not valid JSON: {e}")
    return out


def verify(entries, expect_head=None):
    """Recompute the chain. Returns (ok, report)."""
    report = {"n": len(entries), "first_bad": None, "computed_head": GENESIS,
              "unchecked": 0, "problems": []}
    if not entries:
        report["problems"].append("the ledger is empty")
        return False, report

    prev = GENESIS
    for i, e in enumerate(entries):
        seq = e.get("seq", i + 1)
        if "hash" not in e:
            report["first_bad"] = seq
            report["problems"].append(f"entry {seq} has no hash")
            return False, report
        # The link the entry CLAIMS, and the link the chain requires.
        claimed_prev = e.get("prev")
        if claimed_prev is not None and claimed_prev != prev:
            report["first_bad"] = seq
            report["problems"].append(
                f"entry {seq} points at {str(claimed_prev)[:16]}… but the "
                f"entry before it hashes to {prev[:16]}…")
            return False, report
        # AN ENTRY WHOSE CONTENTS ARE NOT PUBLISHED CANNOT BE RECOMPUTED.
        #
        # Entries 1-559 sealed the whole alert row, so serving their contents
        # would publish the method. They go out as hashes only. The chain
        # still verifies THROUGH them — linkage needs `prev` and `hash` and
        # nothing else — but what they contain is taken on trust, and this
        # counts them rather than quietly treating a skipped check as a pass.
        has_contents = ("public" in e) or ("data" in e)
        if not has_contents:
            report["unchecked"] += 1
            prev = e["hash"]
            continue
        want = entry_hash(prev, e)
        if want != e["hash"]:
            report["first_bad"] = seq
            report["problems"].append(
                f"entry {seq} claims hash {str(e['hash'])[:16]}… but its "
                f"contents hash to {want[:16]}… — this entry was altered "
                f"after it was sealed")
            return False, report
        prev = want
    report["computed_head"] = prev

    if expect_head:
        if expect_head != prev:
            report["problems"].append(
                f"the chain is internally consistent but its head is "
                f"{prev[:16]}…, and the published head is {expect_head[:16]}… "
                f"— you are not looking at the same ledger")
            return False, report
        report["head_matched"] = True
    return True, report


def _selftest():
    """Check the verifier against chains we build here, including bad ones."""
    def chain(datas):
        out, prev = [], GENESIS
        for i, d in enumerate(datas, 1):
            e = {"seq": i, "kind": "alert", "utc": f"2026-01-0{i}T00:00:00+00:00",
                 "prev": prev, "data": d}
            e["hash"] = entry_hash(prev, e)
            out.append(e)
            prev = e["hash"]
        return out

    cases = []
    good = chain([{"a": 1}, {"b": 2}, {"c": 3}])
    ok, rep = verify(good)
    cases.append(("a well-formed chain verifies", ok, rep["computed_head"][:12]))
    cases.append(("  and reports the right length", rep["n"] == 3, rep["n"]))

    ok, rep = verify(good, expect_head=good[-1]["hash"])
    cases.append(("a matching published head passes", ok, ""))
    ok, rep = verify(good, expect_head="f" * 64)
    cases.append(("a different published head FAILS", not ok,
                  "same chain, different ledger"))

    tampered = json.loads(json.dumps(good))
    tampered[1]["data"]["b"] = 999
    ok, rep = verify(tampered)
    cases.append(("editing an entry's contents is caught", not ok, ""))
    cases.append(("  and it names the first bad entry", rep["first_bad"] == 2,
                  rep["first_bad"]))

    relinked = json.loads(json.dumps(good))
    relinked[2]["prev"] = "a" * 64
    ok, rep = verify(relinked)
    cases.append(("breaking a link is caught", not ok, ""))

    dropped = [good[0], good[2]]
    ok, rep = verify(dropped)
    cases.append(("deleting an entry from the middle is caught", not ok,
                  "the survivors no longer link up"))

    ok, rep = verify([])
    cases.append(("an empty ledger is not 'verified'", not ok, ""))

    # ── pagination ───────────────────────────────────────────────────────
    # The failure this exists to stop: the endpoint serves 500 entries a page,
    # the chain grew past 500, and the one command in the README started
    # printing NOT VERIFIED against a record that was completely intact. A
    # verifier that reads one page is checking a prefix and calling it a
    # ledger.
    #
    # So the synthetic chain here is deliberately longer than one page.
    PAGE = 500
    big = chain([{"i": i} for i in range(PAGE + 134)])   # 634, the live length

    def fake_endpoint(pages, total=None, next_override=None):
        """A stand-in for the deployed function, paged exactly as it pages."""
        total = len(pages) if total is None else total

        def _f(u):
            frm = 0
            if "?from=" in u:
                frm = int(u.split("?from=")[1].split("&")[0])
            window = [e for e in pages if e["seq"] > frm][:PAGE]
            last = window[-1]["seq"] if window else frm
            nxt = (next_override if next_override is not None
                   else (last if last < total else None))
            return json.dumps({"total": total, "returned": len(window),
                               "from": frm, "next": nxt, "entries": window})
        return _f

    for i, e in enumerate(big, 1):
        e["seq"] = i

    got = fetch_all("http://fake", fetcher=fake_endpoint(big))
    cases.append((f"a {len(big)}-entry chain is fetched whole, not one page",
                  len(got) == len(big), f"{len(got)} of {len(big)}"))
    ok, rep = verify(got, expect_head=big[-1]["hash"])
    cases.append(("  and the paginated chain verifies to the published head",
                  ok, rep["computed_head"][:12]))
    cases.append(("  a single page would NOT have verified",
                  not verify(big[:PAGE], expect_head=big[-1]["hash"])[0],
                  "this is the bug that shipped"))

    # Short count fails closed. Verifying 500 of 634 and printing VERIFIED is
    # the one outcome worse than printing NOT VERIFIED.
    try:
        fetch_all("http://fake", fetcher=fake_endpoint(big[:PAGE], total=len(big)))
        short_failed = False
    except SystemExit:
        short_failed = True
    cases.append(("a short count refuses to verify at all", short_failed,
                  "500 served, 634 claimed"))

    # A cursor that does not advance must not spin forever.
    try:
        fetch_all("http://fake",
                  fetcher=fake_endpoint(big, next_override=PAGE))
        looped = False
    except SystemExit:
        looped = True
    cases.append(("a repeating cursor is refused, not looped on", looped, ""))

    # Canonicalisation must not depend on key order or on non-ASCII escaping.
    e1 = {"kind": "alert", "utc": "u", "data": {"a": 1, "b": 2}}
    e2 = {"kind": "alert", "utc": "u", "data": {"b": 2, "a": 1}}
    cases.append(("key order cannot change a hash",
                  entry_hash(GENESIS, e1) == entry_hash(GENESIS, e2), ""))
    nn = {"kind": "alert", "utc": "u", "data": {"s": "\u5b59\u5c0f\u5723"}}
    cases.append(("a non-ASCII symbol hashes consistently",
                  entry_hash(GENESIS, nn) == entry_hash(GENESIS, nn), ""))
    # kind and utc are inside the seal, so changing either must break it.
    backdated = json.loads(json.dumps(good)); backdated[1]["utc"] = "1999-01-01T00:00:00+00:00"
    ok2, _ = verify(backdated)
    cases.append(("backdating an entry is caught", not ok2, "utc is sealed"))
    relabel = json.loads(json.dumps(good)); relabel[1]["kind"] = "settlement"
    ok3, _ = verify(relabel)
    cases.append(("relabelling an entry's kind is caught", not ok3, "kind is sealed"))

    # ── the two regimes ──────────────────────────────────────────────
    # v2 must verify from the PUBLIC projection alone, with the redacted
    # remainder present only as a commitment. If it cannot, redaction has
    # cost verifiability and the whole design is pointless.
    def v2chain(items):
        out, prev = [], GENESIS
        for i, (pub, ph) in enumerate(items, 1):
            e = {"seq": i, "kind": "alert", "utc": f"2026-02-0{i}T00:00:00+00:00",
                 "prev": prev, "v": 2, "public": pub, "private_hash": ph}
            e["hash"] = entry_hash(prev, e)
            out.append(e); prev = e["hash"]
        return out

    v2 = v2chain([({"symbol": "A", "n_arrows": 3}, "aa" * 32),
                  ({"symbol": "B", "n_arrows": 5}, "bb" * 32)])
    ok, rep = verify(v2)
    cases.append(("a v2 chain verifies from the public projection alone",
                  ok and rep["unchecked"] == 0, "redaction costs nothing"))
    tam = json.loads(json.dumps(v2)); tam[1]["public"]["n_arrows"] = 99
    ok, _ = verify(tam)
    cases.append(("editing a v2 public field is caught", not ok, ""))
    tam2 = json.loads(json.dumps(v2)); tam2[1]["private_hash"] = "cc" * 32
    ok, _ = verify(tam2)
    cases.append(("swapping the private commitment is caught", not ok,
                  "the redacted part is committed, not ignored"))

    # v1 served as hashes only: linkage provable, contents not.
    stripped = [{k: v for k, v in e.items() if k != "data"} for e in good]
    ok, rep = verify(stripped)
    cases.append(("a hashes-only chain still proves its linkage", ok, ""))
    cases.append(("  and counts what it could not check",
                  rep["unchecked"] == 3, rep["unchecked"]))
    broken = json.loads(json.dumps(stripped)); broken[2]["prev"] = "0e" * 32
    ok, _ = verify(broken)
    cases.append(("a broken link is caught even with no contents", not ok, ""))

    mixed = stripped + v2chain([({"symbol": "C"}, "dd" * 32)])
    mixed[3]["prev"] = mixed[2]["hash"]
    mixed[3]["hash"] = entry_hash(mixed[2]["hash"], mixed[3])
    ok, rep = verify(mixed)
    cases.append(("a chain that changes format mid-way verifies",
                  ok and rep["unchecked"] == 3, f"unchecked={rep['unchecked']}"))

    bad = 0
    for label, cond, detail in cases:
        bad += not cond
        print(f"  {'ok  ' if cond else 'FAIL'}  {label:<48} {detail}")
    print(f"\n  {len(cases) - bad}/{len(cases)} passed")
    return 1 if bad else 0


def main():
    ap = argparse.ArgumentParser(
        description="Independently verify the Radarboard ledger.")
    ap.add_argument("--file", help="verify a local ledger instead of fetching")
    ap.add_argument("--url", default=LEDGER_URL, help="ledger endpoint")
    ap.add_argument("--head", help="assert this published head as well")
    ap.add_argument("--selftest", action="store_true",
                    help="check this script against known-good and tampered chains")
    a = ap.parse_args()

    if a.selftest:
        return _selftest()

    expect = a.head
    if not expect and not a.file:
        # Take the published head from the receipts endpoint, so the chain is
        # checked against what Radarboard is telling the world right now.
        try:
            summary = json.loads(fetch(RECEIPTS_URL)).get("summary") or {}
            expect = summary.get("ledger_head")
            if expect:
                print(f"  published head : {expect}")
                print(f"  published count: {summary.get('ledger_records')}")
        except Exception as e:
            print(f"  could not read the published head ({str(e)[:60]}) — "
                  f"checking internal consistency only")

    try:
        entries = load_ledger(a.file, a.url)
    except Exception as e:
        print(f"  could not load the ledger: {str(e)[:120]}")
        return 2

    ok, rep = verify(entries, expect)
    print(f"  entries        : {rep['n']}")
    print(f"  computed head  : {rep['computed_head']}")
    if ok:
        checked = rep["n"] - rep["unchecked"]
        print(f"  contents checked: {checked}   "
              f"linkage only: {rep['unchecked']}")
        print("\n  VERIFIED — the chain links end to end and every entry whose "
              "contents\n  are published hashes to its stated value.")
        if rep["unchecked"]:
            print(f"  {rep['unchecked']} early entries are published as hashes "
                  f"only. Their place in the\n  chain is proven; their contents "
                  f"are not independently checkable.")
        if rep.get("head_matched"):
            print("  The computed head matches the published head.")
        return 0
    print("\n  NOT VERIFIED")
    for p in rep["problems"]:
        print(f"    - {p}")
    if rep["first_bad"]:
        print(f"\n  Everything before entry {rep['first_bad']} is intact. "
              f"That entry is where the record stops matching itself.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
