# COWORK HANDOVER — 2026-08-16 (late evening)

PII Scrubber project — reviewer session + SAP Build POC build.
**For the next Cowork session: read this whole file before doing anything, then stand by for Teru.**

Human: Teru — chat account `terulins@gmail.com`, **BTP/SAP Build login `terulin.sinulingga@gallagher.com`** (this matters: approval tasks route to the gallagher.com identity).

Facts below are tagged **VERIFIED** (seen on screen this session) or **REASONED** (inferred; could be wrong).

---

## 1. Standing role and rules — unchanged, still in force

- **This Cowork session REVIEWS and advises; a Claude Code agent in VS Code EXECUTES.** No direct channel — Teru pastes text between the two. Tonight was an exception: the BPA POC was built directly through Teru's Chrome (his explicit request), which is UI work, not scrubber-repo work. The repo remains executor territory.
- **Review style (Teru's explicit instruction):** prose reasoning that names causes precisely; bold only for load-bearing claims; own your errors *with their mechanism*; end reviews with a terse verdict block.
- **Credentials:** Teru types all secrets himself ("for credential I will type"). Never read `~/aicore-key.json` (contains the client secret). Client IDs are fine; secrets never.
- **Rotation** of the AI Core key + GitHub PAT is deferred to project completion — owner's accepted decision. Do not re-raise.
- **Blind batch v4 is HELD** — not read, not run, not salted. Releases only after a union release's verification.
- No standing registry grants. Grants are per-release, exact-tag, at the publish step, removed after digest verification.
- Burned eval sets (regression gates only, never quotable): `samples.json`, `holdout_samples.json`, `eval_samples_v2.json`, `holdout_v3.json`. Only quotable figure: **90.0% blind**.

## 2. Where things stand, in one paragraph

The entire BPA upload-and-review POC is **built, mapped, and released (1.0.1)**. The scrubber itself was never touched — deployment `daedcfe9342d21a7` ran 1.2.3/presidio throughout. One thing blocks a live run: **BPA's deploy-time destination picker refuses to list `NER_SCRUBBER`**, and a controlled experiment (§4) proved the destination's configuration is innocent — the picker is serving a stale or consumption-seeded list. The remaining fix is almost certainly *time*, the untried *Public environment*, or a *support ticket* — not more editing.

## 3. What exists and is verified

### 3.1 SAP Build project (all VERIFIED)

Studio URL:
`https://btpsandbox.ap10.process-automation.build.cloud.sap/studio/?action=open&id=ap10.btpsandbox.piiscrubpoc#/studio/project/47bb6ed6-c260-4cc6-96bd-d4bafe92f870`

Project **PII Scrub POC** — released **1.0.1** (1.0.0 also exists; 1.0.1 is the one to deploy — it carries the corrected recipient). Design Console clean at release.

Flow: **Upload Ticket (form trigger) → Scrub PII from text (action) → Review Scrubbed Ticket (approval, Approve/Reject branches) → End**

| Artifact | Content |
|---|---|
| Form `Upload Ticket` | `Ticket reference` (text) · `Ticket text` (text area, **required**) |
| Approval `Review Scrubbed Ticket` | `Ticket reference` (read-only) · `Original ticket (reference only)` (text area, read-only) · `Scrubbed text - correct it here` (text area, **editable + required** — this is the demo) |
| Process `Scrub and Review Ticket` | mappings below |

Mappings on the scrub step: `text` ← Upload Ticket → *Ticket text*; `mode` ← literal `live`; destination = **Destination Environment Variable `NER_SCRUBBER_DEST`** (created, attached, unbound until deploy).
Mappings on the approval: `Original ticket` ← trigger *Ticket text*; `Scrubbed text - correct it here` ← **Scrub PII from text → result → `scrubbed_text`**; `Ticket reference` ← trigger *Ticket reference*. Subject `Review scrubbed ticket`; **Recipients → Users = `terulin.sinulingga@gallagher.com`** (fixed in 1.0.1; 1.0.0 had the gmail address, which routes to nobody's inbox).

Action project **PII Scrubber 1.0.0** — released **and published**; two actions from `pii-scrubber-openapi.json`: `scrubText` (POST `/v1/scrub`, mode default live) and `getInfo` (GET `/v1/info`). Cosmetic quirk (VERIFIED): the scrub step's General panel shows "Artifact Name: Engine identity and build version" — a UI mislabel. The step is the right action; its Inputs (`text`, `mode`) and Outputs (`result.scrubbed_text`, `engine`, `mode`, `redacted_count`) confirm it.

### 3.2 BTP cockpit destinations (subaccount **BTP Free Tier**, global account **Gallagher Group (NZ)**)

Cockpit reachable (by Claude's browser tools) **only** via the region host:
`https://apac.cockpit.btp.cloud.sap/cockpit/?idp=a9cxtseb4.accounts.ondemand.com#/globalaccount/CA1192080TID000000000741239380/subaccount/533a28c1-cf90-4ca0-a70e-f888f6a7e55f/destinations`
(The bare `cockpit.btp.cloud.sap` host is blocked for the browser tools. VERIFIED both ways.)

| Destination | State | Notes |
|---|---|---|
| `NER_SCRUBBER` | VERIFIED correct | HTTP · Internet · OAuth2ClientCredentials · URL `https://api.ai.prod.ap-southeast-2.aws.ml.hana.ondemand.com/v2/inference/deployments/daedcfe9342d21a7` (path **must stay** — BPA appends `/v1/scrub` etc.) · token URL `https://btpsandbox.authentication.ap10.hana.ondemand.com/oauth/token` · client ID `sb-d0e44def-…|aicore!b1456` · props: `URL.headers.AI-Resource-Group=default`, `sap.applicationdevelopment.actions.enabled=true`, `sap.processautomation.enabled=true` (values exact lowercase `true`, spellings compared character-for-character against CAP_GOVERNANCE). Created 19:38, modified 19:56 NZT. |
| `CAP_GOVERNANCE` | pre-existing | The **only** entry BPA's deploy picker shows. Same type/proxy/auth/token-URL/flags as ours. REASONED: visible because it was already consumed by a deployed BPA artifact ("BPA decisionCallback"). |
| `BPA_CACHE_TEST` | **probe — do not bind; delete after diagnosis** | Created this session as a control: HTTP · Internet · **NoAuthentication** · `https://example.org` · both BPA flags `true` · nothing else. |

### 3.3 Untouched

Scrubber deployment `daedcfe9342d21a7` — 1.2.3, presidio engine, running on AI Core throughout (VERIFIED earlier via AI Launchpad). `mode=live` already returns numbered placeholders + `token_map`; **no scrubber code change is needed for this POC**.

## 4. The blocker — evidence chain (read before touching anything)

Symptom: Deploy → Shared Environment → **Define Variables** for `NER_SCRUBBER_DEST` offers a destination list containing **only CAP_GOVERNANCE**. Typing filters the list only — free-typed names are not accepted (VERIFIED).

Ruled out, in order, each by evidence:

1. **Property values/spelling** — side-by-side cockpit comparison: identical keys, identical lowercase `true`. VERIFIED.
2. **Subaccount level** — both destinations live in the same subaccount list. VERIFIED.
3. **Type / proxy / auth** — identical. VERIFIED.
4. **The `URL.headers.*` property or URL path** — killed by the control: `BPA_CACHE_TEST` has neither, and is **also absent** from the picker, immediately after creation *and* on re-check. VERIFIED.
5. **Short-TTL cache** — NER_SCRUBBER stayed invisible across checks spanning roughly an hour after creation. VERIFIED (weakly bounds the TTL from below; doesn't rule out a long one).

Conclusion (REASONED, but the only one left standing): the picker reads a **stale or consumption-seeded registry**, not the live subaccount list. The empty dropdown seen earlier in the Action editor's Test tab is the same fault surfacing earlier — the "harmless design-time caching" verdict from that night is **withdrawn**.

**Editing NER_SCRUBBER further is proven pointless.** Any next session that starts fiddling with destination properties is repeating a refuted experiment.

## 5. First actions for the next session — in order

1. **Reopen the picker.** Studio URL above → version selector `1.0.1 Released` → **Deploy** → Shared Environment → Deploy → wait for *Define Variables* → open the Destination dropdown. Also click **"Use existing value"** once (untried this session — costs one click).
2. Read the list. Three outcomes:
   - **`BPA_CACHE_TEST` and `NER_SCRUBBER` both appear** → it was a slow cache. Bind **`NER_SCRUBBER`** (never the test), Deploy, confirm success. Then cleanup: delete `BPA_CACHE_TEST` in the cockpit; in the Build lobby delete the leftover empty projects (**Scrubber Review Demo**, and an earlier empty duplicate of *PII Scrub POC* if it exists — keep the project whose Overview shows 3 artifacts / release 1.0.1).
   - **Still only CAP_GOVERNANCE** → try **Public** environment once (Deploy → Public → Deploy) purely to see whether its picker differs; if it also fails, stop and raise an SAP case: *SAP Build Process Automation — subaccount destination with `sap.processautomation.enabled=true` not listed in deploy-time destination binding; reproduced with a fresh minimal destination* (component ≈ LOD-BPM-PA; verify in SAP for Me). Attach both cockpit screenshots and the picker screenshot — Teru has them from tonight.
   - **Test appears but NER_SCRUBBER doesn't** → genuinely destination-specific after all; diff again with fresh eyes (this outcome would surprise; nothing tonight predicts it).
3. **After a successful deploy — run it:**
   - Project Overview → **Triggers** tab → open the `Upload Ticket` form link (or Monitoring → Manage → deployed process).
   - Paste the test ticket (§8), Submit.
   - **My Inbox** (top-right icon) as `terulin.sinulingga@gallagher.com` → task *Review scrubbed ticket* → verify the correction box shows placeholders → **edit it** (restore a false positive, e.g. `plant <ORG_1>` back to `plant ELEC`) → Approve.
   - Check the run in **Monitoring → Process and Workflow Instances**. Errors there: 401 = credential mismatch (Teru re-pastes both from the key file); 404 = destination URL path damaged; nothing redacted = `mode` not `live` or `text` unmapped.
4. This completes the demo Teru asked for: *"the most important only to show the correction process before triage."* Triage/MCP plumbing stays parked — it needs only the P1 triage MCP server's **auth header name** from Teru (he types the value).

## 6. Traps already paid for — do not pay twice

- **Form field labels are edited inline on the canvas**, not in the right-hand properties panel. The panel has no Label box (only Character Limit / Input Validation / Required / Read Only / Add Description). The whole "locked/corrupt form designer" episode — incognito tests, fresh projects, a support-ticket verdict — was a misdiagnosis of this. Teru spotted it ("maybe the text entry is not from here").
- **Do not "fix" the destination URL** by trimming the deployment path. BPA appends only the operation path from the OpenAPI spec.
- The Action editor **Test tab's empty destination dropdown** is the §4 fault, not a config signal. Ignore it.
- UI5 quirks that ate time: fill **Token Service URL before** Additional Properties values will accept input; focus-jumps land text in the wrong box (click → `cmd+a` → type); some Value fields ignore `type` actions — triple-click the field, then send **individual keystrokes**.
- Browser session: call `tabs_context_mcp` first — the tab group vanished repeatedly tonight; recreate with `createIfEmpty` and renavigate. Cockpit only via the `apac.` host (§3.2).

## 7. Reviewer-track state (the project's front half — untouched tonight)

- **Owed by this session:** blind batch v4 — HELD until a union release's verification.
- **Owed by executor:** mechanism-claims audit of HANDOVER.
- **With management:** the engine decision (ship combined+restore / stay presidio / local LLM) — `gliner-decision-brief.html` delivered. Batch-as-union product decision escalated in the same brief.
- **Measured, quotable to Teru:** review-time simulator → **~10 s/ticket** correction time (his own run); 4-way concurrency on the free-tier pod measured **0.51×** (hence strictly-serial CPI design); cutovers are delete-then-create (hence queue+retry in the integration design).
- Named trap classes grew by two this session: *a true measurement taken at the wrong layer*; *authorization inferred from ambient signal*.
- Files in `~/Downloads/NER POC/` (Mac): `app.py`, `REVIEWERHANDOFF.md`, `REVIEW-1.2.5-session.md`, `REVIEW-1.2.6-session.md`, `pii-scrubber-openapi.json`, `gliner-decision-brief.html`, `kb-upload-integration-design.html`, `bpa-poc-finish-runbook.html`, `KBPIIarchitecture_LLMNER.html`, plus this file. The review-time simulator is persisted as Cowork artifact `pii-review-time-simulator`.

## 8. Reference

**Test ticket (paste verbatim into Ticket text):**

```
P1: Sales order 39349230 cannot be saved, short dump in VA01.
Document number not available in database. Reported by Sarah Whitcombe
from the Hamilton branch, contact 021 445 9922 or
sarah.whitcombe@gallagher.co.nz. Check table LIKP for plant ELEC.
Customer 0001045992 affected since this morning.
```

**Expected scrub (mode=live, presidio 1.2.3):** name, phone, email redacted as numbered placeholders (`<PERSON_1>`, `<PHONE_1>`, `<EMAIL_1>`); customer number likely redacted; `VA01`, `LIKP`, `39349230` untouched (tcodes/tables protected; document numbers not PII). `plant ELEC` / `Hamilton` may be **wrongly** redacted — that is the point: the reviewer restores them in the correction box. A miss or false alarm here is a demo feature, not a bug.

**API contract:** POST `/v1/scrub` `{text, mode:"live"}` → `{scrubbed_text, entities[], redacted_count, token_map, engine, mode}`. BPA schema deliberately omits `entities[]`/`token_map` (dynamic keys break BPA typing). GET `/v1/info` → build/engine identity — the project's "identity is checked, not inferred" rule.

**Verdict for the incoming session:** build done and released; blocker isolated to BPA's picker with the config exonerated by control; next concrete move is §5 step 1. Do not edit destinations. Do not re-diagnose the form designer.
