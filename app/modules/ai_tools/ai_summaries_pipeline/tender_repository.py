from typing import Dict, List, Optional, Any
from datetime import datetime
import logging

class TenderRepository:
    """
    Data access layer for tender-related operations.
    This is a mock implementation since we don't have a real database yet.
    """

    def __init__(self):
        # Mock database tables
        self._tenders = {}
        self._client_tenders = {}
        self.logger = logging.getLogger(__name__)

    def get_tender_by_id(self, tender_id: str) -> Dict[str, Any]:
        """Retrieve a tender by its ID"""
        # In a real implementation, this would query the database
        if tender_id not in self._tenders:
            # For testing, create a mock tender if it doesn't exist
            self._tenders[tender_id] = {
                'id': tender_id,
                'document_urls': {},
                'markdown_paths': {},
                'ai_summary': None,
                'created_at': datetime.now(),
                'updated_at': datetime.now()
            }
        return self._tenders[tender_id]

    def create_or_update_tender(self, tender_id: str, document_urls: Dict[str, str],
                            markdown_paths: Dict[str, str] = None,
                            ai_summary: str = None) -> Dict[str, Any]:
        """Create or update a tender with the given data"""

        if tender_id in self._tenders:
            # Update existing tender
            tender = self._tenders[tender_id]
            tender['document_urls'].update(document_urls)
            if markdown_paths:
                if 'markdown_paths' not in tender:
                    tender['markdown_paths'] = {}
                tender['markdown_paths'].update(markdown_paths)
            if ai_summary is not None:
                tender['ai_summary'] = ai_summary
            tender['updated_at'] = datetime.now()
        else:
            # Create new tender
            self._tenders[tender_id] = {
                'id': tender_id,
                'document_urls': document_urls,
                'markdown_paths': markdown_paths or {},
                'ai_summary': ai_summary,
                'created_at': datetime.now(),
                'updated_at': datetime.now()
            }

        return self._tenders[tender_id]

    def get_client_tender(self, tender_id: str, client_id: str) -> Dict[str, Any]:
        """Retrieve a client-specific tender"""
        key = f"{client_id}:{tender_id}"
        if key not in self._client_tenders:
            # For testing, create a mock client_tender if it doesn't exist
            self._client_tenders[key] = {
                'tender_id': tender_id,
                'client_id': client_id,
                'ai_doc_path': None,
                'created_at': datetime.now(),
                'updated_at': datetime.now()
            }
        return self._client_tenders[key]

    def update_markdown_paths(self, tender_id: str, new_md_paths: Dict[str, str]) -> Dict[str, Any]:
        """Update the markdown paths for a tender"""
        if tender_id not in self._tenders:
            raise ValueError(f"Tender with ID {tender_id} not found")

        tender = self._tenders[tender_id]
        # Merge new paths with existing ones
        tender['markdown_paths'].update(new_md_paths)
        tender['updated_at'] = datetime.now()
        return tender

    def update_ai_summary(self, tender_id: str, ai_summary: str) -> Dict[str, Any]:
        """Update the AI summary for a tender"""
        if tender_id not in self._tenders:
            raise ValueError(f"Tender with ID {tender_id} not found")

        tender = self._tenders[tender_id]
        tender['ai_summary'] = ai_summary
        tender['updated_at'] = datetime.now()
        return tender

    def update_ai_doc(self, tender_id: str, client_id: str, ai_doc_path: str) -> Dict[str, Any]:
        """Update the client-specific AI document path for a tender"""
        key = f"{client_id}:{tender_id}"
        if key not in self._client_tenders:
            raise ValueError(f"Client tender with ID {key} not found")

        client_tender = self._client_tenders[key]
        client_tender['ai_doc_path'] = ai_doc_path  # Store path instead of content
        client_tender['updated_at'] = datetime.now()
        return client_tender

    def update_chunks_path(self, tender_id: str, client_id: str, chunks_path: str) -> Dict[str, Any]:
        """
        Update chunks path for a client tender

        Args:
            tender_id: ID of the tender
            client_id: ID of the client
            chunks_path: Path to the chunks JSON file

        Returns:
            Updated client tender data
        """
        client_tender = self.get_client_tender(tender_id, client_id)
        client_tender['chunks_path'] = chunks_path
        return client_tender

    def update_processed_doc_path(self, tender_id: str, client_id: str, processed_doc_path: str, reference_metadata_path: str) -> Dict[str, Any]:
        """
        Update processed document path and reference metadata path for a client tender

        Args:
            tender_id: ID of the tender
            client_id: ID of the client
            processed_doc_path: Path to the processed document with clickable references
            reference_metadata_path: Path to the reference metadata JSON file

        Returns:
            Updated client tender data
        """
        client_tender = self.get_client_tender(tender_id, client_id)
        client_tender['processed_doc_path'] = processed_doc_path
        client_tender['reference_metadata_path'] = reference_metadata_path
        client_tender['updated_at'] = datetime.now()
        return client_tender

    def get_chunk_reference(self, tender_id: str, chunk_id: str) -> Dict[str, Any]:
        """
        Get reference information for a specific chunk

        Args:
            tender_id: ID of the tender
            chunk_id: ID of the chunk

        Returns:
            Dictionary with chunk reference information
        """
        tender = self.get_tender_by_id(tender_id)

        # We'll need to load the chunks file and find the reference
        chunks_paths = []
        for client_id in self._client_tenders:
            if client_id.split(':')[0] == tender_id and 'chunks_path' in self._client_tenders[client_id]:
                chunks_paths.append(self._client_tenders[client_id]['chunks_path'])

        if not chunks_paths:
            self.logger.warning(f"No chunks found for tender {tender_id}")
            return None

        # Try to load each chunks file and find the chunk
        for chunks_path in chunks_paths:
            try:
                import json
                with open(chunks_path, 'r', encoding='utf-8') as f:
                    chunks = json.load(f)

                # Look for the chunk with the specified ID
                for chunk in chunks:
                    if chunk['metadata']['chunk_id'] == chunk_id:
                        return {
                            'text': chunk['text'],
                            'pdf_path': chunk['metadata']['pdf_path'],
                            'page_number': chunk['metadata']['page_number'],
                            'title': chunk['metadata']['title']
                        }
            except Exception as e:
                self.logger.error(f"Error loading chunks from {chunks_path}: {e}")

        self.logger.warning(f"Chunk {chunk_id} not found for tender {tender_id}")
        return None
