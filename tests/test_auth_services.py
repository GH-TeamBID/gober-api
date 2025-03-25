# tests/test_auth_services.py

import os
import sys
import pytest
import pytest_asyncio
from unittest.mock import patch, MagicMock
import datetime
import jwt
from fastapi import HTTPException

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

# Import the services and models
from app.modules.auth import services, models, schemas
from app.core.config import settings
from sqlalchemy.orm import Session

# Test data
TEST_USER = {
    "email": "test@example.com",
    "password": "Test123!",
    "role": models.UserRole.CLIENT
}

# Setup fixtures
@pytest.fixture
def db_session():
    """
    Create a mock database session for unit tests
    """
    return MagicMock(spec=Session)

@pytest.fixture
def test_user():
    """
    Create a test user object
    """
    user = models.User(
        id=1,
        email=TEST_USER["email"],
        password_hash=services.get_password_hash(TEST_USER["password"]),
        role=TEST_USER["role"]
    )
    return user

# Unit tests for auth services
def test_verify_password():
    """Test password verification"""
    # Hash a password
    hashed = services.get_password_hash("password123")
    
    # Verify correct password
    assert services.verify_password("password123", hashed) is True
    
    # Verify incorrect password
    assert services.verify_password("wrong_password", hashed) is False

def test_get_password_hash():
    """Test password hashing"""
    # Hash a password
    hashed = services.get_password_hash("password123")
    
    # Verify it's a string and not the original password
    assert isinstance(hashed, str)
    assert hashed != "password123"
    
    # Verify different passwords produce different hashes
    hashed2 = services.get_password_hash("password123")
    assert hashed != hashed2  # Bcrypt adds salt, so hashes should differ

def test_get_user_by_email(db_session, test_user):
    """Test getting a user by email"""
    # Setup mock return value
    db_session.query.return_value.filter.return_value.first.return_value = test_user
    
    # Call the service function
    user = services.get_user_by_email(db_session, TEST_USER["email"])
    
    # Verify the result
    assert user is test_user
    db_session.query.assert_called_once()
    db_session.query.return_value.filter.assert_called_once()

def test_get_user_by_email_not_found(db_session):
    """Test getting a non-existent user by email"""
    # Setup mock return value
    db_session.query.return_value.filter.return_value.first.return_value = None
    
    # Call the service function
    user = services.get_user_by_email(db_session, "nonexistent@example.com")
    
    # Verify the result
    assert user is None
    db_session.query.assert_called_once()

def test_create_user(db_session):
    """Test user creation"""
    # Create a user schema
    user_create = schemas.UserCreate(
        email=TEST_USER["email"],
        password=TEST_USER["password"],
        role=TEST_USER["role"]
    )
    
    # Call the service function
    result = services.create_user(db_session, user_create)
    
    # Verify the database operations
    db_session.add.assert_called_once()
    db_session.commit.assert_called_once()
    db_session.refresh.assert_called_once()
    
    # Verify the created user
    assert result.email == TEST_USER["email"]
    assert result.role == TEST_USER["role"]
    assert hasattr(result, "password_hash")

def test_authenticate_user_success(db_session, test_user):
    """Test successful user authentication"""
    # Setup mock for get_user_by_email
    with patch.object(services, 'get_user_by_email', return_value=test_user):
        # Call the service function with correct password
        user = services.authenticate_user(db_session, TEST_USER["email"], TEST_USER["password"])
        
        # Verify the result
        assert user is test_user

def test_authenticate_user_wrong_password(db_session, test_user):
    """Test authentication with wrong password"""
    # Setup mock for get_user_by_email
    with patch.object(services, 'get_user_by_email', return_value=test_user):
        # Call the service function with wrong password
        user = services.authenticate_user(db_session, TEST_USER["email"], "wrong_password")
        
        # Verify the result
        assert user is None

def test_authenticate_user_not_found(db_session):
    """Test authentication with non-existent user"""
    # Setup mock for get_user_by_email
    with patch.object(services, 'get_user_by_email', return_value=None):
        # Call the service function
        user = services.authenticate_user(db_session, "nonexistent@example.com", "password")
        
        # Verify the result
        assert user is None

def test_create_access_token():
    """Test JWT token creation"""
    # Create a token
    token = services.create_access_token({"sub": TEST_USER["email"]})
    
    # Verify it's a string
    assert isinstance(token, str)
    
    # Decode and verify the token
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    assert payload["sub"] == TEST_USER["email"]
    assert "exp" in payload

def test_create_access_token_with_expiry():
    """Test JWT token creation with custom expiry"""
    # Create a token with 5 minutes expiry
    token = services.create_access_token({"sub": TEST_USER["email"]}, expires_delta=5)
    
    # Decode and verify the token
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    
    # Calculate expected expiry time (approximately)
    now = datetime.datetime.now(datetime.timezone.utc)
    expected_exp = now + datetime.timedelta(minutes=5)
    
    # Allow for a small time difference due to test execution
    assert abs(payload["exp"] - expected_exp.timestamp()) < 10  # Within 10 seconds

