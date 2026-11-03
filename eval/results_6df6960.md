# Evaluation results

**Headline: all 30 requests x 3 runs on commit `6df6960` (polished reply wording): 86/90 pass.** Model
`claude-sonnet-5-5` (effort medium), catalog snapshot `20261103T144315978835Z` (v1). Every price, total and
product selection is exact in all 90 conversations; the 4 misses are two new failures recorded below, not fixed.
The previous commit `8dd5eaa` scored 90/90 (`eval/results_8dd5eaa.md`).

| Per request (turn), from `data/logs/eval_polish.jsonl` | `6df6960` (now) | `8dd5eaa` (before polish) |
|---|---|---|
| Overall pass | 86/90 | 90/90 |
| Mean cost | $0.0100 (p95 $0.0185) | $0.0095 (p95 $0.0206) |
| Latency | median 5.4s, p95 7.6s, max 10.0s | median 5.0s, p95 8.2s, max 11.6s |
| Rewrites after a failed reply check | 0 | 2 |
| Template replies / API errors | 0 / 0 | 0 / 0 |
| Replies containing Markdown (`**`, `#`, `|`) | 0 | not measured |
| Cost of the run | $0.90 | $0.85 |

## New failures on `6df6960` (recorded, not fixed)

### E11-out-of-stock-paper: 0/3 (was 3/3) — "Can I get 2 packs of the Heritage Ivory A4 paper?"

Expected `no_exact_match`; got `matches` with three white copy papers. **Cause:** in all 3 runs the model filled
only `keywords: ["heritage ivory"]` and no longer `paper_colour: "ivory"` (on `8dd5eaa` it set the colour every
time). Keywords only rank, they don't filter, so any in-stock A4 paper "matches". The new reply-style prompt is
the only change, so it shifted how the model fills criteria (inferred). The reply itself still says Heritage
Ivory is out of stock until 20 Nov 2026 and that the others are white, but presents them as matches with a
quote. Likely fix (not done): when keywords name a product that is unavailable, treat its attributes as
required, or tell the model to put a colour named in a product name into `paper_colour`.

### E10-out-of-stock-flyer: 2/3 (was 3/3), run 2

**Cause: scorer gap, not a reply error.** The reply gives the right date as "12 Nov 2026" (the new style's date
format); the scorer accepts "12 November", "Nov 12", "November 12" or "2026-11-12" only.

## Before -> after: the brief's example (E01, run 0)

Before (`8dd5eaa`):

> 5 options match: letter flyers, one side, full colour, under 250 a pack at 20 packs. Each pack has 100 sheets. Here are the top 3:
> 
> 1. PL-PR-LTR-MT-100-40 – Letter Flyers, Matte, 100 gsm: 198.00 per pack (20-pack tier price, list 225.00)
> 2. PL-PR-LTR-GL-100-40 – Letter Flyers, Gloss, 100 gsm: 206.80 per pack (20-pack tier price)
> 3. PL-PR-LTR-MT-130-40 – Letter Flyers, Matte, 130 gsm: 219.12 per pack (20-pack tier price)
> 
> All three are in stock.
> 
> Breakdown for option 1, PL-PR-LTR-MT-100-40, 20 packs:
> - Unit price: 198.00 (tier:20 price rule)
> - Subtotal: 3,960.00
> - Delivery: 0.00 (free, because the subtotal is over 3,000)
> - VAT 7%: 277.20
> - Total: 4,237.20
> 
> Prices exclude VAT, and the budget of 250 per pack was treated as excluding VAT. They come from the catalog snapshot dated 2026-11-03.
> 
> Matte or gloss?

After (`6df6960`):

