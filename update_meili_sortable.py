from app.core.utils.meili import MeiliClient
# Make sure MEILISEARCH_HOST and MEILISEARCH_API_KEY are correctly set
# either via environment variables or passed directly if needed.

print("Connecting to Meilisearch...")
client = MeiliClient('tenders')

# Get current sortable attributes (optional, just to see)
try:
    current_sortable = client.index.get_sortable_attributes()
    print(f"Current sortable attributes: {current_sortable}")
except Exception as e:
    print(f"Error getting current sortable attributes: {e}")
    current_sortable = [] # Assume empty if error

# Define the attributes you want to be sortable
# Add any other fields you might want to sort by in the future
desired_sortable = ['submission_date', 'budget_amount', 'title', 'tender_id', 'n_lots', 'pub_org_name', 'contract_type', 'location']

# Check if an update is needed
if set(desired_sortable) != set(current_sortable):
    print(f"Updating sortable attributes to: {desired_sortable}")
    try:
        update_task_info = client.index.update_sortable_attributes(desired_sortable)
        print(f"Update task submitted: {update_task_info}")
        # Optionally wait for the task
        # client.task_handler.wait_for_task(update_task_info.task_uid)
        # print("Sortable attributes update task completed.")
    except Exception as e:
        print(f"Error updating sortable attributes: {e}")
else:
    print("Sortable attributes are already correctly configured.")
