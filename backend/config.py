from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    qdrant_url: str
    qdrant_service_api_key: str = ""
    qdrant_collection: str = "legal_documents"
    openai_api_key: str
    openai_model: str = "gpt-4o-mini"
    openai_embed_model: str = "text-embedding-3-small"
    secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24 * 7
    cors_origins: list[str] = ["*"]
    max_file_size_mb: int = 20

    class Config:
        env_file = ".env"


settings = Settings()
