"""Founding-member presale via Stripe Checkout.

This is the monetization-signal experiment: instead of collecting free waitlist
emails, we put a real price in front of people and measure who pays. Stripe
Checkout is hosted, so card data never touches our servers (keeps us in the
lightest PCI tier, SAQ-A).

Tier amounts live here, server-side, and are never read from the client — the
browser only sends a tier *key*, so a tampered request can't change the price.
Mirrors the waitlist route's lightweight raw-SQL + lazy-import style.
"""
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, EmailStr
from sqlalchemy import text

from app.config import settings
from app.database import async_session
from app.limiter import limiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/presale", tags=["presale"])


# Server-authoritative catalogue. Amounts are in minor units (pence for GBP).
# `mode=payment` => one-time charge, so we don't need pre-created Stripe Price
# objects or subscription/dunning machinery for the presale.
FOUNDING_TIERS: dict[str, dict] = {
    "annual": {
        "label": "Founding Membership",
        "amount": 9900,  # £99 for the first year, renewable at the locked founding rate
        "description": "One year of penKeep Premium at the founding rate, locked while membership stays active.",
    },
}


class CheckoutRequest(BaseModel):
    email: EmailStr
    tier: str


class ReserveRequest(BaseModel):
    email: EmailStr
    tier: str


def _stripe():
    """Lazily import + configure Stripe so the app boots without the key/SDK."""
    if not settings.stripe_secret_key:
        raise HTTPException(status_code=503, detail="Presale is not open yet.")
    try:
        import stripe
    except ImportError as exc:  # pragma: no cover - dependency missing in dev
        logger.error("stripe package not installed: %s", exc)
        raise HTTPException(status_code=503, detail="Presale is not open yet.")
    stripe.api_key = settings.stripe_secret_key
    return stripe


def _charging() -> bool:
    """True only when we're configured AND cleared to take real money."""
    return settings.presale_charge_enabled and bool(settings.stripe_secret_key)


async def _seats_sold(db) -> int:
    result = await db.execute(
        text("SELECT COUNT(*) FROM founding_orders WHERE status = 'paid'")
    )
    return int(result.scalar() or 0)


async def _reservations_count(db) -> int:
    result = await db.execute(text("SELECT COUNT(*) FROM founding_reservations"))
    return int(result.scalar() or 0)


@router.get("/seats")
async def seats_remaining():
    """Public scarcity counter + the mode the UI should render in.

    `mode` lets the frontend show a no-payment reservation flow vs. a real
    checkout from one server-side flag, so flipping the flag flips the whole UX.
    """
    total = settings.founding_seats_total
    charging = _charging()
    async with async_session() as db:
        try:
            sold = await _seats_sold(db) if charging else await _reservations_count(db)
        except Exception as exc:  # table may not exist pre-migration
            logger.warning("Seat count failed: %s", exc)
            sold = 0
    return {
        "total": total,
        "sold": sold,
        "remaining": max(total - sold, 0),
        "mode": "charge" if charging else "reserve",
    }


@router.post("/reserve", status_code=201)
@limiter.limit("10/hour")
async def reserve_seat(request: Request, body: ReserveRequest):
    """No-money intent capture. This is the default, visa-safe path: it records
    who wants which founding tier so we have a real willingness-to-pay signal,
    but takes no payment, so we aren't trading."""
    if body.tier not in FOUNDING_TIERS:
        raise HTTPException(status_code=400, detail="Unknown tier.")

    async with async_session() as db:
        if await _reservations_count(db) >= settings.founding_seats_total:
            raise HTTPException(status_code=409, detail="Founding seats are sold out.")
        try:
            # Upsert by email so re-reserving just updates the chosen tier.
            await db.execute(
                text(
                    "INSERT INTO founding_reservations (email, tier, created_at) "
                    "VALUES (:email, :tier, :created_at) "
                    "ON CONFLICT (email) DO UPDATE SET tier = :tier"
                ),
                {
                    "email": str(body.email),
                    "tier": body.tier,
                    "created_at": datetime.now(timezone.utc),
                },
            )
            await db.commit()
        except Exception as exc:
            logger.warning("Founding reservation insert failed: %s", exc)
            raise HTTPException(status_code=500, detail="Could not save your reservation.")

    _send_reservation_confirmation(str(body.email), body.tier)
    return {"reserved": True}


