# Pinning, merging and prompt order in three agent memory systems

**2026-10-02 · documentation review · no tests run, no measurements**

A companion to [Sixty-five bytes](../../articles/prefix-caching-project-state/), which measured
what happens to a cached prompt prefix when shared project state changes underneath it.

That note raised two separate problems. This one asks whether three widely used systems have
either of them, by reading their public documentation and quoting it.

**Ordering** is an efficiency failure. Prompt caches match from the start of a request and stop at
the first byte that differs, so volatile material placed early destroys the prefix behind it. You
pay more and nothing tells you.

**Pinning** is a correctness failure. Concurrent readers of a store that moves underneath them
reason from different versions of the truth, and produce confident, mutually inconsistent work.

Three questions, asked of each system:

1. Does it place variable content above stable content in the assembled prompt?
2. Does it expose a pinned version or snapshot a caller can hold?
3. When two writers touch the same record concurrently, does it reconcile, refuse, or overwrite?

The three were chosen to answer differently, not by popularity: a memory layer that puts state
directly in context, a workflow framework that versions state and assembles no prompt, and a
retrieval layer whose content is query dependent by design.

---

## 1. Letta (memory blocks)

**Ordering: the exposed case, by its own description.** From
[Memory blocks](https://docs.letta.com/v1-sdk/memory/memory-blocks):

> Under the hood, memory blocks are simply prepended to the agent's prompt in an XML-like format.

The documented rendering places a metadata header above the value it describes:

```
<persona>
<description>The persona block: Stores details about your current persona...</description>
<metadata>
- chars_current=128
- chars_limit=5000
</metadata>
<value>I am a helpful assistant named Sam...</value>
</persona>
```

Changing a block's value also changes `chars_current`, which sits above it, in material prepended
to the whole prompt. This is the same shape as the finding in the companion note, where a revision
number near the top of a record ended the reusable prefix after 65 bytes, and it was arrived at
independently.

**Pinning: no versioned snapshot.** From
[Shared memory](https://docs.letta.com/v1-sdk/memory/shared-memory):

> When one agent updates the block, all others see the change immediately.

> `blocks.update()` replaces the entire block content, it does not append. All agents with access
> see changes immediately.

A `read_only` flag exists, but the same page states it is not a per-caller pin:

> Read-only applies to the entire block, not per-agent. You cannot make a block read-only for some
> agents but writable for others.

**Concurrency: documented plainly, including the failure.** The page carries this table:

| Operation | Concurrent-safe? |
| --- | --- |
| `memory_insert` | Yes (append-only) |
| `memory_replace` | Mostly (fails if target string changed) |
| `memory_rethink` | No (last-writer-wins) |

> **Anti-pattern:** Multiple agents doing `memory_rethink` on the same block simultaneously leads
> to lost updates.

The mitigations offered are conventions rather than mechanisms:

> Designate one agent (or sleep-time memory) as the "owner" for heavy edits. Other agents append
> via `memory_insert`.

> **Race conditions** - Design blocks so each agent updates their own section.

`memory_replace` failing when the target string has changed is a string level compare and swap,
and is the one structural guard in the set.

**Note on currency.** The shared memory page carries a deprecation notice: it describes the
legacy v1 API, says memory blocks "may be deprecated in the future", and recommends shared memory
repositories and MemFS for new work. Those were not evaluated here, and they may change this
verdict.

---

## 2. LangGraph (checkpointers and reducers)

**Ordering: not its concern, which moves the exposure outward.** LangGraph persists state; the
caller assembles the prompt. There is no verdict to give, and that is the point: the ordering
question becomes a property of whatever renderer you write, unmanaged by the framework.

**Pinning: yes, genuinely.** From the
[Persistence](https://docs.langchain.com/oss/python/langgraph/persistence) documentation:

> Checkpointers persist a thread's graph state as checkpoints. Use them for short-term,
> thread-scoped memory, including conversation continuity, human-in-the-loop workflows, time
> travel, and fault tolerance.

A thread plus a checkpoint identifies a snapshot that can be resumed or rewound.

**Concurrency: refuses rather than guesses, which is the strongest answer of the three.** From
[INVALID_CONCURRENT_GRAPH_UPDATE](https://docs.langchain.com/oss/python/langgraph/errors/INVALID_CONCURRENT_GRAPH_UPDATE):

> A LangGraph StateGraph received concurrent updates to its state from multiple nodes to a state
> property that doesn't support it.

> if multiple nodes in e.g. a fanout within a single step return values for `"some_key"`, the graph
> will throw this error because there is uncertainty around how to update the internal state.

The resolution is to declare the merge rule in advance, per key:

```python
class State(TypedDict):
    # The operator.add reducer fn makes this append-only
    some_key: Annotated[list, operator.add]
```

Two properties are worth separating. Merge semantics are **declared, not inferred**. And where they
have not been declared, the system **refuses the write** instead of picking a winner. Sequential
updates with no reducer replace the value, so the strictness applies to the concurrent case
specifically.

**One documented edge.** Shared state across graph boundaries does not carry the same guarantees:

> When a subgraph updates state, the parent graph may not see the changes immediately. This is
> because each subgraph manages its own checkpoint namespace.

with cross-boundary data directed into Store, which is a separate system from the checkpointed
state.

---

## 3. Mem0 (retrieval memory)

**Ordering: hostile by design rather than by accident.** From the
[Add Memory](https://docs.mem0.ai/core-concepts/memory-operations/add) documentation, describing the
pipeline:

> **Retrieval.** Future searches rank the most relevant memories for the query.

The injected set is query dependent, so it differs between turns deliberately. Wherever that
material sits in the prompt, everything after it loses its prefix, and the effect gets worse as
relevance tuning improves, since a better tuned retriever returns something less like last turn.

This is the opposite failure from the other two. A record ordered badly can be reordered. Content
that is supposed to change every request cannot be made stable without giving up the thing it is
for.

**Pinning: nothing found.** No snapshot or version concept appeared in the pages reviewed.

**Concurrency: safe by being additive.** From the same page:

> **Additive storage.** New memories are added without overwriting or deleting existing memories.

So there is no lost update problem, which is a real guarantee and worth saying plainly. The cost is
that contradictory memories coexist with nothing marking which governs, and the documentation warns
that duplicates can arrive:

> When you switch to `infer=False`, Mem0 stores your payload exactly as provided, so duplicates can
> land. Mixing both modes for the same fact can save it twice.

Extraction is performed by a model:

> Mem0 sends the messages through an LLM that pulls out key facts, decisions, or preferences to
> remember.

so what is stored is not a deterministic function of what happened.

---

## What the three show together

**The two problems are independent, and each system has at most one of them solved.**

| | ordering | pin | concurrent write |
| --- | --- | --- | --- |
| Letta | prepended, counter above value | none | last-writer-wins on full rewrite |
| LangGraph | not its job | yes, checkpoints | refuses unless a merge rule is declared |
| Mem0 | query dependent by design | none found | additive, so no lost updates |

**The dividing line is whether merge semantics are declared.** Where a system makes you say in
advance how concurrent updates combine, concurrency is safe and dull. Where the rule is implicit,
the outcome is last writer wins, a string comparison, or a model's judgement.

**The pin exists where prompt layout does not, and vice versa.** The system that versions state has
no opinion about prompt order. The systems that assemble the prompt have no version to hold. These
are not in conflict with each other; they are simply in different products.

**Nobody reviewed here treats prefix stability as a constraint on state layout.** One prepends
durable state and places a volatile counter above the content it counts. Another's whole value is
returning something different each time. The caching documentation and the memory documentation do
not meet.

## What this does not support

- **It is a documentation review, not a test.** Nothing here was run. Documentation describes
  intent; only a test shows behaviour, and the companion note holds its own numbers to that
  standard.
- **It is dated.** Everything above was read on 2026-10-02. Letta's shared memory page already
  carries a deprecation notice pointing at successors that were not evaluated.
- **Coverage is partial.** Three systems, chosen because they answer differently. Mem0's dedicated
  search page did not load during the review, so the retrieval claims rest on its Add Memory page.
- **No judgement is offered about whether these are good systems.** Each is answering a question it
  chose. A retrieval layer is not wrong to return different content per query; that is its purpose.
  The observation is only that the two failure modes exist, are independent, and are not currently
  addressed in the same place.
