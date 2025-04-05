import os
import uuid
import logging
import asyncio
from datetime import datetime
from typing import Dict, Optional, List, Any
from fastapi import BackgroundTasks
from app.core.utils.azure_blob_client import AzureBlobStorageClient
from app.modules.tenders.models import TenderDocuments
from app.modules.ai_tools.ai_summaries_pipeline.custom_questions import QUESTIONS
from sqlalchemy.orm import Session
from app.core.database import engine
from app.core.config import settings
from .schemas import ProcurementDocument

# Import AI pipeline components with better error handling
try:
    from .ai_summaries_pipeline.tender_repository import TenderRepository
    from .ai_summaries_pipeline.document_retrieval_service import DocumentRetrievalService
    from .ai_summaries_pipeline.document_conversion_service import DocumentConversionService
    from .ai_summaries_pipeline.storage_service import StorageService
    from .ai_summaries_pipeline.ai_document_generator_service import AIDocumentGeneratorService
    from .ai_summaries_pipeline.ai_documents_processing_workflow import AIDocumentsProcessingWorkflow
    from .ai_summaries_pipeline.markdown_chunking_service import MarkdownChunkingService
    from .ai_summaries_pipeline.chunk_reference_utility import ChunkReferenceUtility

    AI_PIPELINE_AVAILABLE = True
except ImportError as e:
    logging.error(f"Error importing AI pipeline components: {str(e)}")
    AI_PIPELINE_AVAILABLE = False

# Configure logging
logger = logging.getLogger(__name__)

# In-memory task storage (replace with database for production)
TASKS: Dict[str, Dict[str, Any]] = {}

async def process_document_summary(
    documents: List[ProcurementDocument],
    tender_hash: str,
    output_id: Optional[str] = None,
    regenerate: bool = False,
    questions: Optional[List[str]] = None,
    background_tasks: Optional[BackgroundTasks] = None,
) -> str:
    """
    Start processing a document summary in the background

    Args:
        documents: List of procurement documents to analyze
        output_id: Optional ID for the output (auto-generated if not provided)
        regenerate: Whether to regenerate existing summaries
        questions: Custom questions to use instead of defaults
        background_tasks: FastAPI background tasks

    Returns:
        str: Task ID for checking status
    """
    # Check if AI pipeline is available
    if not AI_PIPELINE_AVAILABLE:
        raise RuntimeError("AI summary pipeline components are not available")

    # Create a new task
    task_id = str(uuid.uuid4())
    now = datetime.now()

    # Generate a unique output ID if not provided
    if not output_id:
        output_id = f"summary_{str(uuid.uuid4())[:8]}"

    TASKS[task_id] = {
        "status": "queued",
        "created_at": now,
        "updated_at": now,
        "output_id": output_id,
        "document_count": len(documents),
        "result": None,
        "error": None,
        "progress": 0
    }

    logger.info(f"Created summary task {task_id} for {len(documents)} documents with output ID {output_id}")

    # Start the processing task in the background
    if background_tasks:
        background_tasks.add_task(
            _process_document_summary_task,
            tender_hash,
            task_id,
            documents,
            output_id,
            regenerate,
            questions
        )
    else:
        # For testing or direct calls without background tasks
        asyncio.create_task(
            _process_document_summary_task(
                tender_hash,
                task_id,
                documents,
                output_id,
                regenerate,
                questions
            )
        )

    return task_id

