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

EVAL_SUMMARY_PLACEHOLDER

Prices are never worked out by the AI. They come from a fixed calculator that follows your pricing rules
exactly (volume tiers, sale prices, free delivery from ฿3,000, VAT rounding), and every price the assistant
writes is checked against that calculator before the customer sees it. If the AI writes a figure that doesn't
match, the reply is rewritten or replaced with a plain quote from the calculator.

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
- It isn't connected to LINE yet; today it runs as a web page and an API.

## What we recommend next

1. **Pilot it with your sales team for two weeks**: they paste real customer messages in, compare its quote
   with their own, and flag anything they would change. That gives us real-world accuracy, not just our tests.
2. **Connect it to your LINE Official Account**, with a "talk to a person" button that hands the chat to staff.
3. **Make refreshing the catalog a routine**: refresh after every website update, with you approving the
   change report before it goes live.
