from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    redis_url: str
    image_storage_path: str = "/data/images"
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    scrape_rate_limit_min_seconds: float = 2
    scrape_rate_limit_max_seconds: float = 5
    scrape_user_agent: str = "RecipeScraperBot/0.1"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
