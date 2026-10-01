from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "sqlite:///./vpilot.db"
    llm_base_url: str = "https://api.openai.com/v1"
    llm_model: str = "Qwen/Qwen2.5-7B-Instruct"
    llm_api_key: str | None = None
    frontend_origins: str = "http://localhost:5173,http://127.0.0.1:5173"


settings = Settings()
