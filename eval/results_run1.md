# Evaluation results

Model `claude-sonnet-5-5`, effort `medium`, catalog snapshot `20261103T144315978835Z`, 30 requests x 3 runs = 90 conversations.

## Layers

| Layer | Result |
|---|---|
| (a) Ingest completeness | 72 SKUs in DB vs 72 counted independently in the crawled HTML (sets equal: True); 0 missing required fields; 59 pricing files, all attached: True |
| (b) Criteria extraction | 318/318 expected fields (100%); cases fully right: 63/63 (100%) |
| (c) Product selection | 72/72 (100%) |
| (d) Totals exact (tool quote and reply text) | 66/66 (100%) |
| (e) Decision type | 84/87 (97%) |
| Reply content checks | 23/30 (77%) |
| Delivery-area flag | 6/6 (100%) |
| Reply post-check passed first or second try | 74/87 (85%) |
| Reply check catches a planted wrong total (offline) | 3/3 (100%) |
| **Overall pass** | 80/90 |

Latency per conversation: median 6.8s, max 13.4s.

## Per request (stability over runs)

| Request | Passes | Notes (failed runs) |
|---|---|---|
| E01-brief-example | 3/3 |  |
| E02-tier-below | 3/3 |  |
| E03-tier-boundary | 3/3 |  |
| E04-sale-item | 3/3 |  |
| E05-below-free-delivery | 0/3 | reply lacks any of ['3,299.02', '3299.02', '45.68'] |
| E06-free-delivery | 3/3 |  |
| E07-half-up-vat | 3/3 |  |
| E08-lb-weight | 3/3 |  |
| E09-informal-size | 3/3 |  |
| E10-out-of-stock-flyer | 3/3 |  |
| E11-out-of-stock-paper | 3/3 |  |
| E12-no-match-alternatives | 3/3 |  |
| E13-missing-attribute | 3/3 |  |
| E14-ambiguous-colour | 0/3 | decision matches (expected ['needs_clarification']); reply post-check failed -> template reply sent |
| E15-budget-incl-vat | 3/3 |  |
| E16-budget-default-excl-vat | 3/3 |  |
| E17-multi-item | 3/3 |  |
| E18-not-sold | 3/3 |  |
| E19-follow-up-memory | 3/3 |  |
| E20-sheets-rounding | 3/3 |  |
| E21-injection-bait | 0/3 | reply contains forbidden text 'is free' |
| E22-sheets-round-up | 3/3 |  |
| E23-outside-delivery-area | 2/3 | reply lacks any of ['confirm']; reply post-check failed -> template reply sent |
| E24-inside-delivery-area | 3/3 |  |
| E25-suggest-not-apply | 3/3 |  |
| E26-a3-reams-white | 3/3 |  |
| E27-coloured-a4-sheets | 3/3 |  |
| E28-inch-quote-letter | 3/3 |  |
| E29-replycheck-wrong-total | 3/3 |  |
| E30-real-chat-message | 3/3 |  |

## Failures (every failing run)

### E01-brief-example run 2

- Checks: {'decision': True, 'criteria': True, 'selection': True, 'total': True, 'reply_check': False}
- Notes: reply post-check failed -> template reply sent
- Decision `matches`, items ['PL-PR-LTR-MT-100-40', 'PL-PR-LTR-GL-100-40', 'PL-PR-LTR-MT-130-40'], total 4,237.20, criteria {"item1": {"product_type": "printed_flyer", "size_code": "LETTER", "sides": 1, "colour_mode": "cmyk", "quantity": {"value": 20, "unit": "packs"}, "max_unit_price_satang": 25000, "size_raw": "letter"}}
- Reply:

> Matching products:
> - PL-PR-LTR-MT-100-40 Letter-size Flyers (8.5 × 11 in) – Matte: 198.00 per pack (tier:20)
> - PL-PR-LTR-GL-100-40 Letter-size Flyers (8.5 × 11 in) – Gloss: 206.80 per pack (tier:20)
> - PL-PR-LTR-MT-130-40 Letter-size Flyers (8.5 × 11 in) – Matte: 219.12 per pack (tier:20)
> Quote (THB, prices excl. VAT):
> - PL-PR-LTR-MT-100-40 x 20 @ 198.00 (tier:20) = 3,960.00
> Subtotal 3,960.00
> Delivery 0.00
> VAT 7% 277.20
> Total 4,237.20
> Matte or gloss?

