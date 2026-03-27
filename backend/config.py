from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    qdrant_url: str
    qdrant_service_api_key: str = ""
    openai_api_key: str
    openai_model: str = "gpt-4o-mini"
    openai_embed_model: str = "text-embedding-3-small"

    class Config:
        env_file = ".env"


settings = Settings()