async def _process_document_summary_task(
    tender_hash: str,
    task_id: str,
    documents: List[ProcurementDocument],
    output_id: str,
    regenerate: bool = False,
    questions: Optional[List[str]] = None
):
    """Background task for processing document summaries"""
    try:
        # Update task status
        _update_task_status(task_id, "processing", 5)

        logger.info(f"Starting processing for task {task_id} (output_id: {output_id})")
        logger.info(f"Settings, MarkerAPI: {settings.MARKER_API_KEY}, and Gemini API: {settings.GEMINI_API_KEY}")


        # Verify required settings
        marker_api_key = settings.MARKER_API_KEY
        google_ai_api_key = settings.GOOGLE_AI_API_KEY

        if not marker_api_key:
            raise ValueError("MARKER_API_KEY environment variable not set")
        if not google_ai_api_key:
            raise ValueError("GEMINI_API_KEY environment variable not set")

        _update_task_status(task_id, "processing", 10, "Initializing services")

        # Initialize services
        try:
            # Initialize required services for the workflow
            tender_repo = TenderRepository()
            doc_retrieval = DocumentRetrievalService(logger=logger)
            doc_conversion = DocumentConversionService(api_key=marker_api_key, logger=logger)
            storage = StorageService()
            ai_generator = AIDocumentGeneratorService(api_key=google_ai_api_key)

            # Initialize workflow orchestrator
            workflow = AIDocumentsProcessingWorkflow(
                tender_repository=tender_repo,
                document_retrieval_service=doc_retrieval,
                document_conversion_service=doc_conversion,
                storage_service=storage,
                ai_document_generator_service=ai_generator,
                logger=logger
            )
        except Exception as e:
            logger.error(f"Error initializing AI services: {str(e)}", exc_info=True)
            raise RuntimeError(f"Failed to initialize AI services: {str(e)}")

        _update_task_status(task_id, "processing", 20, "Processing documents")

        # Convert the Pydantic models to dictionaries for the workflow
        document_dicts = [doc.model_dump() for doc in documents]
        if questions is None:
            questions = QUESTIONS

        # Process the documents directly using the workflow
        result = await workflow.process_tender(
            documents=document_dicts,
            output_id=output_id,
            regenerate=regenerate,
            questions=questions
        )

        # Update the database with the tender document information
        try:
            with Session(engine) as session:
                tender_document = session.query(TenderDocuments).filter_by(tender_uri=tender_hash).first()

                # Get the Azure folder path (should be in the format 'tenders/{output_id}/')
                azure_folder = f"tenders/{output_id}/"

                if tender_document:
                    # Update existing record
                    tender_document.url_document = azure_folder
                    tender_document.summary = result.get('summary', '')
                else:
                    # Create new record
                    tender_doc = TenderDocuments(
                        id=str(uuid.uuid4()),
                        tender_uri=tender_hash,
                        url_document=azure_folder,
                        summary=result.get('summary', '')
                    )
                    session.add(tender_doc)

                session.commit()
                logger.info(f"Updated database with tender document information for {tender_hash}")
        except Exception as e:
            logger.error(f"Error updating database: {str(e)}", exc_info=True)
            # Continue processing even if database update fails

        # Update task with results
        _update_task_status(task_id, "completed", 100, "Processing complete", result=result)

        logger.info(f"Completed processing for task {task_id}")

    except Exception as e:
        logger.error(f"Error processing task {task_id}: {str(e)}", exc_info=True)
        _update_task_status(task_id, "failed", progress=0, error=str(e))

def _update_task_status(
    task_id: str,
    status: str,
    progress: float = 0,
    message: str = None,
    result: Dict[str, Any] = None,
    error: str = None
):
    """Update the status of a task"""
    if task_id in TASKS:
        TASKS[task_id]["status"] = status
        TASKS[task_id]["updated_at"] = datetime.now()
        TASKS[task_id]["progress"] = progress

        if message:
            TASKS[task_id]["message"] = message
        if result:
            TASKS[task_id]["result"] = result
        if error:
            TASKS[task_id]["error"] = error

async def get_task_status(task_id: str) -> Optional[Dict[str, Any]]:
    """
    Get the status of a processing task

    Args:
        task_id: ID of the task to check

    Returns:
        Task details or None if not found
    """
    if task_id not in TASKS:
        return None

    # Create a copy of the task data and include the task_id
    task_data = TASKS[task_id].copy()
    task_data["task_id"] = task_id

    return task_data
