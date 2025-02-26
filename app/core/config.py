from pydantic_settings import BaseSettings
from pydantic import Field
import os
from functools import lru_cache


class Settings(BaseSettings):
    # App settings
    APP_NAME: str = "Gober API"
    API_PREFIX: str = "/api"
    DEBUG: bool = Field(default=False)
    VERSION: str = "0.1.0"
    
    # Database settings
    DB_SERVER: str = Field(default="your-server.database.windows.net", env="AZURE_SQL_SERVER")
    DB_NAME: str = Field(default="your-database", env="AZURE_SQL_DATABASE")
    DB_USER: str = Field(default="your-username", env="AZURE_SQL_USERNAME")
    DB_PASSWORD: str = Field(default="your-password", env="AZURE_SQL_PASSWORD")
    
    # Security settings
    SECRET_KEY: str = Field(default="your-secret-key-here", env="SECRET_KEY")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    ALGORITHM: str = "HS256"
    
    # CORS settings
    CORS_ORIGINS: list[str] = ["*"]
    
    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """
    Returns cached settings instance to avoid loading .env file on each request
    """
    return Settings()


settings = get_settings() 