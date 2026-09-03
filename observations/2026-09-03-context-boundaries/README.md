# Crossing a context boundary

**2026-09-03 · field observation · one session, one model, no control**

A long AI coding session on a personal machine, spanning several unrelated work
streams, ran out of context mid-work and was automatically compacted: the earlier
conversation replaced by a generated summary, and the session continued from there.

Five things were worth writing down. Two are about what a summary keeps. Three are
about failures that turned out not to be memory problems at all.

---

## 1. A good summary still loses the wrong half

The summary was genuinely good. It carried the narrative arc, every decision and its
reasoning, the file paths in play, an accurate account of mistakes made and fixed, and
a list of every instruction the user had given. Anyone claiming compaction destroys a
session would be overstating it.

What it did not carry was **anything checkable**. Exact code. Exact field names. Exact
measured numbers.

The distinction is not important-versus-unimportant. It is *narratively salient*
versus *verifiable*. A summariser optimises for coherence, so it keeps the story and
drops the citations — and the citations are what let a later claim be tested.

> Compaction does not primarily lose knowledge. It loses **the ability to check
> knowledge**, which is the more dangerous failure, because what survives is a set of
> confident claims with nothing behind them.

A claim you can no longer verify is not weaker than one you can. It is
indistinguishable from one you can, which is worse.

---

## 2. The constraint improved the output

After the boundary, the session wrote a structured record of one project's state.
Because there was no remembered version to lean on, every factual claim in it had to
be re-derived by opening the file and reading it. The result was a document in which
every assertion carries a resolvable pointer to its source.

An uncompacted session would plausibly have produced the *same claims*, sourced from
context rather than from files — and the two documents would have looked identical.
One would have been checkable and one would not, with nothing in the artifact to say
which.

This is uncomfortable and worth stating: the loss forced a discipline that produces
better provenance than convenience does. The lesson is not that compaction is good.
It is that **"the model remembers it" and "the record cites it" are different
epistemic states that produce identical-looking documents**, and only one of them
survives scrutiny.

---

## 3. One tool, built three times, in one session

Three scripts were written to perform the same operation: edit a generated HTML
document by matching a text anchor, splice in new content, and republish it.

| | Rediscovered |
| --- | --- |
| First script | the generated wrapper must be stripped before matching; the anchor failed because it was reconstructed from expectation rather than read from the file |
| Second script | the same anchor-matching failure, in a different character |
| Third script | the wrapper problem again |

All three were written into a session-scoped temporary directory. None will exist
tomorrow.

The second script's failure is the datum. Roughly forty minutes after the first
failure was diagnosed and fixed, the same root cause recurred — the source document
mixes literal characters with named HTML entities, so an anchor built from what the
text *should* say does not match what it *does* say. The fix existed. It lived in a
file nobody had promoted, so it was not somewhere the next attempt would look.

> The cost of throwaway tooling is not that the tool is rebuilt. It is that **its
> defects are rebuilt with it.**

### The contrast is inside the same session

The same session, same author, same day, promoted other tools deliberately and
without being asked: patch scripts written into a project repository with headers
explaining what they change and why, each runnable in a dry-run mode; and two
converters written as reusable utilities with usage lines and a stated reason to
exist.

The abandoned scripts were comparable in size and sophistication to the promoted
ones. The difference was not value, novelty or effort. **It was whether the work
happened inside a directory the author was already thinking about.**

Which suggests the intervention is not "be more disciplined about tools." It is to
make the count visible. A tool built once is scaffolding. A tool built three times in
one session is a missing repository entry, and noticing that requires no judgement —
only a counter.

---

## 4. A written rule that did not govern

The session maintained a running log of tool-use faults, one entry per root cause.

One entry recorded that publishing an update to a hosted document is refused unless
the entire saved source has been read first, *including* a large machine-generated
first line — and stated the remediation explicitly, because it had already happened
twice.

While adding a new entry to that log, the session read the file from line 2, skipping
the expensive first line to save context. The publish was refused. The entry was
updated to record a third occurrence.

The rule was present. It had been written down deliberately. It had been read minutes
earlier. It still did not govern behaviour.

> Externalising knowledge is necessary and **not sufficient**. A rule stored in a
> document does not change what happens unless something forces it to be consulted at
> the moment it applies.

Note also that the saving being pursued is the trap. The expensive line is precisely
the one worth skipping, so the optimisation is always tempting, and the check counts
it every time. Rules that are violated by the locally rational choice need a
mechanism, not a reminder.

---

## 5. Where corrections came from

Two substantive errors were caught during the session, by different routes.

**Self-caught.** The model sampled the first portion of a *sorted* collection and
reported that sample's ceiling as the collection's ceiling. It was wrong by a wide
margin, and had it stood it would have triggered unnecessary regeneration work while
leaving the real defect — uniform sampling of an ordered collection — untouched. It
was caught by measuring the whole collection rather than a sample.

**User-caught.** The model described a source file as a stale duplicate of a build
output and recommended repointing a tool away from it. It was in fact the source a
second target was generated from, and the direction of generation had reversed since
the note the model was working from. The model asserted this twice before being
corrected.

The asymmetry is the finding. **The model caught the error it could test. It could
not catch the error caused by stale stored context, because there was nothing about
that context to suggest testing it.** That is the same failure mode as
post-compaction confidence, arriving by a different route: information that is
plausible, internally consistent, and no longer true.

---

## What this supports, and what it does not

**Supports:** that the cost of context compaction is verifiability rather than
knowledge; that throwaway tooling reproduces its own defects; that externalised
rules require an enforcement point; and that a model's self-correction covers what it
can test and not what it merely believes.

**Does not support:** any quantitative claim about how much is lost at a boundary.
Single session, single model, no control, no before-and-after comparison.

## What would make this a measurement

A hook firing before compaction, reading the transcript deterministically and
recording what existed at that moment — then a report, after compaction, classifying
each item as **survived anyway**, **carried by the record only**, or **lost**.

The third row is the one that matters and the one an honest instrument must be able
to print. A report that can only show successes is marketing.

That instrument did not exist while this session ran, which is why this is an
observation rather than a result.