> We have 5 one-sided, full-colour Letter flyers under ฿250 a pack at 20 packs. Here are the top 3:
> 
> - Matte 100 gsm Letter Flyers (PL-PR-LTR-MT-100-40): ฿198.00 per pack, 20-pack price (normally ฿225.00). It's the cheapest option.
> - Gloss 100 gsm Letter Flyers (PL-PR-LTR-GL-100-40): ฿206.80 per pack, 20-pack price (normally ฿235.00).
> - Matte 130 gsm Letter Flyers (PL-PR-LTR-MT-130-40): ฿219.12 per pack, 20-pack price (normally ฿249.00). It's a thicker sheet.
> 
> My pick is the Matte 100 gsm Letter Flyers (PL-PR-LTR-MT-100-40). For 20 packs (100 sheets each):
> - Unit price x packs: ฿198.00 x 20
> - Subtotal: ฿3,960.00
> - Delivery: ฿0.00 (free, because the subtotal is over ฿3,000.00)
> - VAT 7%: ฿277.20
> - Total: ฿4,237.20
> 
> Prices exclude VAT. Your ฿250 limit was read as a per-pack price before VAT.
> 
> Prices are from our catalog of 3 Nov 2026.
> 
> Would you like matte or gloss?

Same facts, same total (฿4,237.20), same narrowing question; both pass the reply check first time.

## History

| Step | Commit | Result | File |
|---|---|---|---|
| Run 1, full | `1406a44` | 80/90 | `eval/results_run1.md` |
| Re-run of 10 affected requests after 4 bug fixes | `7d095c8` | 27/30 | `eval/results_rerun.md` |
| Full run after the E14 fix | `8dd5eaa` | 90/90 | `eval/results_8dd5eaa.md` |
| **Full run after reply polish** | `6df6960` | **86/90** | this file |

Before -> after per request, run 1 to `8dd5eaa`: E05 0/3 -> 3/3 (reply check flagged the free-delivery tip),
E14 0/3 -> 3/3 ("colour paper" now asks), E21 0/3 -> 3/3 (scorer regex), E23 2/3 -> 3/3 (template lacked the
delivery caveat); template replies 13 -> 0. Details in `eval/results_8dd5eaa.md`.

## Notes worth knowing (not failures, not fixed)

- E21: a reply may open "Yes, it's in stock today" to "Is it free today?"; price correct, never says free.
- Narrowing questions can be weak, e.g. "smooth or uncoated?" for coloured paper.
- Multi-turn requests (E17, E19) are one conversation of several turns, hence 90 turns for 87 model conversations.

## Spend for the whole eval effort

About $2.50 up to `8dd5eaa`, plus the polish smoke test ($0.08) and this run ($0.90): **about $3.50 in total**.

---

# Run report for `6df6960` (generated by `pl eval`)

## Layers

| Layer | Result |
|---|---|
| (a) Ingest completeness | 72 SKUs in DB vs 72 counted independently in the crawled HTML (sets equal: True); 0 missing required fields; 59 pricing files, all attached: True |
| (b) Criteria extraction | 318/318 expected fields (100%); cases fully right: 63/63 (100%) |
| (c) Product selection | 72/72 (100%) |
| (d) Totals exact (tool quote and reply text) | 66/66 (100%) |
| (e) Decision type | 84/87 (97%) |
| Reply content checks | 29/30 (97%) |
| Delivery-area flag | 6/6 (100%) |
| Reply post-check passed first or second try | 87/87 (100%) |
| Reply check catches a planted wrong total (offline) | 3/3 (100%) |
| **Overall pass** | 86/90 |

Latency per conversation: median 5.5s, max 10.0s.

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
| E10-out-of-stock-flyer | 2/3 | reply lacks any of ['12 November', '2026-11-12', 'Nov 12', 'November 12'] |
| E11-out-of-stock-paper | 0/3 | decision matches (expected ['no_exact_match']) |
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

## Failures (every failing run)

### E10-out-of-stock-flyer run 2

