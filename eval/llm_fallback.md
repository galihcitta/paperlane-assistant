# LLM fallback on the live model

`eval/llm_fallback_run.py` copies the v1 site and rewrites one product page (`pl-cp-a4-70.html`) so its
spec table becomes a `<ul class='facts'>` with labels the parser has never seen ("Product reference",
"Sheet format — A4, 210 by 297 millimetres", "Grammage — 70 g/m²", "Shade", "Surface", "Contents"). The
deterministic parser reports `no known layout`, so that page goes to `claude-sonnet-5-5`
(`llm_extract.extract`, structured output; the model copies raw field text, code normalises it). The copy
is served over HTTP and crawled at 1 request/second like the real site.

## Before fix (run 20261103T161220094786Z)

- Status **promoted**, 72/72 SKUs quotable, `llm_pages=1`.
- PL-CP-A4-70: `extraction=llm`; brand, A4, 70 gsm, white, uncoated, ream of 500, ฿109.00, in stock, both
  volume tiers (10+: 104.64, 50+: 98.10) all identical to v1.
- One defect: diff `PL-CP-A4-70: category 'copy-paper' -> None`. The fallback took the category from the
  deterministic items, and there are none when the layout is unknown.

## After fix (run 20261103T161442061711Z)

The page's breadcrumb category is now passed to the fallback directly. Same mutation, same live model:
status **promoted**, diff vs v1 **empty**, PL-CP-A4-70 still `extraction=llm` with every field equal to v1.

```
{"sku": "PL-CP-A4-70", "product_name": "Siam Office Copy Paper A4 70gsm", "brand": "Siam Office", "size_code": "A4", "weight_gsm": 70, "colour": "white", "finish": "uncoated", "pack_unit": "ream", "sheets_per_pack": 500, "list_price_satang": 10900, "stock_status": "in_stock", "extraction": "llm", "tiers": [{"min_qty": 10, "unit_price_satang": 10464}, {"min_qty": 50, "unit_price_satang": 9810}], "quotable": true, "quarantine_reason": null}
```
