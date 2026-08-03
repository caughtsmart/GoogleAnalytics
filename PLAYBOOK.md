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

Standing watch items for the daily run:

- **Direct-channel bot flood (from 30 Jul 2026):** Direct sessions jumped
  from ~150–500/day to 8–10k/day with near-zero revenue, sessions≈users,
  ~1.1 pages/visit. Track its size daily; note that blended conversion rate
  is meaningless while it lasts. If it stops, say so and stand down the item.
- **Unassigned attribution breakage (from 2 Aug 2026):** Unassigned spiked
  to 6.3k sessions AND carried most of the day's revenue (£645 of £960) —
  purchases are losing their source attribution. Until fixed, channel
  revenue splits are unreliable. Flag daily; suggest checking consent
  mode / UTM handling if it persists.
- **Paid Search sessions roughly halved from 2 Aug 2026** — expected
  consequence of the Brand Search phrase negatives added by the Google Ads
  routine. Verify Paid Search *revenue* holds; only flag if it collapses too.

## Report format

Write `reports/YYYY-MM-DD.md` (named for the run date; it covers yesterday)
containing:

1. **Headline** — yesterday's visits, revenue, orders, conversion rate,
   vs 7-day average.
2. **Channel table** — last 30 days sessions + revenue per channel, and
   yesterday's figure with trend arrow.
3. **Products** — top sellers yesterday + the "interest but no sales"
   callout.
4. **Flags & recommendations** — prioritised, each with the concrete action.
5. **Actions taken** — always "none (reporting-only)".
6. **FYI** — data quirks, cross-references, anything odd.

Commit the report to the repo and push (branch
`claude/loaded-dice-ga4-analyst-tf6wkg`, or the default branch if that has
been merged and deleted). Post a short summary of the headline numbers and
top recommendations in the session. Keep the report under ~60 lines — it's
a daily brief, not an audit.