- Checks: {'decision': True, 'criteria': True, 'selection': True, 'reply': False, 'reply_check': True}
- Notes: reply lacks any of ['12 November', '2026-11-12', 'Nov 12', 'November 12']
- Decision `no_exact_match`, items ['PL-PR-A4-MT-170-44', 'PL-PR-A4-GL-130-44', 'PL-PR-A4-GL-100-44'], total None, criteria {"item1": {"product_type": "printed_flyer", "size_code": "A4", "sides": 2, "colour_mode": "cmyk", "finish": "gloss", "weight_gsm": 170, "quantity": {"value": 10, "unit": "packs"}, "size_raw": "A4"}}
- Reply:

> Sorry, we have no A4 gloss 170 gsm double-sided full-colour flyers that you can order right now.
> 
> The exact match is Digital Flyers A4 Gloss 170 gsm (PL-PR-A4-GL-170-44). It's temporarily out of stock and is expected back on 12 Nov 2026. We can't take orders for it until then.
> 
> These in-stock alternatives are also A4, double-sided and full colour. Prices are for 10 packs, and each pack has 100 sheets:
> 
> 1. Digital Flyers A4 Matte 170 gsm (PL-PR-A4-MT-170-44): ฿343.10 per pack at the 10-pack price (normally ฿365.00). It's the same weight, but matte instead of gloss.
> 2. Digital Flyers A4 Gloss 130 gsm (PL-PR-A4-GL-130-44): ฿318.66 per pack at the 10-pack price (normally ฿339.00). It's gloss, but 40 gsm lighter.
> 3. Digital Flyers A4 Gloss 100 gsm (PL-PR-A4-GL-100-44): ฿281.06 per pack at the 10-pack price (normally ฿299.00). It's gloss, but 70 gsm lighter.
> 
> Which matters more to you: the gloss finish or the 170 gsm weight? I can give you a full quote with delivery and VAT once you've picked one. If you'd rather wait for the gloss 170 gsm, it's back on 12 Nov.
> 
> Prices exclude VAT.

### E11-out-of-stock-paper run 0

- Checks: {'decision': False, 'selection': True, 'reply': True, 'reply_check': True}
- Notes: decision matches (expected ['no_exact_match'])
- Decision `matches`, items ['PL-CP-A4-70', 'PL-CP-A4-75', 'PL-CP-A4-80-NUSA'], total 393.76, criteria {"item1": {"product_type": "paper", "size_code": "A4", "quantity": {"value": 2, "unit": "packs"}, "keywords": ["heritage ivory"], "size_raw": "A4"}}
- Reply:

> Heritage Ivory A4 100 gsm (PL-CL-A4-100-IVY) is out of stock right now, so I can't take an order for it. It's expected back on 20 Nov 2026.
> 
> Here are some in-stock A4 options. None of them is ivory, so they differ in colour and weight:
> 
> - Siam Office Copy Paper A4 70 gsm (PL-CP-A4-70): ฿109.00 per ream of 500 sheets, regular price. White, uncoated.
> - Lotus Bright Everyday A4 75 gsm (PL-CP-A4-75): ฿118.00 per ream, regular price. White, uncoated.
> - Nusa Paper Copy A4 80 gsm (PL-CP-A4-80-NUSA): ฿121.50 per ream, regular price. White, uncoated.
> 
> If you want a cream shade, we also list a coloured A4 90 gsm cream paper (PL-CL-A4-90-CRM). I haven't priced it here, but I can quote it if you like.
> 
> My pick is the Siam Office Copy Paper (PL-CP-A4-70). For 2 packs:
> - Unit price x packs: ฿109.00 x 2
> - Subtotal: ฿218.00
> - Delivery: ฿150.00 (free from a ฿3,000.00 subtotal)
> - VAT 7%: ฿25.76
> - Total: ฿393.76
> 
> Prices exclude VAT, and the total includes it. Prices are from our catalog of 3 Nov 2026.
> 
> Would you like to order one of these, wait for the Heritage Ivory, or have me quote the cream paper? If you stay with the white papers, which finish do you prefer: gloss, matte, smooth or uncoated?

### E11-out-of-stock-paper run 1

