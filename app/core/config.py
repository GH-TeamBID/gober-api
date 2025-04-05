from pydantic_settings import BaseSettings
from pydantic import Field, ConfigDict, field_validator
import os
from functools import lru_cache
from typing import List
import secrets


class Settings(BaseSettings):
    # App settings
    APP_NAME: str = "Gober API"
    API_PREFIX: str = "/api"
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"
    VERSION: str = "0.1.0"
    
    # Database settings - Azure SQL
    DB_SERVER: str = os.getenv("DB_SERVER", "localhost")
    DB_NAME: str = os.getenv("DB_NAME", "gober_db")
    DB_USER: str = os.getenv("DB_USER", "db_user")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "db_password")
    
    # Database settings - Amazon Neptune
    NEPTUNE_ENDPOINT: str = os.getenv("NEPTUNE_ENDPOINT", "localhost")
    NEPTUNE_PORT: int = int(os.getenv("NEPTUNE_PORT", "8182"))
    
    # MeiliSearch settings
    MEILISEARCH_HOST: str = os.getenv("MEILISEARCH_HOST", "http://localhost:7700")
    MEILISEARCH_API_KEY: str = os.getenv("MEILISEARCH_API_KEY", "")
    
    # Security settings
    SECRET_KEY: str = os.getenv("SECRET_KEY", secrets.token_hex(32))
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("JWT_EXPIRE_MINUTES", "1440"))  # 24 hours
    REFRESH_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("REFRESH_TOKEN_EXPIRE_MINUTES", "10080"))  # 1 Week
    ALGORITHM: str = "HS256"
    
    # Admin user settings
    ADMIN_EMAIL: str = os.getenv("ADMIN_EMAIL", "admin@example.com")
    ADMIN_PASSWORD: str = os.getenv("ADMIN_PASSWORD", "admin123")
    
    # CORS settings
    CORS_ORIGINS: List[str] = os.getenv("CORS_ORIGINS", "*").split(",")
    
    # Logging settings
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "DEBUG")
    
    # AI settings
    GEMINI_API_ENDPOINT: str = Field(default="your-gemini-api-endpoint", env="GEMINI_API_ENDPOINT")
    GOOGLE_AI_API_KEY: str = Field(default="your-gemini-api-key", env="GOOGLE_AI_API_KEY")
    
    # Neptune settings
    AWS_REGION: str = os.getenv("AWS_REGION", "us-east-1")
    NEPTUNE_IAM_ROLE_ARN: str = os.getenv("NEPTUNE_IAM_ROLE_ARN", "arn:aws:iam::123456789012:role/NeptuneRole")
    
    # AI services API keys
    MARKER_API_KEY: str = os.getenv("MARKER_API", "")
    GOOGLE_AI_API_KEY: str = os.getenv("GOOGLE_AI_API", "")
    
    # Environment name
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")

    BLOB_CONTAINER_NAME: str = os.getenv("BLOB_CONTAINER_NAME")
    BLOB_CONNECTION_STRING: str = os.getenv("BLOB_CONNECTION_STRING", "")
    
    model_config = ConfigDict(
        # This will look for environment-specific files first, then fall back to the default
        env_file = (".env.{environment}", ".env"),
        case_sensitive = True
    )
    
    @field_validator('ENVIRONMENT', mode='before')
    def set_environment(cls, v):
        """Get environment from ENV variable or use default"""
        return os.getenv('ENVIRONMENT', v)
    
    def __init__(self, **kwargs):
        # Replace {environment} placeholder with actual environment name
        if isinstance(self.model_config['env_file'], tuple):
            env_files = []
            for file in self.model_config['env_file']:
                if '{environment}' in file:
                    env = os.getenv('ENVIRONMENT', 'development')
                    file = file.format(environment=env)
                env_files.append(file)
            self.model_config['env_file'] = tuple(env_files)
        
        super().__init__(**kwargs)


@lru_cache()
def get_settings() -> Settings:
    """
    Returns cached settings instance to avoid loading .env file on each request
    """
    return Settings()


settings = get_settings() 