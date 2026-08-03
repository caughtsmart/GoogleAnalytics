#!/usr/bin/env python3
"""Loaded Dice daily GA4 analyst — entry point.

Typical uses:
  python run_daily_report.py                 # yesterday's report, save + email
  python run_daily_report.py --no-email      # save the file only
  python run_daily_report.py --date 2026-08-01
  python run_daily_report.py --demo --stdout # synthetic data, print to terminal

If the run fails for any reason, a short "couldn't run today" email is sent
instead of failing silently (unless email is disabled).
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys
import traceback
from pathlib import Path
from zoneinfo import ZoneInfo

from ga4_analyst.analysis import analyse
from ga4_analyst.config import load_config
from ga4_analyst.report import build_subject, render_html, render_text


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Daily GA4 report for Loaded Dice")
    p.add_argument("--config", default="config.yaml", help="path to config file")
    p.add_argument("--date", help="report date YYYY-MM-DD (default: yesterday)")
    p.add_argument("--demo", action="store_true",
                   help="use synthetic data (no GA4 credentials needed)")
    p.add_argument("--no-email", action="store_true", help="skip sending email")
    p.add_argument("--stdout", action="store_true",
                   help="print the plain-text report to the terminal")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    config = load_config(args.config)

    if args.date:
        target = dt.date.fromisoformat(args.date)
    else:
        now = dt.datetime.now(ZoneInfo(config.timezone))
        target = now.date() - dt.timedelta(days=1)
    date_label = target.strftime("%a %-d %b %Y")

    send_email = config.email.enabled and not args.no_email

    try:
        if args.demo:
            from ga4_analyst.demo_source import DemoSource
            source = DemoSource(config)
        else:
            from ga4_analyst.ga4_source import GA4Source
            source = GA4Source(config)

        print(f"Fetching GA4 data for {target.isoformat()}"
              f"{' (demo mode)' if args.demo else ''}...")
        data = source.fetch(target)

        if not args.demo and all(d.sessions == 0 for d in data.daily):
            raise RuntimeError(
                "GA4 returned zero sessions for the whole window — the "
                "property ID may be wrong, the service account may lack "
                "access, or the property has no data yet."
            )

        analysis = analyse(data, config)
        html = render_html(analysis, config)
        text = render_text(analysis, config)
        subject = build_subject(analysis)

        reports_dir = Path(config.reports_dir)
        reports_dir.mkdir(parents=True, exist_ok=True)
        out_path = reports_dir / f"ga4-report-{target.isoformat()}.html"
        out_path.write_text(html, encoding="utf-8")
        print(f"Saved: {out_path}")

        if args.stdout:
            print("\n" + text + "\n")

        if send_email:
            from ga4_analyst.emailer import send_report
            send_report(config.email, subject, text, html)
            print(f"Emailed to {', '.join(config.email.to)}: {subject}")
        else:
            print(f"Email skipped. Subject would have been: {subject}")

        return 0

    except Exception as exc:  # noqa: BLE001 — top-level: report, don't crash silently
        traceback.print_exc()
        if send_email:
            try:
                from ga4_analyst.emailer import send_failure_note
                send_failure_note(config.email, date_label, f"{type(exc).__name__}: {exc}")
                print("Sent 'couldn't run today' email.")
            except Exception as mail_exc:  # noqa: BLE001
                print(f"Also failed to send the failure email: {mail_exc}",
                      file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
