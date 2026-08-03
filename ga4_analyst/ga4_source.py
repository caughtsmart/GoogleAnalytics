"""Pulls the data we need from the GA4 Data API (runReport).

Three reports per run:
  1. Daily site totals for the target day + the rolling baseline window.
  2. Daily sessions/revenue by default channel group, same range.
  3. Item-level ecommerce stats for the last 7 days ending on the target day.
"""

from __future__ import annotations

import datetime as dt

from .config import Config
from .models import ChannelDay, Dataset, DayTotals, ProductDay

# Channel groups GA4 reports that we fold into friendlier names.
CHANNEL_LABELS = {
    "Organic Search": "Organic search",
    "Paid Search": "Paid search",
    "Paid Social": "Paid social",
    "Organic Social": "Social",
    "Direct": "Direct",
    "Referral": "Referral",
    "Email": "Email",
    "Organic Shopping": "Organic shopping",
    "Paid Shopping": "Paid shopping",
    "Display": "Display ads",
    "Unassigned": "Other/unknown",
}


def _label(channel: str) -> str:
    return CHANNEL_LABELS.get(channel, channel)


class GA4Source:
    """Thin wrapper around the official google-analytics-data client."""

    def __init__(self, config: Config):
        # Imported here so demo mode works without the Google libraries.
        from google.analytics.data_v1beta import BetaAnalyticsDataClient
        from google.oauth2 import service_account

        if not config.property_id:
            raise ValueError("ga4.property_id is not set in config.yaml")
        if not config.credentials_file:
            raise ValueError("ga4.credentials_file is not set in config.yaml")

        credentials = service_account.Credentials.from_service_account_file(
            config.credentials_file,
            scopes=["https://www.googleapis.com/auth/analytics.readonly"],
        )
        self._client = BetaAnalyticsDataClient(credentials=credentials)
        self._property = f"properties/{config.property_id}"
        self._config = config

    def fetch(self, target_date: dt.date) -> Dataset:
        window_start = target_date - dt.timedelta(days=self._config.rolling_days)
        product_start = target_date - dt.timedelta(days=6)
        return Dataset(
            target_date=target_date,
            daily=self._fetch_daily(window_start, target_date),
            channels=self._fetch_channels(window_start, target_date),
            products=self._fetch_products(product_start, target_date),
        )

    # -- individual reports ------------------------------------------------

    def _run(self, dimensions, metrics, start: dt.date, end: dt.date):
        from google.analytics.data_v1beta.types import (
            DateRange,
            Dimension,
            Metric,
            RunReportRequest,
        )

        request = RunReportRequest(
            property=self._property,
            dimensions=[Dimension(name=d) for d in dimensions],
            metrics=[Metric(name=m) for m in metrics],
            date_ranges=[
                DateRange(start_date=start.isoformat(), end_date=end.isoformat())
            ],
            limit=100000,
        )
        return self._client.run_report(request)

    def _fetch_daily(self, start: dt.date, end: dt.date) -> list[DayTotals]:
        response = self._run(
            ["date"],
            [
                "sessions",
                "totalUsers",
                "screenPageViews",
                "addToCarts",
                "checkouts",
                "ecommercePurchases",
                "purchaseRevenue",
            ],
            start,
            end,
        )
        days: dict[dt.date, DayTotals] = {}
        for row in response.rows:
            date = dt.datetime.strptime(row.dimension_values[0].value, "%Y%m%d").date()
            values = [v.value for v in row.metric_values]
            days[date] = DayTotals(
                date=date,
                sessions=int(float(values[0] or 0)),
                users=int(float(values[1] or 0)),
                page_views=int(float(values[2] or 0)),
                add_to_carts=int(float(values[3] or 0)),
                checkouts=int(float(values[4] or 0)),
                purchases=int(float(values[5] or 0)),
                revenue=float(values[6] or 0),
            )
        # Fill any missing days with zeros so baselines stay honest.
        out = []
        day = start
        while day <= end:
            out.append(days.get(day, DayTotals(date=day)))
            day += dt.timedelta(days=1)
        return out

    def _fetch_channels(self, start: dt.date, end: dt.date) -> list[ChannelDay]:
        response = self._run(
            ["date", "sessionDefaultChannelGroup"],
            ["sessions", "purchaseRevenue"],
            start,
            end,
        )
        out = []
        for row in response.rows:
            date = dt.datetime.strptime(row.dimension_values[0].value, "%Y%m%d").date()
            out.append(
                ChannelDay(
                    date=date,
                    channel=_label(row.dimension_values[1].value),
                    sessions=int(float(row.metric_values[0].value or 0)),
                    revenue=float(row.metric_values[1].value or 0),
                )
            )
        return out

    def _fetch_products(self, start: dt.date, end: dt.date) -> list[ProductDay]:
        response = self._run(
            ["date", "itemName"],
            ["itemsViewed", "itemsAddedToCart", "itemsPurchased", "itemRevenue"],
            start,
            end,
        )
        out = []
        for row in response.rows:
            date = dt.datetime.strptime(row.dimension_values[0].value, "%Y%m%d").date()
            item = row.dimension_values[1].value
            if not item or item == "(not set)":
                continue
            out.append(
                ProductDay(
                    date=date,
                    item=item,
                    views=int(float(row.metric_values[0].value or 0)),
                    added_to_cart=int(float(row.metric_values[1].value or 0)),
                    purchased=int(float(row.metric_values[2].value or 0)),
                    revenue=float(row.metric_values[3].value or 0),
                )
            )
        return out
