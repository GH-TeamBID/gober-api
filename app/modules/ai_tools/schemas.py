from pydantic import BaseModel, HttpUrl, Field
from typing import Optional, Dict, List, Any
from datetime import datetime

class ProcurementDocument(BaseModel):
    """A procurement document for AI processing"""
    document_id: str
    title: str
    url: HttpUrl
    document_type: Optional[str] = "default"

class TenderSummaryRequest(BaseModel):
    """Request model for generating a tender summary"""
    documents: List[ProcurementDocument] = Field(..., description="List of procurement documents to analyze")
    output_id: Optional[str] = Field(None, description="Optional ID for the output, will be auto-generated if not provided")
    regenerate: bool = False
    questions: Optional[List[str]] = None
    tender_hash: str

class TenderSummaryResponse(BaseModel):
    """Response model for a tender summary task"""
    task_id: str
    status: str  # queued, processing, completed, failed
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

class TenderSummaryStatusResponse(BaseModel):
    """Response model for a tender summary task status"""
    task_id: str
    status: str
    progress: Optional[float] = None  # 0-100 percentage
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

class TenderQuestionRequest(BaseModel):
    """Request model for asking a question about a tender"""
    tender_hash: str
    question: str
