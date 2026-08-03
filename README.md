# Loaded Dice — Daily GA4 Analysis

Automated daily analysis of the Loaded Dice GA4 property (373767946,
loadeddice.uk). A scheduled Claude session pulls yesterday's data through the
**Windsor.ai connector** (`googleanalytics4`), follows [`PLAYBOOK.md`](PLAYBOOK.md),
writes a dated report to [`reports/`](reports/), commits it, and posts a short
summary in the session.

This mirrors the sibling Google Ads routine
([caughtsmart/GoogleAds](https://github.com/caughtsmart/GoogleAds)) — same
cadence, same report shape, same repo layout.

## How it works

- **Schedule:** every morning at 07:00 UTC, after GA4 has finalised yesterday.
- **Data:** Windsor.ai `get_data` pulls — daily site totals and channel trend
  (30 days), item-level ecommerce (7 days). No Google Cloud project, service
  account, or API key needed.
- **Analysis:** yesterday vs previous day, same day last week, and the
  trailing 28-day average; anomaly flags at ±25% vs the 28-day norm with
  volume guards; top/flop products including the "interest but no sales"
  signal. Details in the playbook.
- **Output:** `reports/YYYY-MM-DD.md` (named for the run date, covering
  yesterday) — headline, channel table, products, flags & recommendations,
  actions taken (always none: reporting-only), FYI. Under ~60 lines.

## Reading the history

Every report is committed, so the folder doubles as the archive:
`git log --oneline reports/` or just browse the directory on GitHub.

## Changing the routine

Edit `PLAYBOOK.md` — thresholds, watch items, and report format all live
there. The daily session pulls the latest playbook from origin before each
run, so changes take effect the next morning.
