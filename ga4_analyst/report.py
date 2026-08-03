"""Renders the analysis as a one-page report.

Two outputs from the same analysis: an HTML page (saved to disk and used
as the email body) and a plain-text version (email fallback / stdout).
The scannable summary comes first; the fuller detail tables sit below it.
"""

from __future__ import annotations

import html

from .analysis import (
    Analysis,
    Metric,
    fmt_change,
    fmt_int,
    fmt_money,
    fmt_pct_value,
)
from .config import Config

GLANCE_KEYS = ["sessions", "revenue", "purchases", "conv_rate"]


def _fmt_value(m: Metric, currency: str) -> str:
    if m.kind == "money":
        return fmt_money(m.value, currency)
    if m.kind == "pct":
        return fmt_pct_value(m.value)
    return fmt_int(m.value)


def _fmt_baseline(m: Metric, value: float | None, currency: str) -> str:
    if value is None:
        return "–"
    if m.kind == "money":
        return fmt_money(value, currency)
    if m.kind == "pct":
        return fmt_pct_value(value)
    return fmt_int(value)


def build_subject(a: Analysis) -> str:
    day = a.date.strftime("%a %-d %b")
    return f"Loaded Dice GA4 — {day}: {a.headline}"


# --------------------------------------------------------------------------
# Plain text
# --------------------------------------------------------------------------

def render_text(a: Analysis, config: Config) -> str:
    c = config.currency
    lines: list[str] = []
    day = a.date.strftime("%A %-d %B %Y")
    lines.append(f"LOADED DICE — GA4 DAILY REPORT — {day}")
    lines.append("=" * 60)

    lines.append("\nYESTERDAY AT A GLANCE")
    for key in GLANCE_KEYS:
        m = a.metrics[key]
        lines.append(
            f"  {m.label}: {_fmt_value(m, c)}  "
            f"({fmt_change(m.pct_vs(m.avg_28))} vs 28-day norm, "
            f"{fmt_change(m.pct_vs(m.last_week))} vs last {a.date.strftime('%A')})"
        )

    lines.append("\nWHAT'S WORKING")
    lines.extend(f"  • {b}" for b in a.working)

    lines.append("\nWHAT NEEDS ATTENTION")
    lines.extend(f"  • {b}" for b in a.attention)

    lines.append("\nPRODUCTS")
    if a.top_sellers:
        for s in a.top_sellers[:3]:
            lines.append(
                f"  • {s.item} — {s.purchased_yday} sold, "
                f"{fmt_money(s.revenue_yday, c)}"
            )
    else:
        lines.append("  • No product sales recorded yesterday.")
    if a.stalled:
        s = a.stalled[0]
        lines.append(
            f"  • Interest but no sales: {s.item} "
            f"({fmt_int(s.views_7d)} views this week, 0 bought)"
        )

    lines.append("\nONE THING TO CONSIDER TODAY")
    lines.append(f"  {a.one_thing}")

    lines.append("\n" + "-" * 60)
    lines.append("Full detail is in the saved HTML report.")
    return "\n".join(lines)


# --------------------------------------------------------------------------
# HTML
# --------------------------------------------------------------------------

