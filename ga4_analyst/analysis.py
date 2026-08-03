"""Turns raw GA4 numbers into the things worth saying.

Baselines: previous day, same day last week, and the rolling ~28-day
average. Anomalies are threshold-based (default ±25% vs the 28-day
average) with minimum-volume guards so tiny numbers can't cry wolf.
"""

from __future__ import annotations

import datetime as dt
from collections import defaultdict
from dataclasses import dataclass, field

from .config import Config
from .models import Dataset, DayTotals


# --------------------------------------------------------------------------
# Result structures
# --------------------------------------------------------------------------

@dataclass
class Metric:
    """One headline number with its baselines."""

    key: str
    label: str
    value: float
    prev_day: float | None
    last_week: float | None
    avg_28: float | None
    kind: str = "int"  # int | money | pct

    def pct_vs(self, baseline: float | None) -> float | None:
        if baseline is None or baseline == 0:
            return None
        return (self.value - baseline) / baseline * 100


@dataclass
class ChannelStat:
    channel: str
    sessions: int
    share: float          # of yesterday's sessions
    avg_28: float
    pct_vs_avg: float | None
    delta_vs_avg: float   # absolute sessions vs 28-day average


@dataclass
class ProductStat:
    item: str
    views_yday: int = 0
    purchased_yday: int = 0
    revenue_yday: float = 0.0
    views_7d: int = 0
    purchased_7d: int = 0
    revenue_7d: float = 0.0


@dataclass
class Anomaly:
    severity: str   # "good" | "bad"
    text: str


@dataclass
class Analysis:
    date: dt.date
    metrics: dict[str, Metric] = field(default_factory=dict)
    channels: list[ChannelStat] = field(default_factory=list)
    top_sellers: list[ProductStat] = field(default_factory=list)
    most_viewed: list[ProductStat] = field(default_factory=list)
    stalled: list[ProductStat] = field(default_factory=list)   # interest, no sales
    anomalies: list[Anomaly] = field(default_factory=list)
    working: list[str] = field(default_factory=list)
    attention: list[str] = field(default_factory=list)
    one_thing: str = ""
    headline: str = ""
    daily: list[DayTotals] = field(default_factory=list)  # for the detail table


# --------------------------------------------------------------------------
# Formatting helpers (used here and by the report)
# --------------------------------------------------------------------------

def fmt_int(n: float) -> str:
    return f"{int(round(n)):,}"


def fmt_money(n: float, currency: str = "£") -> str:
    return f"{currency}{n:,.2f}" if n < 100 else f"{currency}{n:,.0f}"


def fmt_pct_value(n: float) -> str:
    return f"{n * 100:.1f}%"


def fmt_change(pct: float | None) -> str:
    """'↑ 18%' / '↓ 7%' / '→ flat' / 'n/a'."""
    if pct is None:
        return "n/a"
    if abs(pct) < 1:
        return "→ flat"
    arrow = "↑" if pct > 0 else "↓"
    return f"{arrow} {abs(pct):.0f}%"


def describe_change(pct: float | None) -> str:
    """Plain-English size of a move: 'up 18%', 'down a touch', etc."""
    if pct is None:
        return "no baseline yet"
    if abs(pct) < 1:
        return "flat"
    direction = "up" if pct > 0 else "down"
    return f"{direction} {abs(pct):.0f}%"


# --------------------------------------------------------------------------
# The analysis itself
# --------------------------------------------------------------------------

def analyse(data: Dataset, config: Config) -> Analysis:
    target = data.target_date
    by_date = {d.date: d for d in data.daily}
    yday = by_date.get(target, DayTotals(date=target))
    prev = by_date.get(target - dt.timedelta(days=1))
    last_week = by_date.get(target - dt.timedelta(days=7))
    window = [d for d in data.daily if d.date < target]

    def avg(fn) -> float | None:
        if not window:
            return None
        return sum(fn(d) for d in window) / len(window)

    a = Analysis(date=target, daily=data.daily)

    a.metrics = {
        m.key: m
        for m in [
            Metric("sessions", "Visits", yday.sessions,
                   prev.sessions if prev else None,
                   last_week.sessions if last_week else None,
                   avg(lambda d: d.sessions)),
            Metric("users", "Visitors", yday.users,
                   prev.users if prev else None,
                   last_week.users if last_week else None,
                   avg(lambda d: d.users)),
            Metric("revenue", "Revenue", yday.revenue,
                   prev.revenue if prev else None,
                   last_week.revenue if last_week else None,
                   avg(lambda d: d.revenue), kind="money"),
            Metric("purchases", "Orders", yday.purchases,
                   prev.purchases if prev else None,
                   last_week.purchases if last_week else None,
                   avg(lambda d: d.purchases)),
            Metric("conv_rate", "Conversion rate", yday.conv_rate,
                   prev.conv_rate if prev else None,
                   last_week.conv_rate if last_week else None,
                   avg(lambda d: d.conv_rate), kind="pct"),
            Metric("aov", "Average order", yday.aov,
                   prev.aov if prev else None,
                   last_week.aov if last_week else None,
                   avg(lambda d: d.aov), kind="money"),
        ]
    }

    _analyse_channels(a, data, config)
    _analyse_products(a, data, config)
    _find_anomalies(a, yday, config)
    _write_bullets(a, config)
    _pick_one_thing(a, config)
    _write_headline(a, config)
    return a


