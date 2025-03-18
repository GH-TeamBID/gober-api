# app/modules/auth/services.py

from sqlalchemy.orm import Session
from app.modules.auth import models, schemas
from passlib.context import CryptContext
import jwt
import datetime
from app.core.config import settings
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from app.core.database import get_db
from typing import Optional

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_PREFIX}/auth/login")


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
    """
    total = db.query(models.User).count()
    users = db.query(models.User).offset(skip).limit(limit).all()
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

def create_user(db: Session, user: schemas.UserCreate):
    """
    Creates a new user in the database.
    """
    hashed_password = get_password_hash(user.password)
    db_user = models.User(
        email=user.email,
        password_hash=hashed_password,
        role=user.role
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

def create_access_token(data: dict, expires_delta: int = None):
    """
    Creates a JWT token with the provided data.
    """
    to_encode = data.copy()
    
    if expires_delta is None:
        expires_delta = settings.ACCESS_TOKEN_EXPIRE_MINUTES
        
    expire = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=expires_delta)
    to_encode.update({"exp": expire})
    
    token = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return token

def update_password(db: Session, user: models.User, new_password: str):
    """
    Updates a user's password.
    """
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
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except jwt.InvalidTokenError:
        raise credentials_exception
        
    user = get_user_by_email(db, email)
    if user is None:
        raise credentials_exception
        
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