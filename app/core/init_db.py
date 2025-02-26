from app.core.database import Base, engine
from app.modules.auth.models import User
from app.modules.auth.services import pwd_context
from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.core.config import settings
import secrets

# Create all tables
def create_tables():
    Base.metadata.create_all(bind=engine)
    print("Tables created successfully")

# Add initial admin user
def create_initial_user():
    db = SessionLocal()
    try:
        # Check if admin user already exists
        user = db.query(User).filter(User.username == "admin").first()
        if not user:
            hashed_password = pwd_context.hash("admin123")
            new_user = User(username="admin", hashed_password=hashed_password)
            db.add(new_user)
            db.commit()
            print("Initial admin user created")
        else:
            print("Admin user already exists")
    finally:
        db.close()

def generate_secret_key():
    """Generate a secure random secret key"""
    return secrets.token_hex(32)

if __name__ == "__main__":
    create_tables()
    create_initial_user()
    
    # Generate and print a secure secret key
    print("\nYou can use this secure secret key in your .env file:")
    print(f"SECRET_KEY={generate_secret_key()}") 