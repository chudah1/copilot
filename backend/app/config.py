from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_FILES = (
    str(PROJECT_ROOT / ".env"),
    str(PROJECT_ROOT / "backend" / ".env"),
)


class Settings(BaseSettings):
    database_url: str = "sqlite+aiosqlite:///./copilot_investor.db"
    test_database_url: str = "sqlite+aiosqlite:///./test.db"
    redis_url: str = "redis://localhost:6379"
    enable_scheduler: bool = True
    # Run a first monitoring pass the moment a thesis becomes monitorable, so a
    # freshly-onboarded user sees real signal in their first session instead of an
    # empty "all calm" dashboard. Prod safety valve if it strains API budgets.
    enable_first_pulse: bool = True
    # Shared secret that gates the global relevance-metrics endpoint
    # (GET /api/monitoring/relevance). Empty disables the endpoint entirely.
    metrics_token: str = ""

    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_days: int = 7

    encryption_key: str = "change-me-32-byte-key-in-prod!!"  # Must be 32 bytes

    # Founding-member presale.
    # While this is False (the default), the presale runs in *reserve* mode: it
    # captures founding-seat intent without taking any money. Flip to True only
    # once you're legally clear to trade — it switches the same flow to a real
    # Stripe charge. Keeping it off keeps you out of "trading" entirely.
    presale_charge_enabled: bool = False
    # Stripe Checkout config (only used when presale_charge_enabled is True).
    # Empty stripe_secret_key also disables charging, so the app runs fine before
    # payments are set up.
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    presale_currency: str = "gbp"
    # Total founding seats across all tiers; drives the scarcity counter and the
    # hard stop once they're gone. Sold = count of paid founding_orders.
    founding_seats_total: int = 100

    anthropic_api_key: str = ""
    # claude-sonnet-4-20250514 was retired — every call routing through
    # settings.anthropic_model was 404'ing, silently falling through to the
    # OpenAI fallback (news_watch judge, ai_thesis, ai_digest, earnings_review).
    # The current Sonnet ID is claude-sonnet-4-6.
    anthropic_model: str = "claude-sonnet-4-6"
    openai_api_key: str = ""
    gemini_api_key: str = ""
    resend_api_key: str = ""
    sentry_dsn: str = ""
    trading212_base_url: str = "https://live.trading212.com/api/v0"
    alpha_vantage_api_key: str = ""
    market_data_provider: str = "yfinance"
    edgar_user_agent: str = "PenKeep/1.0 contact@penkeep.io"
    frontend_url: str = "http://localhost:3000"
    app_url: str = ""  # e.g. https://app.penkeep.io — added to CORS alongside frontend_url

    # LLM optimizations / reliability
    llm_response_cache_ttl_seconds: int = 15 * 60
    openai_prompt_cache_key: str = "thesis_decompose_v3"
    openai_prompt_cache_retention: str = "24h"  # "in_memory" | "24h"

    model_config = SettingsConfigDict(
        env_file=ENV_FILES,
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
