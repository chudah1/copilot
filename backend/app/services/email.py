import logging
import resend
from app.config import settings

logger = logging.getLogger(__name__)


async def send_digest_email(to_email: str, subject: str, html_content: str) -> bool:
    if not settings.resend_api_key:
        logger.warning("No Resend API key configured — skipping email send")
        return False
    resend.api_key = settings.resend_api_key
    try:
        resend.Emails.send({"from": "Copilot Investor <digest@copilotinvestor.com>", "to": [to_email], "subject": subject, "html": html_content})
        return True
    except Exception as e:
        logger.error(f"Failed to send email to {to_email}: {e}")
        return False


async def send_password_reset_email(to_email: str, reset_token: str) -> bool:
    if not settings.resend_api_key:
        logger.warning("No Resend API key configured — skipping password reset email")
        return False
    resend.api_key = settings.resend_api_key
    reset_url = f"{settings.frontend_url}/reset-password?token={reset_token}"
    html = (
        "<h2>Reset your password</h2>"
        "<p>Click the link below to reset your Copilot Investor password. It expires in 1 hour.</p>"
        f'<p><a href="{reset_url}" style="font-size:18px;font-weight:bold">Reset my password</a></p>'
        "<p>If you didn't request this, ignore this email.</p>"
    )
    try:
        resend.Emails.send({
            "from": "Copilot Investor <noreply@copilotinvestor.com>",
            "to": [to_email],
            "subject": "Reset your password",
            "html": html,
        })
        return True
    except Exception as e:
        logger.error(f"Failed to send password reset email to {to_email}: {e}")
        return False
