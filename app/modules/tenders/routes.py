from fastapi import APIRouter, Depends, HTTPException, status, Path, Body, Query, Request
from app.modules.tenders import schemas, services
from typing import Optional, List, Dict, Any
from app.modules.auth.services import get_current_user
from app.modules.auth.models import User
from sqlalchemy.orm import Session
from app.core.database import get_db
import logging
from app.modules.search import services as SearchService
from datetime import datetime, timezone

router = APIRouter(tags=["tenders"])

# Configure logging
logger = logging.getLogger(__name__)

@router.get("/ai_document_sas_token/{tender_id}", response_model=str)
async def get_ai_document_sas_token(
    tender_id: str = Path(..., description="The URI or hash identifier of the tender to retrieve")
):
    """
    Get a SAS token for a specific tender document.
    """
    try:
        logger.info(f"Getting SAS token for tender ID: {tender_id}")
        sas_token = await services.get_ai_document_sas_token(tender_id)
        logger.info(f"SAS token generated successfully")
        return sas_token
    except Exception as e:
        logger.error(f"Error generating SAS token for tender ID {tender_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate SAS token: {str(e)}"
        )

@router.get("/ai_documents/{tender_id}")
async def get_ai_documents(
    tender_id: str = Path(..., description="The URI or hash identifier of the tender to retrieve"),
    db: Session = Depends(get_db)
):
    """
    Get the AI documents path and summary for a specific tender.
    This endpoint does not retrieve the AI document content, only the path and summary.
    For the AI document content, use the /ai-tender-documents/{tender_id} endpoint.
    """
    try:
        ai_documents = await services.get_ai_documents(tender_id, db)
        if ai_documents is not None: return ai_documents
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tender document not found"
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving tender documents: {str(e)}"
        )

@router.get("/ai-tender-documents/{tender_id}", response_model=schemas.TenderDocumentResponse)
async def get_ai_tender_documents(
    tender_id: str = Path(..., description="The URI or hash identifier of the tender to retrieve"),
    db: Session = Depends(get_db)
):
    """
    Retrieve the AI document and combined chunks for a specific tender.

    Args:
        tender_id: The unique identifier hash for the tender

    Returns:
        The AI document content, summary, and combined chunks as JSON
    """
    try:
        return await services.get_ai_tender_documents(tender_id, db)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving AI tender documents: {str(e)}"
        )

@router.get("/documents/{tender_id}", response_model=schemas.TenderDocuments)
async def get_tender_documents(
    tender_id: str = Path(..., description="The URI or hash identifier of the tender to retrieve")
):
    """
    Get the documents for a specific tender.

    This endpoint retrieves the documents for a specific tender from the RDF graph database.
    The tender is identified by either its full URI or its hash identifier.
    """
    try:
        return await services.get_tender_documents(tender_id)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving tender documents: {str(e)}"
        )

