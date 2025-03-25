#!/usr/bin/env python
# tests/check_config.py

"""
Script to check configuration and environment variables.
This helps diagnose issues with environment variable loading.
"""

import os
import sys
from dotenv import load_dotenv

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

def load_test_env():
    """Load environment variables from .env.test file"""
    # Get the project root directory
    root_dir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
    
    # Path to .env.test file
    env_test_path = os.path.join(root_dir, '.env.test')
    
    # Load environment variables from .env.test
    if os.path.exists(env_test_path):
        print(f"Loading test environment from: {env_test_path}")
        load_dotenv(env_test_path, override=True)
        return True
    else:
        print(f"Warning: Test environment file not found: {env_test_path}")
        return False

# Load test environment variables
load_test_env()

def check_env_vars():
    """Check environment variables"""
    print("\nEnvironment Variables:")
    print(f"AZURE_SQL_SERVER: {os.getenv('AZURE_SQL_SERVER')}")
    print(f"AZURE_SQL_DATABASE: {os.getenv('AZURE_SQL_DATABASE')}")
    print(f"AZURE_SQL_USERNAME: {os.getenv('AZURE_SQL_USERNAME')}")
    print(f"AZURE_SQL_PASSWORD: {'[SET]' if os.getenv('AZURE_SQL_PASSWORD') else '[NOT SET]'}")
    
    # Check for standard SQLAlchemy variable names
    print(f"DB_SERVER: {os.getenv('DB_SERVER')}")
    print(f"DB_NAME: {os.getenv('DB_NAME')}")
    print(f"DB_USER: {os.getenv('DB_USER')}")
    print(f"DB_PASSWORD: {'[SET]' if os.getenv('DB_PASSWORD') else '[NOT SET]'}")
    
    # Check other important variables
    print(f"SECRET_KEY: {'[SET]' if os.getenv('SECRET_KEY') else '[NOT SET]'}")
    print(f"API_PREFIX: {os.getenv('API_PREFIX')}")
    print(f"DEBUG: {os.getenv('DEBUG')}")

def check_settings():
    """Check settings from app.core.config"""
    try:
        from app.core.config import settings
        
        print("\nSettings from app.core.config:")
        print(f"DB_SERVER: {settings.DB_SERVER}")
        print(f"DB_NAME: {settings.DB_NAME}")
        print(f"DB_USER: {settings.DB_USER}")
        print(f"DB_PASSWORD: {'[SET]' if settings.DB_PASSWORD else '[NOT SET]'}")
        
        print(f"SECRET_KEY: {'[SET]' if settings.SECRET_KEY else '[NOT SET]'}")
        print(f"API_PREFIX: {settings.API_PREFIX}")
        print(f"DEBUG: {settings.DEBUG}")
        
        # Check database URL
        from app.core.database import SQLALCHEMY_DATABASE_URL
        print(f"\nSQLALCHEMY_DATABASE_URL: {SQLALCHEMY_DATABASE_URL}")
        
    except Exception as e:
        print(f"Error loading settings: {str(e)}")

if __name__ == "__main__":
    print("=" * 80)
    print("CONFIGURATION CHECK")
    print("=" * 80)
    
    check_env_vars()
    check_settings()
    
    print("\n" + "=" * 80) 