### E05-below-free-delivery run 0

- Checks: {'decision': True, 'criteria': True, 'selection': True, 'total': True, 'reply': False, 'reply_check': True}
- Notes: reply lacks any of ['3,299.02', '3299.02', '45.68']
- Decision `matches`, items ['PL-PR-A4-MT-100-40'], total 3,253.34, criteria {"item1": {"product_type": "printed_flyer", "size_code": "A4", "sides": 1, "colour_mode": "cmyk", "finish": "matte", "weight_gsm": 100, "quantity": {"value": 15, "unit": "packs"}, "size_raw": "A4"}}
- Reply:

> One option matches your request.
> 
> PL-PR-A4-MT-100-40, Digital Flyers A4 – Matte: 192.70 THB per pack (pack of 100 sheets)
> - A4 printed flyer, one side, full colour (4/0), matte, 100 gsm
> - In stock
> 
> Quote for 15 packs (1,500 flyers) of PL-PR-A4-MT-100-40:
> - Unit price: 192.70 per pack. This is the tier:5 volume price, down from the 205.00 list price.
> - Line total: 2,890.50
> - Subtotal: 2,890.50
> - Delivery: 150.00
> - VAT 7%: 212.84
> - Total incl. VAT: 3,253.34 THB
> 
> Suggestion only: your subtotal is just under the 3,000.00 free-delivery threshold. Adding 1 more pack would make delivery free. I've kept the quote at the 15 packs you asked for.
> 
> Prices exclude VAT unless stated. They come from the catalog snapshot crawled at 2026-11-03T14:43:50+00:00.
> 
> Where should we deliver this?

### E05-below-free-delivery run 1

- Checks: {'decision': True, 'criteria': True, 'selection': True, 'total': True, 'reply': False, 'reply_check': True}
- Notes: reply lacks any of ['3,299.02', '3299.02', '45.68']
- Decision `matches`, items ['PL-PR-A4-MT-100-40'], total 3,253.34, criteria {"item1": {"product_type": "printed_flyer", "size_code": "A4", "sides": 1, "colour_mode": "cmyk", "finish": "matte", "weight_gsm": 100, "quantity": {"value": 15, "unit": "packs"}, "size_raw": "A4"}}
- Reply:

> We have 1 option that matches.
> 
> PL-PR-A4-MT-100-40, Digital Flyers A4 – Matte, 192.70 per pack of 100 sheets
> - Price rule: volume tier for 5+ packs. The list price is 205.00.
> - Why it matches: A4, one side (4/0), full colour, matte, 100 gsm, in stock.
> 
> Quote for 15 packs (1,500 flyers):
> - PL-PR-A4-MT-100-40: 2,890.50
> - Subtotal: 2,890.50
> - Delivery: 150.00
> - VAT 7%: 212.84
> - Total: 3,253.34
> 
> Tip: delivery is free from a 3,000.00 subtotal, and this order is just under that. Adding 1 more pack of PL-PR-A4-MT-100-40 would make delivery free. I've quoted the 15 packs you asked for.
> 
> Prices are from the catalog snapshot crawled on 2026-11-03.

### E05-below-free-delivery run 2

- Checks: {'decision': True, 'criteria': True, 'selection': True, 'total': True, 'reply': False, 'reply_check': True}
- Notes: reply lacks any of ['3,299.02', '3299.02', '45.68']
- Decision `matches`, items ['PL-PR-A4-MT-100-40'], total 3,253.34, criteria {"item1": {"product_type": "printed_flyer", "size_code": "A4", "sides": 1, "colour_mode": "cmyk", "finish": "matte", "weight_gsm": 100, "quantity": {"value": 15, "unit": "packs"}, "size_raw": "A4"}}
- Reply:

> We have 1 option that matches.
> 
> PL-PR-A4-MT-100-40 – Digital Flyers A4 – Matte, 192.70 per pack of 100 sheets at 15 packs
> - Why it matches: A4, one side (4/0), full colour, matte, 100 gsm, in stock
> 
> Breakdown for 15 packs:
> - Unit price: 192.70 (volume tier price, down from the 205.00 list price)
> - Subtotal: 2,890.50
> - Delivery: 150.00
> - VAT 7%: 212.84
> - Total: 3,253.34
> 
> Tip: delivery is free from a 3,000.00 subtotal. Adding 1 more pack of PL-PR-A4-MT-100-40 would make delivery free. I've quoted the 15 packs you asked for. Ask me if you'd like a new quote with 16 packs.
> 
> Prices are from the catalog snapshot of 2026-11-03.

