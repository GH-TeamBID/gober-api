# AI Tender Processing Pipeline

An end-to-end pipeline for processing tender documents that extracts structured information from PDFs and generates AI-powered summaries with traceable references to source documents.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Set up environment variables
export MARKER_API_KEY=your_marker_api_key
export GEMINI_API_KEY=your_gemini_api_key

# Run the pipeline
python chunked_ai_summary_generator.py
```

## System Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│ DocumentRetrieval│───▶│ DocumentConversion│───▶│ MarkdownChunking│
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                                        │
                                                        ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│ ReferenceProcess│◀───│ AIDocGeneration │◀───│ ChunkAggregation│
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### Core Components

1. **AIDocumentsProcessingWorkflow**: Main orchestrator class that coordinates the pipeline
   - **Input**: `tender_id`, `client_id`, optional custom `questions`
   - **Output**: Paths to generated documents and metadata

2. **DocumentRetrievalService**: Downloads PDFs from URLs
   - Uses async requests for parallel downloads
   - Caches downloads to prevent duplicate retrievals

3. **DocumentConversionService**: Converts PDFs to markdown
   - Uses Marker API for PDF-to-markdown conversion
   - Handles rate limiting and retries

4. **MarkdownChunkingService**: Processes markdown into hierarchical chunks
   - Segments documents based on header structure
   - Preserves original PDF page references and metadata

5. **AIDocumentGeneratorService**: Generates AI documents with chunk references
   - Leverages Gemini API for context-aware generation
   - Implements parallel processing for sections to improve throughput
   - Enforces reference format: `[chunk_id: chunk_documentID,página,sección]`

6. **ChunkReferenceUtility**: Processes chunk references for traceability
   - Converts references to clickable links
   - Generates metadata for UI integration

7. **TenderRepository**: Data access layer (currently mock implementation)
   - Abstracts storage operations for tender data
   - Prepared for future database integration

8. **StorageService**: Manages file storage and retrieval
   - Not currently used, but prepared for future Azure bucket integration

## Output Files & Directories

The pipeline generates multiple files during processing:

### Directory Structure

```
data/
├── raw_pdfs/                            # Downloaded original PDFs
│   └── DOC20241111091415.pdf            # Format: original filename or timestamp-based name
│
├── markdown/                            # Converted markdown documents
│   └── DOC20241111091415.md             # Same base name as PDF
│
├── chunks/                              # Document chunks
│   └── TENDER_ID/                       # Organized by tender ID
│       ├── doc1_chunks.json             # Hierarchical chunks for a document
│       ├── doc2_chunks.json
│       └── combined_chunks.json         # Flattened list of all chunks
│
└── client_docs/                         # Generated output documents
    └── SECTIONS -> Individual sections of the AI-generated document - logging purposes
    └── CLIENT_ID_TENDER_ID_TIMESTAMP.md # AI-generated document
    └── CLIENT_ID_TENDER_ID_TIMESTAMP_processed.md # Document with processed references
    └── CLIENT_ID_TENDER_ID_TIMESTAMP_references.json # Reference metadata
