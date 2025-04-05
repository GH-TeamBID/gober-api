import os
import logging
import requests
import asyncio
import aiohttp
from typing import Dict, Optional, Tuple
import tempfile
from .temp_file_manager import TempFileManager

class DocumentRetrievalService:
    """Service for retrieving PDF documents from URLs"""

    def __init__(self, logger=None):
        self.logger = logger or logging.getLogger(__name__)
        self.temp_manager = TempFileManager(logger)

    async def retrieve_document(self, url: str) -> Optional[Tuple[str, bytes]]:
        """
        Download PDF from URL and return filepath and content.

        Args:
            url: The URL to download the PDF from

        Returns:
            Tuple containing: temporary filepath to the downloaded PDF and PDF content as bytes,
            or None if download failed
        """
        # Make sure url is a string
        url = str(url) if url is not None else ""

        if not url:
            self.logger.warning("Empty URL provided")
            return None

        try:
            self.logger.info(f"Downloading PDF from {url}...")

            # Create a new aiohttp session
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    response.raise_for_status()

                    # Extract filename from Content-Disposition if available
                    filename = 'document.pdf'
                    if 'Content-Disposition' in response.headers:
                        content_disposition = response.headers['Content-Disposition']
                        if 'filename=' in content_disposition:
                            filename = content_disposition.split('filename=')[1].strip('"\'')

                    # Read content
                    content = await response.read()

                    # Create a temporary file with the content
                    with self.temp_manager.temp_file(suffix='.pdf') as (temp_path, temp_file):
                        temp_file.write(content)
                        temp_file.flush()  # Ensure all data is written

                        self.logger.info(f"PDF downloaded to temporary file {temp_path}")
                        return (temp_path, content)

        except Exception as e:
            self.logger.error(f"Error downloading PDF: {e}")
            return None

    async def retrieve_documents(self, urls: Dict[str, str]) -> Dict[str, Tuple[str, bytes]]:
        """
        Download multiple PDFs from URLs in parallel

        Args:
            urls: Dictionary mapping document IDs to URLs

        Returns:
            Dictionary mapping document IDs to tuples of (local filepath, content bytes)
        """
        pdf_data = {}
        tasks = []
        doc_ids = []

        for doc_id, url in urls.items():
            # Convert URL to string if it isn't already
            url_str = str(url) if url is not None else ""

            if url_str:
                tasks.append(self.retrieve_document(url_str))
                doc_ids.append(doc_id)

        # Execute downloads in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        for i, doc_id in enumerate(doc_ids):
            result = results[i]
            if isinstance(result, Exception):
                self.logger.error(f"Failed to download PDF for {doc_id}: {result}")
            elif result:
                pdf_data[doc_id] = result

        return pdf_data
