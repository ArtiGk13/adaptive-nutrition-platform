from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./data/app.db"

    llm_provider: str = "mock"
    llm_model: str = "qwen2.5:7b"
    llm_base_url: str = "http://127.0.0.1:11434"
    llm_timeout_seconds: float = 120.0
    llm_temperature: float = 0.6
    llm_max_tokens: int = 220

    min_calories_male: int = 1500
    min_calories_female: int = 1200
    max_deficit_ratio: float = 0.25

    log_level: str = "INFO"


settings = Settings()
