from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./data/app.db"

    llm_provider: str = "mock"
    llm_api_key: str | None = None
    llm_model: str | None = None

    min_calories_male: int = 1500
    min_calories_female: int = 1200
    max_deficit_ratio: float = 0.25

    log_level: str = "INFO"


settings = Settings()
