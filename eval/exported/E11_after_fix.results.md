# Evaluation results

Model `claude-sonnet-5-5`, effort `medium`, catalog snapshot `20261103T144315978835Z`, 1 requests x 1 runs = 1 conversations.

## Layers

| Layer | Result |
|---|---|
| (a) Ingest completeness | 72 SKUs in DB vs 72 counted independently in the crawled HTML (sets equal: True); 0 missing required fields; 59 pricing files, all attached: True |
| (b) Criteria extraction | 0/0 expected fields (0%); cases fully right: n/a |
| (c) Product selection | n/a |
| (d) Totals exact (tool quote and reply text) | n/a |
| (e) Decision type | 1/1 (100%) |
| Reply content checks | n/a |
| Delivery-area flag | n/a |
| Reply post-check passed first or second try | 1/1 (100%) |
| Reply check catches a planted wrong total (offline) | n/a |
| **Overall pass** | 1/1 |

Latency per conversation: median 6.6s, max 6.6s.

## Per request (stability over runs)

| Request | Passes | Notes (failed runs) |
|---|---|---|
| X-req_5be5878bf35a | 1/1 |  |

## Failures (every failing run)

None.

Eval run `eval-20261103T172304` (tag in the request log); spend $0.01.
