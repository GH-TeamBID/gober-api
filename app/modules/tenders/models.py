from sqlalchemy import Column, String, DateTime, ForeignKey, UniqueConstraint, Text
from sqlalchemy.sql import func
from app.core.database import Base

class UserTender(Base):
    """Model representing a user's saved tender"""
    __tablename__ = "user_tenders"
    
    id = Column(String(255), primary_key=True)
    user_id = Column(String(255), nullable=False, index=True)
    tender_uri = Column(String(1024), nullable=False, index=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    situation = Column(String(50), nullable=True)
    
    # Ensure a user can only save a specific tender once
    __table_args__ = (
        UniqueConstraint('user_id', 'tender_uri', name='uq_user_tender'),
    )

class TenderDocuments(Base):
    """Model representing a summary for a tender"""
    __tablename__ = "tender_documents"
    
    id = Column(String(255), primary_key=True)
    tender_uri = Column(String(1024), nullable=False, unique=True, index=True)
    summary = Column(Text, nullable=True)
    url_document = Column(String(1024), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
