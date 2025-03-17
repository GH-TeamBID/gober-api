import os
import sys

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

import logging
import json
import asyncio
from dotenv import load_dotenv
from pathlib import Path
from custom_questions import QUESTIONS

from markdown_chunking_service import MarkdownChunkingService
from chunk_reference_utility import ChunkReferenceUtility
from ai_document_generator_service import AIDocumentGeneratorService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('chunking_test.log')
    ]
)

logger = logging.getLogger(__name__)

# Ensure directories exist
def setup_directories():
    os.makedirs("data/chunks", exist_ok=True)
    os.makedirs("data/processed", exist_ok=True)
    logger.info("Directories created")

async def main():
    # Load environment variables
    load_dotenv()

    # Set up directories
    setup_directories()

    # Initialize services
    chunking_service = MarkdownChunkingService(logger)
    reference_utility = ChunkReferenceUtility(logger)

    # Get API key from environment variable
    gemini_api_key = os.getenv("GOOGLE_AI_API")
    if not gemini_api_key:
        logger.error("GOOGLE_AI_API environment variable is not set")
        return

    ai_generator = AIDocumentGeneratorService(api_key=gemini_api_key)

    # Define document paths and PDF URLs (same as in main_ai_summary_generator.py)
    document_info = [
        {
            'markdown_path': "data/markdown/DOC_CN2024-001193585.md",
            'pdf_path': "https://contrataciondelestado.es/FileSystem/servlet/GetDocumentByIdServlet?DocumentIdParam=cGvQdaF/qmEnKvN211kkZep9eLYPa5sPlu0VFp1fA/h5Fg1pTaKl4FN73msJksylIVq1IvdI5PofzpP36PwDr6Jmx2BDu2S/t4P9dvlPFULfdyQgZAdTm3EfcUAC7CJ6&cifrado=QUC1GjXXSiLkydRHJBmbpw%3D%3D",
            'output_prefix': 'DOC1'
        },
        {
            'markdown_path': "data/markdown/DOC20241111091415Pliego_de_prescripciones_tecnicas.md",
            'pdf_path': "https://contrataciondelestado.es/FileSystem/servlet/GetDocumentByIdServlet?DocumentIdParam=z/ghU5864J3UKnVAwwWNrCp9Nvi9o32DrO2HfqSQ/7y0QPTDGl%2BTgSxAzGaBF9hR0w94oIWtN2EkYA0Og4DmgZLmV7aY3ZdlQ8%2BxtPvjDpeB0nvVKRzfe4rpHcnlPhSZ&cifrado=QUC1GjXXSiLkydRHJBmbpw%3D%3D",
            'output_prefix': 'PPT'
        },
        {
            'markdown_path': "data/markdown/DOC20241111092201Pliego_de_clausulas_administrativas.md",
            'pdf_path': "https://contrataciondelestado.es/FileSystem/servlet/GetDocumentByIdServlet?DocumentIdParam=8hgVPRbuSgXhyguKtFy5AiXeHvokF%2B2dllmtzd8sapWTAcvE3IDVxGhRuhi9GWXq2A4V3aEdzAqu7KG6zJkIGd4Rr6XPeaqztAIX1SSQM%2B2B0nvVKRzfe4rpHcnlPhSZ&cifrado=QUC1GjXXSiLkydRHJBmbpw%3D%3D",
            'output_prefix': 'PCA'
        },
        {
            'markdown_path': "data/markdown/DOC20241111094338ANEXO_I_1741284737.md",
            'pdf_path': "https://contrataciondelestado.es/FileSystem/servlet/GetDocumentByIdServlet?DocumentIdParam=wpL05Sv0vuASNVV59os02t1zLXzhEwhUpVrAmIiI4w%2B06WPE0AvLvdg6w0OZqYyrGivKjCsC2R7gEgBRON2aZeZ1y1C5nSiBmcFaXawL1GJt/o8fNevwsujgRzaBbugn&cifrado=QUC1GjXXSiLkydRHJBmbpw%3D%3D",
            'output_prefix': 'ANEXO_I'
        },
        {
            'markdown_path': "data/markdown/DOC20241111094425ANEXO_II.md",
            'pdf_path': "https://contrataciondelestado.es/FileSystem/servlet/GetDocumentByIdServlet?DocumentIdParam=FfZj3XI6OlOTOzDyKek0lnaI3ORlarheXliAsx0JVVCd5gsL7ycTWihmq01TkQC8e9oC1wwahAymbwR1EgIyQ86irt%2BO9F0D/Qe6kMPxUA%2B1aXEvq3KHa/AEHgtDrQw0&cifrado=QUC1GjXXSiLkydRHJBmbpw%3D%3D",
            'output_prefix': 'ANEXO_II'
        }
    ]

    # Process each document
    all_flat_chunks = []
    markdown_paths = []

    for doc in document_info:
        markdown_path = doc['markdown_path']
        pdf_path = doc['pdf_path']
        output_prefix = doc['output_prefix']

        # Check if file exists
        if not os.path.exists(markdown_path):
            logger.warning(f"Markdown file not found: {markdown_path}")
            continue

        markdown_paths.append(markdown_path)
        logger.info(f"Processing document: {markdown_path}")

        # Step 1: Perform hierarchical chunking
        logger.info(f"Performing hierarchical chunking for {output_prefix}...")
        root_chunk = chunking_service.chunk_markdown_file(markdown_path, pdf_path)

        if not root_chunk:
            logger.error(f"Failed to chunk {markdown_path}")
            continue

        # Save the chunked structure to JSON
        chunks_path = f"data/chunks/{output_prefix}_chunks.json"
        chunking_service.save_chunks_to_json(root_chunk, chunks_path)
        logger.info(f"Hierarchical chunks saved to {chunks_path}")

        # Extract flat chunks for easier access
        flat_chunks = chunking_service.extract_flat_chunks(root_chunk)
        flat_chunks_path = f"data/chunks/{output_prefix}_flat_chunks.json"

        # Save flat chunks for easier analysis
        with open(flat_chunks_path, 'w', encoding='utf-8') as f:
            json.dump(flat_chunks, f, ensure_ascii=False, indent=2)

        logger.info(f"Extracted {len(flat_chunks)} chunks from {output_prefix}")

        # Add these chunks to the combined list
        all_flat_chunks.extend(flat_chunks)

    # Save the combined flat chunks
    combined_chunks_path = "data/chunks/combined_flat_chunks.json"
    with open(combined_chunks_path, 'w', encoding='utf-8') as f:
        json.dump(all_flat_chunks, f, ensure_ascii=False, indent=2)

    logger.info(f"Combined {len(all_flat_chunks)} chunks from all documents")

    # Step 2: Generate an AI document with all chunk references
    logger.info("Generating AI document with all chunk references...")

    # Path for the generated AI document
    output_file = "data/processed/ai_document_with_references.md"

    # Generate the AI document using all chunks
    ai_doc_path = await ai_generator.generate_ai_documents_with_chunks(
        markdown_paths=markdown_paths,
        chunks_path=combined_chunks_path,
        questions=QUESTIONS,
        output_file=output_file,
        max_retries=2  # Lower retries for testing
    )

    if not ai_doc_path:
        logger.error("Failed to generate AI document")
        return

    logger.info(f"AI document generated: {ai_doc_path}")

    # Step 3: Process the document to convert references to links
    logger.info("Processing references in the generated document...")

    processed_path = "data/processed/processed_ai_document.md"
    reference_utility.process_document_with_references(
        ai_doc_path,
        combined_chunks_path,
        processed_path
    )
    logger.info(f"Processed document saved to {processed_path}")

    # Generate reference metadata for UI use
    metadata_path = "data/processed/reference_metadata.json"
    reference_metadata = reference_utility.generate_reference_metadata(
        ai_doc_path,
        combined_chunks_path,
        metadata_path
    )
    logger.info(f"Reference metadata saved to {metadata_path}")

    # Print summary of references
    reference_count = len(reference_metadata["references"])
    logger.info(f"Document contains {reference_count} references to source chunks")

    logger.info("Test completed successfully")

if __name__ == "__main__":
    asyncio.run(main())