- Checks: {'decision': False, 'selection': True, 'reply': True, 'reply_check': True}
- Notes: decision matches (expected ['no_exact_match'])
- Decision `matches`, items ['PL-CP-A4-70', 'PL-CP-A4-75', 'PL-CP-A4-80-NUSA'], total 393.76, criteria {"item1": {"product_type": "paper", "size_code": "A4", "quantity": {"value": 2, "unit": "packs"}, "keywords": ["heritage ivory"], "size_raw": "A4"}}
- Reply:

> Heritage Ivory A4 100gsm (PL-CL-A4-100-IVY) is out of stock right now, so I can't take an order for it. It should be back on 20 Nov 2026.
> 
> I don't have an in-stock paper with the same name. These are the closest A4 options that are in stock, and they differ from Heritage Ivory:
> 
> - Siam Office Copy Paper A4 70gsm (PL-CP-A4-70): ฿109.00 per ream, regular price. It's white, uncoated and lighter at 70 gsm.
> - Lotus Bright Everyday A4 75gsm (PL-CP-A4-75): ฿118.00 per ream, regular price. It's white, uncoated, 75 gsm.
> - Nusa Paper Copy A4 80gsm (PL-CP-A4-80-NUSA): ฿121.50 per ream, regular price. It's white, uncoated, 80 gsm.
> 
> If you want a similar colour, there is also a cream A4 90gsm coloured paper (PL-CL-A4-90-CRM). Tell me if you'd like me to quote it.
> 
> For reference, here is the quote for 2 reams of the first option (PL-CP-A4-70):
> - Unit price x packs: ฿109.00 x 2
> - Subtotal: ฿218.00
> - Delivery: ฿150.00 (free from a ฿3,000.00 subtotal)
> - VAT 7%: ฿25.76
> - Total: ฿393.76
> 
> Prices exclude VAT, and the total includes it. Prices are from our catalog of 3 Nov 2026.
> 
> Would you like one of these, or should I quote the cream paper? Do you want to wait for the Heritage Ivory restock?

### E11-out-of-stock-paper run 2

- Checks: {'decision': False, 'selection': True, 'reply': True, 'reply_check': True}
- Notes: decision matches (expected ['no_exact_match'])
- Decision `matches`, items ['PL-CP-A4-70', 'PL-CP-A4-75', 'PL-CP-A4-80-NUSA'], total 393.76, criteria {"item1": {"product_type": "paper", "size_code": "A4", "quantity": {"value": 2, "unit": "packs"}, "keywords": ["heritage ivory"], "size_raw": "A4"}}
- Reply:

> Heritage Ivory A4 100gsm (PL-CL-A4-100-IVY) is out of stock right now, so I can't take an order for it. It's expected back on 20 Nov 2026.
> 
> The matches below are in stock, but none of them is ivory. They are standard white copy paper, and I can't say how close they are to what you want.
> 
> - Siam Office Copy Paper A4 70gsm (PL-CP-A4-70): ฿109.00 per ream (500 sheets), regular price.
> - Lotus Bright Everyday A4 75gsm (PL-CP-A4-75): ฿118.00 per ream, regular price.
> - Nusa Paper Copy A4 80gsm (PL-CP-A4-80-NUSA): ฿121.50 per ream, regular price.
> 
> If you want a cream shade, our list also has a coloured A4 option called PL-CL-A4-90-CRM (90gsm). I haven't checked its price, so I can look it up if you'd like.
> 
> My pick is the Siam Office Copy Paper A4 70gsm (PL-CP-A4-70). For 2 packs:
> - Unit price: ฿109.00 x 2 packs
> - Subtotal: ฿218.00
> - Delivery: ฿150.00 (free from a ฿3,000.00 subtotal)
> - VAT 7%: ฿25.76
> - Total: ฿393.76
> 
> Prices exclude VAT, and the total includes it. They come from our catalog of 3 Nov 2026.
> 
> Do you want to wait for the Heritage Ivory, or should I quote the cream option? If you'd rather stay with white copy paper, which finish do you prefer: gloss, matte, smooth or uncoated?