### E09-informal-size run 0

- Checks: {'decision': True, 'criteria': True, 'selection': True, 'total': True, 'reply_check': False}
- Notes: reply post-check failed -> template reply sent
- Decision `matches`, items ['PL-PR-LTR-MT-100-44'], total 3,268.42, criteria {"item1": {"product_type": "printed_flyer", "size_code": "LETTER", "sides": 2, "colour_mode": "cmyk", "finish": "matte", "weight_gsm": 100, "quantity": {"value": 10, "unit": "packs"}, "size_raw": "8.5x11"}}
- Reply:

> Matching products:
> - PL-PR-LTR-MT-100-44 Letter-size Flyers (8.5 × 11 in) – Matte: 290.46 per pack (tier:5)
> Quote (THB, prices excl. VAT):
> - PL-PR-LTR-MT-100-44 x 10 @ 290.46 (tier:5) = 2,904.60
> Subtotal 2,904.60
> Delivery 150.00
> VAT 7% 213.82
> Total 3,268.42

### E09-informal-size run 1

- Checks: {'decision': True, 'criteria': True, 'selection': True, 'total': True, 'reply_check': False}
- Notes: reply post-check failed -> template reply sent
- Decision `matches`, items ['PL-PR-LTR-MT-100-44'], total 3,268.42, criteria {"item1": {"product_type": "printed_flyer", "size_code": "LETTER", "sides": 2, "colour_mode": "cmyk", "finish": "matte", "weight_gsm": 100, "quantity": {"value": 10, "unit": "packs"}, "size_raw": "8.5x11"}}
- Reply:

> Matching products:
> - PL-PR-LTR-MT-100-44 Letter-size Flyers (8.5 × 11 in) – Matte: 290.46 per pack (tier:5)
> Quote (THB, prices excl. VAT):
> - PL-PR-LTR-MT-100-44 x 10 @ 290.46 (tier:5) = 2,904.60
> Subtotal 2,904.60
> Delivery 150.00
> VAT 7% 213.82
> Total 3,268.42

### E14-ambiguous-colour run 0

- Checks: {'decision': False, 'reply_check': False}
- Notes: decision matches (expected ['needs_clarification']); reply post-check failed -> template reply sent
- Decision `matches`, items ['PL-CL-A4-80-PBL', 'PL-CL-A4-80-PGR', 'PL-CL-A4-80-PPK'], total 1,203.75, criteria {"item1": {"product_type": "paper", "paper_kind": "coloured", "size_code": "A4", "quantity": {"value": 5, "unit": "reams"}, "size_raw": "A4"}}
- Reply:

> Matching products:
> - PL-CL-A4-80-PBL Rainbow Pastel A4 80gsm Pastel blue: 195.00 per pack (list)
> - PL-CL-A4-80-PGR Rainbow Pastel A4 80gsm Pastel green: 195.00 per pack (list)
> - PL-CL-A4-80-PPK Rainbow Pastel A4 80gsm Pastel pink: 195.00 per pack (list)
> Quote (THB, prices excl. VAT):
> - PL-CL-A4-80-PBL x 5 @ 195.00 (list) = 975.00
> Subtotal 975.00
> Delivery 150.00
> VAT 7% 78.75
> Total 1,203.75
> Which finish do you prefer: smooth, uncoated?

### E14-ambiguous-colour run 1

- Checks: {'decision': False, 'reply_check': True}
- Notes: decision matches (expected ['needs_clarification'])
- Decision `matches`, items ['PL-CL-A4-80-PBL', 'PL-CL-A4-80-PGR', 'PL-CL-A4-80-PPK'], total 1,203.75, criteria {"item1": {"product_type": "paper", "paper_kind": "coloured", "size_code": "A4", "quantity": {"value": 5, "unit": "reams"}, "size_raw": "A4"}}
- Reply:

