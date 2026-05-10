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
