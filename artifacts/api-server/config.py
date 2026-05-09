import os


class Settings:
    secret_key: str = os.environ.get("SESSION_SECRET", "krono-secret-key-change-in-production")
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24
    refresh_token_expire_days: int = 30
    debt_interest_rate: float = 0.001

    # KYC
    # Set MOCK_KYC=true to auto-approve submissions (development/testing only)
    mock_kyc: bool = os.environ.get("MOCK_KYC", "false").lower() == "true"
    # Webhook secret shared with the KYC provider (e.g. Idwall, Unico, Serpro)
    kyc_webhook_secret: str = os.environ.get("KYC_WEBHOOK_SECRET", "")


settings = Settings()