def _analyse_channels(a: Analysis, data: Dataset, config: Config) -> None:
    target = data.target_date
    yday_sessions: dict[str, int] = defaultdict(int)
    window_sessions: dict[str, list[int]] = defaultdict(list)
    window_days = max(
        1, len({c.date for c in data.channels if c.date < target})
    )

    for c in data.channels:
        if c.date == target:
            yday_sessions[c.channel] += c.sessions
        else:
            window_sessions[c.channel].append(c.sessions)

    total = sum(yday_sessions.values()) or 1
    stats = []
    for channel in set(yday_sessions) | set(window_sessions):
        sessions = yday_sessions.get(channel, 0)
        avg_28 = sum(window_sessions.get(channel, [])) / window_days
        pct = (sessions - avg_28) / avg_28 * 100 if avg_28 else None
        stats.append(
            ChannelStat(
                channel=channel,
                sessions=sessions,
                share=sessions / total,
                avg_28=avg_28,
                pct_vs_avg=pct,
                delta_vs_avg=sessions - avg_28,
            )
        )
    a.channels = sorted(stats, key=lambda s: -s.sessions)


def _analyse_products(a: Analysis, data: Dataset, config: Config) -> None:
    target = data.target_date
    stats: dict[str, ProductStat] = {}
    for p in data.products:
        s = stats.setdefault(p.item, ProductStat(item=p.item))
        s.views_7d += p.views
        s.purchased_7d += p.purchased
        s.revenue_7d += p.revenue
        if p.date == target:
            s.views_yday += p.views
            s.purchased_yday += p.purchased
            s.revenue_yday += p.revenue

    all_stats = list(stats.values())
    a.top_sellers = sorted(
        (s for s in all_stats if s.purchased_yday > 0),
        key=lambda s: (-s.revenue_yday, -s.purchased_yday),
    )[: config.top_n_products]
    a.most_viewed = sorted(all_stats, key=lambda s: -s.views_yday)[
        : config.top_n_products
    ]
    # Interest but no sales: well-viewed across the week, nothing bought.
    a.stalled = sorted(
        (
            s
            for s in all_stats
            if s.views_7d >= config.interest_no_sales_min_views
            and s.purchased_7d == 0
        ),
        key=lambda s: -s.views_7d,
    )[:3]


