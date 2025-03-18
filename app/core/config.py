from pydantic_settings import BaseSettings
from pydantic import Field, ConfigDict
import os
from functools import lru_cache
from typing import List


class Settings(BaseSettings):
    # App settings
    APP_NAME: str = "Gober API"
    API_PREFIX: str = "/api"
    DEBUG: bool = Field(default=False)
    VERSION: str = "0.1.0"
    
    # Database settings - Azure SQL
    DB_SERVER: str = Field(default="your-server.database.windows.net", env="AZURE_SQL_SERVER")
    DB_NAME: str = Field(default="your-database", env="AZURE_SQL_DATABASE")
    DB_USER: str = Field(default="your-username", env="AZURE_SQL_USERNAME")
    DB_PASSWORD: str = Field(default="your-password", env="AZURE_SQL_PASSWORD")
    
    # Database settings - Amazon Neptune
    NEPTUNE_ENDPOINT: str = Field(default="your-neptune-endpoint", env="NEPTUNE_ENDPOINT")
    NEPTUNE_PORT: int = Field(default=8182, env="NEPTUNE_PORT")
    
    # MeiliSearch settings
    MEILISEARCH_HOST: str = Field(default="http://localhost:7700", env="MEILISEARCH_HOST")
    MEILISEARCH_API_KEY: str = Field(default="your-meilisearch-api-key", env="MEILISEARCH_API_KEY")
    
    # Security settings
    SECRET_KEY: str = Field(default="your-secret-key-here", env="SECRET_KEY")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    ALGORITHM: str = "HS256"
    
    # CORS settings
    CORS_ORIGINS: list[str] = ["*"]
    
    # Logging settings
    LOG_LEVEL: str = Field(default="INFO", env="LOG_LEVEL")
    
    # AI settings
    GEMINI_API_ENDPOINT: str = Field(default="your-gemini-api-endpoint", env="GEMINI_API_ENDPOINT")
    GEMINI_API_KEY: str = Field(default="your-gemini-api-key", env="GEMINI_API_KEY")
    
    # Neptune settings
    AWS_REGION: str = "us-east-1"
    NEPTUNE_IAM_ROLE_ARN: str = ""
    
    model_config = ConfigDict(
        env_file = ".env",
        case_sensitive = True
    )


@lru_cache()
def get_settings() -> Settings:
    """
    Returns cached settings instance to avoid loading .env file on each request
    """
    return Settings()


settings = get_settings() 