import os
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
import json
from sqlalchemy.orm import Session
from app.core.database import engine
from app.modules.tenders.models import TenderDocuments

from app.modules.ai_tools.ai_summaries_pipeline.markdown_chunking_service import MarkdownChunkingService
from app.modules.ai_tools.ai_summaries_pipeline.chunk_reference_utility import ChunkReferenceUtility
from app.modules.ai_tools.ai_summaries_pipeline.temp_file_manager import TempFileManager
from app.core.utils.azure_blob_client import AzureBlobStorageClient

class AIDocumentsProcessingWorkflow:
    """
    Orchestrator for the AI document processing workflow.
    Coordinates the parallel steps, handles concurrency, and aggregates results.
    """

    def __init__(
        self,
        tender_repository,
        document_retrieval_service,
        document_conversion_service,
        storage_service,
        ai_document_generator_service,
        logger=None
    ):
        self.document_retrieval_service = document_retrieval_service
        self.document_conversion_service = document_conversion_service
        self.storage_service = storage_service
        self.ai_document_generator_service = ai_document_generator_service
        self.markdown_chunking_service = MarkdownChunkingService(logger)
        self.chunk_reference_utility = ChunkReferenceUtility(logger)
        self.logger = logger or logging.getLogger(__name__)
        self.temp_manager = TempFileManager(logger)
        self.azure_client = AzureBlobStorageClient()


    async def process_tender(
        self,
        documents: List[Dict[str, Any]],  # List of ProcurementDocument objects
        output_id: str,
        regenerate: bool = False,
        questions: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Process procurement documents directly to generate an AI summary.
        Uses in-memory processing and Azure storage instead of local files.

        Args:
            documents: List of procurement documents (with document_id, title, url, and document_type)
            output_id: Identifier for the output files
            regenerate: Whether to regenerate existing summaries
            questions: Custom questions to use instead of defaults

        Returns:
            Dict with processing results including paths to generated files
        """
        start_time = datetime.now()
        self.logger.info(f"Processing {len(documents)} documents directly with output_id: {output_id}")

        tender_folder = None

        try:
            # Step 1: Download documents
            self.logger.info("Step 1: Downloading documents")
            # Convert HttpUrl objects to strings
            document_urls = {doc["document_id"]: str(doc["url"]) for doc in documents}
            pdf_data = await self.document_retrieval_service.retrieve_documents(document_urls)

            if not pdf_data:
                self.logger.error("Failed to download any documents")
                raise ValueError("Failed to download any documents")

            self.logger.info(f"Downloaded {len(pdf_data)} documents")

            # Step 2: Convert documents to markdown
            self.logger.info("Step 2: Converting documents to markdown")
            markdown_contents = await self.document_conversion_service.convert_documents(pdf_data)

            if not markdown_contents:
                self.logger.error("Failed to convert any documents to markdown")
                raise ValueError("Failed to convert any documents to markdown")

            self.logger.info(f"Converted {len(markdown_contents)} documents to markdown")

            # Step 3: Chunk documents
            self.logger.info("Step 3: Chunking documents")

            # Create a dictionary mapping document IDs to their PDF paths
            pdf_paths = {}
            for doc_id, (temp_path, _) in pdf_data.items():
                pdf_paths[doc_id] = temp_path

            # Process markdown contents directly
            document_chunks = self.markdown_chunking_service.chunk_markdown_contents(markdown_contents, pdf_paths)

            # Extract flat chunks from all documents
            all_flat_chunks = []
            for doc_id, root_chunk in document_chunks.items():
                if root_chunk:  # Check if chunking was successful
                    flat_chunks = self.markdown_chunking_service.extract_flat_chunks(root_chunk)
                    all_flat_chunks.extend(flat_chunks)

            if not all_flat_chunks:
                self.logger.error("Failed to extract any chunks from documents")
                raise ValueError("Failed to extract any chunks from documents")

            # Step 4: Create Azure folder for tender
            self.logger.info("Step 4: Setting up Azure storage")
            tender_folder = self.azure_client.create_tender_folder(output_id)

            # Step 5: Upload combined chunks to Azure
            self.logger.info("Step 5: Uploading combined chunks to Azure")
            combined_chunks_json = json.dumps(all_flat_chunks, ensure_ascii=False, indent=2)
            combined_chunks_path = self.azure_client.upload_tender_file(
                output_id,
                'combined_chunks',
                combined_chunks_json
            )

            self.logger.info(f"Uploaded combined chunks to Azure: {combined_chunks_path}")

            # Step 6: Generate AI document using the chunks
            self.logger.info("Step 6: Generating AI document")

            # Use provided questions or default questions
            doc_questions = questions or [
                """
                1. ¿Cuál es el objeto de la licitación?
                2. ¿Cuáles son los requisitos técnicos principales?
                3. ¿Cuál es el presupuesto y la forma de pago?
                """,
                """
                4. ¿Cuáles son los criterios de adjudicación?
                5. ¿Cuáles son los plazos clave?
                """
            ]

            # Generate AI document directly from content
            ai_doc_content = await self.ai_document_generator_service.generate_ai_documents_with_content(
                chunks_json=combined_chunks_json,
                questions=doc_questions,
                max_retries=3
            )

            if not ai_doc_content:
                self.logger.error("Failed to generate AI document")
                raise ValueError("Failed to generate AI document")

            # Step 7: Upload AI document to Azure
            self.logger.info("Step 7: Uploading AI document to Azure")

            # Upload content directly to Azure
            azure_ai_doc_path = self.azure_client.upload_tender_file(
                output_id,
                'ai_document',
                ai_doc_content
            )

            self.logger.info(f"Uploaded AI document to Azure: {azure_ai_doc_path}")

            # Generate a conversational summary using the AI document content
            # if summary does not exist in the database.
            with Session(engine) as session:
                tender_document = session.query(TenderDocuments).filter_by(tender_uri=output_id).first()
                summary = None
                if tender_document and tender_document.summary:
                    summary = tender_document.summary
                else:
                    summary = await self.ai_document_generator_service.generate_conversational_summary(
                        document_content=ai_doc_content
                    )

            # Prepare result
            processing_time = (datetime.now() - start_time).total_seconds()

            result = {
                "output_id": output_id,
                "document_count": len(documents),
                "ai_doc_path": f"{tender_folder}ai_document.md",
                "chunks_path": f"{tender_folder}combined_chunks.json",
                "summary": summary,
                "processing_time": processing_time
            }

            self.logger.info(f"Document processing completed in {processing_time:.2f} seconds")
            return result

        except Exception as e:
            self.logger.error(f"Error processing documents: {str(e)}", exc_info=True)
            processing_time = (datetime.now() - start_time).total_seconds()

            return {
                "output_id": output_id,
                "error": str(e),
                "processing_time": processing_time,
                "ai_doc_path": tender_folder + "ai_document.md" if tender_folder else None,
                "chunks_path": tender_folder + "combined_chunks.json" if tender_folder else None,
            }
