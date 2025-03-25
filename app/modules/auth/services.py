# app/modules/auth/services.py

from sqlalchemy.orm import Session
from app.modules.auth import models, schemas
from passlib.context import CryptContext
import jwt as pyjwt
import datetime
from app.core.config import settings
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from app.core.database import get_db
from typing import Optional
import logging

pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=12,  # Set explicit rounds
    bcrypt__ident="2b"   # Use the modern 2b identifier
)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_PREFIX}/auth/login")


def get_user_criteria(db: Session, user_id: int):
    """
    Gets the search criteria for a user.
    Returns the raw ORM object which will be converted to the response schema.
    """
    return db.query(models.UserCriteria).filter(models.UserCriteria.user_id == user_id).first()

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifies if the entered password matches the stored hashed password.
    """
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """
    Generates a secure hash for the password.
    """
    return pwd_context.hash(password)

def get_user_by_email(db: Session, email: str):
    """
    Gets a user by their email address.
    """
    return db.query(models.User).filter(models.User.email == email).first()

def get_user_by_id(db: Session, user_id: int):
    """
    Gets a user by their ID.
    """
    return db.query(models.User).filter(models.User.id == user_id).first()

def get_users(db: Session, skip: int = 0, limit: int = 100):
    """
    Gets a list of users with pagination.
    
    Note: SQL Server requires an ORDER BY clause when using OFFSET/LIMIT pagination.
    """
    total = db.query(models.User).count()
    
    # Add ORDER BY clause to make SQL Server happy with pagination
    users = db.query(models.User).order_by(models.User.id).offset(skip).limit(limit).all()
    
    return {"users": users, "total": total}

def delete_user(db: Session, user_id: int):
    """
    Deletes a user by ID.
    """
    user = get_user_by_id(db, user_id)
    if not user:
        return None
    
    db.delete(user)
    db.commit()
    return user

def create_user_criteria(db: Session, user_id: int, criteria: schemas.UserCriteriaCreate):
    """
    Creates search criteria for a user.
    
    Input uses string lists, database uses ORM relationships.
    Returns the full ORM object.
    """
    # Check if user exists
    user = get_user_by_id(db, user_id)
    if not user:
        raise ValueError(f"User with ID {user_id} not found")
    
    # Check if criteria already exists
    existing = get_user_criteria(db, user_id)
    if existing:
        raise ValueError(f"Criteria already exists for user {user_id}")
    
    # Create criteria
    db_criteria = models.UserCriteria(
        user_id=user_id,
        min_budget=criteria.min_budget,
        max_budget=criteria.max_budget
    )
    db.add(db_criteria)
    db.flush()  # Need to flush to get the ID
    
    # Add CPV codes
    for code in criteria.cpv_codes:
        cpv = db.query(models.CpvCode).filter(models.CpvCode.code == code).first()
        if not cpv:
            cpv = models.CpvCode(code=code)
            db.add(cpv)
        db_criteria.cpv_codes.append(cpv)
    
    # Add keywords
    for kw in criteria.keywords:
        keyword = db.query(models.Keyword).filter(models.Keyword.keyword == kw).first()
        if not keyword:
            keyword = models.Keyword(keyword=kw)
            db.add(keyword)
        db_criteria.keywords.append(keyword)
    
    # Add contract types
    for ct in criteria.contract_types:
        contract_type = db.query(models.ContractType).filter(models.ContractType.type_code == ct).first()
        if not contract_type:
            contract_type = models.ContractType(type_code=ct)
            db.add(contract_type)
        db_criteria.contract_types.append(contract_type)
    
    db.commit()
    db.refresh(db_criteria)
    return db_criteria


def update_user_criteria(db: Session, user_id: int, criteria: schemas.UserCriteriaUpdate):
    """
    Updates search criteria for a user.
    
    Input uses string lists, database uses ORM relationships.
    Returns the full ORM object which will be converted by Pydantic.
    """
    # Get existing criteria
    db_criteria = get_user_criteria(db, user_id)
    if not db_criteria:
        # Create if it doesn't exist
        return create_user_criteria(db, user_id, criteria)
    
    # Update budget range
    if criteria.min_budget is not None:
        db_criteria.min_budget = criteria.min_budget
    if criteria.max_budget is not None:
        db_criteria.max_budget = criteria.max_budget
    
    # Clear and update CPV codes
    db_criteria.cpv_codes.clear()
    for code in criteria.cpv_codes:
        cpv = db.query(models.CpvCode).filter(models.CpvCode.code == code).first()
        if not cpv:
            cpv = models.CpvCode(code=code)
            db.add(cpv)
        db_criteria.cpv_codes.append(cpv)
    
    # Clear and update keywords
    db_criteria.keywords.clear()
    for kw in criteria.keywords:
        keyword = db.query(models.Keyword).filter(models.Keyword.keyword == kw).first()
        if not keyword:
            keyword = models.Keyword(keyword=kw)
            db.add(keyword)
        db_criteria.keywords.append(keyword)
    
    # Clear and update contract types
    db_criteria.contract_types.clear()
    for ct in criteria.contract_types:
        contract_type = db.query(models.ContractType).filter(models.ContractType.type_code == ct).first()
        if not contract_type:
            contract_type = models.ContractType(type_code=ct)
            db.add(contract_type)
        db_criteria.contract_types.append(contract_type)
    
    db.commit()
    db.refresh(db_criteria)
    return db_criteria


def delete_user_criteria(db: Session, user_id: int):
    """
    Deletes search criteria for a user.
    """
    db_criteria = get_user_criteria(db, user_id)
    if not db_criteria:
        return None
    
    db.delete(db_criteria)
    db.commit()
    return db_criteria


def update_user(db: Session, user_id: int, user_data: schemas.UserUpdate):
    """
    Updates a user's information (email, name, password, role).
    Only specified fields will be updated.
    
    Args:
        db: Database session
        user_id: ID of the user to update
        user_data: UserUpdate schema with fields to update
        
    Returns:
        Updated user object or None if user not found
    """
    user = get_user_by_id(db, user_id)
    if not user:
        return None
    
    # Update email if provided
    if user_data.email is not None:
        # Check if email is already taken by a different user
        existing_user = get_user_by_email(db, user_data.email)
        if existing_user and existing_user.id != user_id:
            raise ValueError(f"Email {user_data.email} is already in use")
        user.email = user_data.email
    
    # Update name if provided
    if user_data.name is not None:
        user.name = user_data.name
    
    # Update password if provided
    if user_data.password is not None:
        user.password_hash = get_password_hash(user_data.password)
    
    # Update role if provided
    if user_data.role is not None:
        user.role = user_data.role
    
    # Update timestamp
    user.updated_at = datetime.datetime.now(datetime.timezone.utc)
    
    # Commit changes to database
    db.commit()
    db.refresh(user)
    
    return user

def create_user(db: Session, user: schemas.UserCreate):
    """
    Creates a new user in the database.
    """
    hashed_password = get_password_hash(user.password)
    db_user = models.User(
        email=user.email,
        password_hash=hashed_password,
        role=user.role,
        full_name=user.full_name
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def authenticate_user(db: Session, email: str, password: str):
    """
    Authenticates a user in the database.
    """
    user = get_user_by_email(db, email)
    if not user:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user

def create_access_token(data: dict, expires_delta: int = None, user_role: str = None):
    """
    Creates a JWT token with the provided data.
    
    Args:
        data: Dictionary containing base token data (usually contains "sub" with user email)
        expires_delta: Token expiration time in minutes
        user_role: Optional role to include in the token
        
    Returns:
        JWT token string
    """
    
    to_encode = data.copy()
    
    # Add role to token if provided
    if user_role:
        to_encode.update({"role": user_role})
    
    if expires_delta is None:
        expires_delta = settings.ACCESS_TOKEN_EXPIRE_MINUTES
        
    expire = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=expires_delta)
    to_encode.update({"exp": expire})
    
    token = pyjwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return token

def update_password(db: Session, user: models.User, old_password: str, new_password: str):
    """
    Updates a user's password after verifying the old password.
    
    Args:
        db: Database session
        user: User model instance
        old_password: Current password (for verification)
        new_password: New password to set
        
    Returns:
        Updated user object
        
    Raises:
        ValueError: If old password verification fails
    """
    # Verify the old password first
    if not verify_password(old_password, user.password_hash):
        raise ValueError("Current password is incorrect")
    
    # Update to the new password
    user.password_hash = get_password_hash(new_password)
    user.updated_at = datetime.datetime.now(datetime.timezone.utc)
    db.commit()
    db.refresh(user)
    return user

async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    """
    Gets the current user from the JWT token.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        # Use the pyjwt import for consistency
        payload = pyjwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
        
        # We'll also get the role from the token if available
        token_role = payload.get("role")
        
    except pyjwt.PyJWTError:
        raise credentials_exception
        
    user = get_user_by_email(db, email)
    if user is None:
        raise credentials_exception
    
    # Verify that the role in the token matches the role in the database
    # This prevents users from using tokens with escalated privileges
    if token_role and user.role != token_role:
        # Log warning about potential token tampering
        logging.warning(f"Token role mismatch for user {email}. Token: {token_role}, DB: {user.role}")
        # Option 1: Disallow access completely
        # raise credentials_exception
        
        # Option 2: Allow access but ignore the token role (safer option)
        # No action needed as we're using the user from the database
        
    return user

