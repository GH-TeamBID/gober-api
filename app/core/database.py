from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import settings
import logging
from meilisearch import Client
from app.core.neptune import NeptuneClient
from contextlib import asynccontextmanager
import urllib.parse

# Configure logging
logger = logging.getLogger(__name__)

# Create connection string for Azure SQL using pyodbc instead of pytds
# URL encode the password to handle special characters
encoded_password = urllib.parse.quote_plus(settings.DB_PASSWORD)
SQLALCHEMY_DATABASE_URL = f"mssql+pyodbc://{settings.DB_USER}:{encoded_password}@{settings.DB_SERVER}/{settings.DB_NAME}?driver=ODBC+Driver+18+for+SQL+Server"

# Log connection info (without sensitive data)
logger.info(f"Connecting to SQL Server: {settings.DB_SERVER}/{settings.DB_NAME} with user {settings.DB_USER}")

# Create SQLAlchemy engine using pyodbc
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, 
    pool_pre_ping=True,
    connect_args={
        "TrustServerCertificate": "yes",
        "encrypt": "yes",
        # Use only ODBC-compatible connection parameters
        "fast_executemany": True,
    }
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Async context manager for database sessions
@asynccontextmanager
async def get_async_db():
    """
    Async context manager for getting a database session
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# MeiliSearch connection
def get_meilisearch_client():
    """
    Returns a MeiliSearch client
    """
    try:
        api_key = settings.MEILISEARCH_API_KEY if settings.MEILISEARCH_API_KEY != '' else None
        meilisearch_client = Client(settings.MEILISEARCH_HOST, api_key)
        return meilisearch_client
    except Exception as e:
        logger.error(f"Error connecting to MeiliSearch: {str(e)}")
        raise

# Neptune connection
def get_neptune_client() -> NeptuneClient:
    """
    Returns a Neptune client for Amazon Neptune with AWS SigV4 authentication.
    
    Returns:
        NeptuneClient: Neptune client
    """
    try:
        return NeptuneClient(
            endpoint=settings.NEPTUNE_ENDPOINT,
            port=settings.NEPTUNE_PORT,
            region=settings.AWS_REGION,
            iam_role_arn=settings.NEPTUNE_IAM_ROLE_ARN
        )
    except Exception as e:
        logger.error(f"Error connecting to Neptune: {str(e)}")
        raise

# Keep the original function for FastAPI dependencies
def get_db():
    """
    Dependency for getting a database session
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()