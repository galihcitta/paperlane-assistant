# Evaluation results

Model `claude-sonnet-5-5`, effort `medium`, catalog snapshot `20261103T144315978835Z`, 1 requests x 10 runs = 10 conversations.

## Layers

| Layer | Result |
|---|---|
| (a) Ingest completeness | 72 SKUs in DB vs 72 counted independently in the crawled HTML (sets equal: True); 0 missing required fields; 59 pricing files, all attached: True |
| (b) Criteria extraction | 0/0 expected fields (0%); cases fully right: n/a |
| (c) Product selection | n/a |
| (d) Totals exact (tool quote and reply text) | n/a |
| (e) Decision type | 10/10 (100%) |
| Reply content checks | n/a |
| Delivery-area flag | n/a |
| No false claim that a total leaves out delivery | 10/10 (100%) |
| Reply post-check passed first or second try | 10/10 (100%) |
| Reply check catches a planted wrong total (offline) | n/a |
| **Overall pass** | 10/10 |

Latency per conversation: median 6.5s, max 7.7s.

## Per request (stability over runs)

| Request | Passes | Notes (failed runs) |
|---|---|---|
| X-req_c09cb9339d0d | 10/10 |  |

## Failures (every failing run)

None.

Eval run `eval-20261104T004847` (tag in the request log); spend $0.13.
