import os


class Settings:
    secret_key: str = os.environ.get("SESSION_SECRET", "krono-secret-key-change-in-production")
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24
    refresh_token_expire_days: int = 30
    debt_interest_rate: float = 0.001


settings = Settings()
