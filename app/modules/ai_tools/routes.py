from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status

from app.modules.auth.models import User
from .schemas import TenderSummaryRequest, TenderSummaryResponse, TenderSummaryStatusResponse
from .services import process_document_summary, get_task_status

router = APIRouter(tags=["AI Tools"])


@router.post("/tender-summary", response_model=TenderSummaryResponse)
async def generate_tender_summary(
    request: TenderSummaryRequest,
    background_tasks: BackgroundTasks,
):
    """
    Generate an AI summary for a tender with document references.
    
    This is a long-running process that happens in the background.
    You'll receive a task ID that you can use to check the status.
    
    Instead of specifying a tender ID, you provide the actual procurement 
    documents to be analyzed. This allows for more flexible processing
    without relying on pre-existing tender data.
    """
    # Start the processing in the background
    task_id = await process_document_summary(
        documents=request.documents,
        output_id=request.output_id,
        regenerate=request.regenerate,
        questions=request.questions,
        background_tasks=background_tasks
    )
    
    # Return initial response with task ID
    return {
        "task_id": task_id,
        "status": "queued"
    }


@router.post("/tender-summary", response_model=TenderSummaryResponse)
async def generate_tender_summary(
    request: TenderSummaryRequest,
    background_tasks: BackgroundTasks,
):
    """
    Generate an AI summary for a tender with document references.
    
    This is a long-running process that happens in the background.
    You'll receive a task ID that you can use to check the status.
    
    Instead of specifying a tender ID, you provide the actual procurement 
    documents to be analyzed. This allows for more flexible processing
    without relying on pre-existing tender data.
    """
    # Start the processing in the background
    task_id = await process_document_summary(
        documents=request.documents,
        output_id=request.output_id,
        regenerate=request.regenerate,
        questions=request.questions,
        background_tasks=background_tasks
    )
    
    # Return initial response with task ID
    return {
        "task_id": task_id,
        "status": "queued"
    }

@router.get("/tender-summary/{task_id}", response_model=TenderSummaryStatusResponse)
async def get_tender_summary_status(
    task_id: str,
):
    """
    Check the status of a document summary generation task.
    
    When status is "completed", the result field will contain the summary details
    including paths to the generated summary document and reference metadata.
    """
    task = await get_task_status(task_id)
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task with ID {task_id} not found"
        )
    
    # Ensure task_id is in the response (in case get_task_status didn't add it)
    if "task_id" not in task:
        task["task_id"] = task_id
        
    return task
