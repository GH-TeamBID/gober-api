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
    country: Optional[str] = None
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

    def __str__(self):
        return f"""{self.country_code}
                {self.nuts_code}
                {self.geographic_name}
                {self.address}"""

class ProcurementDocument(BaseModel):
    title: str
    document_type: str
    access_url: Optional[str] = None

    def __str__(self):
        return f"""{self.title}
                ({self.document_type})
                {self.access_url[:50]}"""

class Purpose(BaseModel):
    main_classifications: List[str] = []
    additional_classifications: List[str] = []

    def __str__(self):
        return f"""{self.main_classifications}
                {self.additional_classifications}"""

class ContractTerm(BaseModel):
    contract_nature_type: str
    additional_contract_nature: Optional[str] = None
    place_of_performance: Optional[Location] = None

    def __str__(self):
        return f"""{self.contract_nature_type}
                {self.additional_contract_nature}
                {self.place_of_performance}"""

class SubmissionTerm(BaseModel):
    receipt_deadline: Optional[datetime] = None
    language: Optional[str] = None

    def __str__(self):
        return f"""{self.receipt_deadline}
                {self.language}"""

class Period(BaseModel):
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    duration_in_months: Optional[int] = None

    def __str__(self):
        return f"""{self.start_date}
                {self.end_date}
                {self.duration_in_months}"""

class Lot(BaseModel):
    id: str
    title: Optional[str] = None
    description: Optional[str] = None
    estimated_value: Optional[MonetaryValue] = None

    def __str__(self):
        return f"""{self.id}
                {self.title}
                {self.description}
                {self.estimated_value}"""

class TenderDetail(BaseModel):
    """Complete detail of a tender procedure from the RDF graph"""
    uri: str
    identifier: Optional[Identifier] = None
    title: str
    description: Optional[str] = None
    summary: Optional[str] = None

    # Values
    estimated_value: Optional[MonetaryValue] = None
    net_value: Optional[MonetaryValue] = None
    gross_value: Optional[MonetaryValue] = None

    # Dates and periods
    contract_period: Optional[Period] = None
    planned_period: Optional[Period] = None

    # Organization
    buyer: Optional[Organization] = None

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

    def __str__(self):
        return f"""{self.uri}
                {self.identifier}
                {self.title}
                {self.description}
                {self.summary}
                {self.estimated_value}
                {self.net_value}
                {self.gross_value}
                {self.contract_period}
                {self.planned_period}
                {self.buyer}
                {self.purpose}
                {self.contract_term}
                {self.submission_term}
                {self.additional_information}
                {self.status}
                {self.procurement_documents}
                {self.lots}"""

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

class Document(BaseModel):
    """Schema for a tender document"""
    id: str
    uuid: str
    description: Optional[str] = None
    url: Optional[HttpUrl] = None
    doc_type: str
    publication_date: Optional[datetime] = None

class TenderDocuments(BaseModel):
    """Schema for tender documents"""
    tender_uri: str
    documents: List[Document]

class TenderDocumentResponse(BaseModel):
    """Response model for retrieving tender AI documents"""
    tender_hash: str
    summary: Optional[str] = None
    ai_document: str
    combined_chunks: str

class TenderDocumentContentResponse(BaseModel):
    """Response model for the ai-document-content/{tender_id} endpoint that returns both document and chunks"""
    ai_document: str
    combined_chunks: str
