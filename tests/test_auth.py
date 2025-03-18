# tests/test_auth.py

import os
import sys
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

# Import the app
from app.main import app
from app.core.database import get_db, Base
from app.modules.auth.services import get_password_hash
from app.modules.auth.models import User, UserRole

# Test data
TEST_USER = {
    "email": "test@example.com",
    "password": "Test123!",
    "role": UserRole.CLIENT
}

# Global variable to store access token
access_token = None
# Global variable to store admin access token
admin_token = None

# Create a test database engine
TEST_SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(
    TEST_SQLALCHEMY_DATABASE_URL, 
    connect_args={"check_same_thread": False}  # SQLite specific argument
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Override the dependency
def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

# Test client
client = TestClient(app)

# Setup and teardown
@pytest.fixture(scope="module")
def setup_db():
    # Clean up any existing database first
    Base.metadata.drop_all(bind=engine)
    
    # Create the test database
    Base.metadata.create_all(bind=engine)
    
    # Create a test user
    db = TestingSessionLocal()
    hashed_password = get_password_hash(TEST_USER["password"])
    db_user = User(
        email=TEST_USER["email"],
        password_hash=hashed_password,
        role=TEST_USER["role"]
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    db.close()
    
    yield
    
    # Clean up
    Base.metadata.drop_all(bind=engine)

# Tests for auth endpoints
def test_auth_root(setup_db):
    """This test must run first to set up the database"""
    response = client.get("/api/auth/")
    assert response.status_code == 200
    assert response.json() == {"message": "Auth module is working"}

def test_signup(setup_db):
    # Test new user registration
    response = client.post(
        "/api/auth/signup",
        json={
            "email": "newuser@example.com",
            "password": "NewPass123!",
            "role": "client"
        }
    )
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "newuser@example.com"
    assert "id" in data

def test_duplicate_signup(setup_db):
    # Test duplicated email
    response = client.post(
        "/api/auth/signup",
        json={
            "email": TEST_USER["email"],
            "password": "AnotherPass123!",
            "role": "client"
        }
    )
    assert response.status_code == 400
    assert "already registered" in response.json()["detail"]

def test_login(setup_db):
    global access_token  # Declare at the beginning of the function
    # Test login with valid credentials
    response = client.post(
        "/api/auth/login",
        json={
            "email": TEST_USER["email"],
            "password": TEST_USER["password"]
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    
    # Save token for other tests
    access_token = data["access_token"]

def test_login_wrong_password(setup_db):
    # Test login with wrong password
    response = client.post(
        "/api/auth/login",
        json={
            "email": TEST_USER["email"],
            "password": "WrongPassword123!"
        }
    )
    assert response.status_code == 401
    assert "Invalid credentials" in response.json()["detail"]

def test_login_nonexistent_user(setup_db):
    # Test login with non-existent user
    response = client.post(
        "/api/auth/login",
        json={
            "email": "nonexistent@example.com",
            "password": "Password123!"
        }
    )
    assert response.status_code == 401
    assert "Invalid credentials" in response.json()["detail"]

def test_me(setup_db):
    # Test getting user profile
    response = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {access_token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == TEST_USER["email"]
    assert data["role"] == TEST_USER["role"]

def test_me_no_token(setup_db):
    # Test getting user profile without token
    response = client.get("/api/auth/me")
    assert response.status_code == 401

def test_update_password(setup_db):
    global access_token  # Moved to the beginning of the function
    # Test updating password
    response = client.put(
        "/api/auth/password",
        headers={"Authorization": f"Bearer {access_token}"},
        json={
            "current_password": TEST_USER["password"],
            "new_password": "NewPassword123!"
        }
    )
    assert response.status_code == 200
    
    # Test login with new password
    response = client.post(
        "/api/auth/login",
        json={
            "email": TEST_USER["email"],
            "password": "NewPassword123!"
        }
    )
    assert response.status_code == 200
    
    # Save new token
    access_token = response.json()["access_token"]

def test_update_password_wrong_current(setup_db):
    # Test updating password with wrong current password
    response = client.put(
        "/api/auth/password",
        headers={"Authorization": f"Bearer {access_token}"},
        json={
            "current_password": "WrongPassword123!",
            "new_password": "AnotherNew123!"
        }
    )
    assert response.status_code == 400
    assert "Current password is incorrect" in response.json()["detail"]

def test_logout(setup_db):
    # Test logout
    response = client.post(
        "/api/auth/logout",
        headers={"Authorization": f"Bearer {access_token}"}
    )
    assert response.status_code == 200
    assert response.json() == {"message": "Successfully logged out"}

# Tests for the new endpoints
def test_create_admin_user(setup_db):
    # Create an admin user for testing admin-only endpoints
    response = client.post(
        "/api/auth/signup",
        json={
            "email": "admin@example.com",
            "password": "Admin123!",
            "role": "account_manager"
        }
    )
    assert response.status_code == 201
    assert response.json()["email"] == "admin@example.com"
    assert response.json()["role"] == "account_manager"
    
    # Login as admin to get token
    response = client.post(
        "/api/auth/login",
        json={
            "email": "admin@example.com",
            "password": "Admin123!"
        }
    )
    assert response.status_code == 200
    global admin_token
    admin_token = response.json()["access_token"]

def test_get_users(setup_db):
    # Test getting list of users as admin
    response = client.get(
        "/api/auth/users",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "users" in data
    assert "total" in data
    assert data["total"] >= 2  # At least the test user and admin user
    
    # Verify user data structure
    assert len(data["users"]) > 0
    user = data["users"][0]
    assert "id" in user
    assert "email" in user
    assert "role" in user

def test_get_users_unauthorized(setup_db):
    # Test getting users with regular user token (should fail)
    response = client.get(
        "/api/auth/users",
        headers={"Authorization": f"Bearer {access_token}"}
    )
    assert response.status_code == 403
    assert "Not enough permissions" in response.json()["detail"]
    
    # Test without token
    response = client.get("/api/auth/users")
    assert response.status_code == 401

def test_delete_user(setup_db):
    # First create a user to delete
    response = client.post(
        "/api/auth/signup",
        json={
            "email": "todelete@example.com",
            "password": "Delete123!",
            "role": "client"
        }
    )
    assert response.status_code == 201
    user_id = response.json()["id"]
    
    # Delete the user as admin
    response = client.delete(
        f"/api/auth/user/{user_id}",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200
    assert response.json()["id"] == user_id
    assert response.json()["email"] == "todelete@example.com"
    
    # Verify user is deleted
    response = client.post(
        "/api/auth/login",
        json={
            "email": "todelete@example.com",
            "password": "Delete123!"
        }
    )
    assert response.status_code == 401  # User should no longer exist

def test_delete_user_unauthorized(setup_db):
    # Get a user ID to try to delete
    response = client.get(
        "/api/auth/users",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    user_id = response.json()["users"][0]["id"]
    
    # Try to delete as regular user
    response = client.delete(
        f"/api/auth/user/{user_id}",
        headers={"Authorization": f"Bearer {access_token}"}
    )
    assert response.status_code == 403
    assert "Not enough permissions" in response.json()["detail"]
    
    # Try without token
    response = client.delete(f"/api/auth/user/{user_id}")
    assert response.status_code == 401

def test_delete_nonexistent_user(setup_db):
    # Try to delete a user that doesn't exist
    response = client.delete(
        "/api/auth/user/99999",  # Assuming this ID doesn't exist
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 404
    assert "not found" in response.json()["detail"]
