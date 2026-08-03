"""Email delivery via plain SMTP.

Works with any provider that gives you SMTP credentials (Google Workspace
app password, Fastmail, Brevo, etc.). Sends multipart text+HTML, and a
short plain-text note if the day's run failed.
"""

from __future__ import annotations

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from .config import EmailConfig


def _connect(cfg: EmailConfig) -> smtplib.SMTP:
    if cfg.smtp_port == 465:
        server = smtplib.SMTP_SSL(cfg.smtp_host, cfg.smtp_port, timeout=30)
    else:
        server = smtplib.SMTP(cfg.smtp_host, cfg.smtp_port, timeout=30)
        server.starttls()
    if cfg.smtp_username:
        server.login(cfg.smtp_username, cfg.smtp_password)
    return server


def send_report(cfg: EmailConfig, subject: str, text: str, html: str) -> None:
    if not cfg.to:
        raise ValueError("email.to is empty in config.yaml")
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = cfg.from_addr or cfg.smtp_username
    msg["To"] = ", ".join(cfg.to)
    msg.attach(MIMEText(text, "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))
    with _connect(cfg) as server:
        server.send_message(msg)


def send_failure_note(cfg: EmailConfig, date_label: str, error: str) -> None:
    """The 'couldn't run today' note — short, honest, no drama."""
    body = (
        f"Morning. The GA4 report for {date_label} couldn't run.\n\n"
        f"What went wrong:\n{error}\n\n"
        "No numbers were lost — GA4 still has the data. Re-run manually with:\n"
        "  python run_daily_report.py\n"
        "once the underlying problem is sorted."
    )
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = f"Loaded Dice GA4 — {date_label}: report couldn't run"
    msg["From"] = cfg.from_addr or cfg.smtp_username
    msg["To"] = ", ".join(cfg.to)
    with _connect(cfg) as server:
        server.send_message(msg)
