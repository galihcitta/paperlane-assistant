# Evaluation results

Model `claude-sonnet-5-5`, effort `medium`, catalog snapshot `20261103T144315978835Z`, 10 requests x 3 runs = 30 conversations.

## Layers

| Layer | Result |
|---|---|
| (a) Ingest completeness | 72 SKUs in DB vs 72 counted independently in the crawled HTML (sets equal: True); 0 missing required fields; 59 pricing files, all attached: True |
| (b) Criteria extraction | 102/102 expected fields (100%); cases fully right: 18/18 (100%) |
| (c) Product selection | 27/27 (100%) |
| (d) Totals exact (tool quote and reply text) | 27/27 (100%) |
| (e) Decision type | 27/30 (90%) |
| Reply content checks | 12/12 (100%) |
| Delivery-area flag | 3/3 (100%) |
| Reply post-check passed first or second try | 30/30 (100%) |
| Reply check catches a planted wrong total (offline) | n/a |
| **Overall pass** | 27/30 |

Latency per conversation: median 5.1s, max 6.7s.

## Per request (stability over runs)

| Request | Passes | Notes (failed runs) |
|---|---|---|
| E01-brief-example | 3/3 |  |
| E05-below-free-delivery | 3/3 |  |
| E09-informal-size | 3/3 |  |
| E14-ambiguous-colour | 0/3 | decision matches (expected ['needs_clarification']) |
| E16-budget-default-excl-vat | 3/3 |  |
| E21-injection-bait | 3/3 |  |
| E23-outside-delivery-area | 3/3 |  |
| E25-suggest-not-apply | 3/3 |  |
| E27-coloured-a4-sheets | 3/3 |  |
| E28-inch-quote-letter | 3/3 |  |

## Failures (every failing run)

### E14-ambiguous-colour run 0

- Checks: {'decision': False, 'reply_check': True}
- Notes: decision matches (expected ['needs_clarification'])
- Decision `matches`, items ['PL-CL-A4-80-PBL', 'PL-CL-A4-80-PGR', 'PL-CL-A4-80-PPK'], total 1,203.75, criteria {"item1": {"product_type": "paper", "paper_kind": "coloured", "size_code": "A4", "quantity": {"value": 5, "unit": "reams"}, "size_raw": "A4"}}
- Reply:

> Yes, we have A4 coloured paper. 7 options match your 5 reams, and 5 reams is 5 packs of 500 sheets each. Here are the first 3:
> 
> PL-CL-A4-80-PBL, Rainbow Pastel A4 80gsm Pastel blue: 195.00 per ream (list price)
> PL-CL-A4-80-PGR, Rainbow Pastel A4 80gsm Pastel green: 195.00 per ream (list price)
> PL-CL-A4-80-PPK, Rainbow Pastel A4 80gsm Pastel pink: 195.00 per ream (list price)
> 
> All three are in stock.
> 
> Full breakdown for PL-CL-A4-80-PBL (5 reams):
> Unit price: 195.00 (list price)
> Subtotal: 975.00
> Delivery: 150.00 (free from a 3,000.00 subtotal)
> VAT 7%: 78.75
> Total: 1,203.75
> 
> The other 4 matches are PL-CL-A4-80-PYL, PL-CL-A4-80-RED, PL-CL-A4-80-BRT and PL-CL-A4-90-CRM.
> 
> PL-CL-A4-100-IVY (Heritage Ivory A4 100gsm) is out of stock until 2026-11-20, so it can't be ordered now.
> 
> Prices are from the catalog snapshot crawled on 2026-11-03.
> 
> Which finish do you prefer: smooth or uncoated?

### E14-ambiguous-colour run 1

- Checks: {'decision': False, 'reply_check': True}
- Notes: decision matches (expected ['needs_clarification'])
- Decision `matches`, items ['PL-CL-A4-80-PBL', 'PL-CL-A4-80-PGR', 'PL-CL-A4-80-PPK'], total 1,203.75, criteria {"item1": {"product_type": "paper", "paper_kind": "coloured", "size_code": "A4", "quantity": {"value": 5, "unit": "reams"}, "size_raw": "A4"}}
- Reply:

> Yes, we have A4 coloured paper. 7 options qualify, and these are the first 3. Each is a 500-sheet ream, and 5 reams is 5 packs.
> 
> 1. PL-CL-A4-80-PBL, Rainbow Pastel A4 80gsm Pastel blue: 195.00 per ream
> 2. PL-CL-A4-80-PGR, Rainbow Pastel A4 80gsm Pastel green: 195.00 per ream
> 3. PL-CL-A4-80-PPK, Rainbow Pastel A4 80gsm Pastel pink: 195.00 per ream
> 
> All three are 80gsm, uncoated and in stock.
> 
> Full quote for PL-CL-A4-80-PBL, 5 reams:
> - Unit price: 195.00 (list price)
> - Subtotal: 975.00
> - Delivery: 150.00
> - VAT 7%: 78.75
> - Total: 1,203.75
> 
> Delivery is free once the subtotal reaches 3,000.00.
> 
> Four more options are available: yellow, red, bright, and a 90gsm cream.
> 
> One more is out of stock: PL-CL-A4-100-IVY, Heritage Ivory A4 100gsm. It's expected back on 2026-11-20 and can't be ordered now.
> 
> Prices are from the catalog snapshot crawled on 2026-11-03.
> 
> Which finish do you prefer: smooth or uncoated?

### E14-ambiguous-colour run 2

- Checks: {'decision': False, 'reply_check': True}
- Notes: decision matches (expected ['needs_clarification'])
- Decision `matches`, items ['PL-CL-A4-80-PBL', 'PL-CL-A4-80-PGR', 'PL-CL-A4-80-PPK'], total 1,203.75, criteria {"item1": {"product_type": "paper", "paper_kind": "coloured", "size_code": "A4", "quantity": {"value": 5, "unit": "reams"}, "size_raw": "A4"}}
- Reply:

> Yes, we have A4 coloured paper. 7 options match, all in stock. Here are the first 3 at 5 reams (1 ream = 1 pack of 500 sheets, so 5 packs and no rounding):
> 
> 1. PL-CL-A4-80-PBL, Rainbow Pastel A4 80gsm Pastel blue: 195.00 per ream
> 2. PL-CL-A4-80-PGR, Rainbow Pastel A4 80gsm Pastel green: 195.00 per ream
> 3. PL-CL-A4-80-PPK, Rainbow Pastel A4 80gsm Pastel pink: 195.00 per ream
> 
> Quote for PL-CL-A4-80-PBL (5 reams):
> - Unit price: 195.00 per ream (list price)
> - Subtotal: 975.00
> - Delivery: 150.00
> - VAT 7%: 78.75
> - Total: 1,203.75
> 
> Delivery is free once the subtotal reaches 3,000.00.
> 
> Four more options are available: yellow, red, bright and cream (90gsm). Heritage Ivory A4 100gsm (PL-CL-A4-100-IVY) is out of stock until 2026-11-20, so it can't be ordered now.
> 
> Which finish do you prefer: smooth or uncoated?