def test_update_password(db_session, test_user):
    """Test password update"""
    # Call the service function
    result = services.update_password(db_session, test_user, "NewPassword123!")
    
    # Verify the database operations
    db_session.commit.assert_called_once()
    db_session.refresh.assert_called_once()
    
    # Verify the password was updated
    assert services.verify_password("NewPassword123!", result.password_hash)

@pytest.mark.asyncio
async def test_get_current_user_success(db_session, test_user):
    """Test getting current user from valid token"""
    # Create a token for the test user
    token = services.create_access_token({"sub": test_user.email})
    
    # Mock get_user_by_email
    with patch.object(services, 'get_user_by_email', return_value=test_user):
        # Call the service function
        user = await services.get_current_user(token, db_session)
        
        # Verify the result
        assert user is test_user

@pytest.mark.asyncio
async def test_get_current_user_invalid_token(db_session):
    """Test getting current user with invalid token"""
    # Create an invalid token
    token = "invalid_token"
    
    # Call the service function and expect an exception
    with pytest.raises(HTTPException) as excinfo:
        await services.get_current_user(token, db_session)
    
    # Verify the exception
    assert excinfo.value.status_code == 401
    assert "Could not validate credentials" in excinfo.value.detail

@pytest.mark.asyncio
async def test_get_current_user_user_not_found(db_session):
    """Test getting current user when user doesn't exist"""
    # Create a token
    token = services.create_access_token({"sub": "nonexistent@example.com"})
    
    # Mock get_user_by_email to return None
    with patch.object(services, 'get_user_by_email', return_value=None):
        # Call the service function and expect an exception
        with pytest.raises(HTTPException) as excinfo:
            await services.get_current_user(token, db_session)
        
        # Verify the exception
        assert excinfo.value.status_code == 401
        assert "Could not validate credentials" in excinfo.value.detail

# Add tests for the new functions
def test_get_user_by_id(db_session, test_user):
    """Test getting a user by ID"""
    # Setup mock return value
    db_session.query.return_value.filter.return_value.first.return_value = test_user
    
    # Call the service function
    user = services.get_user_by_id(db_session, 1)
    
    # Verify the result
    assert user is test_user
    db_session.query.assert_called_once()
    db_session.query.return_value.filter.assert_called_once()

def test_get_user_by_id_not_found(db_session):
    """Test getting a non-existent user by ID"""
    # Setup mock return value
    db_session.query.return_value.filter.return_value.first.return_value = None
    
    # Call the service function
    user = services.get_user_by_id(db_session, 999)
    
    # Verify the result
    assert user is None
    db_session.query.assert_called_once()

def test_get_users(db_session):
    """Test getting a list of users"""
    # Create test users
    test_users = [
        models.User(id=1, email="user1@example.com", password_hash="hash1", role=models.UserRole.CLIENT),
        models.User(id=2, email="user2@example.com", password_hash="hash2", role=models.UserRole.CLIENT),
        models.User(id=3, email="admin@example.com", password_hash="hash3", role=models.UserRole.ACCOUNT_MANAGER)
    ]
    
    # Setup mock return values
    db_session.query.return_value.count.return_value = len(test_users)
    db_session.query.return_value.offset.return_value.limit.return_value.all.return_value = test_users
    
    # Call the service function
    result = services.get_users(db_session, skip=0, limit=10)
    
    # Verify the result
    assert result["total"] == len(test_users)
    assert result["users"] == test_users
    db_session.query.return_value.offset.assert_called_once_with(0)
    db_session.query.return_value.offset.return_value.limit.assert_called_once_with(10)

def test_delete_user(db_session, test_user):
    """Test deleting a user"""
    # Setup mock for get_user_by_id
    with patch.object(services, 'get_user_by_id', return_value=test_user):
        # Call the service function
        result = services.delete_user(db_session, 1)
        
        # Verify the result
        assert result is test_user
        db_session.delete.assert_called_once_with(test_user)
        db_session.commit.assert_called_once()

def test_delete_user_not_found(db_session):
    """Test deleting a non-existent user"""
    # Setup mock for get_user_by_id
    with patch.object(services, 'get_user_by_id', return_value=None):
        # Call the service function
        result = services.delete_user(db_session, 999)
        
        # Verify the result
        assert result is None
        db_session.delete.assert_not_called()
        db_session.commit.assert_not_called()

@pytest.mark.asyncio
async def test_get_current_admin_user():
    """Test getting current admin user"""
    # Create an admin user
    admin_user = models.User(
        id=1,
        email="admin@example.com",
        password_hash="hash",
        role=models.UserRole.ACCOUNT_MANAGER
    )
    
    # Call the service function
    result = await services.get_current_admin_user(admin_user)
    
    # Verify the result
    assert result is admin_user

@pytest.mark.asyncio
async def test_get_current_admin_user_not_admin():
    """Test getting current admin user when user is not an admin"""
    # Create a regular user
    regular_user = models.User(
        id=1,
        email="user@example.com",
        password_hash="hash",
        role=models.UserRole.CLIENT
    )
    
    # Call the service function and expect an exception
    with pytest.raises(HTTPException) as excinfo:
        await services.get_current_admin_user(regular_user)
    
    # Verify the exception
    assert excinfo.value.status_code == 403
    assert "Not enough permissions" in excinfo.value.detail 