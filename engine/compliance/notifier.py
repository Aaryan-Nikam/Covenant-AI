import asyncio
import logging
import os
import smtplib
from datetime import datetime, timezone
from email.message import EmailMessage

import httpx
from sqlalchemy import select, update

from engine.auth.models import Tenant
from engine.compliance.models import ComplianceCase
from engine.database.connection import get_session_factory

logger = logging.getLogger("ironpass.compliance.notifier")


async def send_aml_alert(
    *,
    tenant_id: str,
    case_id: str,
    risk_score: int,
    subject_id: str | None,
    amount: float | None,
    country_from: str | None,
    flags: list[str],
    opened_at: str,
) -> None:
    """
    Fire webhook and email alerts for a high-risk AML case.

    Accepts only primitive values — safe for asyncio.create_task since
    ORM objects from the caller's session would be detached by then.
    """
    session_factory = get_session_factory()
    async with session_factory() as session:
        tenant = (await session.execute(
            select(Tenant).where(Tenant.id == tenant_id)
        )).scalar_one_or_none()

        if not tenant:
            logger.warning(f"AML alert: tenant {tenant_id} not found, skipping")
            return

        webhook_url = tenant.webhook_url
        notification_email = tenant.notification_email

        # 1. Webhook
        if webhook_url:
            payload = {
                "event": "aml.high_risk_case",
                "case_id": case_id,
                "subject_id": subject_id,
                "risk_score": risk_score,
                "rules_fired": flags,
                "amount": amount,
                "country_from": country_from,
                "opened_at": opened_at,
                "tenant_id": tenant_id,
            }
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.post(webhook_url, json=payload)
                    if not resp.is_success:
                        logger.warning(
                            f"AML webhook returned {resp.status_code} for tenant {tenant_id}"
                        )
            except Exception as e:
                logger.warning(f"AML high-risk webhook failed for tenant {tenant_id}: {e}")

        # 2. Email
        if notification_email:
            smtp_host = os.environ.get("SMTP_HOST")
            smtp_port = os.environ.get("SMTP_PORT", "587")
            smtp_user = os.environ.get("SMTP_USER")
            smtp_pass = os.environ.get("SMTP_PASS")

            if smtp_host and smtp_user and smtp_pass:
                try:
                    msg = EmailMessage()
                    msg.set_content(
                        f"High-risk AML signal escalated to Case {case_id}.\n\n"
                        f"Subject: {subject_id or 'Unknown'}\n"
                        f"Risk Score: {risk_score}/100\n"
                        f"Amount: {amount}\n"
                        f"Country: {country_from}\n"
                        f"Rules Fired: {', '.join(flags)}\n"
                        f"Case Opened: {opened_at}\n\n"
                        f"Log in to your Covenant AI dashboard to review the case."
                    )
                    msg["Subject"] = (
                        f"[Covenant AI] High-Risk AML Case — Score {risk_score}/100"
                    )
                    msg["From"] = smtp_user
                    msg["To"] = notification_email

                    def _send_sync():
                        with smtplib.SMTP(smtp_host, int(smtp_port)) as server:
                            server.starttls()
                            server.login(smtp_user, smtp_pass)
                            server.send_message(msg)

                    await asyncio.to_thread(_send_sync)
                except Exception as e:
                    logger.warning(
                        f"AML high-risk email failed for tenant {tenant_id}: {e}"
                    )
            else:
                logger.info(
                    f"Skipping AML email alert for tenant {tenant_id} — SMTP config missing"
                )

        # Stamp notification_sent_at without re-fetching the ORM object
        await session.execute(
            update(ComplianceCase)
            .where(ComplianceCase.id == case_id)
            .values(notification_sent_at=datetime.now(timezone.utc))
        )
        await session.commit()
