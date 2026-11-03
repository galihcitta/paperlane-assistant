# Evaluation results

**Headline: all 31 requests x 3 runs on commit `24dd4cc`: 93/93 pass.** Model `claude-sonnet-5-5` (effort
medium), catalog snapshot `20261103T144315978835Z` (v1), eval run `eval-20261103T172336`. The 31st request is
the E11 failure exported from the request log (below). Every price, total and product selection is exact. The
previous full run, on `6df6960`, scored 86/90 (`eval/results_6df6960.md`); `8dd5eaa` scored 90/90
(`eval/results_8dd5eaa.md`).

| Per request (turn), from the request log | `24dd4cc` (now) | `6df6960` (before) |
|---|---|---|
| Overall pass | 93/93 | 86/90 |
| Mean cost | $0.0098 (p95 $0.0143) | $0.0100 (p95 $0.0185) |
| Latency | median 5.5s, p95 7.9s, max 8.7s | median 5.4s, p95 7.6s, max 10.0s |
| Rewrites after a failed reply check | 0 | 0 |
| Template replies / API errors | 0 / 0 | 0 / 0 |
| Replies containing Markdown (`**`, `#`, `|`) | 0 | 0 |
| Cost of the run | $0.91 | $0.90 |

`/ops?traffic=eval` agrees with this file: 90 model conversations in both, reply-check pass rate 100.0% in both,
spend $0.9117 in both.

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

## Full report for `24dd4cc`

Model `claude-sonnet-5-5`, effort `medium`, catalog snapshot `20261103T144315978835Z`, 31 requests x 3 runs = 93 conversations.

## Layers

| Layer | Result |
|---|---|
| (a) Ingest completeness | 72 SKUs in DB vs 72 counted independently in the crawled HTML (sets equal: True); 0 missing required fields; 59 pricing files, all attached: True |
| (b) Criteria extraction | 318/318 expected fields (100%); cases fully right: 63/63 (100%) |
| (c) Product selection | 72/72 (100%) |
| (d) Totals exact (tool quote and reply text) | 66/66 (100%) |
| (e) Decision type | 90/90 (100%) |
| Reply content checks | 30/30 (100%) |
| Delivery-area flag | 6/6 (100%) |
| Reply post-check passed first or second try | 90/90 (100%) |
| Reply check catches a planted wrong total (offline) | 3/3 (100%) |
| **Overall pass** | 93/93 |

Latency per conversation: median 5.5s, max 8.7s.

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
| X-req_5be5878bf35a | 3/3 |  |

## Failures (every failing run)

None.

Eval run `eval-20261103T172336` (tag in the request log); spend $0.91.
