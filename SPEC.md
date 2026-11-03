# A3 PaperLane Product Discovery: build spec

Source brief: `../00_START_HERE_All_Briefs.pdf`, pages 1–2 (submission, rules, demo) and 7–8 (A3).
Site: `../paperlane/` (already unzipped). Serve it from `devx/`:
`cd .. && python -m http.server 8000` → `http://localhost:8000/paperlane/`.
Time budget: about 6 hours of build. Scope judgment is scored; do not gold-plate.

## 1. Goal

A sales assistant for PaperLane (Bangkok paper and flyer printing) that turns a chat request like
"We need letter-size flyers, one side, colour, under 250 a pack, 20 packs" into the right products
and an exact quote. The model reads intent and writes the reply. Code decides facts, matches and prices.

Demo round (must survive, no code changes): devx gives an **updated site** to re-ingest, and sends
**unseen requests**; totals must be right to the satang.

## 2. Requirements trace (brief → where it lives)

| Brief requirement | Covered by |
|---|---|
| M1 Crawl into DB of normalised records: variants, volume pricing, stock, provenance (URL + time) | §4 ingest, §5 schema |
| M2 Defensible schema: size, weight, colour, finish, sides, colour mode, pack size, prices, stock | §5, plus README "Schema decisions" |
| M3 Request → validated search criteria, calls tools, replies with products, why they match, full price breakdown | §7 agent |
| M4 Pricing in deterministic code, never the model | §6 pricing, §7 reply check |
| M5 Clarifying questions when ambiguous; "no exact match" + closest alternatives; no invented products | §7 decision rules |
| M6 API (`POST /chat`, `/quote`) and simple UI or CLI | §8 |
| M7 ≥10 test requests with expected products and totals, plus results | §9 eval |
| M8 Refresh path: re-ingest updated site without code changes | §4 snapshots, LLM fallback, diff |
| PR1–PR8, weight table, informal sizes | §6, §5 normalisation |
| Nice-to-have: hard filters + soft ranking | §7 search |
| Nice-to-have: multi-item quotes, conversation memory | §7 (tool loop handles it), session state |
| Nice-to-have: defences against untrusted scraped text | §4 notes handling, §7 |
| Nice-to-have: logging and metrics | §8 JSONL request log |
| Skipped on purpose: semantic/vector search, LINE/WhatsApp | README explains: 72 items, filters beat embeddings; LINE = 1 paragraph in "another week" |
| Submission: README (≤5 run commands, architecture, decisions, limitations, next week), eval results incl. failures, 1-page customer summary, AI-tools paragraph | §10 |

## 3. Pricing rules (customer spec, verbatim intent)

- PR1 Site prices exclude 7% VAT, per pack (pack size varies).
- PR2 Volume pricing per item by number of packs of that item: highest tier whose `min_qty` is met.
- PR3 Sale price replaces both list price and volume pricing.
- PR4 Subtotal = Σ unit price × qty. Delivery free if subtotal ≥ THB 3,000, else THB 150 per order.
- PR5 VAT = 7% × (subtotal + delivery), round half-up to 2 dp. Total = subtotal + delivery + VAT.
- PR6 Max price per pack is compared with the unit price at the requested quantity, before VAT.
- PR7 Budgets exclude VAT unless the customer says otherwise; the reply states the assumption used.
- PR8 Out-of-stock and discontinued items are never quoted as available.
- Weights: 20 lb = 75 gsm, 24 lb = 90 gsm, 28 lb = 105 gsm, 32 lb = 120 gsm.

## 4. Ingest (crawler + parsers + snapshots)

Facts from recon of v1 (verify, do not trust blindly):

