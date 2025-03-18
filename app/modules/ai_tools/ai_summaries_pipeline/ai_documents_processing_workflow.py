import os
import logging
import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime
import json

from markdown_chunking_service import MarkdownChunkingService
from chunk_reference_utility import ChunkReferenceUtility

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
        self.tender_repository = tender_repository
        self.document_retrieval_service = document_retrieval_service
        self.document_conversion_service = document_conversion_service
        self.storage_service = storage_service
        self.ai_document_generator_service = ai_document_generator_service
        self.markdown_chunking_service = MarkdownChunkingService(logger)
        self.chunk_reference_utility = ChunkReferenceUtility(logger)
        self.logger = logger or logging.getLogger(__name__)

    async def process_tender(
        self,
        tender_id: str,
        client_id: str,
        regenerate: bool = False,
        questions: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Process a tender to generate AI summary and client-specific AI document

        Args:
            tender_id: ID of the tender to process
            client_id: ID of the client
            regenerate: Whether to regenerate summaries even if they already exist
            questions: Optional list of questions/sections to use for the AI document

        Returns:
            Dictionary with AI summary and AI document
        """
        start_time = datetime.now()
        self.logger.info(f"Starting tender processing for tender_id={tender_id}, client_id={client_id}")

        # 1. Retrieve Tender and ClientTender information
        tender = self.tender_repository.get_tender_by_id(tender_id)
        client_tender = self.tender_repository.get_client_tender(tender_id, client_id)

        # Check if we need to generate AI docs or can return existing ones
        if not regenerate and tender.get('ai_summary') and client_tender.get('ai_doc_path'):
            self.logger.info("Using existing AI documents")
            # Calculate processing time
            end_time = datetime.now()
            processing_time = (end_time - start_time).total_seconds()
            return {
                'ai_summary': tender['ai_summary'],
                'ai_doc_path': client_tender['ai_doc_path'],
                'chunks_path': client_tender.get('chunks_path'),
                'processed_doc_path': client_tender.get('processed_doc_path'),
                'reference_metadata_path': client_tender.get('reference_metadata_path'),
                'regenerated': False,
                'processing_time': processing_time
            }

        # 2. Identify missing Markdown files
        document_urls = tender.get('document_urls', {})
        markdown_paths = tender.get('markdown_paths', {})

        missing_docs = {}
        for doc_id, url in document_urls.items():
            if doc_id not in markdown_paths or not markdown_paths[doc_id]:
                missing_docs[doc_id] = url

        # 3. Process missing documents in parallel (only if there are any)
        new_markdown_paths = {}
        if missing_docs:
            self.logger.info(f"Processing {len(missing_docs)} missing documents")

            # 3a. Download PDFs
            pdf_paths = await self.document_retrieval_service.retrieve_documents(missing_docs)

            # 3b. Convert to Markdown
            if pdf_paths:
                new_md_paths = await self.document_conversion_service.convert_documents(pdf_paths)
                new_markdown_paths.update(new_md_paths)

            # 3c. Update Tender with new Markdown paths
            if new_markdown_paths:
                tender = self.tender_repository.update_markdown_paths(tender_id, new_markdown_paths)
        else:
            self.logger.info("All documents already have markdown versions, skipping download and conversion")

        # 4. Prepare the complete list of Markdown paths and corresponding PDF paths
        all_markdown_paths = tender['markdown_paths']
        if not all_markdown_paths:
            raise ValueError(f"No markdown documents available for tender {tender_id}")

        # Get the corresponding PDF paths for each markdown
        pdf_paths = {}
        for doc_id, markdown_path in all_markdown_paths.items():
            # For each markdown file, get the original PDF path
            if doc_id in document_urls:
                pdf_paths[doc_id] = document_urls[doc_id]

        # 5. Generate hierarchical chunks for all markdown files
        self.logger.info("Generating hierarchical chunks for markdown files")
        document_chunks = self.markdown_chunking_service.chunk_markdown_files(all_markdown_paths, pdf_paths)

        # Save chunks to JSON files
        chunks_dir = os.path.join("data", "chunks", tender_id)
        os.makedirs(chunks_dir, exist_ok=True)

        chunks_paths = {}
        for doc_id, root_chunk in document_chunks.items():
            if root_chunk:
                # Save hierarchical structure
                json_path = os.path.join(chunks_dir, f"{doc_id}_chunks.json")
                self.markdown_chunking_service.save_chunks_to_json(root_chunk, json_path)
                chunks_paths[doc_id] = json_path

        # Create a combined chunks file for the entire tender
        combined_chunks_path = os.path.join(chunks_dir, "combined_chunks.json")
        all_flat_chunks = []
        for doc_id, root_chunk in document_chunks.items():
            if root_chunk:
                doc_chunks = self.markdown_chunking_service.extract_flat_chunks(root_chunk)
                all_flat_chunks.extend(doc_chunks)

        # Save combined chunks
        try:
            os.makedirs(os.path.dirname(combined_chunks_path), exist_ok=True)
            with open(combined_chunks_path, 'w', encoding='utf-8') as f:
                json.dump(all_flat_chunks, f, ensure_ascii=False, indent=2)
            self.logger.info(f"Saved combined chunks to {combined_chunks_path}")
        except Exception as e:
            self.logger.error(f"Error saving combined chunks: {e}")

        # Update client_tender with chunks path
        if combined_chunks_path:
            client_tender = self.tender_repository.update_chunks_path(tender_id, client_id, combined_chunks_path)

        # 6. Generate client-specific AI document
        ai_doc_path = client_tender.get('ai_doc_path')
        if regenerate or not ai_doc_path:
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

            # Generate output filename for storing results
            timestamp = int(datetime.now().timestamp())
            output_dir = "data/client_docs"
            os.makedirs(output_dir, exist_ok=True)
            output_file = os.path.join(output_dir, f"{client_id}_{tender_id}_{timestamp}.md")

            # Generate the AI document using the chunks
            markdown_paths_list = list(all_markdown_paths.values())
            ai_doc_path = await self.ai_document_generator_service.generate_ai_documents_with_chunks(
                markdown_paths_list,
                combined_chunks_path,
                doc_questions,
                output_file
            )

            if ai_doc_path:
                client_tender = self.tender_repository.update_ai_doc(tender_id, client_id, ai_doc_path)
            else:
                self.logger.error(f"Failed to generate AI document for client {client_id}, tender {tender_id}")
                # If AI document generation failed, we can't continue with summary generation
                end_time = datetime.now()
                processing_time = (end_time - start_time).total_seconds()
                return {
                    'ai_summary': None,
                    'ai_doc_path': None,
                    'chunks_path': combined_chunks_path,
                    'processed_doc_path': None,
                    'reference_metadata_path': None,
                    'regenerated': True,
                    'processing_time': processing_time
                }

        # 7. Process chunk references in the AI document
        processed_doc_path = client_tender.get('processed_doc_path')
        reference_metadata_path = client_tender.get('reference_metadata_path')

        if regenerate or not processed_doc_path or not reference_metadata_path:
            # Create paths for processed files
            processed_dir = os.path.join("data", "processed")
            os.makedirs(processed_dir, exist_ok=True)

            processed_doc_path = os.path.join(processed_dir, f"processed_{client_id}_{tender_id}.md")
            reference_metadata_path = os.path.join(processed_dir, f"reference_metadata_{client_id}_{tender_id}.json")

            # Process the document to replace chunk references with links
            self.logger.info(f"Processing chunk references in {ai_doc_path}")
            try:
                processed_text = self.chunk_reference_utility.process_document_with_references(
                    ai_doc_path,
                    combined_chunks_path,
                    processed_doc_path
                )

                # Generate reference metadata for UI
                reference_metadata = self.chunk_reference_utility.generate_reference_metadata(
                    ai_doc_path,
                    combined_chunks_path,
                    reference_metadata_path
                )

                # Update client_tender with processed document and metadata paths
                client_tender = self.tender_repository.update_processed_doc_path(
                    tender_id, client_id, processed_doc_path, reference_metadata_path
                )

                self.logger.info(f"Processed document saved to {processed_doc_path}")
                self.logger.info(f"Reference metadata saved to {reference_metadata_path}")
            except Exception as e:
                self.logger.error(f"Error processing chunk references: {e}")
                # Continue with the workflow even if reference processing fails

        # 8. Generate AI summary based on the AI document
        if regenerate or not tender.get('ai_summary'):
            # Read the AI document
            try:
                with open(client_tender.get('ai_doc_path'), 'r', encoding='utf-8') as f:
                    ai_doc_content = f.read()

                # Now generate summary using the AI document as context
                ai_summary = await self.ai_document_generator_service.generate_conversational_summary(
                    ai_doc_content, tender_id
                )

                if ai_summary:
                    tender = self.tender_repository.update_ai_summary(tender_id, ai_summary)
                else:
                    self.logger.error(f"Failed to generate AI summary for tender {tender_id}")
            except Exception as e:
                self.logger.error(f"Error reading AI document or generating summary: {e}")

        # Calculate final processing time
        end_time = datetime.now()
        processing_time = (end_time - start_time).total_seconds()
        self.logger.info(f"Tender processing completed in {processing_time:.2f} seconds")

        # Update the return value to include paths
        return {
            'ai_summary': tender.get('ai_summary'),
            'ai_doc_path': client_tender.get('ai_doc_path'),
            'chunks_path': client_tender.get('chunks_path'),
            'processed_doc_path': client_tender.get('processed_doc_path'),
            'reference_metadata_path': client_tender.get('reference_metadata_path'),
            'regenerated': regenerate or not tender.get('ai_summary') or not ai_doc_path,
            'processing_time': processing_time
        }
