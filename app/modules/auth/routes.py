# app/modules/auth/routes.py

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from app.modules.auth import schemas, services, models
from app.core.database import get_db
from typing import List

router = APIRouter()

@router.get("/")
async def auth_root():
    return {"message": "Auth module is working"}


@router.post("/signup", response_model=schemas.UserResponse, status_code=status.HTTP_201_CREATED)
def signup(user: schemas.UserCreate, db: Session = Depends(get_db)):
    # Check if email already exists
    db_user = services.get_user_by_email(db, email=user.email)
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create new user
    return services.create_user(db=db, user=user)


@router.post("/login", response_model=schemas.LoginResponse)
def login(login_req: schemas.LoginRequest, db: Session = Depends(get_db)):
    user = services.authenticate_user(db, login_req.email, login_req.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token = services.create_access_token({"sub": user.email})
    return schemas.LoginResponse(access_token=access_token)


@router.post("/logout")
def logout(current_user: models.User = Depends(services.get_current_user)):
    # In a stateless JWT system, the client is responsible for discarding the token
    # Here we just return a success message
    return {"message": "Successfully logged out"}


@router.put("/password", response_model=schemas.UserResponse)
def update_password(
    password_update: schemas.PasswordUpdate,
    current_user: models.User = Depends(services.get_current_user),
    db: Session = Depends(get_db)
):
    # Verify current password
    if not services.verify_password(password_update.current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )
    
    # Update password
    updated_user = services.update_password(db, current_user, password_update.new_password)
    return updated_user


@router.get("/me", response_model=schemas.UserResponse)
def read_users_me(current_user: models.User = Depends(services.get_current_user)):
    return current_user


@router.get("/users", response_model=schemas.UserListResponse)
async def get_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(services.get_current_admin_user)
):
    """
    Get a list of all users.
    Only accessible to account managers.
    """
    return services.get_users(db, skip=skip, limit=limit)


@router.delete("/user/{user_id}", response_model=schemas.UserResponse)
async def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(services.get_current_admin_user)
):
    """
    Delete a user by ID.
    Only accessible to account managers.
    """
    user = services.delete_user(db, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_id} not found"
        )
    return user