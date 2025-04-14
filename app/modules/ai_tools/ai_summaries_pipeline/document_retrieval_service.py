import os
import logging
import asyncio
import aiohttp
from typing import Dict, Optional, Tuple
from .temp_file_manager import TempFileManager

class DocumentRetrievalService:
    """Service for retrieving PDF documents from URLs"""

    def __init__(self, logger=None):
        self.logger = logger or logging.getLogger(__name__)
        self.temp_manager = TempFileManager(logger)

    async def retrieve_document(self, url: str) -> Optional[Tuple[str, bytes, str]]:
        """
        Download PDF from URL and return filepath, content, and original filename.

        Args:
            url: The URL to download the PDF from

        Returns:
            Tuple containing: temporary filepath to the downloaded PDF, PDF content as bytes, and original filename,
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
                # WARNING: Disabling SSL verification is insecure and should only be used
                # if you trust the source and understand the risks (e.g., MITM attacks).
                # This is added to handle potential self-signed or misconfigured certs
                # on specific government portals like contrataciondelestado.es.
                # Consider more secure alternatives (custom CA bundle) for production.
                async with session.get(url, ssl=False) as response:
                    response.raise_for_status()

                    # Extract filename from Content-Disposition if available
                    filename = None
                    if 'Content-Disposition' in response.headers:
                        content_disposition = response.headers['Content-Disposition']
                        if 'filename=' in content_disposition:
                            filename = content_disposition.split('filename=')[1].strip('"\'')

                    # Try to extract from URL if no filename was found
                    if not filename:
                        url_path = url.split('?')[0]  # Remove query params
                        if '/' in url_path:
                            url_filename = url_path.split('/')[-1]
                            if url_filename and '.' in url_filename:
                                filename = url_filename

                    # If we still don't have a filename, use a default with timestamp
                    if not filename:
                        import datetime
                        timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
                        filename = f"document_{timestamp}.pdf"

                    # Clean up filename by removing DOC{date} prefixes
                    if filename.startswith("DOC"):
                        # Try to find the first real part of the filename after the DOC prefix
                        # The DOC prefix pattern looks like: DOC20250326155238
                        import re
                        match = re.match(r"DOC\d{14}(.*)", filename)
                        if match and match.group(1):
                            filename = match.group(1)

                    # Read content
                    content = await response.read()

                    # Create a temporary file with the content
                    with self.temp_manager.temp_file(suffix='.pdf') as (temp_path, temp_file):
                        temp_file.write(content)
                        temp_file.flush()  # Ensure all data is written

                        self.logger.info(f"PDF downloaded to temporary file {temp_path}, original filename: {filename}")
                        return (temp_path, content, filename)

        except Exception as e:
            self.logger.error(f"Error downloading PDF: {e}")
            return None

    async def retrieve_documents(self, urls: Dict[str, str]) -> Dict[str, Tuple[str, bytes, str]]:
        """
        Download multiple PDFs from URLs in parallel

        Args:
            urls: Dictionary mapping document IDs to URLs

        Returns:
            Dictionary mapping document IDs to tuples of (local filepath, content bytes, original filename)
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
