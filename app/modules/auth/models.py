# app/modules/auth/models.py

from sqlalchemy import Column, Integer, String, Boolean, DateTime, CheckConstraint
from app.core.database import Base
import datetime
from enum import Enum as PyEnum

class UserRole(str, PyEnum):
    CLIENT = "client"
    ACCOUNT_MANAGER = "account_manager"

class User(Base):
    __tablename__ = "user"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False, default=UserRole.CLIENT)
    created_at = Column(DateTime, default=datetime.datetime.now(datetime.timezone.utc))
    updated_at = Column(DateTime, default=datetime.datetime.now(datetime.timezone.utc), onupdate=datetime.datetime.now(datetime.timezone.utc))
    
    # Add check constraint to match SQL definition
    __table_args__ = (
        CheckConstraint(
            "role IN ('client', 'account_manager')",
            name="chk_user_role"
        ),
    )