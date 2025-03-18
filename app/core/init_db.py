from app.core.database import Base, engine, get_neptune_client, get_meilisearch_client
from app.modules.auth.models import User, UserRole
from app.modules.auth.services import get_password_hash
from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.core.config import settings
import secrets
import logging

# Configure logging
logger = logging.getLogger(__name__)

# Create all SQL tables
def create_tables():
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("SQL tables created successfully")
    except Exception as e:
        logger.error(f"Error creating SQL tables: {str(e)}")
        raise

# Initialize Neptune graph database
def init_neptune():
    try:
        client = get_neptune_client()
        # Create basic graph structure
        # This is a placeholder - actual graph initialization would depend on your schema
        client.submit("g.V().drop()").all().result()  # Clear existing data
        logger.info("Neptune graph initialized successfully")
        client.close()
    except Exception as e:
        logger.error(f"Error initializing Neptune: {str(e)}")
        logger.warning("Continuing without Neptune initialization")

# Initialize MeiliSearch indexes
def init_meilisearch():
    try:
        client = get_meilisearch_client()
        # Create and configure indexes
        client.create_index('tenders', {'primaryKey': 'id'})
        client.index('tenders').update_settings({
            'searchableAttributes': [
                'title',
                'description',
                'type',
                'status'
            ],
            'sortableAttributes': [
                'publishDate',
                'closeDate',
                'budget'
            ]
        })
        logger.info("MeiliSearch indexes created successfully")
    except Exception as e:
        logger.error(f"Error initializing MeiliSearch: {str(e)}")
        logger.warning("Continuing without MeiliSearch initialization")

# Add initial admin user
def create_initial_user():
    db = SessionLocal()
    try:
        # Check if admin user already exists
        user = db.query(User).filter(User.email == "admin@example.com").first()
        if not user:
            hashed_password = get_password_hash("admin123")
            new_user = User(
                email="admin@example.com",
                password_hash=hashed_password,
                role=UserRole.ACCOUNT_MANAGER
            )
            db.add(new_user)
            db.commit()
            logger.info("Initial admin user created")
        else:
            logger.info("Admin user already exists")
    except Exception as e:
        logger.error(f"Error creating initial user: {str(e)}")
        db.rollback()
        raise
    finally:
        db.close()

def generate_secret_key():
    """Generate a secure random secret key"""
    return secrets.token_hex(32)

def init_all():
    """Initialize all database components"""
    create_tables()
    create_initial_user()
    
    # These may fail in development if services aren't available
    # We catch exceptions and continue
    try:
        init_neptune()
    except Exception as e:
        logger.warning(f"Neptune initialization skipped: {str(e)}")
    
    try:
        init_meilisearch()
    except Exception as e:
        logger.warning(f"MeiliSearch initialization skipped: {str(e)}")
    
    logger.info("Database initialization completed")

if __name__ == "__main__":
    # Configure logging for script execution
    logging.basicConfig(level=logging.INFO)
    
    # Initialize all components
    init_all()
    
    # Generate and print a secure secret key
    print("\nYou can use this secure secret key in your .env file:")
    print(f"SECRET_KEY={generate_secret_key()}") 