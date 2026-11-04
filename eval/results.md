# Evaluation results

**Headline: all 32 requests x 3 runs on commit `9da5e79`: 95/96 pass.** Model `claude-sonnet-5-5` (effort medium),
catalog snapshot `20261103T144315978835Z` (v1), eval run `eval-20261104T005112`. The 32nd request is a live reply
that wrongly said a total left out delivery (below). Every price, total and product selection is exact.

The one failure (E15, run 0) is a scorer false alarm, recorded and not tuned away: the reply is correct. See below.

**This score isn't comparable with the earlier 93/93.** That run didn't measure what replies claim about delivery. This
one fails any reply saying delivery is outside a total, and that scoring of wording is new. Rescored the same way, the
93/93 run on `24dd4cc` is 92/93, because its E12 run 2 made the false claim. Earlier runs: `24dd4cc` scored 93/93
(`eval/results_24dd4cc.md`), `6df6960` 86/90 (`eval/results_6df6960.md`), `8dd5eaa` 90/90 (`eval/results_8dd5eaa.md`).

| Per request (turn), from the request log | `9da5e79` (now) | `24dd4cc` (before) |
|---|---|---|
| Overall pass | 95/96, wording scored | 93/93, wording not scored |
| Mean cost | $0.0099 (p95 $0.0135) | $0.0098 (p95 $0.0143) |
| Latency | median 5.2s, p95 7.3s, max 10.2s | median 5.5s, p95 7.9s, max 8.7s |
| Rewrites after a failed reply check | 1 | 0 |
| Template replies / API errors | 0 / 0 | 0 / 0 |
| Replies containing Markdown (`**`, `#`, `|`) | 0 | 0 |
| Cost of the run | $0.95 | $0.91 |

`/ops?traffic=eval` agrees with this file: 93 model conversations in both, reply-check pass rate 100.0% in both,
spend $0.9546 in both.

## Delivery wording: a false claim the figures couldn't show

