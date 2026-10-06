# Sixty-five bytes: prompt caching and the shape of project state

**2026-10-02 · Paul Woll · Triuna Labs**

A project record of 51,085 bytes, rendered at revision 0 and again at revision 2, two accepted
changes later. **Sixty-five bytes were still identical** from the start of the file.

Reordering the same selected fields, without removing any of them, took that to 51.8%. Selecting
less material, on its own, accounted for none of the difference.

This note states the measurement, the baselines it was taken against, what it does not
show, and ships a tool and a sample pair so the mechanism can be run rather than taken on
trust.

A companion observation,
[Pinning, merging and prompt order in three agent memory systems](../../observations/2026-10-02-memory-pinning/),
asks whether three widely used systems have this problem, by reading and quoting their
documentation. One of them renders a character counter above the value that counter
describes, which is the finding below arrived at independently.

## Why the number is so small

The first changed byte ends the identical prefix measured here. For prefix-based prompt
caching, **where the first change falls** matters more than how much text repeats later.
Actual cache reuse is decided in tokens at provider-specific eligible breakpoints, not at
an arbitrary byte boundary; the changed suffix may be processed as new input even when
some of its text also appeared in the previous request. See the
[OpenAI](https://developers.openai.com/api/docs/guides/prompt-caching) and
[Claude](https://platform.claude.com/docs/en/build-with-claude/prompt-caching) caching guides.

**A shared prefix is a precondition for reuse, not a cache hit, and this note measures the
precondition.** Providers require an exact match up to a cacheable point in the assembled prompt,
which can include tools and system content. They also impose model-dependent minimum lengths and
cache lifetimes; routing can affect whether an eligible entry is available. An identical byte prefix
therefore does not guarantee a cache read. Nothing here was measured against an API.

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

Measured across record A at revision 0 and revision 2, two accepted changes apart. Three
renderings, and the middle one is the control:

| rendering | identical bytes from the start | share |
| --- | --- | --- |
| the record as stored, custody first | 65 of 51,085 | **0.1%** |
| the same selected fields, custody first *(control)* | 62 of 9,900 | **0.6%** |
| the same selected fields, custody last | 5,124 of 9,900 | **51.8%** |

The control holds exactly the same selected fields as the third row, in the same words, at the same
9,900 bytes. Only the order differs. **Selecting less material moved the shared prefix from 65 bytes
to 62, which is to say it did nothing. Moving the volatile fields to the end moved it to 5,124.**
Compression is not what buys the prefix. Ordering is.

The shared prefix does not end at a section boundary. It ends part way through a line, at
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

[measure_prefix.py](https://github.com/TriunaLabs/research/blob/main/articles/prefix-caching-project-state/measure_prefix.py)
is standalone: standard library only, no network, no dependency on the tooling that produced the
results above. [sample/](https://github.com/TriunaLabs/research/tree/main/articles/prefix-caching-project-state/sample)
holds an invented project record of the same shape, before and after one accepted change.

```
python make_sample.py
python measure_prefix.py sample/before.json sample/after.json
```

```
rendering                                   bytes    shared    share   tokens~
record as stored, custody first             7,380        81     1.1%     1,845
same selected fields, custody first         3,249        91     2.8%       812
same selected fields, custody last          3,249     2,158    66.4%       812

the selected view is 44.0% the size of the record

with custody last, the shared prefix ends here:
  - ac-ambiguity [ <HERE> accepted]: Ambiguous journeys return a range, ...
```

**The sample is a demonstration, not a measurement.** Its ratios differ from the measured
ones because it is a smaller record with proportionally less material to drop. What it
reproduces is the mechanism: the stored record loses its prefix almost immediately, the
projection keeps most of it, and the break lands exactly where a status changed.

## What this does not show

- **No token counts.** Every token figure here is an estimate at a stated divisor.
- **No cache hit rate.** A shared prefix is a precondition for reuse, not the saving it
  produces. Providers require a matching eligible prefix, impose model-dependent minimum lengths
  and cache lifetimes, and may route requests differently, so an identical prefix can still miss.
  The counter that reports an actual cache read is visible only on a raw API path, not inside a
  subscription harness.
- **No money.** Nothing here converts to a cost figure.
- **One record, one pair of revisions**, revision 0 to revision 2, spanning two accepted
  changes. A single smaller change should preserve considerably more of the prefix. That figure
  is not reported because it could not be verified, for the reason below.
- **Not independently reproducible yet.** The records measured are the real state of a working
  project governed by the Living Prompt Contract, a format I maintain, and the tool that produced
  `results.txt` lives in a repository that is not public.
  The method is stated, the logic is published here in standalone form, and the sample
  demonstrates the mechanism. Independent reproduction of *these* numbers has to wait for
  the format and its tooling to be released.

That last point is the honest limit of this note, and it is stated rather than glossed.

**Whether any of this produces provider cache reads or lower costs remains a question for a
measured agent workflow:** run against an API, with the cache counters read and the bill compared.
That is a different piece of work and it has not been done. A caching implementation of any kind,
provider-side or otherwise, belongs in that later measured piece rather than this one.

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
| [measure_prefix.py](https://github.com/TriunaLabs/research/blob/main/articles/prefix-caching-project-state/measure_prefix.py) | standalone measuring tool, standard library only |
| [make_sample.py](https://github.com/TriunaLabs/research/blob/main/articles/prefix-caching-project-state/make_sample.py) | generates the sample pair |
| [sample/before.json](https://github.com/TriunaLabs/research/blob/main/articles/prefix-caching-project-state/sample/before.json), [sample/after.json](https://github.com/TriunaLabs/research/blob/main/articles/prefix-caching-project-state/sample/after.json) | invented record, before and after one accepted change |
| [results.txt](https://github.com/TriunaLabs/research/blob/main/articles/prefix-caching-project-state/results.txt) | raw output of the three measured runs |

Prose here is CC BY 4.0; the scripts are MIT, as per the repository root.
