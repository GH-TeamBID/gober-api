from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime
from app.modules.tenders.models import TenderStatus, TenderType

class Lot(BaseModel):
    id: str
    title: str
    description: str
    budget: Optional[float] = None
    
class ContractingParty(BaseModel):
    id: str
    name: str
    address: Optional[str] = None
    contact_info: Optional[Dict[str, str]] = None
    
class Document(BaseModel):
    id: str
    title: str
    description: str
    issue_date: datetime
    url: str

class LegalDocument(Document):
    id: str
    title: str
    description: str
    url: str
    
class TechnicalDocument(Document):
    id: str
    title: str
    description: str
    url: str
    
class Attachment(Document):
    id: str
    title: str
    description: str
    url: str

class Category(BaseModel):
    id: str
    name: str
    description: Optional[str] = None


class TenderPreview(BaseModel):
    iri: str
    id: str
    status: str
    title: str
    description: str
    close_date: Optional[datetime] = None
    n_lots: int
    organization: str
    budget: Optional[float] = None
    location: Optional[str] = None
    type: str
    category: List[Category]
    issue_date: datetime

class TenderDetail(BaseModel):
    iri: str
    id: str
    title: str
    description: str
    description_plus: Optional[str] = None
    status: str
    close_date: Optional[datetime] = None
    planned_period: Optional[str] = None
    lots: List[Lot]
    contracting_party: ContractingParty
    estimated_value: Optional[float] = None
    total_amount: Optional[float] = None
    tax_exclusive_amount: Optional[float] = None
    realized_location: Optional[str] = None
    type: str
    subtype: Optional[str] = None
    category: List[Category]
    legal_document: Optional[LegalDocument] = None
    technical_document: Optional[TechnicalDocument] = None
    attachments: Optional[List[Attachment]] = None

class TenderBase(BaseModel):
    id: str
    title: str
    description: str
    type: str
    status: str
    organization: str
    budget: Optional[float] = None
    publish_date: datetime
    close_date: Optional[datetime] = None
    source_url: Optional[str] = None
    location: Optional[str] = None

class TenderResponse(TenderBase):
    is_saved: bool = False

class PaginationParams(BaseModel):
    page: int = Field(1, ge=1, description="Page number, starting from 1")
    limit: int = Field(10, ge=1, le=100, description="Number of items per page")
    
class TenderListResponse(BaseModel):
    items: List[TenderResponse]
    total: int
    page: int
    size: int
    total_pages: int = Field(..., description="Total number of pages")
    has_next: bool = Field(..., description="Whether there is a next page")
    has_prev: bool = Field(..., description="Whether there is a previous page")

class TenderFilter(BaseModel):
    type: Optional[str] = None
    status: Optional[str] = None
    organization: Optional[str] = None
    search: Optional[str] = None
    publication_date_from: Optional[datetime] = None
    publication_date_to: Optional[datetime] = None
    location: Optional[str] = None
    category: Optional[str] = None

class SearchResultItem(BaseModel):
    id: str
    score: float
    highlights: Optional[Dict[str, List[str]]] = None

class SearchResults(BaseModel):
    hits: List[SearchResultItem]
    total: int
    processing_time_ms: int

class AIContentUpdate(BaseModel):
    content: str = Field(..., min_length=10)

class SummaryResponse(BaseModel):
    id: int
    tender_id: str
    summary_content: str
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(
        from_attributes = True
    )

class DocumentResponse(BaseModel):
    id: int
    tender_id: str
    document_content: str
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(
        from_attributes = True
    )

class TenderTypeResponse(BaseModel):
    id: str
    name: str

class TenderTypesResponse(BaseModel):
    types: List[TenderTypeResponse]