def render_html(a: Analysis, config: Config) -> str:
    c = config.currency
    e = html.escape
    day = a.date.strftime("%A %-d %B %Y")

    glance_cells = ""
    for key in GLANCE_KEYS:
        m = a.metrics[key]
        pct = m.pct_vs(m.avg_28)
        colour = "#6b7280" if pct is None or abs(pct) < 1 else (
            "#15803d" if pct > 0 else "#b91c1c"
        )
        glance_cells += f"""
        <td style="padding:14px 10px;text-align:center;background:#f8fafc;
                   border-radius:10px;">
          <div style="font-size:12px;color:#6b7280;text-transform:uppercase;
                      letter-spacing:.05em;">{e(m.label)}</div>
          <div style="font-size:26px;font-weight:700;color:#111827;
                      margin:4px 0 2px;">{_fmt_value(m, c)}</div>
          <div style="font-size:13px;font-weight:600;color:{colour};">
            {fmt_change(pct)} <span style="color:#9ca3af;font-weight:400;">vs normal</span>
          </div>
        </td>"""

    def bullet_list(items: list[str]) -> str:
        return "".join(
            f'<li style="margin:6px 0;line-height:1.45;">{e(t)}</li>' for t in items
        )

    sellers_rows = ""
    for s in a.top_sellers:
        sellers_rows += (
            f'<li style="margin:6px 0;line-height:1.45;"><strong>{e(s.item)}</strong>'
            f" — {s.purchased_yday} sold, {fmt_money(s.revenue_yday, c)}</li>"
        )
    if not sellers_rows:
        sellers_rows = '<li style="margin:6px 0;">No product sales recorded yesterday.</li>'
    stalled_html = ""
    if a.stalled:
        s = a.stalled[0]
        stalled_html = (
            f'<p style="margin:10px 0 0;padding:10px 12px;background:#fefce8;'
            f'border-left:3px solid #eab308;border-radius:6px;line-height:1.45;">'
            f"👀 <strong>Interest but no sales:</strong> “{e(s.item)}” — "
            f"{fmt_int(s.views_7d)} views this week, nothing bought.</p>"
        )

    # ---- detail tables (below the fold) ----
    detail_metric_rows = ""
    for m in a.metrics.values():
        detail_metric_rows += f"""
        <tr>
          <td style="padding:6px 10px;border-bottom:1px solid #e5e7eb;">{e(m.label)}</td>
          <td style="padding:6px 10px;border-bottom:1px solid #e5e7eb;text-align:right;">{_fmt_value(m, c)}</td>
          <td style="padding:6px 10px;border-bottom:1px solid #e5e7eb;text-align:right;">{_fmt_baseline(m, m.prev_day, c)} ({fmt_change(m.pct_vs(m.prev_day))})</td>
          <td style="padding:6px 10px;border-bottom:1px solid #e5e7eb;text-align:right;">{_fmt_baseline(m, m.last_week, c)} ({fmt_change(m.pct_vs(m.last_week))})</td>
          <td style="padding:6px 10px;border-bottom:1px solid #e5e7eb;text-align:right;">{_fmt_baseline(m, m.avg_28, c)} ({fmt_change(m.pct_vs(m.avg_28))})</td>
        </tr>"""

    channel_rows = ""
    for ch in a.channels:
        if ch.sessions == 0 and ch.avg_28 < 1:
            continue
        channel_rows += f"""
        <tr>
          <td style="padding:6px 10px;border-bottom:1px solid #e5e7eb;">{e(ch.channel)}</td>
          <td style="padding:6px 10px;border-bottom:1px solid #e5e7eb;text-align:right;">{fmt_int(ch.sessions)}</td>
          <td style="padding:6px 10px;border-bottom:1px solid #e5e7eb;text-align:right;">{ch.share * 100:.0f}%</td>
          <td style="padding:6px 10px;border-bottom:1px solid #e5e7eb;text-align:right;">{fmt_int(ch.avg_28)}</td>
          <td style="padding:6px 10px;border-bottom:1px solid #e5e7eb;text-align:right;">{fmt_change(ch.pct_vs_avg)}</td>
        </tr>"""

    viewed_rows = ""
    for s in a.most_viewed:
        viewed_rows += f"""
        <tr>
          <td style="padding:6px 10px;border-bottom:1px solid #e5e7eb;">{e(s.item)}</td>
          <td style="padding:6px 10px;border-bottom:1px solid #e5e7eb;text-align:right;">{fmt_int(s.views_yday)}</td>
          <td style="padding:6px 10px;border-bottom:1px solid #e5e7eb;text-align:right;">{s.purchased_yday}</td>
          <td style="padding:6px 10px;border-bottom:1px solid #e5e7eb;text-align:right;">{fmt_int(s.views_7d)}</td>
          <td style="padding:6px 10px;border-bottom:1px solid #e5e7eb;text-align:right;">{s.purchased_7d}</td>
        </tr>"""

    anomalies_html = ""
    if a.anomalies:
        rows = "".join(
            f'<li style="margin:6px 0;line-height:1.45;">'
            f'{"🟢" if an.severity == "good" else "🔴"} {e(an.text)}</li>'
            for an in a.anomalies
        )
        anomalies_html = f"""
      <h3 style="font-size:15px;margin:22px 0 6px;color:#111827;">All flags raised</h3>
      <ul style="margin:0;padding-left:20px;color:#374151;">{rows}</ul>"""

    th = ('style="padding:6px 10px;text-align:right;font-size:12px;color:#6b7280;'
          'text-transform:uppercase;letter-spacing:.04em;border-bottom:2px solid #d1d5db;"')
    th_left = th.replace("text-align:right", "text-align:left")

    return f"""<!doctype html>
<html lang="en-GB">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Loaded Dice GA4 — {e(day)}</title>
</head>
<body style="margin:0;padding:0;background:#eef1f5;font-family:-apple-system,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;color:#111827;">
<div style="max-width:680px;margin:0 auto;padding:24px 16px;">

  <div style="background:#111827;color:#fff;border-radius:12px 12px 0 0;padding:18px 24px;">
    <div style="font-size:13px;letter-spacing:.08em;text-transform:uppercase;color:#9ca3af;">Loaded Dice · Daily GA4 report</div>
    <div style="font-size:21px;font-weight:700;margin-top:2px;">{e(day)}</div>
    <div style="font-size:14px;color:#d1d5db;margin-top:2px;">{e(a.headline[:1].upper() + a.headline[1:])}</div>
  </div>

  <div style="background:#ffffff;border-radius:0 0 12px 12px;padding:22px 24px 26px;">

    <h2 style="font-size:16px;margin:0 0 10px;color:#111827;">Yesterday at a glance</h2>
    <table role="presentation" width="100%" cellspacing="6" cellpadding="0" style="border-collapse:separate;">
      <tr>{glance_cells}
      </tr>
    </table>

    <h2 style="font-size:16px;margin:22px 0 6px;color:#15803d;">✅ What's working</h2>
    <ul style="margin:0;padding-left:20px;color:#374151;">{bullet_list(a.working)}</ul>

    <h2 style="font-size:16px;margin:22px 0 6px;color:#b91c1c;">⚠️ What needs attention</h2>
    <ul style="margin:0;padding-left:20px;color:#374151;">{bullet_list(a.attention)}</ul>

    <h2 style="font-size:16px;margin:22px 0 6px;color:#111827;">🛒 Products</h2>
    <ul style="margin:0;padding-left:20px;color:#374151;">{sellers_rows}</ul>
    {stalled_html}

    <div style="margin-top:24px;padding:14px 16px;background:#eff6ff;border-left:3px solid #2563eb;border-radius:6px;">
      <div style="font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:.05em;color:#2563eb;">One thing to consider today</div>
      <div style="margin-top:4px;line-height:1.5;color:#1f2937;">{e(a.one_thing)}</div>
    </div>

    <hr style="border:none;border-top:1px solid #e5e7eb;margin:28px 0 18px;">
    <p style="font-size:12px;color:#9ca3af;margin:0 0 4px;">The detail, for anyone who wants to dig in ↓</p>

    <h3 style="font-size:15px;margin:18px 0 6px;color:#111827;">Key numbers vs baselines</h3>
    <table width="100%" cellspacing="0" cellpadding="0" style="border-collapse:collapse;font-size:13px;">
      <tr><th {th_left}>Metric</th><th {th}>Yesterday</th><th {th}>Day before</th><th {th}>Same day last week</th><th {th}>28-day avg</th></tr>
      {detail_metric_rows}
    </table>

    <h3 style="font-size:15px;margin:22px 0 6px;color:#111827;">Where visitors came from</h3>
    <table width="100%" cellspacing="0" cellpadding="0" style="border-collapse:collapse;font-size:13px;">
      <tr><th {th_left}>Channel</th><th {th}>Visits</th><th {th}>Share</th><th {th}>28-day avg</th><th {th}>vs normal</th></tr>
      {channel_rows}
    </table>

    <h3 style="font-size:15px;margin:22px 0 6px;color:#111827;">Most-viewed products</h3>
    <table width="100%" cellspacing="0" cellpadding="0" style="border-collapse:collapse;font-size:13px;">
      <tr><th {th_left}>Product</th><th {th}>Views yday</th><th {th}>Sold yday</th><th {th}>Views 7d</th><th {th}>Sold 7d</th></tr>
      {viewed_rows}
    </table>
    {anomalies_html}

    <p style="font-size:11px;color:#9ca3af;margin-top:26px;">
      Baselines: “normal” = the rolling 28-day average. Conversion rate =
      orders ÷ visits. Generated automatically from GA4 — if a number looks
      mad, check tracking before panicking.
    </p>
  </div>
</div>
</body>
</html>"""