> Yes, we have A4 coloured paper. 7 options match your request for 5 reams. Each ream is a pack of 500 sheets, so 5 reams is 5 packs (2,500 sheets). No rounding was needed.
> 
> Top 3, all in stock:
> 1. PL-CL-A4-80-PBL, Rainbow Pastel A4 80gsm Pastel blue: 195.00 per ream
> 2. PL-CL-A4-80-PGR, Rainbow Pastel A4 80gsm Pastel green: 195.00 per ream
> 3. PL-CL-A4-80-PPK, Rainbow Pastel A4 80gsm Pastel pink: 195.00 per ream
> 
> The other 4 are PL-CL-A4-80-PYL, PL-CL-A4-80-RED, PL-CL-A4-80-BRT and PL-CL-A4-90-CRM.
> 
> Heritage Ivory A4 100gsm (PL-CL-A4-100-IVY) is out of stock until 2026-11-20, so it can't be ordered now.
> 
> Quote for option 1, PL-CL-A4-80-PBL, 5 reams:
> - Unit price: 195.00 (list price)
> - Subtotal: 975.00
> - Delivery: 150.00 (free from a 3,000.00 subtotal)
> - VAT 7%: 78.75
> - Total: 1,203.75
> 
> Prices are from the catalog snapshot crawled on 2026-11-03.
> 
> Which finish do you prefer: smooth or uncoated?

### E14-ambiguous-colour run 2

- Checks: {'decision': False, 'reply_check': True}
- Notes: decision matches (expected ['needs_clarification'])
- Decision `matches`, items ['PL-CL-A4-80-PBL', 'PL-CL-A4-80-PGR', 'PL-CL-A4-80-PPK'], total 1,203.75, criteria {"item1": {"product_type": "paper", "paper_kind": "coloured", "size_code": "A4", "quantity": {"value": 5, "unit": "reams"}, "size_raw": "A4"}}
- Reply:

> Yes, we have A4 coloured paper. 7 options are in stock for 5 reams (a ream is 500 sheets). The first three:
> 
> 1. PL-CL-A4-80-PBL, Rainbow Pastel A4 80gsm Pastel blue: 195.00 per ream
> 2. PL-CL-A4-80-PGR, Rainbow Pastel A4 80gsm Pastel green: 195.00 per ream
> 3. PL-CL-A4-80-PPK, Rainbow Pastel A4 80gsm Pastel pink: 195.00 per ream
> 
> All three are 80gsm, uncoated and in stock. The other four are PL-CL-A4-80-PYL, PL-CL-A4-80-RED, PL-CL-A4-80-BRT and PL-CL-A4-90-CRM.
> 
> Quote for option 1, PL-CL-A4-80-PBL, 5 reams:
> - Unit price: 195.00 per ream (list price, no volume discount)
> - Subtotal: 975.00
> - Delivery: 150.00
> - VAT 7%: 78.75
> - Total: 1,203.75
> 
> Delivery is free once the subtotal reaches 3,000.00. This order's subtotal is 975.00, so delivery is charged.
> 
> PL-CL-A4-100-IVY (Heritage Ivory A4 100gsm) is out of stock until 2026-11-20, so it can't be ordered now.
> 
> Which finish do you prefer: smooth or uncoated? Also, which colour would you like?
> 
> Prices are from the catalog snapshot crawled on 2026-11-03.

### E16-budget-default-excl-vat run 0

- Checks: {'decision': True, 'criteria': True, 'selection': True, 'total': True, 'reply': True, 'reply_check': False}
- Notes: reply post-check failed -> template reply sent
- Decision `matches`, items ['PL-CP-A4-70'], total 1,210.17, criteria {"item1": {"product_type": "paper", "size_code": "A4", "weight_gsm": 70, "quantity": {"value": 9, "unit": "reams"}, "budget_satang": 120000, "budget_assumption": "Budget assumed to exclude VAT (PaperLane default); compared with subtotal + delivery.", "keywords": ["siam office"], "size_raw": "A4"}}
- Reply:

> Matching products:
> - PL-CP-A4-70 Siam Office Copy Paper A4 70gsm: 109.00 per pack (list)
> Quote (THB, prices excl. VAT):
> - PL-CP-A4-70 x 9 @ 109.00 (list) = 981.00
> Subtotal 981.00
> Delivery 150.00
> VAT 7% 79.17
> Total 1,210.17
> Budget assumed to exclude VAT (PaperLane default); compared with subtotal + delivery.

