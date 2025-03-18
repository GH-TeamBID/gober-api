# app/modules/auth/schemas.py

from pydantic import BaseModel, EmailStr, Field, ConfigDict
from datetime import datetime
from app.modules.auth.models import UserRole
from typing import List

class UserBase(BaseModel):
    email: EmailStr = Field(..., description="User email address")
    role: str = Field(default=UserRole.CLIENT, description="User role")

class UserCreate(UserBase):
    password: str = Field(..., min_length=8, description="User password")

class UserResponse(UserBase):
    id: int
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(
        from_attributes = True
    )

class UserListResponse(BaseModel):
    users: List[UserResponse]
    total: int

class LoginRequest(BaseModel):
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., description="User password")

class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    
class PasswordUpdate(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8)
