import logging
from app.core.config import settings
from azure.storage.blob import BlobServiceClient, BlobSasPermissions, generate_blob_sas
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

def generate_sas_token(blob_path: str) -> str:
    connection_string = settings.BLOB_CONNECTION_STRING
    container_name = settings.BLOB_CONTAINER_NAME

    if not connection_string or not container_name:
        raise ValueError("Environment variables for connection string and container name must be set.")

    try:
        # Create the BlobServiceClient object
        blob_service_client = BlobServiceClient.from_connection_string(connection_string)

        # Check if the container name is correct
        print(f"Using container name: {container_name}")

        # Generate the SAS token
        sas_token = generate_blob_sas(
            account_name=blob_service_client.account_name,
            container_name=container_name,
            blob_name=blob_path,
            account_key=blob_service_client.credential.account_key,
            permission=BlobSasPermissions(read=True),
            expiry=datetime.now() + timedelta(minutes=10)
        )

        print(f"SAS token generated for blob: {sas_token}")

        blob_url_with_sas = f"https://{blob_service_client.account_name}.blob.core.windows.net/{container_name}/{blob_path}?{sas_token}"

        print(f"Blob URL with SAS: {blob_url_with_sas}")

        return blob_url_with_sas
    
    except Exception as e:
        raise RuntimeError(f"Failed to generate SAS token for blob: {blob_path}. Error: {str(e)}")