@router.post("/checkout", status_code=201)
@limiter.limit("10/hour")
async def create_checkout(request: Request, body: CheckoutRequest):
    # Hard gate: never reach Stripe unless explicitly cleared to trade.
    if not settings.presale_charge_enabled:
        raise HTTPException(status_code=503, detail="Presale charging is not enabled.")

    tier = FOUNDING_TIERS.get(body.tier)
    if tier is None:
        raise HTTPException(status_code=400, detail="Unknown tier.")

    stripe = _stripe()

    async with async_session() as db:
        if await _seats_sold(db) >= settings.founding_seats_total:
            raise HTTPException(status_code=409, detail="Founding seats are sold out.")

    base = settings.frontend_url.rstrip("/")
    try:
        session = stripe.checkout.Session.create(
            mode="payment",
            customer_email=str(body.email),
            line_items=[
                {
                    "quantity": 1,
                    "price_data": {
                        "currency": settings.presale_currency,
                        "unit_amount": tier["amount"],
                        "product_data": {
                            "name": f"penKeep · {tier['label']}",
                            "description": tier["description"],
                        },
                    },
                }
            ],
            metadata={"tier": body.tier, "email": str(body.email)},
            payment_intent_data={"metadata": {"tier": body.tier, "email": str(body.email)}},
            success_url=f"{base}/founding/success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{base}/pricing?checkout=cancelled",
        )
    except Exception as exc:
        logger.exception("Stripe checkout creation failed: %s", exc)
        raise HTTPException(status_code=502, detail="Could not start checkout. Try again.")

    # Record the intent as pending; the webhook flips it to paid. ON CONFLICT keeps
    # this idempotent if the user retries with the same Stripe session.
    async with async_session() as db:
        try:
            await db.execute(
                text(
                    "INSERT INTO founding_orders "
                    "(stripe_session_id, email, tier, amount, currency, status, created_at) "
                    "VALUES (:sid, :email, :tier, :amount, :currency, 'pending', :created_at) "
                    "ON CONFLICT (stripe_session_id) DO NOTHING"
                ),
                {
                    "sid": session.id,
                    "email": str(body.email),
                    "tier": body.tier,
                    "amount": tier["amount"],
                    "currency": settings.presale_currency,
                    "created_at": datetime.now(timezone.utc),
                },
            )
            await db.commit()
        except Exception as exc:
            logger.warning("Founding order insert failed: %s", exc)

    return {"checkout_url": session.url}


@router.post("/webhook")
async def stripe_webhook(request: Request):
    """Stripe -> us. Verifies the signature, then marks the order paid.

    The webhook is the source of truth for payment, not the browser redirect:
    the success page can be skipped, but the webhook still fires.
    """
    stripe = _stripe()
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")

    if not settings.stripe_webhook_secret:
        logger.error("Stripe webhook hit but STRIPE_WEBHOOK_SECRET is unset")
        raise HTTPException(status_code=503, detail="Webhook not configured.")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig, settings.stripe_webhook_secret
        )
    except Exception as exc:
        logger.warning("Stripe webhook signature verification failed: %s", exc)
        raise HTTPException(status_code=400, detail="Invalid signature.")

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        await _mark_paid(
            session_id=session["id"],
            email=session.get("customer_email") or session.get("metadata", {}).get("email"),
            tier=session.get("metadata", {}).get("tier"),
        )

    return {"received": True}


async def _mark_paid(session_id: str, email: str | None, tier: str | None) -> None:
    newly_paid = False
    async with async_session() as db:
        try:
            result = await db.execute(
                text(
                    "UPDATE founding_orders "
                    "SET status = 'paid', paid_at = :paid_at "
                    "WHERE stripe_session_id = :sid AND status != 'paid'"
                ),
                {"paid_at": datetime.now(timezone.utc), "sid": session_id},
            )
            await db.commit()
            newly_paid = result.rowcount > 0
        except Exception as exc:
            logger.warning("Marking founding order paid failed: %s", exc)

    if newly_paid and email:
        _send_receipt(email, tier)


def _send_reservation_confirmation(email: str, tier: str | None) -> None:
    try:
        if not settings.resend_api_key:
            return
        import resend

        resend.api_key = settings.resend_api_key
        label = (FOUNDING_TIERS.get(tier or "") or {}).get("label", "Founding Member")
        resend.Emails.send(
            {
                "from": "penKeep <noreply@penkeep.io>",
                "to": email,
                "subject": "Your penKeep founding seat is reserved",
                "html": (
                    f"<p>Your founding seat is reserved — <strong>{label}</strong>.</p>"
                    "<p>You won't be charged now. We'll lock in your founding price and email "
                    "you to complete it the moment we open the doors, before the public launch.</p>"
                    "<p>Reply any time — as a founding member you get a direct line into what "
                    "we build next.</p>"
                    "<p style='color:#7a7268;font-size:13px'>— The penKeep team</p>"
                ),
            }
        )
    except Exception as exc:
        logger.warning("Reservation confirmation email failed: %s", exc)


def _send_receipt(email: str, tier: str | None) -> None:
    try:
        if not settings.resend_api_key:
            return
        import resend

        resend.api_key = settings.resend_api_key
        label = (FOUNDING_TIERS.get(tier or "") or {}).get("label", "Founding Member")
        resend.Emails.send(
            {
                "from": "penKeep <noreply@penkeep.io>",
                "to": email,
                "subject": "You're a penKeep Founding Member",
                "html": (
                    f"<p>You're in — <strong>{label}</strong>.</p>"
                    "<p>Your founding price is locked. We'll email you the moment "
                    "your account is ready, before the public launch.</p>"
                    "<p>Reply to this email any time — as a founding member you get a "
                    "direct line into what we build next.</p>"
                    "<p style='color:#7a7268;font-size:13px'>— The penKeep team</p>"
                ),
            }
        )
    except Exception as exc:
        logger.warning("Founding receipt email failed: %s", exc)