def _find_anomalies(a: Analysis, yday: DayTotals, config: Config) -> None:
    threshold = config.anomaly_threshold_pct
    currency = config.currency

    def volume_ok(metric: Metric) -> bool:
        # Ignore % swings when the underlying numbers are too small to matter.
        if metric.key in ("sessions", "users"):
            return max(metric.value, metric.avg_28 or 0) >= config.min_sessions_for_anomaly
        return yday.purchases >= config.min_purchases_for_anomaly or (
            a.metrics["purchases"].avg_28 or 0
        ) >= config.min_purchases_for_anomaly

    names = {
        "sessions": ("Visits", "were"),
        "revenue": ("Revenue", "was"),
        "purchases": ("Orders", "were"),
        "conv_rate": ("Conversion rate", "was"),
        "aov": ("Average order value", "was"),
    }
    for key, (name, verb) in names.items():
        m = a.metrics[key]
        pct = m.pct_vs(m.avg_28)
        if pct is None or abs(pct) < threshold or not volume_ok(m):
            continue
        if m.kind == "money":
            now = fmt_money(m.value, currency)
            usual = fmt_money(m.avg_28, currency)
        elif m.kind == "pct":
            now = fmt_pct_value(m.value)
            usual = fmt_pct_value(m.avg_28)
        else:
            now = fmt_int(m.value)
            usual = fmt_int(m.avg_28)
        a.anomalies.append(
            Anomaly(
                severity="good" if pct > 0 else "bad",
                text=(
                    f"{name} {verb} {describe_change(pct)} on the 28-day norm "
                    f"({now} vs a typical {usual})."
                ),
            )
        )

    # Channel-level spikes and crashes (only channels big enough to matter).
    for ch in a.channels:
        if ch.pct_vs_avg is None:
            continue
        big_enough = (
            max(ch.sessions, ch.avg_28) >= config.min_sessions_for_anomaly / 2
            and ch.share >= 0.03
        )
        if big_enough and abs(ch.pct_vs_avg) >= threshold:
            a.anomalies.append(
                Anomaly(
                    severity="good" if ch.pct_vs_avg > 0 else "bad",
                    text=(
                        f"{ch.channel} traffic was {describe_change(ch.pct_vs_avg)} "
                        f"vs its norm ({fmt_int(ch.sessions)} visits vs a typical "
                        f"{fmt_int(ch.avg_28)})."
                    ),
                )
            )

    # Checkout drop-off: people reaching checkout but not completing.
    if yday.checkouts >= config.min_purchases_for_anomaly * 2:
        completion = yday.purchases / yday.checkouts
        if completion < 0.4:
            a.anomalies.append(
                Anomaly(
                    severity="bad",
                    text=(
                        f"Only {completion * 100:.0f}% of shoppers who reached "
                        f"checkout actually bought ({yday.purchases} orders from "
                        f"{yday.checkouts} checkouts) — worth checking nothing is "
                        "broken at payment."
                    ),
                )
            )

    # A product suddenly selling hard.
    for s in a.top_sellers[:3]:
        prior = (s.purchased_7d - s.purchased_yday) / 6 if s.purchased_7d else 0
        if s.purchased_yday >= 3 and s.purchased_yday >= prior * 3:
            a.anomalies.append(
                Anomaly(
                    severity="good",
                    text=(
                        f"“{s.item}” suddenly took off: {s.purchased_yday} sold "
                        f"yesterday vs about {prior:.1f} a day over the previous "
                        "week. Check the stock level."
                    ),
                )
            )
            break


def _write_bullets(a: Analysis, config: Config) -> None:
    currency = config.currency
    sessions = a.metrics["sessions"]
    revenue = a.metrics["revenue"]
    conv = a.metrics["conv_rate"]
    aov = a.metrics["aov"]

    # What's working: strongest legitimate positives, biggest first.
    candidates_up: list[tuple[float, str]] = []
    pct = sessions.pct_vs(sessions.avg_28)
    if pct is not None and pct >= 8:
        driver = ""
        movers = [c for c in a.channels if c.delta_vs_avg > 0]
        if movers:
            top = max(movers, key=lambda c: c.delta_vs_avg)
            total_delta = sessions.value - (sessions.avg_28 or 0)
            if total_delta > 0 and top.delta_vs_avg / total_delta >= 0.5:
                driver = f" — almost all of it from {top.channel.lower()}"
            else:
                driver = f", led by {top.channel.lower()}"
        candidates_up.append(
            (pct, f"Traffic {describe_change(pct)} on a normal day "
                  f"({fmt_int(sessions.value)} visits){driver}.")
        )
    pct = revenue.pct_vs(revenue.avg_28)
    if pct is not None and pct >= 8:
        candidates_up.append(
            (pct, f"Takings {describe_change(pct)} on a normal day "
                  f"({fmt_money(revenue.value, currency)} from "
                  f"{fmt_int(a.metrics['purchases'].value)} orders).")
        )
    pct = conv.pct_vs(conv.avg_28)
    if pct is not None and pct >= 8:
        candidates_up.append(
            (pct, f"A better-than-usual share of visitors bought something "
                  f"({fmt_pct_value(conv.value)} vs a typical "
                  f"{fmt_pct_value(conv.avg_28)}).")
        )
    pct = aov.pct_vs(aov.avg_28)
    if pct is not None and pct >= 8:
        candidates_up.append(
            (pct, f"Baskets were bigger than usual — average order "
                  f"{fmt_money(aov.value, currency)}, {describe_change(pct)} "
                  "on the norm.")
        )
    if a.top_sellers:
        top = a.top_sellers[0]
        candidates_up.append(
            (5, f"“{top.item}” led the day: {top.purchased_yday} sold for "
                f"{fmt_money(top.revenue_yday, currency)}.")
        )
    a.working = [text for _, text in sorted(candidates_up, key=lambda t: -t[0])[:3]]
    if not a.working:
        a.working = ["Nothing shot the lights out — a steady, unremarkable day."]

    # Needs attention: anomalies first (bad ones), then soft negatives.
    attention: list[str] = [an.text for an in a.anomalies if an.severity == "bad"]
    if len(attention) < 3:
        pct = conv.pct_vs(conv.avg_28)
        if pct is not None and pct <= -10 and not any("Conversion" in t for t in attention):
            attention.append(
                f"Visitors were browsing but buying less than usual — conversion "
                f"{fmt_pct_value(conv.value)} vs a typical {fmt_pct_value(conv.avg_28)}."
            )
    if len(attention) < 3:
        drops = [
            c for c in a.channels
            if c.pct_vs_avg is not None and c.pct_vs_avg <= -15 and c.avg_28 >= 10
        ]
        for c in sorted(drops, key=lambda c: c.delta_vs_avg)[: 3 - len(attention)]:
            if not any(c.channel in t for t in attention):
                attention.append(
                    f"{c.channel} was quieter than usual "
                    f"({fmt_int(c.sessions)} visits, {describe_change(c.pct_vs_avg)} "
                    "vs its norm)."
                )
    if a.stalled and len(attention) < 3:
        s = a.stalled[0]
        attention.append(
            f"“{s.item}” had {fmt_int(s.views_7d)} looks this week and zero "
            "sales — lots of window shopping, no takers."
        )
    a.attention = attention[:3] or [
        "Nothing needs attention. Suspicious, but we'll take it."
    ]