async def get_current_admin_user(current_user: models.User = Depends(get_current_user)):
    """
    Verifies the current user is an admin.
    """
    if current_user.role != models.UserRole.ACCOUNT_MANAGER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    return current_user

def verify_token(token: str):
    """
    Verifies a JWT token and returns the payload.
    """
    # Fix the JWT import issue - ensure we're using PyJWT
    import jwt as pyjwt
    
    try:
        payload = pyjwt.decode(
            token, 
            settings.SECRET_KEY, 
            algorithms=[settings.ALGORITHM]
        )
        return payload
    except pyjwt.PyJWTError:
        return None

def search_cpv_codes(
    db: Session, 
    code_filter: str = None, 
    description_filter: str = None, 
    lang: str = "en",
    skip: int = 0, 
    limit: int = 20
):
    """
    Search for CPV codes with filtering and pagination.
    
    Args:
        db: Database session
        code_filter: Optional filter for CPV code (SQL LIKE pattern)
        description_filter: Optional filter for description (SQL LIKE pattern)
        lang: Language for description search ('en' or 'es')
        skip: Number of results to skip (for pagination)
        limit: Maximum number of results to return
        
    Returns:
        Dictionary containing the pagination info and list of CPV codes
    """
    query = db.query(models.CpvCode)
    
    # Apply filters if provided
    if code_filter:
        query = query.filter(models.CpvCode.code.like(f"%{code_filter}%"))
    
    if description_filter:
        if lang == "es":
            # Search in Spanish description
            query = query.filter(models.CpvCode.es_description.like(f"%{description_filter}%"))
        else:
            # Default: search in English description
            query = query.filter(models.CpvCode.description.like(f"%{description_filter}%"))
    
    # Get total count for pagination
    total = query.count()
    
    # Apply pagination
    query = query.order_by(models.CpvCode.code).offset(skip).limit(limit)
    
    # Execute query
    cpv_codes = query.all()
    
    return {
        "items": cpv_codes,
        "total": total,
        "skip": skip,
        "limit": limit,
        "has_more": total > (skip + limit)
    }