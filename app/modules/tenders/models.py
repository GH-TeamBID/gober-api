from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.core.database import Base
import datetime
from enum import Enum as PyEnum

class TenderStatus(str, PyEnum):
    ACTIVE = "active"
    CLOSED = "closed"
    AWARDED = "awarded"
    CANCELLED = "cancelled"

class TenderType(str, PyEnum):
    PUBLIC = "public"
    PRIVATE = "private"
    INTERNATIONAL = "international"
    NATIONAL = "national"

# This model represents the relationship between clients and tenders
# It's used to track which tenders are saved by which clients
class ClientTender(Base):
    __tablename__ = "client_tenders"
    
    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("user.id"), nullable=False)  # Updated to reference "user" table
    tender_id = Column(String(100), nullable=False)  # This is the ID of the tender in Neptune
    saved_at = Column(DateTime, default=datetime.datetime.now(datetime.timezone.utc))
    
    # Relationships
    client = relationship("app.modules.auth.models.User")

# This model stores AI-generated summaries for tenders
class SummaryTender(Base):
    __tablename__ = "summary_tenders"
    
    id = Column(Integer, primary_key=True, index=True)
    tender_id = Column(String(100), nullable=False)  # This is the ID of the tender in Neptune
    summary_content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.now(datetime.timezone.utc))
    updated_at = Column(DateTime, default=datetime.datetime.now(datetime.timezone.utc), onupdate=datetime.datetime.now(datetime.timezone.utc))

# This model stores AI-generated documents for tenders
class DocumentTender(Base):
    __tablename__ = "document_tenders"
    
    id = Column(Integer, primary_key=True, index=True)
    tender_id = Column(String(100), nullable=False)  # This is the ID of the tender in Neptune
    document_content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.now(datetime.timezone.utc))
    updated_at = Column(DateTime, default=datetime.datetime.now(datetime.timezone.utc), onupdate=datetime.datetime.now(datetime.timezone.utc))
