from pydantic import BaseModel, Field, HttpUrl, AnyUrl
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

class ContractNatureType(str, Enum):
    SUPPLY = "supply"
    SERVICES = "services"
    WORKS = "works"
    
class TenderStatus(str, Enum):
    PLANNED = "planned"
    ACTIVE = "active"
    CLOSED = "closed"
    AWARDED = "awarded"
    CANCELLED = "cancelled"

class MonetaryValue(BaseModel):
    amount: float
    currency: str

class Identifier(BaseModel):
    notation: str
    scheme: Optional[str] = None

class Address(BaseModel):
    country_code: Optional[str] = None
    nuts_code: Optional[str] = None
    address_area: Optional[str] = None
    admin_unit: Optional[str] = None
    post_code: Optional[str] = None
    post_name: Optional[str] = None
    thoroughfare: Optional[str] = None

class ContactPoint(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    telephone: Optional[str] = None
    fax: Optional[str] = None

class Organization(BaseModel):
    id: str
    legal_name: str
    tax_identifier: Optional[Identifier] = None
    legal_identifier: Optional[Identifier] = None
    buyer_profile: Optional[HttpUrl] = None
    address: Optional[Address] = None
    contact_point: Optional[ContactPoint] = None

class Location(BaseModel):
    country_code: Optional[str] = None
    nuts_code: Optional[str] = None
    geographic_name: Optional[str] = None
    address: Optional[Address] = None

class ProcurementDocument(BaseModel):
    id: str
    title: str
    document_type: str
    access_url: Optional[HttpUrl] = None

class Purpose(BaseModel):
    main_classifications: List[str] = []
    additional_classifications: List[str] = []

class ContractTerm(BaseModel):
    contract_nature_type: str
    additional_contract_nature: Optional[str] = None
    place_of_performance: Optional[Location] = None

class SubmissionTerm(BaseModel):
    receipt_deadline: Optional[datetime] = None
    languages: List[str] = []

class Period(BaseModel):
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    duration_in_months: Optional[int] = None

class Lot(BaseModel):
    id: str
    title: Optional[str] = None
    description: Optional[str] = None
    estimated_value: Optional[MonetaryValue] = None

class TenderDetail(BaseModel):
    """Complete detail of a tender procedure from the RDF graph"""
    id: str
    uri: AnyUrl
    identifier: Optional[Identifier] = None
    title: str
    description: Optional[str] = None
    summary: Optional[str] = None
    
    # Values
    estimated_value: Optional[MonetaryValue] = None
    net_value: Optional[MonetaryValue] = None
    gross_value: Optional[MonetaryValue] = None
    
    # Dates and periods
    submission_deadline: Optional[datetime] = None
    contract_period: Optional[Period] = None
    planned_period: Optional[Period] = None
    
    # Organization
    buyer: Optional[Organization] = None
    
    # Location
    place_of_performance: Optional[Location] = None
    
    # Classification
    purpose: Optional[Purpose] = None
    
    # Contract details
    contract_term: Optional[ContractTerm] = None
    submission_term: Optional[SubmissionTerm] = None
    
    # Additional information
    additional_information: Optional[str] = None
    status: Optional[TenderStatus] = None
    
    # Related documents
    procurement_documents: List[ProcurementDocument] = []
    
    # Lots
    lots: List[Lot] = []

class TenderResponse(BaseModel):
    """API response model for tender details"""
    data: TenderDetail
    meta: Dict[str, Any] = {}

class UserTender(BaseModel):
    """Schema representing a user's saved tender relationship"""
    id: Optional[str] = None
    user_id: str
    tender_uri: str
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: Optional[datetime] = None
    situation: Optional[str] = None

    class Config:
        orm_mode = True
        json_encoders = {
            datetime: lambda dt: dt.isoformat()
        }

class TenderSummary(BaseModel):
    """Schema representing a tender summary"""
    id: Optional[str] = None
    tender_uri: str
    summary: str
    url_document: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        orm_mode = True
        json_encoders = {
            datetime: lambda dt: dt.isoformat()
        }

class TenderSummaryCreate(BaseModel):
    """Schema for creating a tender summary"""
    tender_uri: str
    summary: str

class TenderPreview(BaseModel):
    """Schema for tender preview data used in listing/search results"""
    tender_hash: str
    tender_id: str
    title: Optional[str] = None
    description: Optional[str] = None
    submission_date: Optional[datetime] = None
    n_lots: int = 0
    pub_org_name: Optional[str] = None
    budget: Optional[MonetaryValue] = None
    location: Optional[str] = None
    contract_type: Optional[str] = None
    cpv_categories: List[str] = []

class PaginatedTenderResponse(BaseModel):
    """Paginated response for tender listing"""
    items: List[TenderPreview] = []
    total: int = 0
    page: int = 1
    size: int = 10
    has_next: bool = False
    has_prev: bool = False

class UserTenderCreate(BaseModel):
    """Schema for creating a user tender relationship"""
    tender_uri: str
    user_id: str
    situation: Optional[str] = None

class SaveTenderRequest(BaseModel):
    """Schema for the client request to save a tender"""
    tender_uri: str
    situation: Optional[str] = None
    
class UnsaveTenderRequest(BaseModel):
    """Schema for the client request to unsave a tender"""
    tender_uri: str
