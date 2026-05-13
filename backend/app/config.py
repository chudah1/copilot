from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite+aiosqlite:///./copilot_investor.db"
    test_database_url: str = "sqlite+aiosqlite:///./test.db"
    redis_url: str = "redis://localhost:6379"
    enable_scheduler: bool = True

    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_days: int = 7

    encryption_key: str = "change-me-32-byte-key-in-prod!!"  # Must be 32 bytes

    anthropic_api_key: str = ""
    openai_api_key: str = ""
    gemini_api_key: str = ""
    resend_api_key: str = ""
    trading212_base_url: str = "https://live.trading212.com/api/v0"
    alpha_vantage_api_key: str = ""
    market_data_provider: str = "alpha_vantage"
    frontend_url: str = "http://localhost:3000"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
