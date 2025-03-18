"""
Initialize and configure Meilisearch indices.

This script is responsible for setting up the Meilisearch indices required by the application.
It configures search settings, filterable attributes, and ranking rules.
"""

import logging
from app.core.database import get_meilisearch_client
from app.core.config import settings

# Configure logging
logger = logging.getLogger(__name__)

# Constants
TENDERS_INDEX = "tenders"

async def init_meilisearch():
    """Initialize Meilisearch indices and settings."""
    try:
        logger.info("Initializing Meilisearch...")
        client = get_meilisearch_client()
        
        # Create or get tenders index
        try:
            index = client.get_index(TENDERS_INDEX)
            logger.info(f"Found existing index: {TENDERS_INDEX}")
        except:
            logger.info(f"Creating new index: {TENDERS_INDEX}")
            index = client.create_index(TENDERS_INDEX, {"primaryKey": "id"})
        
        # Configure tenders index settings
        index.update_settings({
            # Define searchable attributes and their order of importance
            "searchableAttributes": [
                "title",
                "description",
                "organization",
                "location",
                "category",
                "type",
                "status"
            ],
            
            # Define filterable attributes
            "filterableAttributes": [
                "type",
                "status",
                "organization",
                "location",
                "category"
            ],
            
            # Define sortable attributes
            "sortableAttributes": [
                "publish_date",
                "close_date",
                "title",
                "organization"
            ],
            
            # Define ranking rules
            "rankingRules": [
                "words",
                "typo",
                "proximity",
                "attribute",
                "sort",
                "exactness"
            ],
            
            # Configure typo tolerance
            "typoTolerance": {
                "enabled": True,
                "minWordSizeForTypos": {
                    "oneTypo": 5,
                    "twoTypos": 9
                },
                "disableOnWords": [],
                "disableOnAttributes": []
            },
            
            # Configure pagination
            "pagination": {
                "maxTotalHits": 10000  # Maximum number of results
            },
            
            # Configure highlighting
            "highlightPreTag": "<mark>",
            "highlightPostTag": "</mark>"
        })
        
        logger.info(f"Successfully configured Meilisearch index: {TENDERS_INDEX}")
        return True
        
    except Exception as e:
        logger.error(f"Error initializing Meilisearch: {str(e)}")
        return False

if __name__ == "__main__":
    # Allow running this script directly
    import asyncio
    asyncio.run(init_meilisearch()) 