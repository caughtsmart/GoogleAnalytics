# Loaded Dice — Daily GA4 Analyst

Every morning this job pulls **yesterday's Google Analytics 4 data**, compares
it against sensible baselines, works out what actually matters, and delivers a
**one-page plain-English report** — emailed to Graham and saved as a dated HTML
file. Written for marketing to read over a coffee, not for analysts.

**What the report covers** (each with the change vs baseline and a "so what"):

1. **Yesterday at a glance** — visits, revenue, orders, conversion rate.
2. **What's working** — the 2–3 genuinely good things.
3. **What needs attention** — soft spots and anomaly alerts.
4. **Products** — top sellers, plus the "lots of interest, no sales" callout.
5. **One thing to consider today** — a single suggested action.

Full detail (baseline tables, channel breakdown, most-viewed products, every
flag raised) sits below the summary in the same file.

**Baselines:** previous day, same day last week, and a rolling 28-day average.
**Anomaly flagging:** threshold-based (default ±25% vs the 28-day average) with
minimum-volume guards, so it stays quiet on normal days and speaks up on odd ones.

A sample of the output is in [`docs/sample-report.html`](docs/sample-report.html).

---

## Try it right now (no credentials needed)

```bash
pip install -r requirements.txt
cp config.example.yaml config.yaml
python run_daily_report.py --demo --no-email --stdout
```

`--demo` generates plausible synthetic shop data so you can see exactly what a
report looks like before GA4 is wired up.

## One-time GA4 setup

1. **GA4 Property ID** — the *numeric* ID from GA4 → Admin → Property Settings
   (not the `G-XXXX` measurement ID).
2. **Google Cloud project** — create or reuse one at
   [console.cloud.google.com](https://console.cloud.google.com).
3. **Enable the Google Analytics Data API** in that project
   (APIs & Services → Library → "Google Analytics Data API").
4. **Service account + JSON key** — IAM & Admin → Service Accounts → create one,
   then Keys → Add key → JSON. Save the file as
   `secrets/service-account.json` (the folder is gitignored).
5. **Grant access** — GA4 → Admin → Property Access Management → add the
   service account's email address as **Viewer**.

> The JSON key is a password. Never commit it, never email it. `secrets/`,
> `config.yaml` and `*service-account*.json` are all gitignored already.

Then edit `config.yaml`:

- `ga4.property_id` — your numeric property ID
- `email.*` — SMTP details for the sending mailbox (a Google Workspace
  [app password](https://support.google.com/accounts/answer/185833) works well)
- set the SMTP password as an environment variable, not in the file:
  `export GA4_SMTP_PASSWORD="..."`

## Running it

```bash
python run_daily_report.py                  # yesterday: save + email
python run_daily_report.py --no-email       # save the file only
python run_daily_report.py --date 2026-08-01
python run_daily_report.py --stdout         # also print the text version
```

Each run writes `reports/ga4-report-YYYY-MM-DD.html` and (unless disabled)
emails the same report. If a run fails — API down, bad credentials, no data —
it emails a short *"couldn't run today"* note instead of failing silently.

## Scheduling the daily run

GA4 takes a few hours to finalise a day, so run for **yesterday**, after
~06:00 UK.

**Option A — GitHub Actions (no server needed).** The workflow in
`.github/workflows/daily-report.yml` runs at 06:15 UTC daily. Enable it by
adding three repository secrets (Settings → Secrets and variables → Actions):

| Secret                     | Contents                                  |
| -------------------------- | ----------------------------------------- |
| `GA4_CONFIG_YAML`          | your full `config.yaml`                   |
| `GA4_SERVICE_ACCOUNT_JSON` | the full service account JSON key         |
| `GA4_SMTP_PASSWORD`        | the SMTP/app password                     |

Until the secrets exist the workflow skips harmlessly. It also commits each
dated report into `reports/` so the history is browsable on GitHub, and you can
trigger a run manually from the Actions tab ("Run workflow").

**Option B — cron on any always-on machine:**

```cron
# 06:30 UK time every day
30 6 * * * cd /path/to/GoogleAnalytics && GA4_SMTP_PASSWORD="..." /usr/bin/python3 run_daily_report.py >> cron.log 2>&1
```

**Option C — a Cowork/Claude scheduled task** that runs
`python run_daily_report.py` each morning.

## Tuning

All knobs live in `config.yaml`:

- `anomalies.threshold_pct` — how big a move (vs the 28-day average) gets
  flagged. Raise it if the report cries wolf; lower it if it's too quiet.
- `anomalies.min_sessions` / `min_purchases` — volume guards so a jump from
  2 to 4 visits doesn't make headlines.
- `products.interest_no_sales_min_views` — weekly views needed before a
  never-bought product gets called out.
- `baselines.rolling_days` — the window that defines "normal".

## Project layout

```
run_daily_report.py        entry point / CLI
ga4_analyst/
  config.py                config loading (config.yaml + env vars)
  models.py                shared data structures
  ga4_source.py            GA4 Data API pulls (runReport)
  demo_source.py           synthetic data for --demo
  analysis.py              baselines, anomaly detection, insight writing
  report.py                one-page HTML + plain-text rendering
  emailer.py               SMTP delivery + failure notes
config.example.yaml        copy to config.yaml and fill in
.github/workflows/         optional daily scheduler
docs/sample-report.html    what the output looks like
```

## Later (not day one)

Ideas already on the list: cross-reference with Shopify sales, a Monday weekly
roll-up, sparkline charts in the HTML, and campaign-level attribution.
