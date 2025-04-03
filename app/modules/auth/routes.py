# app/modules/auth/routes.py

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from app.modules.auth import schemas, services, models
from app.core.database import get_db
from typing import List
from app.core.config import settings

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
    
    # Create a token that includes both the user email and role
    access_token = services.create_access_token(
        data={"sub": user.email},
        user_role=user.role
    )

    # Refresh token
    refresh_token = services.create_access_token(
        data={"sub": user.email},
        user_role=user.role,
        expires_delta=settings.REFRESH_TOKEN_EXPIRE_MINUTES
    )
    
    # Return both the token and user role
    return schemas.LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        user_role=user.role
    )


@router.get("/role", response_model=schemas.UserRoleResponse)
async def get_current_user_role(current_user: models.User = Depends(services.get_current_user)):
    """
    Get the current user's role.
    This endpoint is separate from other user data to support independent role checks.
    """
    return schemas.UserRoleResponse(role=current_user.role)


@router.post("/logout")
def logout(current_user: models.User = Depends(services.get_current_user)):
    # In a stateless JWT system, the client is responsible for discarding the token
    # Here we just return a success message
    return {"message": "Successfully logged out"}


@router.post("/update-password", response_model=schemas.UserResponse)
def update_password(
    password_update: schemas.PasswordUpdate,
    current_user: models.User = Depends(services.get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update the current user's password after verifying the old password.
    """
    try:
        updated_user = services.update_password(
            db=db, 
            user=current_user, 
            old_password=password_update.old_password,
            new_password=password_update.new_password
        )
        return schemas.UserResponse.model_validate(updated_user)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


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


@router.put("/user/{user_id}", response_model=schemas.UserResponse)
async def update_user(
    user_id: int,
    user_data: schemas.UserUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(services.get_current_admin_user)
):
    """
    Update a user's information.
    Only accessible to account managers (admin).
    Fields not included in the request will remain unchanged.
    """
    try:
        updated_user = services.update_user(db, user_id, user_data)
        if updated_user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with ID {user_id} not found"
            )
        return updated_user
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
        
@router.get("/users/{user_id}/criteria", response_model=schemas.UserCriteriaResponse)
async def get_criteria(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(services.get_current_user)
):
    """
    Get search criteria for a user.
    Users can only get criteria for themselves unless they are admins.
    
    Returns rich object representations of relationships.
    """
    # Check permissions
    if current_user.id != user_id and current_user.role != models.UserRole.ACCOUNT_MANAGER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    # Get criteria with all relationships loaded
    criteria = services.get_user_criteria(db, user_id)
    if not criteria:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No criteria found for user {user_id}"
        )
    
    # Force loading of relationships to avoid lazy loading issues
    _ = criteria.cpv_codes
    _ = criteria.keywords
    _ = criteria.contract_types
    
    return criteria

@router.post("/users/{user_id}/criteria", response_model=schemas.UserCriteriaResponse)
async def create_criteria(
    user_id: int,
    criteria: schemas.UserCriteriaCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(services.get_current_user)
):
    """
    Create search criteria for a user.
    Users can only create criteria for themselves unless they are admins.
    
    Input accepts simple lists of strings, returns rich objects.
    """
    # Check permissions
    if current_user.id != user_id and current_user.role != models.UserRole.ACCOUNT_MANAGER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    try:
        # Create criteria - service returns ORM object with relationships
        result = services.create_user_criteria(db, user_id, criteria)
        
        # Force loading of relationships to avoid lazy loading issues
        _ = result.cpv_codes
        _ = result.keywords
        _ = result.contract_types
        
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.put("/users/{user_id}/criteria", response_model=schemas.UserCriteriaResponse)
async def update_criteria(
    user_id: int,
    criteria: schemas.UserCriteriaUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(services.get_current_user)
):
    """
    Update search criteria for a user.
    Users can only update criteria for themselves unless they are admins.
    
    Input accepts simple lists of strings, returns rich objects.
    """
    # Check permissions
    if current_user.id != user_id and current_user.role != models.UserRole.ACCOUNT_MANAGER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    # Update criteria - service returns ORM object with relationships
    result = services.update_user_criteria(db, user_id, criteria)
    
    # Force loading of relationships to avoid lazy loading issues
    _ = result.cpv_codes
    _ = result.keywords
    _ = result.contract_types
    
    return result

@router.delete("/users/{user_id}/criteria", response_model=schemas.UserCriteriaResponse)
async def delete_criteria(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(services.get_current_user)
):
    """
    Delete search criteria for a user.
    Users can only delete criteria for themselves unless they are admins.
    """
    # Check permissions
    if current_user.id != user_id and current_user.role != models.UserRole.ACCOUNT_MANAGER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    criteria = services.delete_user_criteria(db, user_id)
    if not criteria:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No criteria found for user {user_id}"
        )
    
    return criteria

@router.get("/cpv-codes", response_model=schemas.PaginatedCpvCodeResponse)
async def search_cpv_codes(
    code: str = Query(None, description="Filter by CPV code"),
    description: str = Query(None, description="Filter by description"),
    lang: str = Query("en", description="Language for description search (en or es)"),
    skip: int = Query(0, ge=0, description="Number of items to skip"),
    limit: int = Query(20, ge=1, le=100, description="Maximum number of items to return"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(services.get_current_user)
):
    """
    Search for CPV (Common Procurement Vocabulary) codes.
    
    Supports filtering by code and description, and returns paginated results.
    
    - **code**: Filter by CPV code (partial match)
    - **description**: Filter by description (partial match)
    - **lang**: Language for description search (en or es)
    - **skip**: Number of items to skip for pagination
    - **limit**: Maximum number of items to return
    """
    if lang not in ["en", "es"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Language must be 'en' or 'es'"
        )
    
    result = services.search_cpv_codes(
        db, 
        code_filter=code, 
        description_filter=description, 
        lang=lang,
        skip=skip, 
        limit=limit
    )
    
    return result

@router.get("/public/cpv-codes", response_model=schemas.PaginatedCpvCodeResponse)
async def public_search_cpv_codes(
    code: str = Query(None, description="Filter by CPV code"),
    description: str = Query(None, description="Filter by description"),
    lang: str = Query("en", description="Language for description search (en or es)"),
    skip: int = Query(0, ge=0, description="Number of items to skip"),
    limit: int = Query(20, ge=1, le=100, description="Maximum number of items to return"),
    db: Session = Depends(get_db)
):
    """
    Public endpoint to search for CPV codes without authentication.
    
    Supports filtering by code and description, and returns paginated results.
    
    - **code**: Filter by CPV code (partial match)
    - **description**: Filter by description (partial match)
    - **lang**: Language for description search (en or es)
    - **skip**: Number of items to skip for pagination
    - **limit**: Maximum number of items to return
    """
    if lang not in ["en", "es"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Language must be 'en' or 'es'"
        )
    
    result = services.search_cpv_codes(
        db, 
        code_filter=code, 
        description_filter=description, 
        lang=lang,
        skip=skip, 
        limit=limit
    )
    
    return result

@router.post("/refresh-access-token") #, response_model=schemas.LoginResponse
def refresh_access_token(
    current_user: models.User = Depends(services.get_current_user),
    db: Session = Depends(get_db)
):
    #return current_user
    """
    Refresh access token by refresh token
    """
    # Create a token that includes both the user email and role
    access_token = services.create_access_token(
        data={"sub": current_user.email},
        user_role=current_user.role
    )
    
    return schemas.LoginResponse(
        access_token=access_token,
        refresh_token=None,
        token_type="bearer",
        user_role=current_user.role
    )