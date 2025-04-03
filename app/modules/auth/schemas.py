# app/modules/auth/schemas.py

from pydantic import BaseModel, EmailStr, Field, ConfigDict
from datetime import datetime
from app.modules.auth.models import UserRole
from typing import List, Optional

class BudgetRange(BaseModel):
    min_budget: Optional[float] = None
    max_budget: Optional[float] = None

class CpvCodeSchema(BaseModel):
    code: str
    description: Optional[str] = None
    es_description: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)
    
class ContractTypeSchema(BaseModel):
    type_code: str
    description: Optional[str] = None
    es_description: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)

class KeywordSchema(BaseModel):
    keyword: str
    
    model_config = ConfigDict(from_attributes=True)

# Base schema for input operations (create/update)
class UserCriteriaBase(BaseModel):
    min_budget: Optional[float] = None
    max_budget: Optional[float] = None
    cpv_codes: List[str] = []
    keywords: List[str] = []
    contract_types: List[str] = []

class UserCriteriaCreate(UserCriteriaBase):
    pass

class UserCriteriaUpdate(UserCriteriaBase):
    pass

# Response schema with rich object representations
class UserCriteriaResponse(BaseModel):
    id: int
    user_id: int
    min_budget: Optional[float] = None
    max_budget: Optional[float] = None
    cpv_codes: List[CpvCodeSchema] = []  # Output as full objects with descriptions
    keywords: List[KeywordSchema] = []    # Output as full objects
    contract_types: List[ContractTypeSchema] = []  # Output as full objects with descriptions
    
    model_config = ConfigDict(from_attributes=True)

class UserBase(BaseModel):
    email: EmailStr = Field(..., description="User email address")
    role: str = Field(default=UserRole.CLIENT, description="User role")
    full_name: Optional[str] = Field(None, description="User's full name")

class UserCreate(UserBase):
    password: str = Field(..., min_length=8, description="User password")

class UserUpdate(BaseModel):
    email: Optional[EmailStr] = Field(None, description="User email address")
    full_name: Optional[str] = Field(None, description="User's full name")
    password: Optional[str] = Field(None, min_length=8, description="New password")
    role: Optional[str] = Field(None, description="User role")

class UserResponse(UserBase):
    id: int
    created_at: datetime
    updated_at: datetime
    criteria: Optional[UserCriteriaResponse] = None

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
    refresh_token: Optional[str]
    token_type: str = "bearer"
    user_role: str

    class Config:
        from_attributes = True  # For ORM compatibility (formerly orm_mode)

class UserRoleResponse(BaseModel):
    """
    Schema for returning just the user's role.
    Used by the dedicated role endpoint.
    """
    role: str
    
    class Config:
        from_attributes = True

class PasswordUpdate(BaseModel):
    old_password: str = Field(..., min_length=8)
    new_password: str = Field(..., min_length=8)

class PaginatedCpvCodeResponse(BaseModel):
    """
    Schema for paginated CPV code responses
    """
    items: List[CpvCodeSchema]
    total: int
    skip: int
    limit: int
    has_more: bool
    
    model_config = ConfigDict(from_attributes=True)