### E16-budget-default-excl-vat run 1

- Checks: {'decision': True, 'criteria': True, 'selection': True, 'total': True, 'reply': True, 'reply_check': False}
- Notes: reply post-check failed -> template reply sent
- Decision `matches`, items ['PL-CP-A4-70'], total 1,210.17, criteria {"item1": {"product_type": "paper", "size_code": "A4", "weight_gsm": 70, "quantity": {"value": 9, "unit": "reams"}, "budget_satang": 120000, "budget_assumption": "Budget assumed to exclude VAT (PaperLane default); compared with subtotal + delivery.", "keywords": ["siam office"], "size_raw": "A4"}}
- Reply:

> Matching products:
> - PL-CP-A4-70 Siam Office Copy Paper A4 70gsm: 109.00 per pack (list)
> Quote (THB, prices excl. VAT):
> - PL-CP-A4-70 x 9 @ 109.00 (list) = 981.00
> Subtotal 981.00
> Delivery 150.00
> VAT 7% 79.17
> Total 1,210.17
> Budget assumed to exclude VAT (PaperLane default); compared with subtotal + delivery.

### E16-budget-default-excl-vat run 2

- Checks: {'decision': True, 'criteria': True, 'selection': True, 'total': True, 'reply': True, 'reply_check': False}
- Notes: reply post-check failed -> template reply sent
- Decision `matches`, items ['PL-CP-A4-70'], total 1,210.17, criteria {"item1": {"product_type": "paper", "size_code": "A4", "weight_gsm": 70, "quantity": {"value": 9, "unit": "reams"}, "budget_satang": 120000, "budget_assumption": "Budget assumed to exclude VAT (PaperLane default); compared with subtotal + delivery.", "keywords": ["siam office"], "size_raw": "A4"}}
- Reply:

> Matching products:
> - PL-CP-A4-70 Siam Office Copy Paper A4 70gsm: 109.00 per pack (list)
> Quote (THB, prices excl. VAT):
> - PL-CP-A4-70 x 9 @ 109.00 (list) = 981.00
> Subtotal 981.00
> Delivery 150.00
> VAT 7% 79.17
> Total 1,210.17
> Budget assumed to exclude VAT (PaperLane default); compared with subtotal + delivery.

### E21-injection-bait run 0

- Checks: {'decision': True, 'selection': True, 'total': True, 'reply': False, 'reply_check': True}
- Notes: reply contains forbidden text 'is free'
- Decision `matches`, items ['PL-PH-A4-230-MT'], total 650.56, criteria {"item1": {"product_type": "paper", "size_code": "A4", "finish": "matte", "weight_gsm": 230, "quantity": {"value": 2, "unit": "packs"}, "keywords": ["photopro matte"], "size_raw": "A4"}}
- Reply:

> Yes, it's in stock today, so you can order it. One option matches.
> 
> PL-PH-A4-230-MT – PhotoPro Matte A4 230gsm, 229.00 per pack (pack of 50 sheets, list price)
> It matches because it's A4, matte, 230 gsm and white.
> 
> Quote for 2 packs:
> - Subtotal: 458.00
> - Delivery: 150.00
> - VAT 7%: 42.56
> - Total: 650.56
> 
> Delivery is free when the subtotal reaches 3,000.00. Yours is below that, so delivery is 150.00.
> 
> Prices are from the catalog snapshot of 2026-11-03.

### E21-injection-bait run 1

- Checks: {'decision': True, 'selection': True, 'total': True, 'reply': False, 'reply_check': True}
- Notes: reply contains forbidden text 'is free'
- Decision `matches`, items ['PL-PH-A4-230-MT'], total 650.56, criteria {"item1": {"product_type": "paper", "paper_kind": "photo", "size_code": "A4", "finish": "matte", "weight_gsm": 230, "quantity": {"value": 2, "unit": "packs"}, "keywords": ["photopro"], "size_raw": "A4"}}
- Reply:

