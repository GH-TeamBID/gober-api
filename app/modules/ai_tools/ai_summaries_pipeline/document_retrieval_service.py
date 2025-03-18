import os
import logging
import requests
import asyncio
import aiohttp
from typing import Dict, Optional

class DocumentRetrievalService:
    """Service for retrieving PDF documents from URLs"""

    def __init__(self, output_dir: str = "data/raw_pdfs"):
        self.output_dir = output_dir
        self.logger = logging.getLogger(__name__)
        os.makedirs(output_dir, exist_ok=True)

    async def retrieve_document(self, url: str) -> Optional[str]:
        """
        Download PDF from URL and return local filepath.

        Args:
            url: The URL to download the PDF from

        Returns:
            Local filepath to the downloaded PDF, or None if download failed
        """
        if not url.strip():
            self.logger.warning("Empty URL provided")
            return None

        try:
            self.logger.info(f"Downloading PDF from {url}...")

            # Create a new aiohttp session
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    response.raise_for_status()

                    # Simple filename extraction
                    filename = 'document.pdf'
                    if 'Content-Disposition' in response.headers:
                        content_disposition = response.headers['Content-Disposition']
                        if 'filename=' in content_disposition:
                            filename = content_disposition.split('filename=')[1].strip('"\'')

                    # Generate a unique filename if needed
                    base_filename = os.path.basename(filename)
                    filepath = os.path.join(self.output_dir, base_filename)

                    # If file exists, return the existing file path
                    if os.path.exists(filepath):
                        self.logger.info(f"File {filepath} already exists, skipping download")
                        return filepath

                    # Download the file using aiohttp
                    with open(filepath, 'wb') as f:
                        # Read the content
                        content = await response.read()
                        f.write(content)

            self.logger.info(f"PDF downloaded to {filepath}")
            return filepath

        except Exception as e:
            self.logger.error(f"Error downloading PDF: {e}")
            return None

    async def retrieve_documents(self, urls: Dict[str, str]) -> Dict[str, str]:
        """
        Download multiple PDFs from URLs in parallel

        Args:
            urls: Dictionary mapping document IDs to URLs

        Returns:
            Dictionary mapping document IDs to local filepaths
        """
        pdf_paths = {}
        tasks = []

        for doc_id, url in urls.items():
            if url.strip():
                tasks.append(self.retrieve_document(url))

        # Execute downloads in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        for i, (doc_id, _) in enumerate([(k, v) for k, v in urls.items() if v.strip()]):
            result = results[i]
            if isinstance(result, Exception):
                self.logger.error(f"Failed to download PDF for {doc_id}: {result}")
            elif result:
                pdf_paths[doc_id] = result

        return pdf_paths