```

### Key Output Files

1. **PDF Documents** (`data/raw_pdfs/*.pdf`)
   - Original downloaded tender documents
   - Preserved for traceability and reference

2. **Markdown Files** (`data/markdown/*.md`)
   - Converted text content from PDFs
   - Include page markers: `{PAGE_NUMBER}------------------------------------------------`
   - Used as input for chunking

3. **Chunk Files** (`data/chunks/TENDER_ID/*.json`)
   - **Document Chunks** (`doc*_chunks.json`):
     ```json
     {
       "text": "Full document text",
       "metadata": {
         "chunk_id": "chunk_0_document",
         "level": 0,
         "title": "Document Title",
         "parent_id": null,
         "pdf_path": "data/raw_pdfs/document.pdf",
         "page_number": 1,
         "start_line": 1,
         "end_line": 100
       },
       "children": [
         {
           "text": "Section text",
           "metadata": {...},
           "children": [...]
         }
       ]
     }
     ```

   - **Combined Chunks** (`combined_chunks.json`):
     ```json
     [
       {
         "chunk_id": "chunk_0_document",
         "level": 0,
         "title": "Document Title",
         "text": "Full document text",
         "parent_id": null,
         "pdf_path": "data/raw_pdfs/document.pdf",
         "page_number": 1,
         "start_line": 1,
         "end_line": 100
       },
       {...}
     ]
     ```

4. **AI Document** (`data/client_docs/CLIENT_ID_TENDER_ID_TIMESTAMP.md`)
   - AI-generated summary with section-based responses to prompts
   - Contains references to chunks: `[chunk_id: chunk_0_1_section_name]`
   - Format:
     ```markdown
     # AI Summary for Tender T12345

     ## 1. ¿Cuál es el objeto de la licitación?

     El objeto de la licitación es [...] [chunk_id: chunk_0_1_objeto]

     ## 2. ¿Cuáles son los requisitos técnicos principales?
     [...]
     ```

5. **Processed Document** (`data/client_docs/CLIENT_ID_TENDER_ID_TIMESTAMP_processed.md`)
   - Same content as AI Document but with references converted to clickable links
   - References appear as: `[📄](path/to/pdf#page=5 "Document Title, Page 5")`
   - Used for display in frontend applications

6. **Reference Metadata** (`data/client_docs/CLIENT_ID_TENDER_ID_TIMESTAMP_references.json`)
   - Maps references to their source documents and pages
   - Used by frontend for interactive features
   - Format:
     ```json
     {
       "references": [
         {
           "reference_id": "ref_1",
           "chunk_id": "chunk_0_1_objeto",
           "position": {
             "start": 120,
             "end": 150
           },
           "source": {
             "pdf_path": "data/raw_pdfs/document.pdf",
             "page_number": 5,
             "title": "Document Title"
           }
         }
       ]
     }
     ```

## Technical Implementation

### Data Structures

#### Chunk Metadata
```python
@dataclass
class ChunkMetadata:
    chunk_id: str         # Unique identifier
    level: int            # Hierarchical level (0=doc, 1=section...)
    title: str            # Title from header
    parent_id: str        # Parent chunk ID
    pdf_path: str         # Path to source PDF
    page_number: int      # Page in source PDF
    start_line: int       # Start line in markdown
    end_line: int         # End line in markdown
```

#### Document Chunk
```python
@dataclass
class DocumentChunk:
    text: str
    metadata: ChunkMetadata
    children: List["DocumentChunk"] = None
```

### API Integration

#### Marker API (PDF Conversion)
- Content types: PDF, DOCX
- Response includes markdown content, pagination and status

#### Gemini API (AI Generation)
- Model: gemini-2.0-flash-lite
- Response includes generated text

## Performance Considerations

- **Memory Usage**: Large PDFs can consume significant memory during conversion
  - Recommended server: 4+ GB RAM for production use

- **Processing Time** example for `chunked_ai_summary_generator.py`:
  - PDF Download: ~2.5s total for 5 documents downloaded in parallel
  - PDF Conversion: ~3.4s total for 5 documents processed in parallel
  - Chunking: ~0.02s total
  - AI Generation: ~9.1s total, 2 calls in parallel, + 1 call for ai_summary
  - Document references processing: ~0.01s total

  - **After multiple runs, the average processing time ~ 15s**

- **Concurrency**:
  - PDF downloads: Parallel (async - aiohttp)
  - PDF conversion: Parallel (async - aiohttp)
  - AI generation: Sections processed in parallel
  - Rate limiting applied to API calls

## Development Guidelines

1. **Error Handling**: Always wrap API calls in try-except blocks
2. **Logging**: Use the provided logger for consistent logging
3. **Testing**: Run `chunked_ai_summary_generator.py` to verify chunking functionality
4. **Branching**: Use feature branches, merge to main with PR

---

*Internal documentation - confidential*
