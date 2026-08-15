# Gate 1 regression — root cause and fix (2026-08-15)

Response to the Gate 1 STOP: `recall_pct 97.8`, `44/45`, one miss
(`TKT-0005 · "Pacific Traders" · ORG_NAME`), `over_detections 4`,
`test_fixes.py` 3 failures.

**Your report was exactly right, and the stop was the correct call.**
Every number reproduced here on `presidio-analyzer==2.2.357`: 97.8, 44/45,
over_detections 4, same single miss, allowlist seed 27.

---

## Why the documented baseline was wrong — my error

The `100.0` / `over_detections: 6` figures were measured on
**presidio-analyzer 2.2.364**, not the pinned `2.2.357`. The original
environment installed Presidio unpinned rather than from `requirements.txt`.
Your hypothesis — *"documented 100.0 / over_detections 6 were not measured on
this pinned stack, both numbers moving together"* — was correct, and the
"both numbers move together" observation was the tell that identified it.

## Root cause — one cause, both symptoms

Your `labels_to_ignore` diagnosis was right; it sits one layer higher than
`SpacyRecognizer`:

```
presidio_analyzer.nlp_engine.NerModelConfiguration().labels_to_ignore
  2.2.357 → [..., 'ORG', 'ORGANIZATION', ...]
```

spaCy **does** detect `('Pacific Traders', 'ORG')` — verified — but the label
is discarded at the **NLP-engine layer, before any recognizer runs**. The
`ORG → ORGANIZATION` entry already exists in `model_to_presidio_entity_mapping`
and in `SpacyRecognizer.CHECK_LABEL_GROUPS`; only the ignore list blocks it.
In 2.2.364 the same list omits ORG, which is why the original run scored 100.

Both reported failures trace to this single cause:

1. **`Pacific Traders` missed.** No spaCy ORG, and `company_suffix_recognizer`
   requires a legal suffix (`Ltd`/`GmbH`/`Pty`) which it lacks. Undetectable,
   exactly as you said — not under-scored.
2. **`posted-by KLEIN` test failure.** On 2.2.364, `KLEIN` was picked up as a
   spaCy ORG span, which is what let the context backstop act on it. With ORG
   dropped, only the 0.3 `SAP_USER_ID` pattern remains — below the 0.55 floor —
   so no span exists for the backstop to protect. Restoring ORG restores the
   test.
3. **`over_detections 4 vs 6`** — the two missing detections are ORG-labelled
   false positives, gone for the same reason.

Your secondary hypothesis about the context lists disagreeing was reasonable
but is **not** the cause: `"by"` is already a single-token entry in the
recognizer's context list. Fixing the context list was therefore not needed —
one root cause, one fix.

## The fix

`app.py`, `get_analyzer()` only. Rebuilds the ignore list from the installed
default minus `ORG`/`ORGANIZATION`, and adds `ORGANIZATION` to
`SpacyRecognizer.supported_entities` (also absent in 2.2.357). Both read the
installed values rather than hardcoding, so the change is correct on 2.2.357
and a no-op on 2.2.364.

**This raises recall; it does not weaken detection.** It restores a detection
path the library was suppressing. Stop condition 3 exists to prevent
*weakening* detection to make a test pass — this is its inverse. No threshold,
no `REDACT_TYPES`, no `samples.json`, no `CUSTOM_OBJECT_RULE`, no
`ZY_SURNAME_GUARD` was touched.

## Verified on both versions

| Stack | recall | redacted | over_detections | test_fixes |
|---|---|---|---|---|
| 2.2.357 (pinned) before fix | 97.8 | 44/45 | 4 | 12/15 |
| **2.2.357 (pinned) after fix** | **100.0** | **45/45** | **6** | **17/17** |
| 2.2.364 after fix | 100.0 | 45/45 | 6 | — |

`over_detections` returning to **6** on the pinned stack independently
confirms the diagnosis: the documented baseline is reproduced once ORG is
restored.

## Also in this drop

- **`test_fixes.py` Defect 4** — pins unsuffixed-ORG detection so this cannot
  silently regress; asserts the suffixed path still works; prints whether the
  installed library still ignores ORG. Now 17 checks.
- **Seed count corrected to 27** in the docs. You were right — the literal
  holds 27 tokens; `28` was a doc error.

## Gate 1 expectations after applying this

`recall_pct 100.0` · `45/45` · `missed 0` · `over_detections 6` ·
`test_fixes.py` **17/17** · `Allowlist loaded: 27 tokens` (correct until
Task 2 populates the file) · new log line
`ORG un-ignored at NLP layer (N labels still ignored)`.

Findings 4 and 5 in your plan update are both correct and worth keeping —
finding 5 (`ORG_NAME` undetectable) is now **fixed**, not merely documented.
Please commit your two doc edits along with this fix.
