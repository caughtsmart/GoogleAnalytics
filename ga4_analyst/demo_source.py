"""Synthetic data generator so the whole pipeline can be tested
before GA4 credentials exist (run_daily_report.py --demo).

Numbers are seeded by date, so the same day always produces the same
report. The generated "yesterday" deliberately includes an organic-search
spike and one much-viewed-never-bought product, so you can see what the
report looks like when it has something to say.
"""

from __future__ import annotations

import datetime as dt
import random

from .config import Config
from .models import ChannelDay, Dataset, DayTotals, ProductDay

CHANNELS = {
    "Organic search": 0.38,
    "Direct": 0.22,
    "Paid search": 0.12,
    "Social": 0.10,
    "Email": 0.08,
    "Referral": 0.06,
    "Paid social": 0.04,
}

PRODUCTS = [
    ("Warhammer 40k Combat Patrol: Orks", 55.0, 0.045),
    ("Pokemon TCG Prismatic Evolutions Booster Box", 145.0, 0.06),
    ("MTG Bloomburrow Play Booster Box", 115.0, 0.05),
    ("Citadel Paint Set: Mega Bundle", 89.0, 0.03),
    ("Disney Lorcana Fabled Booster Box", 120.0, 0.04),
    ("One Piece OP-11 Booster Box", 75.0, 0.055),
    ("Age of Sigmar Spearhead: Stormcast", 47.5, 0.035),
    ("Necron Warriors Squad", 28.5, 0.04),
    ("D&D Player's Handbook 2024", 42.0, 0.045),
    ("Ticket to Ride: Europe", 39.0, 0.03),
    ("Kill Team: Hivestorm Box", 105.0, 0.05),
    ("Vallejo Game Color 72-Set", 130.0, 0.02),
    ("Star Wars Unlimited Booster Box", 85.0, 0.04),
    ("Catan Board Game", 35.0, 0.035),
    ("Blood Bowl Second Season Edition", 65.0, 0.025),
]

# The demo's "interest but no sales" product: viewed a lot, never bought.
STALLED_PRODUCT = ("Horus Heresy Age of Darkness Box", 180.0, 0.0)


class DemoSource:
    """Drop-in replacement for GA4Source that invents plausible data."""

    def __init__(self, config: Config):
        self._config = config

    def fetch(self, target_date: dt.date) -> Dataset:
        window_start = target_date - dt.timedelta(days=self._config.rolling_days)
        daily: list[DayTotals] = []
        channels: list[ChannelDay] = []
        products: list[ProductDay] = []

        day = window_start
        while day <= target_date:
            rng = random.Random(f"loaded-dice-{day.isoformat()}")
            is_target = day == target_date
            # Weekend bump, gentle weekday rhythm.
            weekday_factor = [0.95, 0.9, 0.92, 0.97, 1.05, 1.25, 1.2][day.weekday()]
            base_sessions = 420 * weekday_factor * rng.uniform(0.88, 1.12)

            # Make the demo's target day interesting: organic spike.
            organic_boost = 1.45 if is_target else 1.0

            day_channels = {}
            for channel, share in CHANNELS.items():
                sessions = base_sessions * share * rng.uniform(0.85, 1.15)
                if channel == "Organic search":
                    sessions *= organic_boost
                day_channels[channel] = int(sessions)

            sessions = sum(day_channels.values())
            users = int(sessions * rng.uniform(0.78, 0.86))
            page_views = int(sessions * rng.uniform(3.2, 4.1))

            # Product-level activity, summed up into the day's ecommerce totals.
            day_purchases = 0
            day_revenue = 0.0
            if day >= target_date - dt.timedelta(days=6):
                catalogue = PRODUCTS + [STALLED_PRODUCT]
            else:
                catalogue = PRODUCTS
            for name, price, buy_rate in catalogue:
                views = int(sessions * rng.uniform(0.01, 0.06))
                if name == STALLED_PRODUCT[0]:
                    views = int(sessions * rng.uniform(0.08, 0.11))  # hot page
                purchased = sum(
                    1 for _ in range(views) if rng.random() < buy_rate
                )
                revenue = purchased * price * rng.uniform(0.95, 1.05)
                carts = purchased + int(views * rng.uniform(0.01, 0.03))
                if day >= target_date - dt.timedelta(days=6):
                    products.append(
                        ProductDay(
                            date=day,
                            item=name,
                            views=views,
                            added_to_cart=carts,
                            purchased=purchased,
                            revenue=round(revenue, 2),
                        )
                    )
                day_purchases += purchased
                day_revenue += revenue

            add_to_carts = int(day_purchases * rng.uniform(2.2, 2.9))
            checkouts = int(day_purchases * rng.uniform(1.3, 1.7))

            daily.append(
                DayTotals(
                    date=day,
                    sessions=sessions,
                    users=users,
                    page_views=page_views,
                    add_to_carts=add_to_carts,
                    checkouts=checkouts,
                    purchases=day_purchases,
                    revenue=round(day_revenue, 2),
                )
            )

            revenue_split = rng.uniform(0.85, 1.15)
            for channel, ch_sessions in day_channels.items():
                share = ch_sessions / sessions if sessions else 0
                channels.append(
                    ChannelDay(
                        date=day,
                        channel=channel,
                        sessions=ch_sessions,
                        revenue=round(day_revenue * share * revenue_split, 2),
                    )
                )

            day += dt.timedelta(days=1)

        return Dataset(
            target_date=target_date, daily=daily, channels=channels, products=products
        )
