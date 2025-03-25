import os
import logging

logger = logging.getLogger(__name__)

def setup_directories():
    """Create required directories for AI processing"""
    directories = [
        "data/raw_pdfs",
        "data/markdown",
        "data/chunks",
        "data/processed",
        "data/client_docs",
        "data/storage"
    ]
    for directory in directories:
        os.makedirs(directory, exist_ok=True)
    
    logger.debug("Created AI processing directories")

# Create directories on module import
setup_directories()
