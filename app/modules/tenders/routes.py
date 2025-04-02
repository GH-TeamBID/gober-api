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
    tender_id: str = Path(..., description="The URI or hash identifier of the tender to retrieve")
):
    """  """
    try:
        ai_documents = await services.get_ai_documents(tender_id)
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
async def get_tenders(request: Request, input_data: dict = {}):
    #page: int = Query(1, ge=1, description="Page number (1-based)"), size: int = Query(10, ge=1, le=100, description="Number of items per page")
    """
    Get a paginated list of tenders sorted by submission deadline.
    
    This endpoint retrieves a list of tender previews from the RDF graph database,
    with pagination and sorting by submission deadline (most recent first).
    
    - **page**: Page number (starting from 1)
    - **size**: Number of items per page (default: 10, max: 100)
    
    Returns:
        PaginatedTenderResponse: Paginated list of tender previews
    """
    try:
        params = dict(request.query_params)
        filters = input_data['filters'] if 'filters' in input_data else None
        """ page = int(params['page']) if 'page' in params and params['page'] != '' else 1
        size = int(params['size']) if 'size' in params and params['size'] != '' else 10
        return await services.get_tenders_paginated(page=page, size=size) """
        result = SearchService.do_search('tenders', params, filters)
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
            for tender in result['items']
        ]
        result['items'] = items
        return {**result}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving tenders: {str(e)}"
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