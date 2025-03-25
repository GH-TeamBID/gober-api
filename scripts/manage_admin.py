#!/usr/bin/env python
"""
Admin user management utility for Gober API.
This script allows you to create, list, update, and delete admin users.
"""

import os
import sys
import logging
import argparse
from sqlalchemy.exc import SQLAlchemyError

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.core.database import SessionLocal
from app.modules.auth.models import User, UserRole
from app.modules.auth.services import get_password_hash, verify_password

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def create_admin(email, password, force=False):
    """Create a new admin user"""
    db = SessionLocal()
    try:
        # Check if user already exists
        existing_user = db.query(User).filter(User.email == email).first()
        if existing_user:
            if existing_user.role == UserRole.ACCOUNT_MANAGER:
                logger.warning(f"Admin user with email {email} already exists")
                if not force:
                    return False
                
                # Update existing admin if force is True
                existing_user.password_hash = get_password_hash(password)
                db.commit()
                logger.info(f"Updated password for admin user {email}")
                return True
                
            elif force:
                # Convert existing user to admin
                existing_user.role = UserRole.ACCOUNT_MANAGER
                existing_user.password_hash = get_password_hash(password)
                db.commit()
                logger.info(f"Converted user {email} to admin role")
                return True
            else:
                logger.error(f"User {email} exists but is not an admin. Use --force to convert")
                return False
        
        # Create new admin user
        new_admin = User(
            email=email,
            password_hash=get_password_hash(password),
            role=UserRole.ACCOUNT_MANAGER
        )
        db.add(new_admin)
        db.commit()
        logger.info(f"Created new admin user: {email}")
        return True
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error: {str(e)}")
        return False
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating admin: {str(e)}")
        return False
    finally:
        db.close()

def list_admins():
    """List all admin users"""
    db = SessionLocal()
    try:
        admins = db.query(User).filter(User.role == UserRole.ACCOUNT_MANAGER).all()
        
        if not admins:
            logger.info("No admin users found")
            return
        
        print("\nAdmin Users:")
        print("-" * 60)
        print(f"{'ID':<5} {'Email':<40} {'Created At':<20}")
        print("-" * 60)
        
        for admin in admins:
            print(f"{admin.id:<5} {admin.email:<40} {admin.created_at}")
        
        print("-" * 60)
    except Exception as e:
        logger.error(f"Error listing admins: {str(e)}")
    finally:
        db.close()

def delete_admin(email):
    """Delete an admin user"""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if not user:
            logger.error(f"No user found with email: {email}")
            return False
        
        if user.role != UserRole.ACCOUNT_MANAGER:
            logger.error(f"User {email} is not an admin")
            return False
        
        db.delete(user)
        db.commit()
        logger.info(f"Deleted admin user: {email}")
        return True
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting admin: {str(e)}")
        return False
    finally:
        db.close()

def main():
    """Main entry point for the script"""
    parser = argparse.ArgumentParser(description='Admin user management')
    
    subparsers = parser.add_subparsers(dest='command', help='Command to run')
    
    # Create command
    create_parser = subparsers.add_parser('create', help='Create admin user')
    create_parser.add_argument('--email', required=True, help='Admin email')
    create_parser.add_argument('--password', required=True, help='Admin password')
    create_parser.add_argument('--force', action='store_true', help='Force update if user exists')
    
    # List command
    subparsers.add_parser('list', help='List all admin users')
    
    # Delete command
    delete_parser = subparsers.add_parser('delete', help='Delete admin user')
    delete_parser.add_argument('--email', required=True, help='Admin email to delete')
    
    args = parser.parse_args()
    
    if args.command == 'create':
        create_admin(args.email, args.password, args.force)
    elif args.command == 'list':
        list_admins()
    elif args.command == 'delete':
        delete_admin(args.email)
    else:
        parser.print_help()

if __name__ == '__main__':
    main() 