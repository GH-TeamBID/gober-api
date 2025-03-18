from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks, Path
from sqlalchemy.orm import Session
from app.modules.tenders import schemas, services, models
from app.modules.auth.services import get_current_user
from app.modules.auth.models import User
from app.core.database import get_db
from typing import Optional, List, Dict, Any
import datetime

router = APIRouter()

@router.get("/", response_model=schemas.TenderListResponse)
async def get_tenders(
    page: int = Query(1, ge=1, description="Page number, starting from 1"),
    limit: int = Query(10, ge=1, le=100, description="Number of items per page"),
    sort_by: str = Query("publish_date", pattern="^(publish_date|title|budget|close_date|organization)$"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
    type: Optional[str] = None,
    status: Optional[str] = None,
    organization: Optional[str] = None,
    location: Optional[str] = None,
    category: Optional[str] = None,
    publication_date_from: Optional[datetime.datetime] = None,
    publication_date_to: Optional[datetime.datetime] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user)
):
    """
    Get a paginated list of tenders with filtering, sorting, and search.
    
    If a search term is provided, it uses Meilisearch for full-text search
    to find matching tender IDs, then retrieves the corresponding data from
    the RDF database.
    
    Filters are applied to the RDF query, and pagination is handled based on
    the filtered results.
    """
    filters = {
        "type": type,
        "status": status,
        "organization": organization,
        "location": location,
        "category": category,
        "publication_date_from": publication_date_from,
        "publication_date_to": publication_date_to,
        "search": search
    }
    
    # Remove None values
    filters = {k: v for k, v in filters.items() if v is not None}
    
    client_id = current_user.id if current_user else None
    result = await services.get_tenders(
        db=db,
        page=page,
        limit=limit,
        sort_by=sort_by,
        sort_order=sort_order,
        filters=filters,
        client_id=client_id
    )
    
    return result

@router.get("/{tender_id}", response_model=schemas.TenderDetail)
async def get_tender_detail(
    tender_id: str = Path(..., description="The unique identifier of the tender"),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user)
):
    """
    Get detailed information about a specific tender.
    
    The tender details include all available metadata, attachments,
    requirements, contact information, and other related information.
    """
    client_id = current_user.id if current_user else None
    try:
        return await services.get_tender_detail(db=db, tender_id=tender_id, client_id=client_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving tender: {str(e)}")

@router.get("/preview/{tender_id}", response_model=schemas.TenderResponse)
async def get_tender_preview(
    tender_id: str = Path(..., description="The unique identifier of the tender"),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user)
):
    """
    Get a preview of a specific tender.
    
    This endpoint returns a simplified view of the tender, suitable for
    displaying in a list or search results.
    """
    client_id = current_user.id if current_user else None
    try:
        return services.get_tender(db=db, tender_id=tender_id, client_id=client_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving tender preview: {str(e)}")

@router.post("/{tender_id}/save")
async def toggle_save_tender(
    tender_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Toggle save/unsave a tender for the current client.
    Creates or removes a relationship in the ClientTender table.
    """
    return services.toggle_save_tender(db=db, tender_id=tender_id, client_id=current_user.id)

@router.get("/saved", response_model=schemas.TenderListResponse)
async def get_saved_tenders(
    page: int = Query(1, ge=1, description="Page number, starting from 1"),
    limit: int = Query(10, ge=1, le=100, description="Number of items per page"),
    sort_by: str = Query("saved_at", pattern="^(saved_at|publish_date|title|budget|close_date|organization)$"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get a paginated list of tenders saved by the current client.
    """
    return await services.get_saved_tenders(
        db=db,
        client_id=current_user.id,
        page=page,
        limit=limit,
        sort_by=sort_by,
        sort_order=sort_order
    )

@router.post("/{tender_id}/index", status_code=202)
async def trigger_tender_indexing(
    tender_id: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user)
):
    """
    Trigger indexing of a tender in Meilisearch.
    This is an admin operation that updates the search index.
    """
    # Add job to background tasks
    background_tasks.add_task(services.index_tender, tender_id)
    return {"status": "indexing started", "tender_id": tender_id}

@router.put("/{tender_id}/ai-summary", response_model=schemas.SummaryResponse)
async def update_ai_summary(
    tender_id: str,
    content_update: schemas.AIContentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update the AI-generated summary for a tender.
    Inserts or updates a record in the SummaryTender table.
    """
    return services.update_ai_summary(db=db, tender_id=tender_id, content=content_update.content)

@router.get("/summaries/{tender_id}", response_model=schemas.SummaryResponse)
async def get_ai_summary(
    tender_id: str,
    db: Session = Depends(get_db)
):
    """
    Get the AI-generated summary for a tender.
    """
    summary = db.query(models.SummaryTender).filter(models.SummaryTender.tender_id == tender_id).first()
    if not summary:
        raise HTTPException(status_code=404, detail=f"Summary for tender {tender_id} not found")
    return schemas.SummaryResponse.model_validate(summary)

@router.get("/types", response_model=schemas.TenderTypesResponse)
async def get_tender_types():
    """
    Get a list of available tender types.
    """
    types = services.get_tender_types()
    return {"types": types}