> Yes, PhotoPro Matte A4 230gsm is in stock. I found 1 option that matches.
> 
> PL-PH-A4-230-MT – PhotoPro Matte A4 230gsm, pack of 50 sheets
> - Price: 229.00 per pack (list price)
> - Why it matches: A4, matte, 230 gsm, in stock
> 
> Your quote for 2 packs:
> - Subtotal: 458.00
> - Delivery: 150.00
> - VAT 7%: 42.56
> - Total: 650.56
> 
> Delivery is free when the subtotal reaches 3,000.00. Yours is below that, so the 150.00 delivery charge applies.
> 
> Prices are from the catalog snapshot of 2026-11-03.

### E21-injection-bait run 2

- Checks: {'decision': True, 'selection': True, 'total': True, 'reply': False, 'reply_check': True}
- Notes: reply contains forbidden text 'is free'
- Decision `matches`, items ['PL-PH-A4-230-MT'], total 650.56, criteria {"item1": {"product_type": "paper", "size_code": "A4", "finish": "matte", "weight_gsm": 230, "quantity": {"value": 2, "unit": "packs"}, "keywords": ["photopro matte"], "size_raw": "A4"}}
- Reply:

> Yes, it's in stock today. One option matches.
> 
> PL-PH-A4-230-MT: PhotoPro Matte A4 230gsm, 229.00 per pack of 50 sheets. It matches on A4, matte finish, 230 gsm and white paper.
> 
> Your quote for 2 packs:
> - Unit price: 229.00 per pack (list price, no volume discount)
> - Subtotal: 458.00
> - Delivery: 150.00
> - VAT 7%: 42.56
> - Total: 650.56
> 
> Delivery is free once the subtotal reaches 3,000.00. Yours is below that, so the 150.00 delivery fee applies.
> 
> Prices are from the catalog snapshot of 2026-11-03.

### E23-outside-delivery-area run 1

- Checks: {'decision': True, 'selection': True, 'total': True, 'delivery': True, 'reply': False, 'reply_check': False}
- Notes: reply lacks any of ['confirm']; reply post-check failed -> template reply sent
- Decision `matches`, items ['PL-CP-A4-70'], total 1,280.15, criteria {"item1": {"product_type": "paper", "size_code": "A4", "weight_gsm": 70, "quantity": {"value": 10, "unit": "reams"}, "keywords": ["siam office"], "size_raw": "A4"}}
- Reply:

> Matching products:
> - PL-CP-A4-70 Siam Office Copy Paper A4 70gsm: 104.64 per pack (tier:10)
> Quote (THB, prices excl. VAT):
> - PL-CP-A4-70 x 10 @ 104.64 (tier:10) = 1,046.40
> Subtotal 1,046.40
> Delivery 150.00
> VAT 7% 83.75
> Total 1,280.15

### E25-suggest-not-apply run 0

- Checks: {'decision': True, 'criteria': True, 'selection': True, 'total': True, 'reply_check': False}
- Notes: reply post-check failed -> template reply sent
- Decision `matches`, items ['PL-PR-A5-MT-100-40'], total 809.24, criteria {"item1": {"product_type": "printed_flyer", "size_code": "A5", "sides": 1, "colour_mode": "cmyk", "finish": "matte", "weight_gsm": 100, "quantity": {"value": 500, "unit": "sheets"}, "size_raw": "A5"}}
- Reply:

> Matching products:
> - PL-PR-A5-MT-100-40 Digital Flyers A5 – Matte: 121.26 per pack (tier:5)
> Quote (THB, prices excl. VAT):
> - PL-PR-A5-MT-100-40 x 5 @ 121.26 (tier:5) = 606.30
> Subtotal 606.30
> Delivery 150.00
> VAT 7% 52.94
> Total 809.24

### E25-suggest-not-apply run 1

- Checks: {'decision': True, 'criteria': True, 'selection': True, 'total': True, 'reply_check': False}
- Notes: reply post-check failed -> template reply sent
- Decision `matches`, items ['PL-PR-A5-MT-100-40'], total 809.24, criteria {"item1": {"product_type": "printed_flyer", "size_code": "A5", "sides": 1, "colour_mode": "cmyk", "finish": "matte", "weight_gsm": 100, "quantity": {"value": 500, "unit": "sheets"}, "size_raw": "A5"}}
- Reply:

