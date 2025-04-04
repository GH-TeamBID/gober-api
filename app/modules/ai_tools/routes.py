from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from sqlalchemy.orm import Session

from app.modules.auth.models import User
from app.core.database import get_db
from app.modules.tenders.models import TenderDocuments
from app.core.utils.azure_blob_client import AzureBlobStorageClient
from .schemas import TenderSummaryRequest, TenderSummaryResponse, TenderSummaryStatusResponse, TenderDocumentResponse
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
        background_tasks=background_tasks,
        tender_hash=request.tender_hash
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

@router.get("/tender-documents/{tender_hash}", response_model=TenderDocumentResponse)
async def get_tender_documents(
    tender_hash: str,
    db: Session = Depends(get_db)
):
    """
    Retrieve the AI document and combined chunks for a specific tender.

    Args:
        tender_hash: The unique identifier hash for the tender

    Returns:
        The AI document content, summary, and combined chunks as JSON
    """
    # Find the tender in the database
    tender_document = db.query(TenderDocuments).filter_by(tender_uri=tender_hash).first()

    if not tender_document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tender with hash {tender_hash} not found"
        )

    # Get the Azure folder path from the database
    azure_folder = tender_document.url_document

    if not azure_folder:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No documents found for tender {tender_hash}"
        )

    # Initialize Azure client
    azure_client = AzureBlobStorageClient()

    try:
        # Fetch the AI document
        ai_doc_path = f"{azure_folder}ai_document.md"
        ai_doc_content = azure_client.download_document(ai_doc_path)

        # Fetch the combined chunks
        chunks_path = f"{azure_folder}combined_chunks.json"
        chunks_content = azure_client.download_document(chunks_path)

        # Convert bytes to strings if needed
        if isinstance(ai_doc_content, bytes):
            ai_doc_content = ai_doc_content.decode('utf-8')

        if isinstance(chunks_content, bytes):
            chunks_content = chunks_content.decode('utf-8')

        # Return the document content, summary, and chunks
        return {
            "tender_hash": tender_hash,
            "summary": tender_document.summary,
            "ai_document": ai_doc_content,
            "combined_chunks": chunks_content
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving tender documents: {str(e)}"
        )
