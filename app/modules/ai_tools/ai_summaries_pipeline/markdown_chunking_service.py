import os
import re
import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import json


@dataclass
class ChunkMetadata:
    """Metadata for a chunk of text from a document"""
    chunk_id: str  # Unique identifier for the chunk
    level: int  # Hierarchical level (0 = document, 1 = section, 2 = subsection, etc.)
    title: str  # Title of the chunk
    parent_id: Optional[str]  # ID of the parent chunk
    pdf_path: str  # Path to the original PDF
    page_number: Optional[int]  # Page number in the original PDF
    start_line: int  # Start line in the markdown
    end_line: int  # End line in the markdown


@dataclass
class DocumentChunk:
    """A chunk of text from a document with metadata"""
    text: str
    metadata: ChunkMetadata
    children: List["DocumentChunk"] = None  # Child chunks

    def __post_init__(self):
        if self.children is None:
            self.children = []


class MarkdownChunkingService:
    """Service for chunking markdown documents hierarchically"""

    # Regular expressions for detecting headers
    HEADER_PATTERN = re.compile(r'^(#{1,6})\s+(.+?)(?:\s+\{#([^}]+)\})?$', re.MULTILINE)
    PAGE_MARKER_PATTERN = re.compile(r'\{(\d+)\}------------------------------------------------')

    def __init__(self, logger=None):
        """Initialize the chunking service"""
        self.logger = logger or logging.getLogger(__name__)

    def chunk_markdown_file(self, markdown_path: str, pdf_path: str) -> DocumentChunk:
        """
        Process a markdown file and create a hierarchical structure of chunks.

        Args:
            markdown_path: Path to the markdown file
            pdf_path: Path to the original PDF file

        Returns:
            Root chunk with hierarchical structure
        """
        try:
            # Read the markdown file
            with open(markdown_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Create the document root chunk
            root_chunk = self._process_markdown_content(content, markdown_path, pdf_path)
            return root_chunk

        except Exception as e:
            self.logger.error(f"Error chunking markdown file {markdown_path}: {e}")
            return None

    def chunk_markdown_files(self, markdown_paths: Dict[str, str], pdf_paths: Dict[str, str]) -> Dict[str, DocumentChunk]:
        """
        Process multiple markdown files and create hierarchical structures.

        Args:
            markdown_paths: Dictionary mapping document IDs to markdown paths
            pdf_paths: Dictionary mapping document IDs to PDF paths

        Returns:
            Dictionary mapping document IDs to root chunks
        """
        document_chunks = {}

        for doc_id, markdown_path in markdown_paths.items():
            pdf_path = pdf_paths.get(doc_id)
            if not pdf_path:
                self.logger.warning(f"No PDF path found for document {doc_id}")
                continue

            root_chunk = self.chunk_markdown_file(markdown_path, pdf_path)
            if root_chunk:
                document_chunks[doc_id] = root_chunk

        return document_chunks

    def _process_markdown_content(self, content: str, markdown_path: str, pdf_path: str) -> DocumentChunk:
        """
        Process markdown content and extract hierarchical chunks

        Args:
            content: Markdown content
            markdown_path: Path to the markdown file
            pdf_path: Path to the original PDF file

        Returns:
            Root document chunk containing all other chunks as children
        """
        # Create a root chunk for the entire document
        filename = os.path.basename(markdown_path)
        doc_id = filename.split('.')[0]  # Use filename without extension as document ID

        root_chunk = DocumentChunk(
            text=content,
            metadata=ChunkMetadata(
                chunk_id=f"doc_{doc_id}",
                level=0,
                title=filename,
                parent_id=None,
                pdf_path=pdf_path,
                page_number=None,
                start_line=0,
                end_line=len(content.split('\n'))
            )
        )

        # Extract hierarchical chunks
        chunks = self._extract_hierarchical_chunks(content, pdf_path)

        # Build chunk hierarchy - this must be done before assigning section IDs
        self._build_chunk_hierarchy(chunks, root_chunk)

        # Now assign structured chunk IDs with document_ID,page_number,section_id format
        section_counters = {}

        def assign_structured_ids(chunk, parent_section_id=None):
            # Determine section ID based on hierarchy
            if parent_section_id is None:
                # Top-level sections
                section_counter = section_counters.get(chunk.metadata.level, 0) + 1
                section_counters[chunk.metadata.level] = section_counter
                section_id = f"s{chunk.metadata.level}_{section_counter}"
            else:
                # Subsections - attach to parent section ID
                section_counter = section_counters.get((parent_section_id, chunk.metadata.level), 0) + 1
                section_counters[(parent_section_id, chunk.metadata.level)] = section_counter
                section_id = f"{parent_section_id}.{section_counter}"

            # Ensure page number is always set (default to 1 if not available)
            # Convert from 0-index to 1-index for PDF viewing
            page_number = (chunk.metadata.page_number + 1) if chunk.metadata.page_number is not None else 1

            # Update the actual metadata page_number field to be 1-indexed
            chunk.metadata.page_number = page_number

            # Create the structured chunk ID: document_ID,page_number,section_id
            chunk.metadata.chunk_id = f"chunk_{doc_id},{page_number},{section_id}"

            # Recursively assign IDs to children
            for child in chunk.children:
                assign_structured_ids(child, section_id)

        # Assign structured IDs to all chunks (except root)
        for chunk in root_chunk.children:
            assign_structured_ids(chunk)

        return root_chunk

    def _extract_hierarchical_chunks(self, content: str, pdf_path: str) -> List[DocumentChunk]:
        """
        Extract hierarchical chunks based on markdown headers.

        Args:
            content: Markdown content
            pdf_path: Path to the original PDF

        Returns:
            List of chunks
        """
        lines = content.splitlines()
        chunks = []

        # Find all headers and their positions
        headers = []
        current_page = 1

        for line_num, line in enumerate(lines, 1):
            # Check for page markers
            page_marker_match = self.PAGE_MARKER_PATTERN.match(line)
            if page_marker_match:
                current_page = int(page_marker_match.group(1))
                continue

            # Check for headers
            header_match = self.HEADER_PATTERN.match(line)
            if header_match:
                level = len(header_match.group(1))  # Number of # characters
                title = header_match.group(2).strip()
                headers.append({
                    'level': level,
                    'title': title,
                    'line_num': line_num,
                    'page': current_page
                })

        # Create chunks based on headers
        for i, header in enumerate(headers):
            # Determine chunk boundaries
            start_line = header['line_num']
            end_line = len(lines)

            if i < len(headers) - 1:
                end_line = headers[i + 1]['line_num'] - 1

            # Extract the text for this chunk
            chunk_text = '\n'.join(lines[start_line - 1:end_line])

            # Create unique ID based on header level and title
            chunk_id = f"chunk_{i}_{header['level']}_{self._normalize_title(header['title'])}"

            # Create chunk metadata
            metadata = ChunkMetadata(
                chunk_id=chunk_id,
                level=header['level'],
                title=header['title'],
                parent_id=None,  # Will be set when building hierarchy
                pdf_path=pdf_path,
                page_number=header['page'],
                start_line=start_line,
                end_line=end_line
            )

            # Create the chunk
            chunk = DocumentChunk(
                text=chunk_text,
                metadata=metadata
            )

            chunks.append(chunk)

        return chunks

    def _build_chunk_hierarchy(self, chunks: List[DocumentChunk], root_chunk: DocumentChunk) -> None:
        """
        Build a hierarchy of chunks based on header levels.

        Args:
            chunks: List of chunks
            root_chunk: Root document chunk
        """
        if not chunks:
            return

        # Sort chunks by their start line to ensure correct order
        sorted_chunks = sorted(chunks, key=lambda x: x.metadata.start_line)

        # Keep track of the most recent chunk at each level
        level_chunks = {0: root_chunk}

        for chunk in sorted_chunks:
            level = chunk.metadata.level

            # Find the parent chunk (the most recent chunk with a lower level)
            parent_level = level - 1
            while parent_level > 0 and parent_level not in level_chunks:
                parent_level -= 1

            parent_chunk = level_chunks.get(parent_level, root_chunk)

            # Set parent ID in metadata
            chunk.metadata.parent_id = parent_chunk.metadata.chunk_id

            # Add as child to parent
            parent_chunk.children.append(chunk)

            # Update the most recent chunk at this level
            level_chunks[level] = chunk

    def _normalize_title(self, title: str) -> str:
        """
        Normalize a title for use in an ID.

        Args:
            title: The title to normalize

        Returns:
            Normalized title suitable for an ID
        """
        # Remove special characters, convert to lowercase, replace spaces with underscores
        normalized = re.sub(r'[^\w\s]', '', title).lower().replace(' ', '_')
        # Truncate to a reasonable length
        return normalized[:30]

    def save_chunks_to_json(self, root_chunk: DocumentChunk, output_path: str) -> None:
        """
        Save the chunk hierarchy to a JSON file.

        Args:
            root_chunk: Root document chunk
            output_path: Path to save the JSON file
        """
        try:
            def chunk_to_dict(chunk):
                return {
                    'text': chunk.text,
                    'metadata': {
                        'chunk_id': chunk.metadata.chunk_id,
                        'level': chunk.metadata.level,
                        'title': chunk.metadata.title,
                        'parent_id': chunk.metadata.parent_id,
                        'pdf_path': chunk.metadata.pdf_path,
                        'page_number': chunk.metadata.page_number,
                        'start_line': chunk.metadata.start_line,
                        'end_line': chunk.metadata.end_line
                    },
                    'children': [chunk_to_dict(child) for child in chunk.children]
                }

            # Convert the entire hierarchy to a dictionary
            chunk_dict = chunk_to_dict(root_chunk)

            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            # Write to JSON file
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(chunk_dict, f, ensure_ascii=False, indent=2)

            self.logger.info(f"Saved chunk hierarchy to {output_path}")

        except Exception as e:
            self.logger.error(f"Error saving chunks to JSON: {e}")

    def extract_flat_chunks(self, root_chunk: DocumentChunk) -> List[Dict[str, Any]]:
        """
        Extract a flat list of all chunks with their metadata.

        Args:
            root_chunk: Root document chunk

        Returns:
            List of dictionaries with chunk text and metadata
        """
        flat_chunks = []

        def traverse_chunks(chunk):
            # Add the current chunk
            flat_chunks.append({
                'text': chunk.text,
                'metadata': {
                    'chunk_id': chunk.metadata.chunk_id,
                    'level': chunk.metadata.level,
                    'title': chunk.metadata.title,
                    'parent_id': chunk.metadata.parent_id,
                    'pdf_path': chunk.metadata.pdf_path,
                    'page_number': chunk.metadata.page_number,
                    'start_line': chunk.metadata.start_line,
                    'end_line': chunk.metadata.end_line
                }
            })

            # Traverse all children
            for child in chunk.children:
                traverse_chunks(child)

        traverse_chunks(root_chunk)
        return flat_chunks

    def get_chunk_by_id(self, root_chunk: DocumentChunk, chunk_id: str) -> Optional[DocumentChunk]:
        """
        Find a chunk by its ID in the hierarchy.

        Args:
            root_chunk: Root document chunk
            chunk_id: ID of the chunk to find

        Returns:
            The found chunk, or None if not found
        """
        if root_chunk.metadata.chunk_id == chunk_id:
            return root_chunk

        for child in root_chunk.children:
            found = self.get_chunk_by_id(child, chunk_id)
            if found:
                return found

        return None
