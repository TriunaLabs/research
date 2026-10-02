# Sixty-five bytes: prompt caching and the shape of project state

**2026-10-02 · Paul Woll · Triuna Labs**

A project record of 51,085 bytes was handed to a model twice, with one accepted change in
between. **Sixty-five bytes were reusable** as a cached prompt prefix.

Reordering the same information, without removing any of it, took that to 51.8%.

This note states the measurement, the baselines it was taken against, what it does not
show, and ships a tool and a sample pair so the mechanism can be run rather than taken on
trust.

## Why the number is so small

Prompt caches match from the start of a request and stop at the first byte that differs.
Everything after that point is reprocessed and billed as new, even when it is byte for byte
identical to the previous request. So reuse is not decided by how much of your context
repeats. It is decided by **where the first change falls**.

The record in question is JSON, and it opens with the format version, the record id, and
then `"revision": 2`. The revision increments on every accepted change. Sixty-five bytes
in, the two requests diverge.

That is not a defect in the record. Identity and revision first is correct for an
authoritative document, which is what you want when you open it, diff it or verify it. It
is simply the wrong order for a prompt, and those are two different jobs.

## What was measured

| rendering | what it is |
| --- | --- |
| **record as stored** | the canonical JSON exactly as a session is handed it, because attaching the record is the current workflow |
| **projection** | a compact active view: objective, constraints, accepted requirements and decisions, acceptance criteria, accepted findings, open high priority questions, live tasks. Rendered as prompt text, emitted slowest moving first, with revision and integrity hash last |
| **checkpoint** | the human readable checkpoint the tooling already produces, included because a shipped projection is a fairer comparison than one written for a measurement |

Bytes and characters are exact. **Token figures are estimates** at a stated characters per
token: there was no offline tokenizer and no API key on the machine. The headline figures
are ratios for that reason, and the ratios are unchanged at 4.0 and 3.5 characters per
token, since both sides are the same kind of text.

## Result 1: a projection is about a fifth of the record

| project record | stored | projection | share | checkpoint | share |
| --- | --- | --- | --- | --- | --- |
| A, revision 2 | 51,085 B | 9,900 B | **19.4%** | 19,024 B | 37.1% |
| B, revision 0 | 47,424 B | 10,744 B | **22.7%** | 17,451 B | 36.7% |
| C, revision 0 | 35,829 B | 9,114 B | **25.4%** | 14,042 B | 39.1% |

Three records, 19 to 25 percent. A range rather than a number.

No transcript comparison is offered. The session transcript behind this work is 89 MB,
almost entirely tool results and whole file reads that nobody would paste into a prompt.
Dividing 9,900 by 89,000,000 produces a flattering figure that means nothing.

## Result 2: the ordering matters more than the size

Measured across two real revisions of record A, spanning a set of accepted changes:

| rendering | identical bytes from the start | share |
| --- | --- | --- |
| projection, volatility order | 5,124 of 9,900 | **51.8%** |
| the record as stored | 65 of 51,085 | **0.1%** |

The reusable prefix does not end at a section boundary. It ends part way through a line, at
the exact character where one acceptance criterion changed from `proposed` to `accepted`.
That is worth knowing when choosing an order: **records carrying a status are less stable
than they look, and belong below the ones that do not.**

## What the projection drops

Counted, not estimated, for record A: 3 history entries, 4 evidence bodies, 4 closed tasks,
10 artifact records, 3 fault records, 1 correction record.

The projection **cannot be resumed from**, only worked from. It carries no history, no
evidence bodies and no artifact ledger. The full record stays authoritative. A reduction
whose losses are not stated is not a measurement.

## Run it yourself

`measure_prefix.py` is standalone: standard library only, no network, no dependency on the
tooling that produced the results above. `sample/` holds an invented project record of the
same shape, before and after one accepted change.

```
python make_sample.py
python measure_prefix.py sample/before.json sample/after.json
```

```
rendering                             bytes  reusable    share   tokens~
record as stored, custody first       7,380        81     1.1%     1,845
projection, volatility order          3,249     2,158    66.4%       812

the projection is 44.0% the size of the record

the projection's reusable prefix ends here:
  - ac-ambiguity [ <HERE> accepted]: Ambiguous journeys return a range, ...
```

**The sample is a demonstration, not a measurement.** Its ratios differ from the measured
ones because it is a smaller record with proportionally less material to drop. What it
reproduces is the mechanism: the stored record loses its prefix almost immediately, the
projection keeps most of it, and the break lands exactly where a status changed.

## What this does not show

- **No token counts.** Every token figure here is an estimate at a stated divisor.
- **No cache hit rate.** Prefix share is the property a cache needs, not the saving it
  produces. Caches have minimum sizes and expiry windows, and the counter that reports a
  cache read is visible only on a raw API path, not inside a subscription harness.
- **No money.** Nothing here converts to a cost figure.
- **One record, one pair of revisions**, spanning more than one accepted change. A smaller
  change should preserve considerably more of the prefix. That figure is not reported
  because it could not be verified, for the reason below.
- **Not independently reproducible yet.** The records measured are a working project's real
  state and the tool that produced `results.txt` lives in a repository that is not public.
  The method is stated, the logic is published here in standalone form, and the sample
  demonstrates the mechanism. Independent reproduction of *these* numbers has to wait for
  the format and its tooling to be released.

That last point is the honest limit of this note, and it is stated rather than glossed.

## A note on verification, including of this measurement

Partway through, the validator behind these records was tightened to check two values it
had previously trusted. That immediately made one already accepted change unreplayable:
the stored change contains a value the stricter validator now rejects. The current state
is valid and the receipts still record what was agreed; what was lost is the ability to
re-derive the intermediate steps.

The first version of the measuring tool papered over exactly that. It reimplemented the
step it could not run, produced documents whose integrity hashes did not match the ones
already on file, and printed the numbers anyway. It now refuses to report figures it
cannot verify and says why. The pair compared above is revision 0, verified against the
hash the first accepted change declares as its base, and the current record.

## Files

| file | what it is |
| --- | --- |
| `measure_prefix.py` | standalone measuring tool, standard library only |
| `make_sample.py` | generates the sample pair |
| `sample/before.json`, `sample/after.json` | invented record, before and after one accepted change |
| `results.txt` | raw output of the three measured runs |

Prose here is CC BY 4.0; the scripts are MIT, as per the repository root.