def _pick_one_thing(a: Analysis, config: Config) -> None:
    conv = a.metrics["conv_rate"]
    sessions = a.metrics["sessions"]

    if a.stalled:
        s = a.stalled[0]
        a.one_thing = (
            f"“{s.item}” is pulling eyeballs ({fmt_int(s.views_7d)} views this "
            "week) but no orders. Check the price against rivals, refresh the "
            "photos, or give it a push in the next email — interest this warm "
            "shouldn't go to waste."
        )
        return

    bad_channels = [
        c for c in a.channels
        if c.pct_vs_avg is not None
        and c.pct_vs_avg <= -config.anomaly_threshold_pct
        and c.avg_28 >= config.min_sessions_for_anomaly / 2
    ]
    if bad_channels:
        c = min(bad_channels, key=lambda c: c.delta_vs_avg)
        a.one_thing = (
            f"{c.channel} has gone quiet ({describe_change(c.pct_vs_avg)} vs "
            "normal). Worth checking the obvious: paused campaigns, a dropped "
            "ranking, or a broken link in whatever was driving it."
        )
        return

    conv_pct = conv.pct_vs(conv.avg_28)
    traffic_pct = sessions.pct_vs(sessions.avg_28)
    if conv_pct is not None and conv_pct <= -15 and (traffic_pct or 0) >= -5:
        a.one_thing = (
            "Plenty of people through the door, fewer at the till — conversion "
            f"was {describe_change(conv_pct)} on normal. Do a quick test order "
            "on mobile and check the checkout isn't misbehaving."
        )
        return

    spikes = [an for an in a.anomalies if an.severity == "good"]
    if spikes:
        good_channels = [
            c for c in a.channels
            if c.pct_vs_avg is not None and c.pct_vs_avg >= config.anomaly_threshold_pct
            and c.avg_28 >= 10
        ]
        if good_channels:
            c = max(good_channels, key=lambda c: c.delta_vs_avg)
            a.one_thing = (
                f"{c.channel} is running hot ({describe_change(c.pct_vs_avg)} vs "
                "normal). Find out what's driving it and feed the fire — that "
                "kind of momentum is cheaper to keep than to restart."
            )
            return

    if a.top_sellers:
        top = a.top_sellers[0]
        a.one_thing = (
            f"Steady day. If you want one lever to pull: “{top.item}” is "
            "selling — make sure it's stocked and visible on the homepage."
        )
    else:
        a.one_thing = (
            "Steady, quiet day with no orders logged. If that doesn't match "
            "the till, check GA4's purchase tracking is still firing."
        )


def _write_headline(a: Analysis, config: Config) -> None:
    """Short phrase for the email subject, e.g. 'revenue up 22%, one product stalling'."""
    bits: list[str] = []
    revenue = a.metrics["revenue"]
    sessions = a.metrics["sessions"]
    rev_pct = revenue.pct_vs(revenue.avg_28)
    ses_pct = sessions.pct_vs(sessions.avg_28)

    if rev_pct is not None and abs(rev_pct) >= 10:
        bits.append(f"revenue {describe_change(rev_pct)}")
    if ses_pct is not None and abs(ses_pct) >= 10 and len(bits) < 2:
        bits.append(f"traffic {describe_change(ses_pct)}")
    if a.stalled and len(bits) < 2:
        bits.append("one product stalling")
    bad = [an for an in a.anomalies if an.severity == "bad"]
    if bad and len(bits) < 2 and not a.stalled:
        bits.append(f"{len(bad)} thing{'s' if len(bad) > 1 else ''} to check")
    if not bits:
        bits.append("a steady day")
    a.headline = ", ".join(bits[:2])
