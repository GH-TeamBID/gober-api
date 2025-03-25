# app/modules/auth/models.py

from sqlalchemy import Column, Integer, String, DateTime, CheckConstraint, Table, ForeignKey, Float
from sqlalchemy.orm import relationship
from app.core.database import Base
import datetime
from enum import Enum as PyEnum

# Association tables for many-to-many relationships
user_cpv_codes = Table(
    "user_cpv_codes",
    Base.metadata,
    Column("user_criteria_id", Integer, ForeignKey("user_criteria.id"), primary_key=True),
    Column("cpv_code", String(20), ForeignKey("cpv_codes.code"), primary_key=True)
)

user_keywords = Table(
    "user_keywords",
    Base.metadata,
    Column("user_criteria_id", Integer, ForeignKey("user_criteria.id"), primary_key=True),
    Column("keyword", String(100), ForeignKey("keywords.keyword"), primary_key=True)
)

user_contract_types = Table(
    "user_contract_types",
    Base.metadata,
    Column("user_criteria_id", Integer, ForeignKey("user_criteria.id"), primary_key=True),
    Column("contract_type", String(50), ForeignKey("contract_types.type_code"), primary_key=True)
)

class UserCriteria(Base):
    __tablename__ = "user_criteria"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("user.id"), unique=True, nullable=False)
    
    # Budget range
    min_budget = Column(Float, nullable=True)
    max_budget = Column(Float, nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="criteria")
    
    # Many-to-many relationships
    cpv_codes = relationship("CpvCode", secondary=user_cpv_codes, 
                            collection_class=list, cascade="all, delete")
    keywords = relationship("Keyword", secondary=user_keywords, 
                            collection_class=list, cascade="all, delete")
    contract_types = relationship("ContractType", secondary=user_contract_types, 
                               collection_class=list, cascade="all, delete")

# Value objects for the many-to-many relationships
class CpvCode(Base):
    __tablename__ = "cpv_codes"
    
    code = Column(String(20), primary_key=True)
    description = Column(String(500), nullable=True)
    es_description = Column(String(500), nullable=True)
    
    def __repr__(self):
        return f"<CpvCode code={self.code}>"

class Keyword(Base):
    __tablename__ = "keywords"
    
    keyword = Column(String(100), primary_key=True)
    
    def __repr__(self):
        return f"<Keyword keyword={self.keyword}>"

class ContractType(Base):
    __tablename__ = "contract_types"
    
    type_code = Column(String(50), primary_key=True)
    description = Column(String(200), nullable=True)
    es_description = Column(String(200), nullable=True)
    
    def __repr__(self):
        return f"<ContractType type_code={self.type_code}>"

class UserRole(str, PyEnum):
    CLIENT = "client"
    ACCOUNT_MANAGER = "account_manager"

class User(Base):
    __tablename__ = "user"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(100), nullable=True)
    role = Column(
        String(50), 
        nullable=False, 
        default=UserRole.CLIENT.value  # Use .value explicitly for default
    )
    created_at = Column(DateTime, default=datetime.datetime.now(datetime.timezone.utc))
    updated_at = Column(DateTime, default=datetime.datetime.now(datetime.timezone.utc), onupdate=datetime.datetime.now(datetime.timezone.utc))
    criteria = relationship("UserCriteria", uselist=False, back_populates="user", 
                          cascade="all, delete-orphan")
    
    # Add check constraint to match SQL definition
    __table_args__ = (
        CheckConstraint(
            "role IN ('client', 'account_manager')",
            name="chk_user_role"
        ),
    )