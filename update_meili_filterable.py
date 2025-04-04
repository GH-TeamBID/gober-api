from app.core.utils.meili import MeiliClient
import logging

# Configure basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

logger.info("Connecting to Meilisearch...")
try:
    # Ensure MEILISEARCH_HOST/API_KEY are set in your environment/config
    client = MeiliClient('tenders') # Make sure index_name is correct
    index = client.index
    logger.info(f"Connected to index '{client.index_name}'.")
except Exception as e:
    logger.error(f"Failed to connect to Meilisearch: {e}")
    exit(1)

# --- Filterable Attributes ---
try:
    current_filterable = index.get_filterable_attributes()
    logger.info(f"Current filterable attributes: {current_filterable}")
except Exception as e:
    logger.error(f"Error getting current filterable attributes: {e}")
    current_filterable = [] # Assume empty if error, proceed cautiously

# Define the attributes you NEED to be filterable
# IMPORTANT: Include ALL attributes you filter by (existing + 'id')
# Also include fields used in body_filters in do_search (like budget_amount, submission_date etc.)
desired_filterable = sorted(list(set([
    'id', # <--- Add this field for saved tender filtering
    'budget_amount',
    'cpvs',
    'location',
    'status',
    'updated',
    'submission_date', # Used for date range filters
    'contract_type',   # If you filter by this
    # Add any other fields used in body_filters or direct filters
])))

logger.info(f"Desired filterable attributes: {desired_filterable}")

# Check if an update is needed
# Sort both lists before comparing to ignore order differences
if sorted(list(set(current_filterable))) != desired_filterable:
    logger.info(f"Updating filterable attributes...")
    try:
        update_task_info = index.update_filterable_attributes(desired_filterable)
        logger.info(f"Filterable attributes update task submitted: {update_task_info}")
        # Optionally wait for the task to complete for confirmation
        # task_status = client.client.wait_for_task(update_task_info['taskUid']) # Adjusted based on MeiliClient structure if needed
        # logger.info(f"Filterable attributes update task completed with status: {task_status['status']}")
    except Exception as e:
        logger.error(f"Error updating filterable attributes: {e}")
else:
    logger.info("Filterable attributes are already correctly configured.")

logger.info("Meilisearch filterable attributes check finished.")
