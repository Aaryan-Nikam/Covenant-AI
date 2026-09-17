"""
Covenant AI — SLA Breach Notifier.

Fires webhook and/or email when a breach is detected.
Both channels are best-effort — failures are logged but never raise.
"""

import logging
import os
import smtplib
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from engine.sla.models import SLAPolicy, SLABreach

logger = logging.getLogger("ironpass.sla.notifier")


async def send_breach_notification(
    policy: SLAPolicy,
    breach: SLABreach,
    db: AsyncSession,
) -> None:
    """
    Fire webhook and email notifications for a breach.
    Sets breach.notification_sent_at on success (either channel).
    """
    sent = False

    # ---- Webhook ----
    if policy.webhook_url:
        sent = await _send_webhook(policy, breach) or sent

    # ---- Email ----
    if policy.notification_email:
        sent = await _send_email(policy, breach) or sent

    if sent:
        breach.notification_sent_at = datetime.now(timezone.utc)
        # Caller (evaluator) commits after this


async def _send_webhook(policy: SLAPolicy, breach: SLABreach) -> bool:
    payload = {
        "policy_name": policy.name,
        "metric_type": policy.metric_type,
        "metric_value": breach.metric_value,
        "threshold_value": breach.threshold_value,
        "breached_at": breach.breached_at.isoformat(),
        "tenant_id": str(policy.tenant_id),
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(policy.webhook_url, json=payload)
        if resp.is_success:
            logger.info(f"SLA webhook delivered: policy={policy.name} → {policy.webhook_url}")
            return True
        else:
            logger.warning(
                f"SLA webhook non-2xx: policy={policy.name} "
                f"status={resp.status_code} url={policy.webhook_url}"
            )
            return False
    except Exception as e:
        logger.warning(f"SLA webhook failed: policy={policy.name} error={e}")
        return False


async def _send_email(policy: SLAPolicy, breach: SLABreach) -> bool:
    smtp_host = os.environ.get("SMTP_HOST")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    smtp_user = os.environ.get("SMTP_USER")
    smtp_pass = os.environ.get("SMTP_PASS")
    smtp_from = os.environ.get("SMTP_FROM", smtp_user)

    if not all([smtp_host, smtp_user, smtp_pass]):
        logger.warning(
            "SLA email skipped — SMTP_HOST / SMTP_USER / SMTP_PASS not configured"
        )
        return False

    subject = f"[Covenant AI] SLA Breach: {policy.name}"
    html_body = f"""
    <html><body style="font-family: sans-serif; color: #1a1a1a;">
      <h2 style="color:#dc2626;">⚠️ SLA Breach Detected</h2>
      <table style="border-collapse:collapse;width:100%;max-width:600px;">
        <tr><td style="padding:8px;border:1px solid #e5e7eb;font-weight:bold;">Policy</td>
            <td style="padding:8px;border:1px solid #e5e7eb;">{policy.name}</td></tr>
        <tr><td style="padding:8px;border:1px solid #e5e7eb;font-weight:bold;">Metric</td>
            <td style="padding:8px;border:1px solid #e5e7eb;">{policy.metric_type}</td></tr>
        <tr><td style="padding:8px;border:1px solid #e5e7eb;font-weight:bold;">Current Value</td>
            <td style="padding:8px;border:1px solid #e5e7eb;color:#dc2626;font-weight:bold;">{breach.metric_value:.4f}</td></tr>
        <tr><td style="padding:8px;border:1px solid #e5e7eb;font-weight:bold;">Threshold</td>
            <td style="padding:8px;border:1px solid #e5e7eb;">{breach.threshold_value}</td></tr>
        <tr><td style="padding:8px;border:1px solid #e5e7eb;font-weight:bold;">Breached At</td>
            <td style="padding:8px;border:1px solid #e5e7eb;">{breach.breached_at.strftime('%Y-%m-%d %H:%M:%S UTC')}</td></tr>
      </table>
      <p style="margin-top:24px;font-size:12px;color:#6b7280;">
        Sent by Covenant AI SLA Monitor — log in to the dashboard to view breach history.
      </p>
    </body></html>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = smtp_from
    msg["To"] = policy.notification_email
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.sendmail(smtp_from, [policy.notification_email], msg.as_string())
        logger.info(f"SLA email sent: policy={policy.name} → {policy.notification_email}")
        return True
    except Exception as e:
        logger.warning(f"SLA email failed: policy={policy.name} error={e}")
        return False
