# PaperLane assistant (devx take-home A3)

A sales assistant for PaperLane that turns chat requests like *"We need letter-size flyers, one side, colour,
under 250 a pack, 20 packs"* into the right products and an exact quote. **The model reads intent and writes the
reply; code decides facts, matches and prices**, and a code check rejects a reply whose prices, totals, SKUs or
product names don't match that turn's tool results.

## Who uses it

**Phase 1, sales staff (the pilot).** Staff paste a customer's message into the chat page, read the draft reply
and its quote table, edit if needed, copy the reply and send it to the customer themselves. Nothing reaches a
customer without a person in between, and every edit tells us where the assistant is wrong. **Phase 2,
customers directly on LINE**, once the pilot's edit rate shows the drafts go out unchanged almost every time,
with a "talk to a person" handoff to staff. **Operations** (whoever updates the website) run `pl ingest` after
a site change, review the report, and `pl promote` a held refresh; they watch `/ops` for the thresholds below.
This is the same plan as the owner summary (`CUSTOMER_SUMMARY.md`, "What we recommend next").

## Run it (5 commands)

From this folder, with Python 3.11+ and the site served at `http://localhost:8000/paperlane/`
(`cd .. && python -m http.server 8000`, as in the brief):

```bash
python3 -m venv .venv && .venv/bin/pip install -q -e '.[dev]'
.venv/bin/pl ingest --base-url http://localhost:8000/paperlane/
export ANTHROPIC_API_KEY=sk-ant-...
.venv/bin/pl serve        # UI + API on http://127.0.0.1:8080
.venv/bin/pl eval         # 31 requests (30 model + 1 offline) x 3 runs -> eval/results.md
```

Other entry points: `pl chat` (terminal REPL), `pl quote PL-CP-A4-70:10` (pricing only, no model), `pytest`
(no key needed; reads the catalog site from `../paperlane`, as in the take-home layout), `python eval/refresh_rehearsal.py ../paperlane <tmpdir>` (re-ingest a mutated copy of the site).

For the demo's updated site: `pl ingest --base-url <new url>`, then read the report it prints (also in
`data/reports/`). Items whose data fails a check are stored not quotable and listed; everything else goes live,
and a running server picks up the new snapshot on the next message. **If the run has warnings (dead links, SKU
count changed by more than 20%), it is held: the previous snapshot stays live and the command exits 3 until you
run `pl promote <run_id>` (or re-run with `--accept`).** It is rejected (exit 2) only if nothing usable was parsed.

## Architecture

```
                 ┌──────────── ingest (pl ingest / POST /ingest) ────────────┐
 site ──HTTP──▶ crawl (BFS, 1 req/s, robots Crawl-delay) ──▶ raw files data/raw/<run>/
                 │   parse: 4 layouts, label-driven ──fail──▶ LLM fallback (same schema, same validation)
                 │   tiers: api/pricing/<SKU>.json (what tiers.js loads)       notes ──▶ quarantined table
                 │   validate ──▶ SQLite snapshot (run_id) ──▶ diff vs live ──▶ promote | reject
                 └───────────────────────────────────────────────────────────┘
 chat ──▶ Claude (tool use, ≤4 rounds) ──▶ search_products ──▶ search.py: normalise ▸ required? ▸ hard filters
                │                          get_product          ▸ rank ▸ relax ▸ decision + prices
                │                          quote ─────────────▶ pricing.py (pure Decimal, PR1–PR8)
                └──▶ reply check (figures, totals, SKUs, names vs this turn's tool output) ──fail──▶ regenerate ──fail──▶ template reply
```

