import logging
from html import escape

import resend
from app.config import settings

logger = logging.getLogger(__name__)

# Set once at import time; key is read from env and does not change at runtime.
if settings.resend_api_key:
    resend.api_key = settings.resend_api_key

_SERIF = "Georgia,'Times New Roman',serif"
_MONO = "'SFMono-Regular',Consolas,'Liberation Mono',Menlo,monospace"

# Brand palette
_P = "#ECE7DB"   # parchment
_C = "#F5F0E8"   # card
_I = "#161510"   # ink
_B = "#C8BBA8"   # border
_M = "#7A3520"   # mahogany
_R = "#C1492A"   # rust
_T = "#4A3F35"   # body text
_F = "#9A8A78"   # faint


def _email_shell(badge: str, badge_color: str, rule_color: str, body_html: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:{_P};font-family:{_SERIF};">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:{_P};">
  <tr><td align="center" style="padding:48px 16px 64px;">
    <table role="presentation" width="100%" style="max-width:560px;" cellpadding="0" cellspacing="0" border="0">
      <tr><td style="background:{rule_color};height:3px;font-size:0;line-height:0;">&nbsp;</td></tr>
      <tr><td style="background:{_C};border-left:1px solid {_B};border-right:1px solid {_B};">
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
          <tr><td style="padding:28px 36px 24px;border-bottom:1px solid {_B};">
            <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"><tr>
              <td><p style="margin:0;font-family:{_MONO};font-size:11px;letter-spacing:0.22em;text-transform:uppercase;color:{_M};">penKeep</p></td>
              <td align="right"><p style="margin:0;font-family:{_MONO};font-size:10px;letter-spacing:0.16em;text-transform:uppercase;color:{badge_color};">{badge}</p></td>
            </tr></table>
          </td></tr>
          <tr><td style="padding:36px 36px 40px;">{body_html}</td></tr>
        </table>
      </td></tr>
      <tr><td style="background:{_B};height:1px;font-size:0;line-height:0;">&nbsp;</td></tr>
      <tr><td style="padding:20px 36px 0;">
        <p style="margin:0;font-family:{_MONO};font-size:11px;line-height:1.6;color:{_F};">penKeep &middot; <a href="https://penkeep.io" style="color:{_F};text-decoration:none;">penkeep.io</a></p>
      </td></tr>
    </table>
  </td></tr>
</table>
</body></html>"""


def _btn(href: str, label: str) -> str:
    return (
        f'<table role="presentation" cellpadding="0" cellspacing="0" border="0">'
        f'<tr><td style="background:{_M};">'
        f'<a href="{href}" style="display:inline-block;padding:13px 28px;font-family:{_MONO};'
        f'font-size:11px;letter-spacing:0.18em;text-transform:uppercase;color:{_C};text-decoration:none;">'
        f'{label}</a></td></tr></table>'
    )


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
    return _send_email_via_resend("penKeep <digest@penkeep.io>", to_email, subject, html_content)


async def send_onboarding_email(to_email: str, subject: str, html_content: str) -> bool:
    return _send_email_via_resend("penKeep <hello@penkeep.io>", to_email, subject, html_content)


async def send_earnings_alert_email(to_email: str, subject: str, html_content: str) -> bool:
    return _send_email_via_resend("penKeep <alerts@penkeep.io>", to_email, subject, html_content)


async def send_health_band_drop_email(
    to_email: str, ticker: str, prev_label: str, new_label: str, score: int
) -> bool:
    dashboard_url = f"{settings.frontend_url}/dashboard"
    body = (
        f'<p style="margin:0 0 10px;font-family:{_MONO};font-size:10px;letter-spacing:0.20em;text-transform:uppercase;color:{_F};">{escape(ticker)} &middot; Thesis health</p>'
        f'<h1 style="margin:0 0 28px;font-size:24px;font-weight:normal;color:{_I};line-height:1.25;">Your health score has dropped</h1>'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="margin:0 0 28px;border:1px solid {_B};">'
        f'<tr>'
        f'<td width="50%" style="padding:16px 20px;border-right:1px solid {_B};vertical-align:top;">'
        f'<p style="margin:0 0 6px;font-family:{_MONO};font-size:10px;letter-spacing:0.18em;text-transform:uppercase;color:{_F};">Was</p>'
        f'<p style="margin:0;font-size:20px;font-weight:normal;color:{_T};">{escape(prev_label)}</p></td>'
        f'<td width="50%" style="padding:16px 20px;vertical-align:top;">'
        f'<p style="margin:0 0 6px;font-family:{_MONO};font-size:10px;letter-spacing:0.18em;text-transform:uppercase;color:{_F};">Now</p>'
        f'<p style="margin:0;font-size:20px;font-weight:normal;color:{_R};">{escape(new_label)}</p></td>'
        f'</tr>'
        f'<tr><td colspan="2" style="padding:12px 20px;border-top:1px solid {_B};background:#EDE5DB;">'
        f'<p style="margin:0;font-family:{_MONO};font-size:11px;letter-spacing:0.12em;text-transform:uppercase;color:{_F};">Current score: <strong style="color:{_T};">{score} / 100</strong></p>'
        f'</td></tr></table>'
        f'<p style="margin:0 0 32px;font-size:14px;line-height:1.75;color:{_T};">Recent monitoring events have weakened one or more of your core claims. Review them to understand what changed and decide whether your thesis still holds.</p>'
        + _btn(dashboard_url, "Review thesis")
    )
    html = _email_shell("Health update", "#B07D3A", "#B07D3A", body)
    return _send_email_via_resend(
        "penKeep <alerts@penkeep.io>", to_email, f"{ticker} thesis dropped to {new_label}", html
    )


async def send_thesis_break_email(to_email: str, ticker: str, summary: str) -> bool:
    review_url = f"{settings.frontend_url}/dashboard/positions/{ticker}"
    body = (
        f'<p style="margin:0 0 10px;font-family:{_MONO};font-size:10px;letter-spacing:0.20em;text-transform:uppercase;color:{_F};">{escape(ticker)}</p>'
        f'<h1 style="margin:0 0 20px;font-size:24px;font-weight:normal;color:{_I};line-height:1.25;">Your thesis may be breaking</h1>'
        f'<p style="margin:0 0 20px;font-size:14px;line-height:1.75;color:{_T};">A monitoring signal just contradicted a core reason you wrote for owning <strong>{escape(ticker)}</strong>:</p>'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="margin:0 0 28px;">'
        f'<tr><td style="border-left:2px solid {_R};padding:14px 18px;background:#EDE5DB;">'
        f'<p style="margin:0;font-size:14px;line-height:1.7;color:{_T};font-style:italic;">{escape(summary)}</p>'
        f'</td></tr></table>'
        f'<p style="margin:0 0 32px;font-size:14px;line-height:1.75;color:{_T};">This is the kind of change you said would matter. Now decide whether your reason still holds.</p>'
        + _btn(review_url, "Review your reason")
    )
    html = _email_shell("Thesis alert", _R, _R, body)
    return _send_email_via_resend(
        "penKeep <alerts@penkeep.io>", to_email, f"{ticker}: your thesis may be breaking", html
    )


async def send_password_reset_email(to_email: str, reset_token: str) -> bool:
    reset_url = f"{settings.frontend_url}/reset-password?token={reset_token}"
    body = (
        f'<p style="margin:0 0 10px;font-family:{_MONO};font-size:10px;letter-spacing:0.20em;text-transform:uppercase;color:{_F};">Account</p>'
        f'<h1 style="margin:0 0 20px;font-size:24px;font-weight:normal;color:{_I};line-height:1.25;">Reset your password</h1>'
        f'<p style="margin:0 0 32px;font-size:14px;line-height:1.75;color:{_T};">Click below to reset your penKeep password. This link expires in one hour. If you didn\'t request a reset, you can safely ignore this.</p>'
        + _btn(reset_url, "Reset password")
        + f'<p style="margin:24px 0 0;font-family:{_MONO};font-size:12px;line-height:1.6;color:{_F};">Or copy this link into your browser:<br><span style="color:{_M};word-break:break-all;">{escape(reset_url)}</span></p>'
    )
    html = _email_shell("Account", _F, _M, body)
    return _send_email_via_resend(
        "penKeep <noreply@penkeep.io>", to_email, "Reset your password", html
    )