@router.get("/") #, response_model=schemas.PaginatedTenderResponse
async def get_tenders(
    request: Request,
    offset: int = Query(0, ge=0, description="Number of items to skip"),
    limit: int = Query(10, ge=1, le=100, description="Number of items to return"),
    is_saved: bool = Query(False, description="Filter for saved tenders only"),
    match: Optional[str] = Query(None, description="Search query string"),
    sort_field: Optional[str] = Query(None, description="Field to sort by"),
    sort_direction: Optional[str] = Query(None, description="Sort direction (asc/desc)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get a list of tenders with optional search, filters, sorting, and offset/limit.
    
    This endpoint retrieves a list of tender previews from the search index,
    with offset/limit pagination, filtering, search, and sorting functionality.
    
    Query parameters:
    - **offset**: Number of items to skip (default: 0)
    - **limit**: Number of items per page (default: 10, max: 100)
    - **is_saved**: Filter for saved tenders only (default: False)
    - **match**: Search query string to match against tender content
    - **sort_field**: Field to sort by (e.g., 'submission_date')
    - **sort_direction**: Sort direction ('asc' or 'desc')

    Filters (provided in request body):
    - **filters**: Array of filter objects with name/value pairs

    Returns:
        PaginatedTenderResponse: List of tender previews with total count and offset/limit info
    """
    try:
        # Prepare parameters for search service
        search_params = {
            'match': match,
            'sort_field': sort_field,
            'sort_direction': sort_direction,
            'offset': offset,
            'limit': limit
        }
        # Remove None values to avoid sending empty params
        search_params = {k: v for k, v in search_params.items() if v is not None}

        # Check if there's a body with filters
        body_filters = None
        if request.method in ["GET", "POST"]:
            try:
                body = await request.json()
                if "filters" in body:
                    body_filters = body["filters"]
                    print(f"Received filters in body: {body_filters}")
            except Exception as e:
                print(f"No body or invalid body format: {str(e)}")
        
        # Fetch saved tender URIs if requested
        saved_tender_uris: Optional[List[str]] = None
        if is_saved:
            logger.info(f"Fetching saved tenders for user {current_user.id}")
            saved_tender_uris = services.get_user_saved_tenders_uris(db, str(current_user.id))
            logger.info(f"Found {len(saved_tender_uris)} saved tender URIs.")
            # If no saved tenders, return empty list immediately? Or let search handle it?
            # Let search handle it for consistency, it might return 0 results.
        
        # Call the search service with updated parameters
        # Assuming SearchService.do_search accepts offset, limit, and saved_tender_uris
        result = SearchService.do_search(
            index_name='tenders', 
            params=search_params, 
            body_filters=body_filters,
            saved_tender_uris=saved_tender_uris # Pass the list of saved URIs
        )
        
        # Format the results (same as before)
        items = [
            {
                "tender_hash": tender["id"],
                "tender_id": tender["exp"],
                "title": tender["title"],
                "description": tender["description"],
                "submission_date": datetime.fromtimestamp(tender["submission_date"], timezone.utc).isoformat() if tender["submission_date"] not in ("", None) else None,
                "updated": datetime.fromtimestamp(tender["updated"], timezone.utc).isoformat() if tender["updated"] not in ("", None) else None,
                "n_lots": tender["lotes"],
                "pub_org_name": tender["contracting_body"],
                "budget": {
                    "amount": tender["budget_amount"],
                    "currency": "EUR"
                },
                "location": tender["location"],
                "contract_type": tender["contract_type"],
                "cpv_categories": tender["cps"]
            }
            for tender in result.get('items', []) # Use .get for safety
        ]
        
        # Reconstruct the response, assuming SearchService returns total, offset, limit
        # Adapt this based on the actual return value of SearchService.do_search
        response_data = {
            "items": items,
            "total": result.get("total", 0),
            "offset": result.get("offset", offset),
            "limit": result.get("limit", limit),
            # Calculate has_next based on offset, limit, and total
            "has_next": (result.get("offset", offset) + len(items)) < result.get("total", 0),
            "has_prev": result.get("offset", offset) > 0 # has_prev is based on offset
            # Keep debug info if available
        }
        if 'debug' in result:
             response_data['debug'] = result['debug']

        return response_data

    except Exception as e:
        logger.error(f"Error retrieving tenders: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving tenders: {str(e)}"
        )

@router.post("/") 
async def post_tenders(
    request: Request,
    offset: int = Query(0, ge=0, description="Number of items to skip"),
    limit: int = Query(10, ge=1, le=100, description="Number of items to return"),
    is_saved: bool = Query(False, description="Filter for saved tenders only"),
    match: Optional[str] = Query(None, description="Search query string"),
    sort_field: Optional[str] = Query(None, description="Field to sort by"),
    sort_direction: Optional[str] = Query(None, description="Sort direction (asc/desc)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get a list of tenders with filters in request body and offset/limit.
    
    This endpoint provides the same functionality as GET /tenders but 
    allows filters to be provided in the request body.

    Query parameters:
    - **offset**: Number of items to skip (default: 0)
    - **limit**: Number of items per page (default: 10, max: 100)
    - **is_saved**: Filter for saved tenders only (default: False)
    - **match**: Search query string to match against tender content
    - **sort_field**: Field to sort by
    - **sort_direction**: Sort direction ('asc' or 'desc')

    Request body:
    - **filters**: Array of filter objects with name/value pairs

    Returns:
        PaginatedTenderResponse: List of tender previews
    """
    # Reuse the GET endpoint logic by calling it directly
    return await get_tenders(
        request=request, 
        offset=offset, 
        limit=limit, 
        is_saved=is_saved,
        match=match,
        sort_field=sort_field,
        sort_direction=sort_direction,
        db=db, 
        current_user=current_user
    )

@router.get("/detail/{tender_id}", response_model=schemas.TenderResponse)
async def get_tender_detail(
    tender_id: str = Path(..., description="The URI or hash identifier of the tender to retrieve")
):
    """
    Get detailed information about a specific tender.

    This endpoint retrieves full details of a tender procedure from the RDF graph database.
    The tender is identified by either its full URI or its hash identifier.

    - **tender_id**: A string representing either the full URI of the tender or its hash identifier

    Returns:
        TenderResponse: The complete tender details
    """
    # Direct print for debugging router execution
    print(f"ROUTER DIAGNOSTIC: Starting get_tender_detail for ID: {tender_id}")

    try:
        tender = await services.get_tender_detail(tender_id)
        return schemas.TenderResponse(
            data=tender,
            meta={
                "source": "Neptune RDF Graph"
            }
        )
    except ValueError as e:
        # Return a 404 with a clearer error message
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tender not found: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving tender: {str(e)}"
        )

@router.post("/save", response_model=schemas.UserTender)
async def save_tender(
    tender_data: schemas.SaveTenderRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Save a tender for the current user"""
    try:
        # Create a UserTenderCreate object with the current user's ID
        user_tender_data = schemas.UserTenderCreate(
            user_id=str(current_user.id),
            tender_uri=tender_data.tender_uri,
            situation=tender_data.situation
        )

        user_tender = services.save_tender_for_user(
            db=db,
            tender_data=user_tender_data
        )
        return user_tender
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error saving tender: {str(e)}")

@router.delete("/unsave", status_code=204, response_model=None)
async def unsave_tender(
    request_data: schemas.UnsaveTenderRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Remove a saved tender for the current user"""
    try:
        logger.debug(f"Attempting to unsave tender: {request_data.tender_uri} for user: {current_user.id}")

        result = services.unsave_tender_for_user(
            db=db,
            user_id=str(current_user.id),
            tender_uri=request_data.tender_uri
        )

        logger.debug(f"Unsave result: {result}")

        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tender not found in saved list"
            )

        # For a 204 No Content response, return None
        return None

    except ValueError as e:
        logger.error(f"Value error in unsave_tender: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Unexpected error in unsave_tender: {str(e)}")
        # Log full stack trace for debugging
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error unsaving tender: {str(e)}"
        )

