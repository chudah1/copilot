import logging
import resend
from app.config import settings

logger = logging.getLogger(__name__)

# Set once at import time; key is read from env and does not change at runtime.
if settings.resend_api_key:
    resend.api_key = settings.resend_api_key


def _send_email_via_resend(from_addr: str, to_email: str, subject: str, html: str) -> bool:
    if not settings.resend_api_key:
        logger.warning("No Resend API key configured — skipping email send")
        return False
    try:
        resend.Emails.send({"from": from_addr, "to": [to_email], "subject": subject, "html": html})
        return True
    except Exception as e:
        logger.error(f"Failed to send email to {to_email}: {e}")
        return False


async def send_digest_email(to_email: str, subject: str, html_content: str) -> bool:
    return _send_email_via_resend("Copilot Investor <digest@copilotinvestor.com>", to_email, subject, html_content)


async def send_onboarding_email(to_email: str, subject: str, html_content: str) -> bool:
    return _send_email_via_resend("Copilot Investor <hello@copilotinvestor.com>", to_email, subject, html_content)


async def send_earnings_alert_email(to_email: str, subject: str, html_content: str) -> bool:
    return _send_email_via_resend("Copilot Investor <alerts@copilotinvestor.com>", to_email, subject, html_content)


async def send_password_reset_email(to_email: str, reset_token: str) -> bool:
    reset_url = f"{settings.frontend_url}/reset-password?token={reset_token}"
    html = (
        "<h2>Reset your password</h2>"
        "<p>Click the link below to reset your Copilot Investor password. It expires in 1 hour.</p>"
        f'<p><a href="{reset_url}" style="font-size:18px;font-weight:bold">Reset my password</a></p>'
        "<p>If you didn't request this, ignore this email.</p>"
    )
    return _send_email_via_resend("Copilot Investor <noreply@copilotinvestor.com>", to_email, "Reset your password", html)
