"""Outgoing email (password-reset links and password-changed notices).

Providers: "brevo" and "resend" (HTTPS APIs; Render's free plan blocks SMTP
ports), "smtp", or "none". Credentials come only from the environment.
Message bodies are never logged: they can contain reset links.
"""

import html as html_lib
import logging
import smtplib
import ssl
from email.message import EmailMessage

import httpx

from app.core.config import settings

logger = logging.getLogger("alty.email")

# Tests replace this with a list to capture messages instead of sending.
outbox: list[dict] | None = None


def _sender() -> tuple[str, str]:
    return settings.EMAIL_FROM.strip(), settings.EMAIL_FROM_NAME.strip() or "Abellar Realty"


def _text_to_html(text: str) -> str:
    escaped = html_lib.escape(text)
    paragraphs = [part.strip("\n") for part in escaped.split("\n\n")]
    return "".join("<p>" + part.replace("\n", "<br>") + "</p>" for part in paragraphs if part)


def send_email(to: str, subject: str, text: str, html: str | None = None) -> bool:
    """Send one message; False when it could not be sent (never raises)."""
    message = {"to": to, "subject": subject, "text": text, "html": html}
    if outbox is not None:
        outbox.append(message)
        return True
    provider = settings.EMAIL_PROVIDER.strip().casefold()
    address, name = _sender()
    if provider == "none" or not address:
        logger.warning("Email not sent: EMAIL_PROVIDER/EMAIL_FROM not configured")
        return False
    try:
        if provider == "brevo":
            response = httpx.post(
                "https://api.brevo.com/v3/smtp/email",
                headers={"api-key": settings.BREVO_API_KEY, "accept": "application/json"},
                json={"sender": {"email": address, "name": name}, "to": [{"email": to}], "subject": subject,
                      "textContent": text, **({"htmlContent": html} if html else {})},
                timeout=settings.EMAIL_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
        elif provider == "resend":
            response = httpx.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {settings.RESEND_API_KEY}"},
                # Resend's API documents "html" as required: always send one.
                json={"from": f"{name} <{address}>", "to": [to], "subject": subject, "text": text,
                      "html": html or _text_to_html(text)},
                timeout=settings.EMAIL_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
        elif provider == "smtp":
            email = EmailMessage()
            email["From"] = f"{name} <{address}>"
            email["To"] = to
            email["Subject"] = subject
            email.set_content(text)
            if html:
                email.add_alternative(html, subtype="html")
            context = ssl.create_default_context()
            if settings.SMTP_PORT == 465:
                server = smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, context=context,
                                          timeout=settings.EMAIL_TIMEOUT_SECONDS)
            else:
                server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=settings.EMAIL_TIMEOUT_SECONDS)
                server.starttls(context=context)
            with server:
                if settings.SMTP_USERNAME:
                    server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
                server.send_message(email)
        else:
            logger.warning("Email not sent: unknown EMAIL_PROVIDER %r", provider)
            return False
    except (httpx.HTTPError, smtplib.SMTPException, OSError) as exc:
        # Log the failure type only: no recipient body, links or credentials.
        logger.warning("Email via %s failed: %s", provider, type(exc).__name__)
        return False
    return True