| File | Role |
|---|---|
| `pl/crawl.py` | Same-origin BFS crawler, rate-limited, stores every response for provenance |
| `pl/parse.py`, `pl/normalise.py` | Label-driven parsers for the four page layouts; unit/size/weight/money/stock normalisers |
| `pl/llm_extract.py` | Fallback extractor for pages the parsers can't read: the model copies field text, code normalises it |
| `pl/ingest.py`, `pl/db.py`, `pl/diff.py` | Snapshot per run, promotion gates, diff report |
| `pl/pricing.py` | The only place prices are computed |
| `pl/search.py` | Criteria validation and the decision (clarify / matches / no_exact_match / not_sold) |
| `pl/agent.py`, `pl/replycheck.py` | Claude tool loop, session memory, reply post-check, JSONL request log |
| `pl/api.py`, `pl/static/index.html` | FastAPI (`POST /chat`, `POST /quote`, `POST /ingest`, `GET /items`) and a one-page UI |
| `eval/` | Requests with expected products and totals, runner, independent price calculator, refresh rehearsal |

## Assumptions

We didn't send clarifying questions to devx; these are our calls, and the code behaves exactly this way.

| # | Assumption | Why | Where |
|---|---|---|---|
| 1 | Several items qualify and every required attribute is given → rank by stated preferences, then cheapest effective unit price at the requested quantity; show the top 3, the full breakdown for #1, and end with one narrowing question. | Answers the request completely and still asks the question a salesperson would, instead of stalling on a clarification. | `search.py` ranking, `narrowing_question` |
| 2 | Quantities in sheets are rounded up to whole packs, and the reply says so. | PaperLane sells whole packs only; rounding down would under-deliver, and a silent change surprises the customer. | `search.packs_for`, `rounding_note`; quote tool `qty_sheets`; eval E20, E22, E25 |
| 3 | If a few more packs (at most ฿150.00 extra in total) would cross the ฿3,000 free-delivery threshold, suggest it; never change the quoted quantity. | It's often a good deal for the customer (G8→G9 costs +45.68), but the order size is their decision. | `pricing._insights`; eval E05 |
| 4 | Out-of-stock items are named with their expected return date and never quoted; discontinued items are "no longer sold"; in-stock alternatives are offered. | PR8, and a customer who asked for a specific item needs to know why it isn't in the quote. | `search` `unavailable`, `pricing.quote` refusals; eval E10, E11, refresh rehearsal |
| 5 | The site says "Bangkok and vicinity". A delivery location outside that (or not recognised as inside it) is still quoted, with a flag that sales must confirm delivery. | Losing the quote is worse than a manual check; vicinity = Bangkok plus Nonthaburi, Pathum Thani, Samut Prakan, Samut Sakhon, Nakhon Pathom. | `search.delivery_area`; eval E23, E24 |
| 6 | Budgets exclude VAT (PR7) unless the customer says "including VAT" / "all-in"; an ex-VAT budget is compared with subtotal + delivery. The reply states which was used. | PR7 says so; delivery is part of what the customer pays before VAT. | `search.normalise` `budget_assumption`; eval E15, E16 |
| 7 | A flyer pack is 100 printed sheets ("500 flyers" = 5 packs). Artwork, turnaround and custom sizes (a readable size we don't list, e.g. DL) are out of scope; the assistant says so. A size the code can't read gets a question listing the sizes we sell. | That's the site's pack definition; the rest isn't in the catalog, so any answer would be invented. | `Quantity`, custom-size decision, system prompt; eval E25 |
| 8 | Prices are those of the snapshot the quote was built from; each quote line shows `source_url` and `crawled_at`. | A quote must be traceable to what the site said at the time. | `pricing.Quote`, UI footer |
| 9 | The updated demo site may change page layouts: label-driven parsers plus an LLM fallback handle it, and an unsafe snapshot is rejected, not promoted. | The demo forbids code changes, so the pipeline has to absorb layout drift or fail safe. | `parse.py`, `llm_extract.py`, `ingest.py` gates |
| 10 | Crawl at 1 request/second, following `robots.txt` (stricter than the brief's 2/s). | robots.txt says `Crawl-delay: 1`; the stricter of the two rules wins. | `crawl.Fetcher` |

## Key decisions and trade-offs

**Code decides, the model talks.** The model's only jobs are reading the customer's words into a `Criteria`
object and writing the reply. Whether to ask a question, which products qualify, what they cost and what to
offer when nothing fits are all decided in `search.py` and `pricing.py`, so they are unit-tested and identical on
every run. The model can't price: tool results carry formatted THB strings, and `replycheck.py` compares every
money-looking figure (currency-marked incl. บาท, two decimals, or a bare amount of 3+ digits that isn't a
quantity) against **this turn's** tool output and the customer's message, plus the two fixed delivery-policy
figures. On a line that names one SKU, each figure must be that SKU's own (unit/list/line price, tier, its
quote total); a "total"/"subtotal" on a line naming no product must equal the quote's. Every SKU and every
catalog product name mentioned must appear in this turn's tool output. What it can't catch: wrong prose claims
("matte" for a gloss item), paraphrased product names, and a figure attached to a product by name only. On a mismatch the model gets one rewrite; if that also fails, the customer gets a template reply built
straight from the tool JSON. The figure is never "probably right".

**Scraping: labels, not positions; tiers from the JSON.** The site shows the same facts in four layouts (flyer
variant table, spec table, spec `<dl>`, prose). Every value is found through its label via a synonym map
("Basis weight" = "Weight" = "Paper weight"), so a reordered or renamed-but-known column still parses. Volume
tiers aren't in the HTML: `assets/tiers.js` fetches `api/pricing/<SKU>.json` for each `data-sku` element, so the
crawler does the same (and skips `data-sale='1'` elements exactly as the JS does). Category-page "from ฿x" prices
are ignored because they can be a B&W variant.

**Refresh path without code changes.** Each ingest writes a new snapshot tagged with a `run_id`. It is promoted
to live only if every product page parsed (deterministically or via the LLM fallback), no row is missing a
required field, tier prices decrease, and the SKU count is within ±20% of the live snapshot. Otherwise the old
snapshot stays live. Every run writes a diff report (new/removed SKUs, price, sale, tier, stock and other field
changes) so a human can see what moved. An unknown label or a failed validation sends that page to the LLM
fallback instead of guessing; the fallback only copies text, the same normalisers and validation run on it, and
those rows are marked `extraction='llm'` and listed in the report.

**Untrusted text.** The `pl-ph-a4-230-mt` page carries a customer note addressed to "AI shopping assistants".
Notes are cut out of the page before parsing, stored in a separate `notes` table, and never sent to any model
(not to the agent, not to the extraction fallback). Eval case E21 checks the assistant doesn't repeat the claim.

**No vector search.** 72 SKUs with a dozen typed attributes is a filtering problem, not a retrieval problem.
Customer wording ("8.5x11", "4/0", "20 lb bond") maps to exact values with small normalisers, and hard
constraints must be exact (an A4 match must never come back for "letter"). Embeddings would add a
fuzzy step exactly where the brief demands exactness. Soft wishes (brand, "recycled") are a keyword boost in
ranking. With thousands of SKUs and free-text descriptions I'd add BM25 or embeddings as a ranking signal only,
behind the same hard filters.

**Relaxation is fixed and explicit.** When nothing in stock fits: relax max price/budget, then finish, then
weight, then paper colour, and each alternative states exactly what differs and by how much ("unit price 113.52
is 13.52 over the max 100.00"). Size, product type, sides and colour mode are never relaxed. Out-of-stock exact
matches are reported with their back-in-stock date and never quoted (PR8).

**Several matches → top 3, a full quote for the best, one narrowing question.** This answers the brief's
example completely and still asks the question a salesperson would ("Matte or gloss?"). Code also computes
upsell hints (e.g. G8→G9: one more pack crosses free delivery and costs only 45.68 more).

## Schema decisions

SQLite, one row per SKU per ingest run; money in integer satang (no floats anywhere near prices).

| Field | Decision |
|---|---|
| `size_code` + `width_mm`/`height_mm` | Named size wins (A3/A4/A5/LETTER/LEGAL); dimensions are parsed from mm or inches and used to recognise "8.5x11" style text. Letter = 216 × 279, Legal = 216 × 356 (rounded from inches). |
| `weight_gsm`, `weight_lb_stated`, `weight_source` | gsm is the comparable value. A bare "24 lb" is converted with the customer's table (20/24/28/32 lb = 75/90/105/120 gsm) and marked `converted_from_lb`; "24 lb (90 gsm)" is `stated`. An lb value outside the table is left empty, which fails validation rather than guessing. |
| `colour` / `colour_raw` | Paper colour family (white, ivory, pink, assorted…) plus the original text. For flyers the site's "Colour" column is print colour, so it goes to `colour_mode`, not `colour`. |
| `finish` / `finish_raw` | matte, gloss, uncoated, smooth, laid. Flyer finish comes from the page title ("– Matte"). |
| `sides` (1/2), `colour_mode` (cmyk/bw) | Flyers only; NULL for blank paper. |
| `pack_unit`, `sheets_per_pack` | ream vs pack, and sheet count, so "2,000 sheets" converts per product (and rounds up, with a note, when it doesn't divide). |
| `list_price_satang`, `sale_price_satang`, `tiers` | Sale is a separate column (PR3 needs to know it's a sale, not just a price). Tiers are their own table with source URL. |
| `stock_status`, `back_in_stock`, `stock_raw` | in_stock / out_of_stock / discontinued / unknown. Unknown availability text is a validation failure, never treated as in stock. |
| `extraction`, `source_url`, `crawled_at`, `run_id` | Provenance on every row; quotes carry the source URL and crawl time per line. |

## Known limitations

- **Restated prices need a fresh tool call.** The reply check trusts only the current turn's tool output, so a
  follow-up like "what was the total again?" must call the tool again (the system prompt says so). If the model
  doesn't, the reply fails the check and the customer gets the template reply.
- **The reply check is about numbers and names, not prose.** It can't tell that "matte" was said of a gloss item,
  misses paraphrased product names, and only ties a price to a product when the SKU is on the same line.
- **One bad row holds its whole page without an API key.** A row missing a required field (e.g. a flyer with no
  sides) sends the page to the LLM fallback; with no key every SKU on that page is stored not quotable.
- **Two requests on the same chat session at once aren't serialised.** Different sessions are safe (the shared
  DB connection is locked); simultaneous messages in one session can interleave its history.

- **Eval scope.** 31 requests x 3 runs on the v1 catalog: 93/93 pass on the final commit (86/90 after the
  reply-wording polish, before the E11 fix), totals and product selection exact in every run. That is a
  designed test set, not real customer traffic; real messages will be messier (Thai, typos, several questions in
  one message).
- **Narrowing questions can be weak**, e.g. "smooth or uncoated?" for coloured paper, where both are plain
  finishes.
- **Wording can be off even when the price is right.** In eval E21 the reply opened "Yes, it's in stock today"
  to "Is it free today?". The price (650.56) was correct and it never said "free", but the wording was poor.
- **Only catalog brands and colours in keywords become filters.** "Heritage Ivory" now filters on brand and
  colour (the E11 fix), but a product line named only by its marketing words ("Premium", "Everyday") still only
  ranks, so a request for an out-of-stock line named that way could be answered with a similar product.
- **Cost and speed:** about $0.01 and 5.5 seconds per message (p95 7.9 seconds) on Claude Sonnet 5.5.

## With another week

- Put the agent behind LINE: a LINE Messaging API webhook maps `userId` to `session_id`, replies with the same
  text plus a Flex Message for the quote table; move session state from the in-process dict to Redis so several
  workers can serve one conversation; add a "talk to a person" handoff that posts the conversation to the sales
  team's LINE group.
- Run the eval in CI on every change and on every promoted snapshot (with the expected values regenerated by
  the independent calculator from the new site), and alert on the production metrics below.
- Quote documents: a PDF quote with a number, validity date and the snapshot it was priced from.
- A small review screen for the ingest diff, so an owner approves a refresh before it goes live instead of the
  automatic gates alone.

### Metrics I'd watch in production

1. **Reply-check failure rate** (and template-reply rate): the model trying to state a figure that isn't from a tool.
2. **Decision mix per day** (clarify / matches / no_exact_match / not_sold): a jump in no_exact_match or not_sold means a catalog change or a demand gap.
3. **Quote-to-order conversion and edits by sales staff**: how often a person changes what the assistant quoted.
4. **p95 latency and cost per conversation** from the JSONL log (`data/logs/requests.jsonl`).

1, 2 and 4 are on `/ops` (below); 3 needs the pilot's order data.

### Operations page (`/ops`)

`pl serve` also serves `/ops`: one static page (inline SVG, no JavaScript) over the request log
(`data/logs/requests.jsonl`, one structured trace per request), the `runs` table and `eval/results.json`. Each
card compares a metric to its threshold and says what to do when it's crossed; the table below is generated from
the same config (`pl/ops.py` `THRESHOLDS`, checked by a test). `?traffic=live|eval|all` switches traffic;
`pl eval` tags its requests `eval`. Each recent request opens its trace (customer message with phones and emails
masked, criteria, every tool call with arguments and a result summary, check problems per attempt, reply, token
usage) and exports as a `requests.yaml` case (`/ops/export/<request_id>?expect=<decision>`), runnable with
`pl eval --cases <file>`. Trace attributes use the OpenTelemetry GenAI names (`gen_ai.operation.name`,
`gen_ai.request.model`, `gen_ai.usage.input_tokens` including cache tokens, `gen_ai.usage.cache_read.input_tokens`,
`gen_ai.tool.name`, `gen_ai.tool.call.arguments`, ...). Price drift re-prices the latest logged quotes with
`eval/independent_quote.py` against the live snapshot's raw pages.

| Metric | Alert when | Action |
|---|---|---|
| Reply-check failure rate (first attempt) | > 10% | Open the failing traces. If the figure was right, the check has a false positive: fix it narrowly in replycheck.py. If it was wrong, fix the prompt or tool output. |
| Template-reply rate | > 2% | Customers are getting the plain fallback. Open the traces: both attempts failed the check, or the API errored (see error). |
| Decision mix: no exact match | > 30% | Many requests find nothing: check for a catalog gap or out-of-stock items in the traces. |
| Decision mix: not sold | > 20% | Customers ask for things PaperLane doesn't list: share with the owner as demand. |
| Latency p50 | > 8 s | Check tool rounds and rewrites in slow traces; check API status. |
| Latency p95 | > 15 s | Same as p50; slow tails usually mean a rewrite or 2+ tool rounds. |
| Cost per conversation | > $0.03 | Check cache reads in the traces (a cache miss costs ~10x), rewrites and tool rounds. |
| Catalog age (live snapshot) | > 7 days | Prices may be stale: run `pl ingest --base-url ...` and review the report. |
| Last ingest held or rejected | > 0 runs | Read data/reports/<run>.md. If the warnings are expected, `pl promote <run>`; otherwise fix the site or the parser. The previous snapshot stays live. |
| Logged quotes that re-price differently | > 0 quotes | A logged quote no longer matches the independent calculator on the live snapshot's raw pages: if the site changed, re-ingest; if not, it's a pricing bug. Open the trace. |

## How I used AI tools

Built with Claude Code (Claude Opus 5.5). One session turned the brief into `SPEC.md` (decisions, golden totals,
the §12 working assumptions); a second built the code from that spec; a third ran an independent
adversarial review of the code and found the seven bugs fixed in the "Fix" commits (all-or-nothing refresh, ranking by price
per pack, a reply check that accepted any number from the session, and so on). Inside the product, Claude
Sonnet 5.5 reads the customer's words into structured criteria, writes the reply, and re-reads a product page
only when the deterministic parser can't (`eval/llm_fallback.md`).

What I didn't take on trust: the golden totals were recomputed by `eval/independent_quote.py`, a separate
regex-and-Decimal calculator that shares no code with `pl/`; ingest completeness is checked against an
independent count of SKUs in the raw HTML; the refresh path was rehearsed on a mutated copy of the site; and the
live eval exposed four bugs the unit tests had passed (reply-check false positives, a rewrite that told the
customer it was "the corrected reply", the template dropping the delivery caveat, the fallback losing the
category), and one regression of my own ("colour paper" stopped asking, E14). Each is fixed in its own commit;
the before/after and each full run (90/90 on `8dd5eaa`, 86/90 after the reply-wording polish, 93/93 on the
final commit with the E11 failure exported from the request log as a 31st case) are in `eval/results.md`.
