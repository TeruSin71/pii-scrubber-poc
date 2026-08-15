# Person-context promoter — documented negative result

**2026-08-15.** P2 backlog item, built and measured against the 40-sample
holdout, then **reverted rather than shipped**. `app.py` is unchanged.
`test_person_context.py` is kept as the executable spec; it does not run green
because the implementation it describes is not in the tree.

The deployment `d5e6ea76217ed207` is untouched. **96.4% remains the current
number.**

## What was built

A post-pass in `detect()` that emitted a PERSON span for a name-shaped token
sitting immediately after an explicit agent cue (`posted by ZHANG`). It ran
after allowlist suppression, so an explicit cue outranked the allowlist by the
same rule `_in_user_context` already applies.

It was not a tenth `PatternRecognizer` because presidio-analyzer 2.2.357
reports `match.span()` for the whole match and has no capture-group support —
a `<cue> <name>` pattern would have redacted the cue too, turning
`posted by ZHANG` into `<PERSON>`. Python's `re` allows only fixed-width
lookbehind, so the cue could not be moved out of the match either.

## Mechanism: verified working

With `escalated` added to the cue list in memory:

```
cue matches: [('Escalated by ', 0, 13)]
slot starts 'ZHANG this morning...'
name matched: 'ZHANG' [13:18]
scrubbed: Escalated by <PERSON> this morning, please treat as urgent.
```

Correct span extent, cue preserved, no over-redaction. The plumbing is sound.

## Reach: one third of the residual class

| Measurement | Result |
|---|---|
| Holdout, 40 unseen samples, as shipped | **0 fires**, 96.4% unchanged, controls byte-identical |
| Holdout, with `escalated` added | 1 fire, 97.3% |

`escalated` was **not** added. Adding it after reading the holdout output
trades a defensible blind 96.4% for an indefensible 97.3%.

## Three leaks, three distinct causes

| Sample | Cause | Solvable by rules? |
|---|---|---|
| HO-001 | cue enumeration — `escalated` absent from the list | **Yes**, by list |
| HO-031 | strict adjacency — `.match()` at `cue.end()`, so `contact is the shift lead Mere Tuhoe` misses | Needs a **window** after the cue, not a longer list |
| HO-018 | cue-free subject position — the actor is the sentence subject, no cue exists | **No.** Needs POS/dependency parsing |

Evidence for the adjacency limit, with `contact is` added in memory:

```
"Site contact is Mere Tuhoe."                 -> fires, span 'Mere Tuhoe'
"Site contact is the shift lead Mere Tuhoe."  -> slot='the shift lead Mere Tuhoe', no match
```

Any intervening words (`the shift lead`, `our`, `Mr`) defeat it.

**Conclusion: a rule-based promoter reaches roughly one third of the residual
PERSON class. The remainder requires the NLP layer, not more rules.**

Shipping it anyway would have put an unexercised control in the README. A
documented gap on a backlog is the better artefact.

## Related finding — the `lg` item is frame robustness, not vocabulary

`en_core_web_sm` is not uniformly blind to the name it misses:

```
"The shift lead is Mere Tuhoe."               -> [('Mere Tuhoe', 'PERSON')]
"Site contact is the shift lead Mere Tuhoe."  -> NO SPANS
```

Same name, same model, two sentence frames, opposite results. So the model
upgrade should be scoped as **frame robustness**, not as "the small model does
not know this name."

## Process finding — spec-to-implementation narrowing

Both `escalated by` and `contact is` were named in the written backlog spec.
The implementation chose a `<verb> by` template family, which structurally
excluded `contact is` and dropped `escalated` from the enumeration. Neither
omission was visible in the 24 unit tests, because those were written from the
same model of "what a cue looks like" that produced the cue list — they
confirmed the model rather than tested it.

**The failure mode worth catching earlier: a template chosen during
implementation silently narrows the spec, and tests derived from that same
template cannot detect the narrowing.** Check implementation coverage against
the spec text, not against the tests.
