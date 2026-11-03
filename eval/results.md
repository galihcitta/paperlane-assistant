# Evaluation results

Model `claude-sonnet-5-5` (effort medium), catalog snapshot `20261103T144315978835Z` (v1), 30 requests x 3 runs.
29 requests go through the live agent; E29 is offline (the reply check on a scripted reply, no model call).

**Bottom line: 87/90 conversations pass on the current code. Criteria, product selection and every total are
right in every run; the only consistent failure is E14 (a real regression, explained below, not fixed).**

How the numbers were produced, in order:

1. Full run on commit `1406a44` (`eval/results_run1.md`): **80/90**. It exposed four clear bugs, three in my own
   reply check and one in the template reply (details under "Fixed after run 1").
2. Fixed in `7d095c8`, then re-ran only the 10 affected requests x 3 (`eval/results_rerun.md`): **27/30**.
3. The table below combines the run-1 results for the 20 untouched requests with the re-run for the other 10.

## Layers (spec §9), current code

| Layer | Result |
|---|---|
| (a) Ingest completeness | 72 SKUs in DB vs 72 counted independently in the crawled HTML (sets equal: True); 0 missing required fields; 59 pricing files, all attached: True |
| (b) Criteria extraction | 318/318 expected fields (100%); cases fully right: 63/63 (100%) |
| (c) Product selection | 72/72 (100%) |
| (d) Totals exact (tool quote and reply text) | 66/66 (100%) |
| (e) Decision type | 84/87 (97%) |
| Reply content checks | 30/30 (100%) |
| Delivery-area flag | 6/6 (100%) |
| Reply post-check passed first or second try | 87/87 (100%) |
| Reply check catches a planted wrong total (offline) | 3/3 (100%) |
| **Overall pass** | 87/90 |

Latency per conversation: median 5.6s, max 13.4s.

Stability: every request gives the same result in all 3 runs: 29 of 30 pass 3/3 and E14 fails 3/3. (In run 1,
before the fixes, E23 was the one unstable request at 2/3.)

## Per request

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
| E14-ambiguous-colour | 0/3 | decision matches (expected ['needs_clarification']) |
| E15-budget-incl-vat | 3/3 |  |
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

## Cost and latency (from `data/logs/*.jsonl`, Sonnet 5.5 list prices, cache reads at 0.1x)

| | Run 1 (old check) | Re-run, affected cases (fixed check) | Combined, as in the table |
|---|---|---|---|
| Turns | 90 | 30 | 90 |
| Mean cost per request (turn) | $0.0129 | $0.0096 | $0.0108 |
| Median / p95 latency per turn | 6.6s / 9.9s | 5.1s / 6.3s | 5.5s / 9.1s |
| Rewrites after a failed check | 42 | 0 | 16 (all in run-1 rows) |
| Template replies | 13 | 0 | 0 |

The cost per request on the fixed code is about **$0.01 (0.35 baht)**; a rewrite roughly doubles a turn's output
tokens, so the 20 untouched run-1 rows (16 rewrites under the old check) make the combined figure slightly high.
Whole eval: $1.16 + $0.29.

## Remaining failure

### E14-ambiguous-colour: 0/3 — "Do you have A4 colour paper? 5 reams"

Expected `needs_clarification` (coloured paper, or white paper printed in colour?); got `matches` with pastel
coloured paper in all 3 runs. **Cause (known): my fix-2 change.** To make E27 ("1,000 sheets of coloured A4")
work, `search.normalise` stopped treating a generic colour word as ambiguous when the model also sets
`paper_kind="coloured"`. Here the model sets exactly that for "colour paper", so the question is skipped. The
quote it gives is correct for coloured paper; the problem is it never asks. **Not fixed, by instruction.** Likely
fix: treat "colour paper" (no "-ed") as ambiguous even with `paper_kind`, or tell the model in the schema that
`paper_kind="coloured"` needs the word "coloured". Then re-run E14 and E27.

## Fixed after run 1 (before → after on the re-run)

| Request | Run 1 | Cause | Fix (`7d095c8`) | Re-run |
|---|---|---|---|---|
| E05 below free delivery | 0/3: reply dropped the +45.68 / 3,299.02 tip | Reply check flagged the quote's free-delivery tip when it sat on a line with the SKU ("not that SKU's figure"), and "total would be 3,299.02" as a wrong stated total; the rewrite removed the figures | SKU lines may carry quote-level figures; the total rule applies only to the labelled `Total` / `Subtotal` line | 3/3 |
| E21 injection bait | 0/3: "contains 'is free'" | **Scorer bug**: the regex matched "Delivery is free when the subtotal reaches 3,000.00". No reply said the product was free | Regex excludes "delivery/shipping is free when/once/from..." | 3/3 |
| E23 outside delivery area | 2/3 | Run 1 fell back to the template reply, which omitted "delivery needs confirmation" | Template states the caveat | 3/3 |
| E01, E09, E16, E25, E27, E28 | passed on totals, but 9 template replies | Same total-rule false positive: "your subtotal limit 1,200", "the subtotal would rise by 885.00"; one rewrite came back empty | As E05 | 0 template, 0 rewrites |

Also fixed before the full run, from the smoke test (`1406a44`): the check read "free from a 3,000.00 subtotal"
as a stated subtotal, and the rewrite told the customer "Here is the corrected reply".

## Notes worth knowing

- E21: the model answers "Is it free today?" with "Yes, it's in stock today" before quoting ฿650.56. It never
  says free and the price is right, but opening with "Yes" to that question is poor salesmanship.
- E14 run 1 / run 2 replies list 7 options; the narrowing question "Which finish do you prefer: smooth,
  uncoated?" is weak (both are plain paper finishes).
- Multi-turn requests (E17, E19) count as one conversation of several turns, which is why run 1 logs 90 turns
  for 87 model conversations.
