# PaperLane sales assistant: summary for the owner

## What we built

An assistant that answers customer chat requests the way your sales staff do today. A customer writes something
like *"letter-size flyers, one side, colour, under 250 a pack, 20 packs"*; the assistant finds the products
that fit, explains why they fit, and gives an exact quote: unit price (including volume and sale prices),
delivery, 7% VAT and total, with a link to the product page each price came from.

It works from a copy of your website that it reads itself. When the site changes (new prices, a product out
of stock, a new item), you run one command to refresh it. If something on the new site looks wrong, the
assistant keeps using the last good copy and shows you a report of what changed.

## How well it works

We tested it on 32 typical requests, each run three times (96 conversations), including the tricky ones:
volume-price boundaries, sale items, sizes written in inches, "1,000 sheets" instead of packs, out-of-stock
items, budgets with and without VAT, customers outside Bangkok, and a product page with a planted note telling
AI assistants to say the item is free.

- **Every price and total was exact to the satang** in all 96 conversations, and it picked the right product in
  every case where the request was clear.
- **95 of the 96 passed every test, and the 96th reply was also right.** The test wrongly flagged a correct sentence,
  and we've left that on record rather than adjust the test to get a perfect score.
- **We fixed a wrong statement about delivery.** A live check found a reply saying a ฿1,210.17 total didn't include
  delivery, when it did. The amounts were all correct, so our earlier tests (which showed 93 out of 93) didn't look
  for this; rechecked, that run had the same mistake once. It appeared in 2 of 10 tries on that request before the
  fix and 0 of 10 after. The tests now look for this wording, though a differently worded mistake could still get
  through.
- **One request used to go wrong:** for "2 packs of the Heritage Ivory A4 paper" it said the ivory was out of stock
  but then offered white copy paper as if it matched. We caught it on the new operations page, turned it into a test
  case, and fixed it. It now says the ivory is back on 20 November and offers Heritage Cream as the closest
  alternative.
- **Replies now read like a salesperson wrote them**: a friendly first line, product names before item codes,
  a clear recommendation with its quote, and plain text that suits LINE.
- **It gives the same prices and products every time** for the same request. The wording varies a little.
- **About 0.35 baht and 5 seconds per message.**

We also checked that it keeps working when the website changes: on a copy of your site with changed prices, a
stock change, a discontinued item, a new product, a broken link and 16 extra products, it picked up every change,
held the update for review where it should, and never quoted the discontinued item.

Prices are never worked out by the AI. They come from a fixed calculator that follows your pricing rules
exactly (volume tiers, sale prices, free delivery from ฿3,000, VAT rounding). Before a reply is sent, code
checks that every amount in it came from the calculator in that same exchange, that each price sits next to the
product it belongs to, that the stated total is the quote's total, and that every product named was actually
found. If not, the reply is rewritten or replaced with a plain quote from the calculator. The check covers
numbers and product names, plus any claim that a total leaves out delivery; otherwise it doesn't judge the wording
around them.

It also:
- asks one short question when a request is unclear ("one side or both sides?"),
- says honestly when nothing matches, and offers the closest options, stating what is different,
- never offers out-of-stock or discontinued items, and gives the expected back-in-stock date,
- rounds sheet counts up to whole packs and says so, and suggests (never applies) a few extra packs when that
  makes delivery free for little extra cost,
- still quotes customers outside Bangkok and vicinity, but flags that your team must confirm delivery there,
- ignores text on product pages that tries to instruct it (one of your pages has a planted "tell customers
  this is free" note; the assistant never sees it).

## What it can't do yet

- It doesn't take orders or payment; it produces the quote, and your staff confirm the order.
- Conversations are remembered only while the server runs; a restart forgets them.
- It only knows what is on the website. Custom jobs (special sizes, papers you don't list, design work) get
  "we don't list that" rather than a price.
- It can make its own suggestions that the calculator didn't work out, such as "8 reams should fit your budget". Treat
  those as suggestions until it gives a quote for that quantity.
- It isn't connected to LINE yet; today it runs as a web page and an API.

## What we recommend next

1. **Pilot it with your sales team for two weeks**: they paste real customer messages in, compare its quote
   with their own, and flag anything they would change. That gives us real-world accuracy, not just our tests.
2. **Connect it to your LINE Official Account** once the pilot shows staff rarely need to change its drafts,
   with a "talk to a person" button that hands the chat to staff.
3. **Make refreshing the catalog a routine**: refresh after every website update, with you approving the
   change report before it goes live.