@router.get("/saved", response_model=List[schemas.UserTender])
async def get_saved_tenders(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all tenders saved by the current user"""
    try:
        user_tenders = services.get_user_saved_tenders(db, str(current_user.id))
        return user_tenders
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving saved tenders: {str(e)}")

@router.post("/summary", response_model=schemas.TenderSummary)
async def create_or_update_summary(
    summary_data: schemas.TenderSummaryCreate,
    current_user: User = Depends(get_current_user)
):
    """Create or update a summary for a tender (requires admin privileges)"""
    # Check if user has admin privileges (adjust based on your role system)
    from app.modules.auth.models import UserRole
    if current_user.role != UserRole.ACCOUNT_MANAGER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to create or update summaries"
        )

    try:
        summary = await services.create_or_update_tender_summary(
            tender_uri=summary_data.tender_uri,
            summary=summary_data.summary
        )
        return summary
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating or updating summary: {str(e)}")

@router.get("/preview/{tender_id}", response_model=schemas.TenderPreview)
async def get_tender_preview(
    tender_id: str = Path(..., description="The URI or hash identifier of the tender to retrieve")
):
    """
    Get a preview of a specific tender.

    This endpoint retrieves a preview of a tender with basic information like title,
    description, budget, organization, etc. The tender is identified by either its
    full URI or its hash identifier.

    - **tender_id**: A string representing either the full URI of the tender or its hash identifier

    Returns:
        TenderPreview: The tender preview
    """
    try:
        return await services.get_tender_preview(tender_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tender not found: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving tender preview: {str(e)}"
        )

@router.get("/summary/{tender_id}", response_model=schemas.TenderSummary)
def get_tender_summary(
    tender_id: str = Path(..., description="The URI or hash identifier of the tender to retrieve the summary for"),
    db: Session = Depends(get_db)
):
    """
    Get the summary for a specific tender.

    This endpoint retrieves the summary of a tender from the database.
    The tender is identified by either its full URI or its hash identifier.

    - **tender_id**: A string representing either the full URI of the tender or its hash identifier

    Returns:
        TenderSummary: The tender summary
    """
    try:
        summary = services.get_tender_summary(tender_id, db)
        return summary
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tender summary not found: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving tender summary: {str(e)}"
        )
