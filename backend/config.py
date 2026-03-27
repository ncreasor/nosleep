from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    qdrant_url: str
    qdrant_service_api_key: str

    class Config:
        env_file = ".env"


settings = Settings()
