# PaperLane sales assistant: summary for the owner

## What we built

An assistant that answers customer chat requests the way your sales staff do. A customer writes *"letter-size
flyers, one side, colour, under 250 a pack, 20 packs"*, and it finds the products that fit, explains why, and gives
an exact quote: unit price, delivery, 7% VAT and total. It asks one short question when a request is unclear, says so
when nothing matches and offers the closest options, and never offers out-of-stock or discontinued items.

It works from a copy of your website. One command refreshes it when the site changes. If something looks wrong, it
keeps the last good copy and shows you a report of what changed.

Prices never come from the AI. A fixed calculator applies your pricing rules, and code checks every amount and
product name before a reply is shown. A reply that fails is rewritten or replaced.

## How well it works

We tested 32 typical requests, three times each (96 conversations), including volume-price boundaries, sale items,
out-of-stock items and a product page with a planted note telling AI assistants to say the item is free.

- **Every price and total was exact to the satang**, and it picked the right product whenever the request was clear.
- **95 of the 96 passed every test.** The 96th reply was also correct, but the test wrongly flagged it. We've left
  that on record rather than adjust the test.
- **Refreshing works.** On a changed copy of your site it picked up every change and never quoted a discontinued item.
- **It costs about 0.35 baht and takes about 5 seconds per message.**

We found and fixed two mistakes, both with correct amounts: a reply that said a total left out delivery when it
included it, and one that offered white paper as if it matched an out-of-stock ivory. A differently worded mistake
could still get through.

## What it can't do yet

- **Take orders or price custom jobs.** It quotes listed products; your staff confirm the order.
- **Sell a new type of product.** If you add envelopes to the site, say, it keeps saying you don't sell them until
  we update it.
- **Judge all of its own wording.** The checks cover amounts and product names, so a suggestion like "8 reams should
  fit your budget" needs its own quote.
- **Confirm delivery outside Bangkok and vicinity.** It quotes and flags it for your team.
- **Remember conversations after a restart, or connect to LINE.** It runs as a web page and an API.

## What we recommend next

1. **Pilot it with your sales team for two weeks**, comparing its quotes with theirs on real messages.
2. **Connect it to LINE** once staff rarely change its drafts, with a "talk to a person" button.
3. **Refresh the catalog after every website update**, and approve each change report.
