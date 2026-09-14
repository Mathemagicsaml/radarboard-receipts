# Licences

Two different things live in this repository and they are licensed
differently, because they are different kinds of thing.

## The code — MIT

`verify_ledger.py`, `RECEIPTS_API.md` and anything else executable or
specification-shaped in this repo is MIT, in `LICENSE`.

Reimplement the verifier in another language, vendor it, fork it, ship it
inside something commercial. A verifier that anyone can rewrite is the only
kind worth publishing: an independent reimplementation is what catches a
wrong specification, and on the first run against the live chain it caught
ours.

## The record — CC BY 4.0

The data served by the public endpoints — the receipts summary, the per-call
rows, and the ledger entries — is licensed
**Creative Commons Attribution 4.0 International**.

    https://creativecommons.org/licenses/by/4.0/

You may share and adapt it, including commercially. The one condition is
attribution: credit Radarboard, link the licence, and say if you changed
anything.

Please do not present a modified extract as the unmodified record. The point
of a hash chain is that the record can be checked; republishing an altered
copy under the original name defeats the only thing that makes it worth
having. `verify_ledger.py` exists so anyone can tell the difference, and it
is MIT precisely so you can run it against us.

## What is NOT licensed here

The Radarboard engine is private and no part of it is in this repository. The
scanner, its scoring, the signal set and the alerting logic are not published
under either licence and are not included in the data grant.

The record is open. How it was produced is not.
