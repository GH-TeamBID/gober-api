import os
import logging
from datetime import datetime, timedelta
from app.core.config import settings
from azure.storage.blob import BlobServiceClient, BlobClient, ContainerClient, generate_blob_sas, BlobSasPermissions


class AzureBlobStorageClient:
    """Client for Azure Blob Storage operations."""

    def __init__(self):
        """Initialize Azure Blob Storage client."""
        self.connection_string = settings.BLOB_CONNECTION_STRING
        self.container_name = settings.BLOB_CONTAINER_NAME

        if not self.connection_string or not self.container_name:
            raise ValueError("Environment variables for connection string and container name must be set.")

        self.blob_service_client = BlobServiceClient.from_connection_string(self.connection_string)
        self.container_client = self.blob_service_client.get_container_client(self.container_name)

        logging.info(f"Azure Blob Storage client initialized with container: {self.container_name}")

    def upload_document(self, file_path, blob_path=None):
        """
        Upload a document to Azure Blob Storage.

        Args:
            file_path (str): Local path to the file to upload
            blob_path (str, optional): Path in blob storage. If not provided, uses filename from file_path

        Returns:
            str: URL of the uploaded blob
        """
        try:
            # If blob_path is not provided, use the filename from file_path
            if not blob_path:
                blob_path = os.path.basename(file_path)

            # Get the blob client
            blob_client = self.container_client.get_blob_client(blob_path)

            # Upload the file
            with open(file_path, "rb") as data:
                blob_client.upload_blob(data, overwrite=True)

            logging.info(f"File {file_path} uploaded to {blob_path}")

            return blob_path #blob_client.url

        except Exception as e:
            error_msg = f"Failed to upload document to blob: {blob_path}. Error: {str(e)}"
            logging.error(error_msg)
            raise RuntimeError(error_msg)

    def upload_bytes(self, data, blob_path):
        """
        Upload bytes data to Azure Blob Storage.

        Args:
            data (bytes): Bytes data to upload
            blob_path (str): Path in blob storage

        Returns:
            str: URL of the uploaded blob
        """
        try:
            # Get the blob client
            blob_client = self.container_client.get_blob_client(blob_path)

            # Upload the bytes data
            blob_client.upload_blob(data, overwrite=True)

            logging.info(f"Bytes data uploaded to {blob_path}")

            return blob_client.url

        except Exception as e:
            error_msg = f"Failed to upload bytes to blob: {blob_path}. Error: {str(e)}"
            logging.error(error_msg)
            raise RuntimeError(error_msg)

    def upload_text(self, text, blob_path):
        """
        Upload text data to Azure Blob Storage.

        Args:
            text (str): Text data to upload
            blob_path (str): Path in blob storage

        Returns:
            str: Path of the uploaded blob
        """
        try:
            # Get the blob client
            blob_client = self.container_client.get_blob_client(blob_path)

            # Upload the text data
            blob_client.upload_blob(text.encode('utf-8'), overwrite=True)

            logging.info(f"Text data uploaded to {blob_path}")

            return blob_path

        except Exception as e:
            error_msg = f"Failed to upload text to blob: {blob_path}. Error: {str(e)}"
            logging.error(error_msg)
            raise RuntimeError(error_msg)

    def create_tender_folder(self, folder_name):
        """
        Creates a logical folder structure for a tender.
        In Azure Blob Storage, folders are virtual concepts represented by blob name prefixes.

        Args:
            tender_hash (str): Unique identifier for the tender

        Returns:
            str: The folder prefix path for the tender
        """
        # In Azure Blob Storage, folders are just prefixes in blob names
        # We'll use a standard path format for all tenders
        folder_path = f"tenders/{folder_name}/"

        # No need to create placeholder files in Azure Blob Storage
        # Folders are virtual concepts represented by the prefix in the blob name
        logging.info(f"Using tender folder structure: {folder_path}")

        return folder_path

    def upload_tender_file(self, folder_name, file_type, content, file_name=None):
        """
        Upload a file to the specific tender folder with standard naming.

        Args:
            tender_hash (str): Unique identifier for the tender
            file_type (str): Type of file ('combined_chunks' or 'ai_document')
            content (str or bytes): Content to upload
            file_name (str, optional): Custom file name to use instead of standard names

        Returns:
            str: Blob path of the uploaded file
        """
        # Create the folder structure if it doesn't exist
        folder_path = f"tenders/{folder_name}/"

        # Determine the file name based on type
        if not file_name:
            if file_type == 'combined_chunks':
                file_name = 'combined_chunks.json'
            elif file_type == 'ai_document':
                file_name = 'ai_document.md'
            elif file_type == 'pdf_document':
                file_name = 'document.pdf'
            else:
                file_name = f"{file_type}.data"

        # Complete blob path
        blob_path = f"{folder_path}{file_name}"

        # Upload based on content type
        if isinstance(content, str):
            return self.upload_text(content, blob_path)
        elif isinstance(content, bytes):
            self.upload_bytes(content, blob_path)
            return blob_path
        else:
            raise ValueError(f"Unsupported content type: {type(content)}")

    def upload_tender_pdf(self, folder_name, pdf_content, filename):
        """
        Upload a PDF file to the specific tender folder's pdfs directory.

        Args:
            folder_name (str): Unique identifier for the tender
            pdf_content (bytes): PDF content as bytes
            filename (str): Name to use for the PDF file (should include .pdf extension)

        Returns:
            str: Blob path of the uploaded PDF file
        """
        # Create the folder path
        folder_path = f"tenders/{folder_name}/pdfs/"

        # Ensure filename is non-empty and valid
        if not filename or filename == 'document.pdf':
            import datetime
            timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
            filename = f"document_{timestamp}.pdf"

        # Sanitize filename to avoid problematic characters
        safe_filename = filename.replace(' ', '_')

        # Complete blob path
        blob_path = f"{folder_path}{safe_filename}"

        # Upload the PDF content
        self.upload_bytes(pdf_content, blob_path)

        logging.info(f"PDF uploaded to {blob_path}")
        return blob_path

    def download_document(self, blob_path, file_path=None):
        """
        Download a document from Azure Blob Storage.

        Args:
            blob_path (str): Path in blob storage
            file_path (str, optional): Local path to save the file. If not provided, returns the content as bytes

        Returns:
            bytes or str: Content as bytes if file_path is not provided, otherwise the path to the saved file
        """
        try:
            # Get the blob client
            blob_client = self.container_client.get_blob_client(blob_path)

            # Download the blob
            downloaded_blob = blob_client.download_blob()

            if file_path:
                # Save to file if file_path is provided
                with open(file_path, "wb") as file:
                    file.write(downloaded_blob.readall())
                logging.info(f"Blob {blob_path} downloaded to {file_path}")
                return file_path
            else:
                # Return content as bytes if file_path is not provided
                content = downloaded_blob.readall()
                logging.info(f"Blob {blob_path} downloaded as bytes")
                return content

        except Exception as e:
            error_msg = f"Failed to download document from blob: {blob_path}. Error: {str(e)}"
            logging.error(error_msg)
            raise RuntimeError(error_msg)

    def delete_document(self, blob_path):
        """
        Delete a document from Azure Blob Storage.

        Args:
            blob_path (str): Path in blob storage

        Returns:
            bool: True if deletion was successful
        """
        try:
            # Get the blob client
            blob_client = self.container_client.get_blob_client(blob_path)

            # Delete the blob
            blob_client.delete_blob()

            logging.info(f"Blob {blob_path} deleted")

            return True

        except Exception as e:
            error_msg = f"Failed to delete document from blob: {blob_path}. Error: {str(e)}"
            logging.error(error_msg)
            raise RuntimeError(error_msg)

    def list_documents(self, prefix=None):
        """
        List documents in the container.

        Args:
            prefix (str, optional): Filter results to items that begin with this prefix

        Returns:
            list: List of blob names
        """
        try:
            # List blobs in the container
            blobs = self.container_client.list_blobs(name_starts_with=prefix)

            # Extract blob names
            blob_names = [blob.name for blob in blobs]

            return blob_names

        except Exception as e:
            error_msg = f"Failed to list documents in container. Error: {str(e)}"
            logging.error(error_msg)
            raise RuntimeError(error_msg)

    def generate_sas_url(self, blob_path, minutes=10, read_only=True):
        """
        Generate a SAS URL for a blob.

        Args:
            blob_path (str): Path in blob storage
            minutes (int, optional): Number of minutes the SAS URL will be valid
            read_only (bool, optional): If True, SAS will be read-only

        Returns:
            str: SAS URL for the blob
        """
        try:
            # Generate the SAS token
            permissions = BlobSasPermissions(read=True, write=not read_only)

            sas_token = generate_blob_sas(
                account_name=self.blob_service_client.account_name,
                container_name=self.container_name,
                blob_name=blob_path,
                account_key=self.blob_service_client.credential.account_key,
                permission=permissions,
                expiry=datetime.now() + timedelta(minutes=minutes)
            )

            # Generate the full URL with SAS token
            blob_url_with_sas = f"https://{self.blob_service_client.account_name}.blob.core.windows.net/{self.container_name}/{blob_path}?{sas_token}"

            logging.info(f"SAS URL generated for blob: {blob_path}")

            return blob_url_with_sas

        except Exception as e:
            error_msg = f"Failed to generate SAS URL for blob: {blob_path}. Error: {str(e)}"
            logging.error(error_msg)
            raise RuntimeError(error_msg)
