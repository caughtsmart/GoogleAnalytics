"""Configuration loading.

Everything tunable lives in config.yaml (copy config.example.yaml).
The SMTP password is the one thing that should NOT go in the file —
set the GA4_SMTP_PASSWORD environment variable instead.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class EmailConfig:
    enabled: bool = True
    to: list[str] = field(default_factory=list)
    from_addr: str = ""
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""  # prefer env var GA4_SMTP_PASSWORD


@dataclass
class Config:
    property_id: str = ""
    credentials_file: str = ""
    timezone: str = "Europe/London"
    currency: str = "£"
    rolling_days: int = 28
    anomaly_threshold_pct: float = 25.0
    min_sessions_for_anomaly: int = 30
    min_purchases_for_anomaly: int = 3
    top_n_products: int = 5
    interest_no_sales_min_views: int = 25
    reports_dir: str = "reports"
    email: EmailConfig = field(default_factory=EmailConfig)


def load_config(path: str | Path) -> Config:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(
            f"Config file not found: {path}. "
            "Copy config.example.yaml to config.yaml and fill it in."
        )
    raw = yaml.safe_load(path.read_text()) or {}

    ga4 = raw.get("ga4", {})
    baselines = raw.get("baselines", {})
    anomalies = raw.get("anomalies", {})
    products = raw.get("products", {})
    email_raw = raw.get("email", {})

    email = EmailConfig(
        enabled=bool(email_raw.get("enabled", True)),
        to=list(email_raw.get("to", [])),
        from_addr=email_raw.get("from", ""),
        smtp_host=email_raw.get("smtp_host", ""),
        smtp_port=int(email_raw.get("smtp_port", 587)),
        smtp_username=email_raw.get("smtp_username", ""),
        smtp_password=os.environ.get(
            "GA4_SMTP_PASSWORD", email_raw.get("smtp_password", "")
        ),
    )

    return Config(
        property_id=str(ga4.get("property_id", "")),
        credentials_file=str(ga4.get("credentials_file", "")),
        timezone=raw.get("timezone", "Europe/London"),
        currency=raw.get("currency", "£"),
        rolling_days=int(baselines.get("rolling_days", 28)),
        anomaly_threshold_pct=float(anomalies.get("threshold_pct", 25)),
        min_sessions_for_anomaly=int(anomalies.get("min_sessions", 30)),
        min_purchases_for_anomaly=int(anomalies.get("min_purchases", 3)),
        top_n_products=int(products.get("top_n", 5)),
        interest_no_sales_min_views=int(
            products.get("interest_no_sales_min_views", 25)
        ),
        reports_dir=raw.get("reports_dir", "reports"),
        email=email,
    )
