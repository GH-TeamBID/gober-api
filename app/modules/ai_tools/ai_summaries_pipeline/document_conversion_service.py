import os
import logging
import asyncio
from typing import Optional, Dict, Tuple, Any
from .temp_file_manager import TempFileManager

class DocumentConversionService:
    """Service for converting PDFs to markdown using Marker API"""

    def __init__(self, api_key: str, logger=None):
        """
        Initialize the document conversion service

        Args:
            api_key: API key for the Marker API
            logger: Optional logger
        """
        self.api_key = api_key
        self.submit_url = "https://www.datalab.to/api/v1/marker"
        self.logger = logger or logging.getLogger(__name__)
        self.temp_manager = TempFileManager(logger)

    async def convert_to_markdown(self, pdf_data: Tuple[str, bytes, str]) -> Optional[Tuple[str, str]]:
        """
        Convert PDF to markdown using the Marker API

        Args:
            pdf_data: Tuple containing (temp file path, PDF content bytes, original filename)

        Returns:
            Tuple of (Markdown content as string, original filename) if successful, None otherwise
        """
        temp_path, pdf_bytes, original_filename = pdf_data

        try:
            # Import aiohttp here for async HTTP requests
            import aiohttp

            # Set up the request
            headers = {
                'accept': 'application/json',
                'X-API-Key': self.api_key
            }

            data = {
                'output_format': 'markdown',
                'disable_image_extraction': 'true',
                'paginate': 'true',
                'skip_cache': 'false',
            }

            # Create a temporary file with the PDF content
            with self.temp_manager.temp_file(suffix='.pdf') as (temp_file_path, temp_file):
                # Write the bytes to the temporary file
                temp_file.write(pdf_bytes)
                temp_file.flush()

                # Submit the PDF for processing using aiohttp
                self.logger.info(f"Submitting PDF for conversion using temporary file...")

                async with aiohttp.ClientSession() as session:
                    # Use file-based upload
                    with open(temp_file_path, 'rb') as f:
                        form_data = aiohttp.FormData()
                        form_data.add_field('file',
                                          f,
                                          filename=os.path.basename(temp_path),
                                          content_type='application/pdf')

                        # Add other form fields
                        for key, value in data.items():
                            form_data.add_field(key, value)

                        # Submit the request
                        async with session.post(self.submit_url, headers=headers, data=form_data) as response:
                            response.raise_for_status()
                            result = await response.json()

                            if not result.get('success'):
                                self.logger.error(f"Error: {result.get('error', 'Unknown error')}")
                                return None

                            request_id = result['request_id']
                            check_url = f"https://www.datalab.to/api/v1/marker/{request_id}"

                            # Poll for results
                            self.logger.info(f"Processing request {request_id}...")
                            max_attempts = 100
                            for attempt in range(max_attempts):
                                async with session.get(check_url, headers=headers) as status_response:
                                    status_response.raise_for_status()
                                    status = await status_response.json()

                                    if status.get('status') == 'complete':
                                        # Get the markdown content
                                        markdown_content = status.get('markdown', '')
                                        self.logger.info(f"Successfully converted PDF to markdown")
                                        return (markdown_content, original_filename)
                                    elif status.get('status') == 'error':
                                        self.logger.error(f"Error processing PDF: {status.get('error')}")
                                        return None

                                    # Wait before polling again
                                    await asyncio.sleep(0.2)

                            self.logger.warning("Maximum polling attempts reached. Request may still be processing.")
                            return None

        except Exception as e:
            self.logger.error(f"Error converting PDF to markdown: {e}")
            return None

    async def convert_documents(self, pdf_data: Dict[str, Tuple[str, bytes, str]]) -> Dict[str, Tuple[str, str]]:
        """
        Convert multiple PDFs to markdown in parallel

        Args:
            pdf_data: Dictionary mapping document IDs to tuples of (temp file path, PDF content bytes, original filename)

        Returns:
            Dictionary mapping document IDs to tuples of (markdown content, original filename)
        """
        markdown_contents = {}
        tasks = []
        doc_ids = []

        for doc_id, data in pdf_data.items():
            tasks.append(self.convert_to_markdown(data))
            doc_ids.append(doc_id)

        # Execute conversions in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        for i, doc_id in enumerate(doc_ids):
            result = results[i]
            if isinstance(result, Exception):
                self.logger.error(f"Failed to convert PDF for {doc_id}: {result}")
            elif result:
                markdown_contents[doc_id] = result

        return markdown_contents
