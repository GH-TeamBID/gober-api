from app.core.database import Base, engine, get_neptune_client, get_meilisearch_client
from app.modules.auth.models import User, UserRole
from app.modules.auth.services import get_password_hash
from app.core.database import SessionLocal
import secrets
import logging
import subprocess
import sys
import os
from app.core.config import settings

# Configure logging
logger = logging.getLogger(__name__)

# Use Alembic to run migrations
def run_migrations():
    try:
        logger.info("Running database migrations with Alembic")
        # Get the absolute path of the project root
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
        
        # Run Alembic migrations
        subprocess.check_call(
            ["alembic", "upgrade", "head"], 
            cwd=project_root
        )
        logger.info("Database migrations completed successfully")
    except Exception as e:
        logger.error(f"Error running migrations: {str(e)}")
        raise

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
def create_initial_user(
    email=None, 
    password=None, 
    force_create=False
):
    """
    Create initial admin user if one does not already exist.
    
    Args:
        email (str, optional): Admin email. If None, uses ADMIN_EMAIL from settings or defaults to "admin@example.com"
        password (str, optional): Admin password. If None, uses ADMIN_PASSWORD from settings or defaults to "admin123"
        force_create (bool): If True, create a new admin even if one already exists
        
    Returns:
        bool: True if user was created, False if user already existed
    """
    # Use parameters, then settings, then defaults
    admin_email = email or getattr(settings, "ADMIN_EMAIL", "admin@example.com")
    admin_password = password or getattr(settings, "ADMIN_PASSWORD", "admin123")
    
    # Get the string value of the enum - this is what's stored in the database
    admin_role_value = UserRole.ACCOUNT_MANAGER.value
    logger.info(f"Using admin role value: {admin_role_value} (type: {type(admin_role_value)})")
    
    db = SessionLocal()
    try:
        logger.info("Checking if admin user exists")
        
        # Use the string value directly for comparison
        user = db.query(User).filter(User.role == admin_role_value).first()
        
        logger.info(f"Query completed, user found: {user is not None}")
        
        if user and not force_create:
            logger.info(f"Admin user {user.email} already exists")
            return False
        
        if user and force_create:
            logger.info(f"Force creating new admin user {admin_email}")
        
        # Create new admin user with role value
        hashed_password = get_password_hash(admin_password)
        new_user = User(
            email=admin_email,
            password_hash=hashed_password,
            role=admin_role_value  # Use the string value explicitly
        )
        db.add(new_user)
        db.commit()
        logger.info(f"Admin user {admin_email} created successfully")
        return True
    except Exception as e:
        logger.error(f"Error creating admin user: {str(e)}")
        db.rollback()
        raise
    finally:
        db.close()

def generate_secret_key():
    """Generate a secure random secret key"""
    return secrets.token_hex(32)

def init_all():
    """Initialize all database components"""
    # Use Alembic for database migrations instead of directly creating tables
    run_migrations()
    
    # Create initial admin user
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
    
    # Parse command line arguments for admin creation
    import argparse
    parser = argparse.ArgumentParser(description='Initialize database and create admin user')
    parser.add_argument('--email', help='Admin user email')
    parser.add_argument('--password', help='Admin user password')
    parser.add_argument('--force', action='store_true', help='Force creation even if admin exists')
    parser.add_argument('--skip-migrations', action='store_true', help='Skip running migrations')
    parser.add_argument('--admin-only', action='store_true', help='Only create admin user')
    
    args = parser.parse_args()
    
    if args.admin_only:
        # Only create admin user
        create_initial_user(args.email, args.password, args.force)
    else:
        # Initialize all components
        if args.skip_migrations:
            # Skip migrations and only initialize other components
            try:
                create_initial_user(args.email, args.password, args.force)
                try:
                    init_neptune()
                except Exception as e:
                    logger.warning(f"Neptune initialization skipped: {str(e)}")
                try:
                    init_meilisearch()
                except Exception as e:
                    logger.warning(f"MeiliSearch initialization skipped: {str(e)}")
            except Exception as e:
                logger.error(f"Initialization error: {str(e)}")
        else:
            # Run full initialization
            init_all()
    
    # Generate and print a secure secret key
    print("\nYou can use this secure secret key in your .env file:")
    print(f"SECRET_KEY={generate_secret_key()}") 