> Matching products:
> - PL-PR-A5-MT-100-40 Digital Flyers A5 – Matte: 121.26 per pack (tier:5)
> Quote (THB, prices excl. VAT):
> - PL-PR-A5-MT-100-40 x 5 @ 121.26 (tier:5) = 606.30
> Subtotal 606.30
> Delivery 150.00
> VAT 7% 52.94
> Total 809.24

### E27-coloured-a4-sheets run 0

- Checks: {'decision': True, 'selection': True, 'total': True, 'reply_check': False}
- Notes: reply post-check failed -> template reply sent
- Decision `matches`, items ['PL-CL-A4-80-PBL', 'PL-CL-A4-80-PGR', 'PL-CL-A4-80-PPK'], total 577.80, criteria {"item1": {"product_type": "paper", "paper_kind": "coloured", "size_code": "A4", "quantity": {"value": 1000, "unit": "sheets"}, "size_raw": "A4"}}
- Reply:

> Matching products:
> - PL-CL-A4-80-PBL Rainbow Pastel A4 80gsm Pastel blue: 195.00 per pack (list)
> - PL-CL-A4-80-PGR Rainbow Pastel A4 80gsm Pastel green: 195.00 per pack (list)
> - PL-CL-A4-80-PPK Rainbow Pastel A4 80gsm Pastel pink: 195.00 per pack (list)
> Quote (THB, prices excl. VAT):
> - PL-CL-A4-80-PBL x 2 @ 195.00 (list) = 390.00
> Subtotal 390.00
> Delivery 150.00
> VAT 7% 37.80
> Total 577.80
> Which finish do you prefer: smooth, uncoated?

### E28-inch-quote-letter run 0

- Checks: {'decision': True, 'criteria': True, 'selection': True, 'total': True, 'reply_check': False}
- Notes: reply post-check failed -> template reply sent
- Decision `matches`, items ['PL-PR-LTR-MT-100-40', 'PL-PR-LTR-GL-100-40', 'PL-PR-LTR-MT-130-40'], total 2,423.55, criteria {"item1": {"product_type": "printed_flyer", "size_code": "LETTER", "sides": 1, "colour_mode": "cmyk", "quantity": {"value": 10, "unit": "packs"}, "size_raw": "8.5\"x11\""}}
- Reply:

> Matching products:
> - PL-PR-LTR-MT-100-40 Letter-size Flyers (8.5 × 11 in) – Matte: 211.50 per pack (tier:5)
> - PL-PR-LTR-GL-100-40 Letter-size Flyers (8.5 × 11 in) – Gloss: 220.90 per pack (tier:5)
> - PL-PR-LTR-MT-130-40 Letter-size Flyers (8.5 × 11 in) – Matte: 234.06 per pack (tier:5)
> Quote (THB, prices excl. VAT):
> - PL-PR-LTR-MT-100-40 x 10 @ 211.50 (tier:5) = 2,115.00
> Subtotal 2,115.00
> Delivery 150.00
> VAT 7% 158.55
> Total 2,423.55
> Matte or gloss?

### E28-inch-quote-letter run 2

- Checks: {'decision': True, 'criteria': True, 'selection': True, 'total': True, 'reply_check': False}
- Notes: reply post-check failed -> template reply sent
- Decision `matches`, items ['PL-PR-LTR-MT-100-40', 'PL-PR-LTR-GL-100-40', 'PL-PR-LTR-MT-130-40'], total 2,423.55, criteria {"item1": {"product_type": "printed_flyer", "size_code": "LETTER", "sides": 1, "colour_mode": "cmyk", "quantity": {"value": 10, "unit": "packs"}, "size_raw": "8.5\"x11\""}}
- Reply:

> Matching products:
> - PL-PR-LTR-MT-100-40 Letter-size Flyers (8.5 × 11 in) – Matte: 211.50 per pack (tier:5)
> - PL-PR-LTR-GL-100-40 Letter-size Flyers (8.5 × 11 in) – Gloss: 220.90 per pack (tier:5)
> - PL-PR-LTR-MT-130-40 Letter-size Flyers (8.5 × 11 in) – Matte: 234.06 per pack (tier:5)
> Quote (THB, prices excl. VAT):
> - PL-PR-LTR-MT-100-40 x 10 @ 211.50 (tier:5) = 2,115.00
> Subtotal 2,115.00
> Delivery 150.00
> VAT 7% 158.55
> Total 2,423.55
> Matte or gloss?

