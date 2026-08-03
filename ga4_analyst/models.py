"""Plain data structures shared between the fetchers, analysis and report."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field


@dataclass
class DayTotals:
    """Site-wide totals for one calendar day."""

    date: dt.date
    sessions: int = 0
    users: int = 0
    page_views: int = 0
    add_to_carts: int = 0
    checkouts: int = 0
    purchases: int = 0
    revenue: float = 0.0

    @property
    def conv_rate(self) -> float:
        """Purchases per session, as a fraction (0.023 = 2.3%)."""
        return self.purchases / self.sessions if self.sessions else 0.0

    @property
    def aov(self) -> float:
        """Average order value."""
        return self.revenue / self.purchases if self.purchases else 0.0


@dataclass
class ChannelDay:
    """Sessions/revenue for one channel on one day."""

    date: dt.date
    channel: str
    sessions: int = 0
    revenue: float = 0.0


@dataclass
class ProductDay:
    """Item-level ecommerce stats for one product on one day."""

    date: dt.date
    item: str
    views: int = 0
    added_to_cart: int = 0
    purchased: int = 0
    revenue: float = 0.0


@dataclass
class Dataset:
    """Everything one run pulls from GA4 (or the demo generator).

    daily covers the target day plus the rolling baseline window before it.
    channels covers the same range. products covers the target day plus the
    previous 6 days (a 7-day window for the "interest but no sales" signal).
    """

    target_date: dt.date
    daily: list[DayTotals] = field(default_factory=list)
    channels: list[ChannelDay] = field(default_factory=list)
    products: list[ProductDay] = field(default_factory=list)