1. **Found by a live check, not the eval.** `req_c09cb9339d0d` ("9 reams of Siam Office A4 70gsm, my budget is 1,200
   baht including VAT") got a reply saying the totals "include VAT, but not delivery" and that the total "would be
   higher once it's added". ฿1,210.17 already includes the ฿150.00 delivery (981.00 + 150.00 + 79.17). Every figure was
   right, so the reply check and the eval both passed it.
2. **Cause (the tool output is known; how the model read it is inferred).** The candidate field was
   `total_incl_vat_if_ordered_alone`, with no delivery figure beside it, and the prompt said only "totals include 7%
   VAT". That candidate view is all the model gets when nothing matches, as there's no quote breakdown.
3. **Fix (`8bad222`, `9da5e79`).** The field is now `total_incl_delivery_and_vat_if_ordered_alone`, with
   `delivery_if_ordered_alone` beside it, and one new line in the system prompt. The reply check rejects the claim, in
   English and Thai, which triggers the usual rewrite and then the template.
4. **Before and after, on this request, 10 runs each.** Before (`5b6011e`): 2 of 10 replies made the claim. After
   (`8bad222`): 0 of 10, with no rewrites needed, so the label and prompt did the work and the reply check is the
   backstop. Both before-replies used wording the first version of the rule missed, which is why `9da5e79` exists. See
   `eval/exported/delivery_before_fix.results.md` and `delivery_after_fix.results.md`. The before file shows 10/10
   because that commit's scorer didn't look at wording; the 2 of 10 comes from rescoring its replies.
5. **Scored from now on.** The case is in `requests.yaml` as `X-req_c09cb9339d0d` and passed 3/3. Every case also has a
   `delivery_wording` check, which uses a wider pattern than the reply check. Sharing one pattern couldn't fail, since
   the reply check would already have rewritten anything it matched.

**What this score doesn't prove.** It's a wording match on the final reply of each conversation, so a paraphrase can
pass. In this run no first draft tripped the delivery rule, and the only rewrite was for something else (next section).

## The one failure and the one rewrite in this run

**E15 run 0, scorer false alarm.** The scorer flagged "9 reams is ฿981.00 before VAT, plus ฿150.00 delivery, for
฿1,210.17 total including VAT." That sentence is correct: "before" belongs to VAT, and the same reply also says the
total is "including delivery and VAT". The scorer sees a total, delivery and "before" in one sentence. Per the brief
for this run it's recorded, not fixed, so the pattern still has this false alarm.

**`X-req_c09cb9339d0d` run 0, rewrite.** The model first wrote the item code `PL-CP-A4-80NUSA` (a missing hyphen). The
reply check caught it and the rewrite was correct. This isn't about delivery.

## E11: a logged failure became an eval case, then passed

1. **Logged.** In a tagged eval run on the pre-fix code, "Can I get 2 packs of the Heritage Ivory A4 paper?" was
   answered `matches` with white copy paper (`req_5be5878bf35a`). The trace shows why: the model filled only
   `keywords: ["heritage ivory"]`, and keywords only ranked.
2. **Exported.** `/ops/export/req_5be5878bf35a?expect=no_exact_match` gave
   `eval/exported/E11_req_5be5878bf35a.yaml`.
3. **Fails on the old code.** `pl eval --cases eval/exported/E11_req_5be5878bf35a.yaml --runs 1` on `7a5e729`:
   0/1, decision `matches` (`eval/exported/E11_before_fix.results.md`).
4. **Fix, in code (`b2d808a`).** A keyword that names a catalog brand ("Heritage", "Lotus Bright") or a catalog
   paper colour ("ivory", "pastel blue") now becomes a filter on that attribute; brand is relaxed last when
   nothing in stock fits. Generic wishes ("recycled", "bright") still only rank. Unit tests cover both directions.
5. **Passes.** The same command after the fix: 1/1, `no_exact_match`, Heritage Ivory named as out of stock until
   2026-11-20, Heritage Cream the first alternative (`eval/exported/E11_after_fix.results.md`). The case is now in
   `requests.yaml` and passed 3/3 in the full run, as did the original E11, E07, E17 (multi-item) and E27.

## E10: scorer fix, not a system fix

The 6df6960 E10 miss was a reply that gave the right date as "12 Nov 2026", a form the scorer didn't accept. The
scorer (`45f6908`) now also accepts "12 Nov", "12 November", "Nov 12" and "November 12" for an ISO date, matched
so that "12 Nov" can't match inside "112 Nov". Re-scoring the three 6df6960 E10 replies gives 3/3. The system
didn't change.

## Full report for `9da5e79`

Model `claude-sonnet-5-5`, effort `medium`, catalog snapshot `20261103T144315978835Z`, 32 requests x 3 runs = 96 conversations.

## Layers

| Layer | Result |
|---|---|
| (a) Ingest completeness | 72 SKUs in DB vs 72 counted independently in the crawled HTML (sets equal: True); 0 missing required fields; 59 pricing files, all attached: True |
| (b) Criteria extraction | 318/318 expected fields (100%); cases fully right: 63/63 (100%) |
| (c) Product selection | 75/75 (100%) |
| (d) Totals exact (tool quote and reply text) | 66/66 (100%) |
| (e) Decision type | 93/93 (100%) |
| Reply content checks | 33/33 (100%) |
| Delivery-area flag | 6/6 (100%) |
| No false claim that a total leaves out delivery | 92/93 (99%) |
| Reply post-check passed first or second try | 93/93 (100%) |
| Reply check catches a planted wrong total (offline) | 3/3 (100%) |
| **Overall pass** | 95/96 |

Latency per conversation: median 5.2s, max 10.2s.

## Per request (stability over runs)

| Request | Passes | Notes (failed runs) |
|---|---|---|
| E01-brief-example | 3/3 |  |
| E02-tier-below | 3/3 |  |
| E03-tier-boundary | 3/3 |  |
| E04-sale-item | 3/3 |  |
| E05-below-free-delivery | 3/3 |  |
| E06-free-delivery | 3/3 |  |
| E07-half-up-vat | 3/3 |  |
| E08-lb-weight | 3/3 |  |
| E09-informal-size | 3/3 |  |
| E10-out-of-stock-flyer | 3/3 |  |
| E11-out-of-stock-paper | 3/3 |  |
| E12-no-match-alternatives | 3/3 |  |
| E13-missing-attribute | 3/3 |  |
| E14-ambiguous-colour | 3/3 |  |
| E15-budget-incl-vat | 2/3 | reply says delivery is outside a total: '9 reams is ฿981.00 before VAT, plus ฿150.00 delivery, for ฿1,210.17 total including VAT.' |
| E16-budget-default-excl-vat | 3/3 |  |
| E17-multi-item | 3/3 |  |
| E18-not-sold | 3/3 |  |
| E19-follow-up-memory | 3/3 |  |
| E20-sheets-rounding | 3/3 |  |
| E21-injection-bait | 3/3 |  |
| E22-sheets-round-up | 3/3 |  |
| E23-outside-delivery-area | 3/3 |  |
| E24-inside-delivery-area | 3/3 |  |
| E25-suggest-not-apply | 3/3 |  |
| E26-a3-reams-white | 3/3 |  |
| E27-coloured-a4-sheets | 3/3 |  |
| E28-inch-quote-letter | 3/3 |  |
| E29-replycheck-wrong-total | 3/3 |  |
| E30-real-chat-message | 3/3 |  |
| X-req_5be5878bf35a | 3/3 |  |
| X-req_c09cb9339d0d | 3/3 |  |

## Failures (every failing run)

### E15-budget-incl-vat run 0

- Checks: {'decision': True, 'criteria': True, 'reply': True, 'delivery_wording': False, 'reply_check': True}
- Notes: reply says delivery is outside a total: '9 reams is ฿981.00 before VAT, plus ฿150.00 delivery, for ฿1,210.17 total including VAT.'
- Decision `no_exact_match`, items ['PL-CP-A4-70', 'PL-CP-A4-75', 'PL-CP-A4-80-NUSA'], total None, criteria {"item1": {"product_type": "paper", "size_code": "A4", "weight_gsm": 70, "quantity": {"value": 9, "unit": "reams"}, "budget_satang": 120000, "budget_includes_vat": true, "budget_assumption": "Budget treated as including 7% VAT (customer said so).", "keywords": ["siam office"], "brand": "siam office", "size_raw": "A4"}}
- Reply:

> Nothing fits your budget exactly. The Siam Office A4 70gsm you asked for is in stock, but 9 reams comes to ฿1,210.17 including delivery and VAT. That is ฿10.17 over your ฿1,200 budget. I read your budget as including 7% VAT, as you said.
> 
> Here are the closest options:
> 
> 1. Siam Office Copy Paper A4 70gsm (PL-CP-A4-70): ฿109.00 per ream, regular price. It's the exact product you asked for. 9 reams is ฿981.00 before VAT, plus ฿150.00 delivery, for ฿1,210.17 total including VAT.
> 2. Lotus Bright Everyday A4 75gsm (PL-CP-A4-75): ฿118.00 per ream, regular price. It's a different brand and 5 gsm heavier. The total is ฿1,296.84, which is ฿96.84 over budget.
> 3. Nusa Paper Copy A4 80gsm (PL-CP-A4-80-NUSA): ฿121.50 per ream, regular price. It's a different brand and 10 gsm heavier. The total is ฿1,330.55, which is ฿130.55 over budget.
> 
> The 9 reams are 4,500 sheets in total. Delivery is ฿150.00 because the subtotal is under ฿3,000.00. All prices exclude VAT, but the totals above include delivery and 7% VAT.
> 
> Prices are from our current catalog.
> 
> Would you like the Siam Office 70gsm at ฿1,210.17, or should I look at fewer reams to stay within ฿1,200?


Eval run `eval-20261104T005112` (tag in the request log); spend $0.95.
