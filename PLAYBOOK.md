# Loaded Dice — Daily GA4 Analysis Playbook

This playbook drives the automated daily analysis of the Loaded Dice GA4
property (**373767946**, loadeddice.uk, GBP). A scheduled Claude session runs
it every morning, writes a dated report to `reports/`, and surfaces
recommendations.

## Scope

- **Data source:** GA4 via the Windsor.ai connector (`googleanalytics4`,
  account `373767946` "Loaded Dice - GA4"). Do not use the Google GA4 Data
  API directly.
- **Analyse yesterday** against three baselines: previous day, same day last
  week, and the trailing 28-day average.
- Marketing-friendly language: "visits"/"visitors", not "sessions"/"users",
  in prose (tables can use the technical terms).

## Data pulls (Windsor.ai `get_data`, connector `googleanalytics4`)

1. **Daily site totals (30 days):** fields `date, sessions, totalusers,
   screen_page_views, add_to_carts, checkouts, ecommerce_purchases,
   purchase_revenue`, from 29 days before yesterday through yesterday.
2. **Channel daily trend (30 days):** fields `date, default_channel_group,
   sessions, purchase_revenue`, same range.
3. **Products (7 days):** fields `date, item_name, items_viewed,
   items_added_to_cart, items_purchased, item_revenue`, last 7 days ending
   yesterday. This pull is large — aggregate it with a script, don't read
   it raw.
4. Derive: conversion rate (`ecommerce_purchases / sessions`), AOV
   (`purchase_revenue / ecommerce_purchases`), yesterday vs trailing-7-day
   and trailing-28-day averages, per-channel yesterday vs its 28-day norm.

## Analysis checklist

- **Traffic & sources.** Yesterday's visits/visitors vs the three baselines.
  Which channels drove any growth or drop — name the channel, don't just
  report the total.
- **Revenue & conversions.** Orders, revenue, conversion rate, AOV vs
  baselines. Flag conversion-rate or AOV moves beyond ±25% of the 28-day norm.
- **Top & flop products.** Best sellers yesterday (by revenue); the
  "interest but no sales" signal — items with ≥100 views over 7 days and 0
  purchases; any product suddenly selling (≥3× its prior daily rate).
- **Anomalies.** Any metric or channel beyond ±25% of its 28-day average
  (ignore channels averaging <15 sessions/day — noise). Checkout drop-off:
  flag if purchases/checkouts falls under ~40%. Traffic-quality checks:
  sessions≈users with pages/visit collapsing means bots, not customers —
  call it out rather than celebrating a "traffic spike".
- **Cross-reference Google Ads** where relevant: the sibling routine
  (caughtsmart/GoogleAds, same format) changes campaigns; expect its
  changes to show up here (e.g. Paid Search session drops after negatives
  were added on 2 Aug 2026 are intentional, not an alarm).

## Adjustment policy

**Mode: REPORTING-ONLY, permanently** — GA4 is read-only by nature and this
routine changes nothing anywhere (no GA4 config, no Shopify, no ad
platforms). Recommendations are listed in the report with a concrete next
step so Graham can act on them in any session.

**GA4 revenue is NOT the source of truth (established 7 Aug 2026).** GA4
captures roughly a third of Online Store revenue — 6 Aug: GA4 16 orders
/£575.11 vs Shopify 23 web orders/£1,688.07; 22 July shows the same gap, so
it is long-standing (consent mode, ad-blockers, iOS ITP), not a break.
**Decision (Graham, 7 Aug 2026): read revenue from Shopify, and do not add
server-side GA4 tracking.** The Shopify GA4 integration runs through the
Google & YouTube channel's Web Pixel, which is client-side by design — this
gap cannot be configured away, and the decision is to live with it rather
than buy a server-side app (Elevar/Littledata/Stape). **Do not re-recommend
server-side tracking in future reports.** Revisit only if Graham starts
making budget decisions on GA4 channel-level ROI, and say so once, briefly.

So, every run:
- **Pull the day's orders from Shopify** (`orders`, filter `created_at` for
  the day, take `channelInformation.channelDefinition.handle` and
  `totalPriceSet`). **The Online Store ("web") total is THE revenue figure
  for the report** — lead the headline with it.
- Note Point of Sale, eBay and Shopify Collective totals separately so the
  day's real trading is visible; these never appear in GA4 and are not part
  of any "gap".
- Quote GA4's revenue only as a secondary, clearly-labelled figure when it
  is useful (e.g. channel mix), never as the headline, and never as the
  basis for calling a revenue rise or fall.
- Use GA4 for what it is good at: traffic volume, channel mix, landing
  pages, product views/carts, and the bot diagnostics.
- **Gift cards produce no GA4 purchase events at all** (6 Aug: £750 across
  2 orders, 15 add-to-carts, zero recorded) — always take gift card sales
  from Shopify.

Standing watch items for the daily run:

- **Direct-channel bot flood (from 30 Jul 2026):** Direct sessions jumped
  from ~150–500/day to 8–10k/day with near-zero revenue, sessions≈users,
  ~1.1 pages/visit. Confirmed signature (diagnosed 3 Aug): headless Chrome —
  browser=Chrome, OS=Windows, **screen_resolution=1280x1200** (99% of the
  junk), language=English, spread across non-UK countries via residential
  proxies (Vietnam/Brazil/HK top the list). Measure it daily with a
  `screen_resolution` filtered pull and report the flood's size as its own
  line. **Status 6 Aug: the Cloudflare fix worked for exactly one day
  (6,484 → 739 on 4 Aug) then was evaded — 4,112 on 5 Aug.** The
  fingerprint did NOT change; the *geography* did, from Vietnam/Brazil/
  Bangladesh to US/Singapore/Hong Kong/Japan/Germany, with UK IPs appearing
  for the first time. So also pull the **country split of the 1280x1200
  traffic** each run, not just the total — a shifting country mix is the
  tell that a geo-based rule is being routed around. Keep reporting until a
  genuinely clean week.
- **Dead-page check (added 5 Aug 2026):** each run, pull yesterday's
  `landing_page` with sessions and revenue, and look for pages taking heavy
  traffic while producing no item-view events and £0 revenue. Verify any
  suspect page via the Shopify connector before reporting it.
  **Important context (confirmed by Graham 5 Aug): sealed Pokémon TCG is
  deliberately NOT sold online — it is POS/in-store only, kept ACTIVE for
  the till but unpublished from the Online Store on purpose.** So a 404 on
  a sealed Pokémon product page is NOT a misconfiguration to fix by
  publishing. Report it as a *demand signal*: how many people wanted it and
  where they came from, so the link can be pointed at an in-store landing
  page instead. Never recommend publishing sealed Pokémon online.
  (Pokémon accessories — Funko, Ultra Pro/VaultX binders, playmats,
  portfolios — ARE sold online and are fine to treat normally.)
  **Diagnosing a dead-page spike (method proven 6 Aug):** pull `date_hour`
  for the landing page — a single-hour spike means a broadcast or a
  publish event, spread traffic means organic sharing. Then check the
  product's `resourcePublications` publishDate in Shopify. The 4 Aug ETB
  spike (62 of 78 sessions in the 10:00 hour) matched a publish to
  Point of Sale + **Microsoft Copilot** at 10:27:50 exactly — no campaign
  was involved. Publishing a POS-only product to any non-Online-Store
  channel can put its 404 URL into circulation.
- **"Unassigned" in fresh data is usually processing lag, not breakage
  (learned 4 Aug 2026):** GA4 takes 24–48h to finish attributing a day —
  the 07:00 pull sees yesterday partially processed, so a big
  (not set)/(not set) bucket the morning after is normal and re-resolves
  to real sources a day later (2 Aug's "£645 Unassigned" became Paid
  Search/Direct/Facebook/Klaviyo overnight). Each run: re-pull the
  PREVIOUS day's source/medium split and report the restated numbers;
  only flag Unassigned that survives 48h.
- **Klaviyo UTM tracking (root cause of the "email is dead" scare, found
  4 Aug 2026):** campaigns sent 31 Jul–3 Aug had `add_tracking_params:
  false`, so their clicks landed in GA4 as Direct — while Klaviyo's own
  attribution showed them earning £190 + £794 + £0. GA4's Email channel
  only ever showed the flows (which kept their UTMs). Graham is
  re-enabling account-level UTM tracking. Daily check: pull yesterday's
  sent campaigns via the Klaviyo connector (`get_campaigns`, filter
  scheduled_at ≥ yesterday) and flag any with `add_tracking_params:
  false` before it costs another day of blind data. Judge email
  performance from Klaviyo's campaign report, not GA4, until UTMs have
  been back on for a full week.
- **Paid Search sessions roughly halved from 2 Aug 2026** — expected
  consequence of the Brand Search phrase negatives added by the Google Ads
  routine. Verify Paid Search *revenue* holds; only flag if it collapses too.

## Report format

Write `reports/YYYY-MM-DD.md` (named for the run date; it covers yesterday)
containing:

1. **Headline** — yesterday's **Shopify Online Store revenue and orders**
   (the source of truth), the other sales channels' totals in one line, and
   real (de-botted) visits from GA4. Compare revenue against the 7-day and
   28-day Shopify averages, not GA4's.
2. **Channel table** — last 30 days sessions + revenue per channel, and
   yesterday's figure with trend arrow. This one is GA4-sourced by
   necessity (Shopify has no channel attribution) — label it as GA4 and
   treat its revenue column as indicative mix, not absolute money.
3. **Products** — top sellers yesterday + the "interest but no sales"
   callout.
4. **Flags & recommendations** — prioritised, each with the concrete action.
5. **Actions taken** — always "none (reporting-only)".
6. **FYI** — data quirks, cross-references, anything odd.

**Commit the report straight to `main` and push** (`git pull --rebase
origin main`, commit, `git push -u origin main`). Do not create a branch
and do not open a pull request — this is an append-only daily log, each run
adds one new file under `reports/` plus any playbook learnings, so there is
nothing to review. If a push is rejected because main moved, rebase and
push again. Post a short summary of the headline numbers and top
recommendations in the session. Keep the report under ~60 lines — it's a
daily brief, not an audit.