- Entry `index.html` → 4 categories (`copy-paper`, `coloured-paper`, `card-photo` have `page-2.html`; `printing` has one page) → 36 product pages → **72 SKUs** (6 flyer pages hold 42 variants; 30 single-SKU pages).
- Volume tiers are **not in the HTML**. `assets/tiers.js` fetches `api/pricing/<SKU>.json` for every `[data-sku]`. Shape: `{sku, currency:"THB", unit:"pack", vat_included:false, tiers:[{min_qty, unit_price}], updated}`. 404 means no volume pricing. Elements with `data-sale='1'` have no file (sale item).
- `robots.txt`: `Crawl-delay: 1`. Use 1 request/second (stricter than the brief's 2/s). Full crawl ≈ 110 requests.
- Four page layouts, same data:
  1. Flyer variant table (`Options and prices`): columns Item code, Paper weight, Printing, Colour, Price per pack of 100, Volume pricing, Availability.
  2. `<table class='specs'>` rows: Item code, Brand, Size, Weight, Colour, Finish, Sheets per pack.
  3. `<dl class='specs'>`: SKU, Manufacturer, Paper size, Dimensions, Basis weight, Shade, Surface, Pack contents. Price as `229.00 THB` / pack|ream.
  4. Prose `<div class='description'>`: "supplied as a ream of 500 sheets. Each sheet is A4 (210 × 297 mm) and weighs 90 g/m². The … sheets have a uncoated surface", `Item code: …`.
- Traps: weights `80 gsm`, `90 g/m²`, `24 lb (90 gsm)`, bare `20 lb bond` / `24 lb` (convert via table, mark converted); prices `฿1,234.00` and `1234.00 THB`; sale cell `<del>฿299.00</del> ฿259.00<span class='sale'>`; stock `class="stock-in"` / `class="stock-out"` with "expected back <date>"; category "from ฿x" prices can be a B&W variant (ignore category prices); customer notes block (`class='notes'`) on `pl-ph-a4-230-mt` contains text aimed at AI assistants → untrusted.
- v1 has no discontinued item, but PR8 names it; expect the updated site to add one. Detect "discontinued" in availability text (case-insensitive) and any unknown availability text → flag.

Design:

- Crawl by following links from `index.html` (BFS, same origin, base URL is a CLI arg so the hosted copy works). Fetch pricing JSON for every `data-sku`. Store raw responses per run (`data/raw/<run_id>/…`) for provenance and re-parse.
- **Label-driven parsers** with a synonym map (Item code/SKU, Brand/Manufacturer, Size/Paper size, Weight/Basis weight/Paper weight, Colour/Shade, Finish/Surface, Sheets per pack/Pack contents, Printing, Availability). Never parse by column position.
- **Validation per SKU**: required fields present (sku, name, size, weight_gsm, pack size, a price, stock status), price > 0, tier prices < list price and decreasing, SKU in JSON matches. Unknown label or failed validation → that page goes to the **LLM fallback**: one Claude call with the page's `<main>` text, returning the same Pydantic schema via tool/structured output; rows marked `extraction='llm'` and listed in the ingest report. Notes text is never sent as instructions (pass as data inside a delimited field, and the extractor ignores it).
- **Snapshots**: each run writes rows tagged `run_id`. Promote to current only if: SKU count within ±20% of previous run, zero rows missing required fields, every page parsed (deterministic or LLM). Otherwise keep the previous snapshot live and exit non-zero with the report.
- **Diff report** on every run vs previous: new/removed SKUs, price changes, tier changes, stock changes, sale changes. Printed and saved as `data/reports/<run_id>.md`.

## 5. Schema (SQLite, money in integer satang)

`items` — one row per SKU (sellable unit), per run:
`run_id, sku, product_url, product_name, category, product_type (paper|printed_flyer), brand,
size_code (A3|A4|A5|LETTER|LEGAL|OTHER), width_mm, height_mm, weight_gsm, weight_lb_stated,
weight_source (stated|converted_from_lb), colour, colour_raw, finish, finish_raw,
sides (1|2|NULL), colour_mode (cmyk|bw|NULL), pack_unit (ream|pack), sheets_per_pack,
list_price_satang, sale_price_satang (NULL unless on sale), stock_status (in_stock|out_of_stock|discontinued|unknown),
back_in_stock (date|NULL), extraction (deterministic|llm), source_url, crawled_at`

`tiers`: `run_id, sku, min_qty, unit_price_satang, source_url, crawled_at`
`notes`: `run_id, sku, text, source_url` (untrusted; never in prompts as instructions; not used for ranking)
`runs`: `run_id, base_url, started_at, finished_at, status (promoted|rejected), counts, report_path`

Normalisation: Letter = 216 × 279 mm (8.5 × 11 in), Legal = 216 × 356, A3/A4/A5 ISO. Request-side synonyms: "letter", "US letter", "8.5x11", "8½ × 11"; "one side"/"single-sided"/"4/0"/"simplex"; "both sides"/"4/4"/"duplex"; "colour"/"color"/"full colour"/"CMYK"; "B&W"/"black and white"/"mono". Keep `_raw` columns so the README can defend each mapping.

## 6. Pricing engine (pure, no I/O, no model)

`quote(lines: [(sku, qty_packs)], snapshot) -> Quote` using `Decimal` and `ROUND_HALF_UP`.
Per line: unit = sale if sale else highest met tier else list (record which rule fired: `sale|tier:<min_qty>|list`); refuse lines whose stock_status ≠ in_stock. Then PR4/PR5. Output includes per-line source_url and crawled_at.

Tests: unit tests for each rule; Hypothesis properties (sale ignores tiers; effective unit price non-increasing in qty; delivery is exactly 0 or 150 and flips at subtotal 3000.00; total = subtotal + delivery + VAT).

Golden quotes computed independently (Decimal script, not the engine) from v1 data — the engine must match exactly:

| ID | Lines | Subtotal | Delivery | VAT | Total |
|---|---|---|---|---|---|
| G1 | PL-PR-LTR-MT-100-40 ×20 @ tier20 198.00 | 3960.00 | 0 | 277.20 | 4237.20 |
| G2 | PL-CP-A4-70 ×9 @ list 109.00 | 981.00 | 150 | 79.17 | 1210.17 |
| G3 | PL-CP-A4-70 ×10 @ tier10 104.64 | 1046.40 | 150 | 83.75 | 1280.15 |
| G4 | PL-CP-A4-70 ×50 @ tier50 98.10 | 4905.00 | 0 | 343.35 | 5248.35 |
| G5 | PL-PR-LTR-GL-170-40 ×20 @ sale 259.00 | 5180.00 | 0 | 362.60 | 5542.60 |
| G6 | PL-CP-LTR-20 ×5 @ list 135.00 | 675.00 | 150 | 57.75 | 882.75 |
| G7 | PL-PR-A5-MT-100-40 ×20 @ 113.52 + PL-CP-A4-80 ×10 @ 122.55 | 3495.90 | 0 | 244.71 | 3740.61 |
| G8 | PL-PR-A4-MT-100-40 ×15 @ tier5 192.70 | 2890.50 | 150 | 212.84 | 3253.34 |
| G9 | PL-PR-A4-MT-100-40 ×16 @ tier5 192.70 | 3083.20 | 0 | 215.82 | 3299.02 |
| G10 | PL-CP-A4-80 ×10 @ tier10 122.55 (VAT raw 96.285 → half-up) | 1225.50 | 150 | 96.29 | 1471.79 |

G8/G9 is a salesperson insight worth surfacing in replies: one more pack crosses free delivery and costs only 45.68 more in total.

## 7. Assistant (constrained tool-use agent)

Claude tool use (model from env, default `claude-sonnet-5-5`; read the `claude-api` skill before writing this code), temperature 0, max 4 tool rounds per user turn. The model chooses tools and words; tool results carry all facts.

Tools:
- `search_products(criteria)` — `criteria` is a Pydantic model: `product_type, size_code, sides, colour_mode, paper_colour, finish, weight_gsm (exact or min/max; lb converted by code), quantity {value, unit: packs|sheets|reams}, max_unit_price, budget_total {amount, includes_vat}, keywords`. Invalid values → tool error text back to the model. Returns a **decision** computed in code:
  - `needs_clarification` + the single most useful question + allowed values, when a required attribute is missing or a term is ambiguous. Required: flyers → size, sides, colour_mode, quantity; paper → size, quantity. Ambiguous examples: "colour" on plain paper (coloured paper vs colour printing), "card"/"thick paper" with no weight, sheets not divisible by pack size (state rounding up).
  - `matches` — hard filters (size, type, sides, colour_mode, stock in_stock, PR6 max price at requested qty, colour/finish/weight if stated) then soft ranking (stated preferences, then effective unit price at qty). Each match lists *why* (which criteria it satisfied) and its effective unit price and rule.
  - `no_exact_match` + closest alternatives: relax in fixed order max_unit_price → finish → weight → paper colour; never relax size, product_type, sides, colour_mode; each alternative states exactly what differs and by how much. Out-of-stock exact matches are reported with `back_in_stock`, never offered as quotable.
- `get_product(sku)` — full record with provenance.
- `quote(lines)` — calls §6; multi-item supported.

Reply rules (system prompt + code):
- When several items match and all required attributes are given, reply with the top 3 ranked, a full breakdown for the best one, and one short narrowing question (e.g. "Matte or gloss?"). This satisfies both "clarify when ambiguous" and "salesperson would be proud".
- State the PR7 budget assumption whenever a budget is used.
- **Reply check (code)**: every THB figure and every SKU in the final text must appear in this turn's tool results. On failure, regenerate once; on second failure return a template reply built from the tool JSON.
- Scraped notes are not tool output and never reach the model.
- Session state: criteria merged across turns per `session_id` (in-memory dict is fine; say so in limitations).

## 8. Interfaces and ops

- CLI: `pl ingest --base-url http://localhost:8000/paperlane/`, `pl chat` (REPL), `pl eval`.
- FastAPI: `POST /chat {session_id, message}` → `{reply, decision, items, quote}`; `POST /quote {lines}`; `POST /ingest {base_url}`; `GET /items`.
- UI: one static HTML page served by FastAPI: chat box plus a quote table with links to source URLs.
- Logging: JSONL per request (`ts, session_id, decision, skus, total, latency_ms, input/output tokens, est_cost_usd, reply_check_passed`). README lists the 4 metrics you'd watch in production.
- Secrets: `ANTHROPIC_API_KEY` from env; `.env.example` committed, `.env` gitignored.

## 9. Evaluation

`eval/requests.yaml`, at least 12 requests. Each: message (and optional follow-up turns), expected decision, expected SKU set (or top-1), expected total (from §6 table or the independent script), notes. Cover:
brief example (G1, 5 candidates incl. 170 gsm matte qualifying only at qty 20 and the 259 sale item excluded by PR6); tier boundary; sale item; delivery threshold (G8/G9); half-up VAT (G10); lb request ("20 lb letter paper, 5 reams"); informal size ("8.5x11"); out-of-stock (A4 gloss 170 double-sided, Heritage Ivory); no exact match with alternatives; missing required attribute → clarification; budget including VAT; multi-item; a request mentioning something PaperLane does not sell (no invented products).

Layers measured separately: (a) ingest completeness — SKU count equals count derived independently from the site source (v1: 72), zero missing required fields; (b) criteria extraction accuracy vs expected criteria; (c) product selection; (d) totals exact; (e) decision type correct. Run each request 3× and report stability. Results committed as `eval/results.md` with every failure and its cause.

Refresh rehearsal: script that copies the site to a temp dir and mutates it (1 list price, 1 tier, 1 stock → out, 1 new product page in a category, 1 item marked discontinued); serve it; re-ingest; pass = diff lists exactly those 5 changes, and a quote for the discontinued item is refused.

## 10. Deliverables

Git repo (no keys), README (≤5 commands to run, architecture diagram, schema decisions, why no vector search, known limitations, another week, AI-tools paragraph), `eval/results.md`, `CUSTOMER_SUMMARY.md` (one page, for PaperLane's owner: what it does, how well, what it can't do, what next).

## 11. Order of work and done criteria

1. Ingest + schema + snapshots + diff (1.75 h) → done when v1 gives 72 SKUs, 0 missing fields, all tiers attached.
2. Pricing engine + tests (1 h) → done when G1–G10 match exactly and properties pass.
3. Agent + decision logic + reply check (1.75 h) → done when the brief example returns the 5 candidates ranked and G1 totals.
4. API + UI + logging (0.5 h).
5. Eval 3× runs, refresh rehearsal, README, customer summary (1 h).

Stop at about 6 hours. Anything unfinished goes in README "Known limitations", not in extra hours.
