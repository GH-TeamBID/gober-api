from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import settings
import logging
from meilisearch import Client
from app.core.neptune import NeptuneClient

# Configure logging
logger = logging.getLogger(__name__)

# Create connection string for Azure SQL using settings
SQLALCHEMY_DATABASE_URL = f"mssql+pytds://{settings.DB_USER}:{settings.DB_PASSWORD}@{settings.DB_SERVER}/{settings.DB_NAME}"

# Create SQLAlchemy engine and session with encryption enabled
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, 
    pool_pre_ping=True,
    connect_args={
        "encrypt": True,  # Enable encryption
        "check_hostname": True,  # Verify hostname in certificate
        "trust_server_certificate": False  # Verify server certificate
    }
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# MeiliSearch connection
def get_meilisearch_client():
    """
    Returns a MeiliSearch client
    """
    try:
        meilisearch_client = Client(settings.MEILISEARCH_HOST, settings.MEILISEARCH_API_KEY)
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

# Database session dependency
def get_db():
    """
    Dependency for getting a database session
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()