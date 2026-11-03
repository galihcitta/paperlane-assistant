# Refresh rehearsal

Site copy mutated in `/private/tmp/claude-501/-Users-galihcitta-Works-playground-ai-lab-devx/75138a92-fb2f-4758-b826-245c5a24790e/scratchpad/rehearsal/www/paperlane` (5 changes), served on port 8001, re-ingested with the unchanged code.

- Snapshot status: **promoted** (run `20261103T155640790528Z`)
- Diff lists exactly the 5 planted changes: **PASS**
- Quote for discontinued PL-CS-A4-160-AST refused: **PASS** ([{'sku': 'PL-CS-A4-160-AST', 'reason': 'discontinued'}])
- Discontinued item not offered by search (A4 160gsm card): **PASS** (offered: ['PL-CS-A4-160-WH'])

## Round 2: 'Only 3 left' wording, a dead link, +16 SKUs
- First ingest status: **held** (previous snapshot still live: True); warnings: ['dead link: http://localhost:8001/paperlane/promo/black-friday.html: HTTP 404', 'SKU count 89 differs from previous 73 by more than 20%']
- After `pl promote 20261103T155826298011Z`: 'Only 3 left' item in stock and quotable, 16 new SKUs quotable: **PASS** (89 SKUs live)

## Expected

```
price: ['PL-CP-A4-70: list 109.00 -> 112.00']
tiers: ['PL-CP-A4-80: tiers [10+: 122.55, 50+: 116.10] -> [10+: 119.90, 50+: 116.10]']
stock: ['PL-CP-A4-75: in_stock -> out_of_stock (back 2026-12-01)', 'PL-CS-A4-160-AST: in_stock -> discontinued']
new: ['PL-CP-A4-90-ECO PaperLane Essentials Recycled A4 90gsm @ 139.00 (in_stock)']
```

## Ingest report produced by the pipeline

# Ingest report 20261103T155640790528Z

- Source: http://localhost:8001/paperlane/
- Status: **promoted**
- Counts: pages=46, product_pages=37, skus=73, quotable=73, not_quotable=0, with_tiers=59, on_sale=1, not_in_stock=4, llm_pages=0, requests=106, warnings=0, notes_quarantined=2

## Changes vs 20261103T144315978835Z

### new (1)
- PL-CP-A4-90-ECO PaperLane Essentials Recycled A4 90gsm @ 139.00 (in_stock)

### price (1)
- PL-CP-A4-70: list 109.00 -> 112.00

### tiers (1)
- PL-CP-A4-80: tiers [10+: 122.55, 50+: 116.10] -> [10+: 119.90, 50+: 116.10]

### stock (2)
- PL-CP-A4-75: in_stock -> out_of_stock (back 2026-12-01)
- PL-CS-A4-160-AST: in_stock -> discontinued

