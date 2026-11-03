# Evaluation results

Model `claude-sonnet-5-5`, effort `medium`, catalog snapshot `20261103T144315978835Z`, 1 requests x 1 runs = 1 conversations.

## Layers

| Layer | Result |
|---|---|
| (a) Ingest completeness | 72 SKUs in DB vs 72 counted independently in the crawled HTML (sets equal: True); 0 missing required fields; 59 pricing files, all attached: True |
| (b) Criteria extraction | 0/0 expected fields (0%); cases fully right: n/a |
| (c) Product selection | n/a |
| (d) Totals exact (tool quote and reply text) | n/a |
| (e) Decision type | 0/1 (0%) |
| Reply content checks | n/a |
| Delivery-area flag | n/a |
| Reply post-check passed first or second try | 1/1 (100%) |
| Reply check catches a planted wrong total (offline) | n/a |
| **Overall pass** | 0/1 |

Latency per conversation: median 6.4s, max 6.4s.

## Per request (stability over runs)

| Request | Passes | Notes (failed runs) |
|---|---|---|
| X-req_5be5878bf35a | 0/1 | decision matches (expected ['no_exact_match']) |

## Failures (every failing run)

### X-req_5be5878bf35a run 0

- Checks: {'decision': False, 'reply_check': True}
- Notes: decision matches (expected ['no_exact_match'])
- Decision `matches`, items ['PL-CP-A4-70', 'PL-CP-A4-75', 'PL-CP-A4-80-NUSA'], total 393.76, criteria {"item1": {"product_type": "paper", "size_code": "A4", "quantity": {"value": 2, "unit": "packs"}, "keywords": ["heritage ivory"], "size_raw": "A4"}}
- Reply:

> Heritage Ivory A4 100gsm (PL-CL-A4-100-IVY) is out of stock right now, so I can't take an order for it. It's expected back on 20 Nov 2026.
> 
> None of the other A4 papers is Heritage Ivory. These in-stock A4 papers are the closest, but they're white, not ivory, and lighter than 100 gsm:
> 
> - Siam Office Copy Paper A4 70gsm (PL-CP-A4-70): ฿109.00 per ream, regular price. White, uncoated, 500 sheets.
> - Lotus Bright Everyday A4 75gsm (PL-CP-A4-75): ฿118.00 per ream, regular price. White, uncoated.
> - Nusa Paper Copy A4 80gsm (PL-CP-A4-80-NUSA): ฿121.50 per ream, regular price. White, uncoated.
> 
> If you want a cream shade, I can look at the coloured A4 papers, such as the 90 gsm cream. I haven't checked its price or availability yet.
> 
> For comparison, 2 packs of the first option (PL-CP-A4-70):
> - Unit price: ฿109.00 x 2 packs
> - Subtotal: ฿218.00
> - Delivery: ฿150.00 (free from a ฿3,000.00 subtotal)
> - VAT 7%: ฿25.76
> - Total: ฿393.76
> 
> Prices exclude VAT, and the total includes it. Prices are from our catalog of 3 Nov 2026.
> 
> Would you like to wait for the Heritage Ivory, or should I look at a cream alternative?


Eval run `eval-20261103T172124` (tag in the request log); spend $0.01.
