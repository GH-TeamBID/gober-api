import boto3
import json
import requests
import logging
import urllib.parse
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from typing import Dict, Any, Optional, Union
from app.core.config import settings

# Configure logging
logger = logging.getLogger(__name__)

class NeptuneClient:
    """
    Client for Amazon Neptune that supports both Gremlin and REST API access
    with AWS SigV4 authentication.
    """
    
    def __init__(self, endpoint: str, port: int, region: str, iam_role_arn: Optional[str] = None):
        """
        Initialize the Neptune client.
        
        Args:
            endpoint (str): Neptune endpoint (without protocol)
            port (int): Neptune port
            region (str): AWS region
            iam_role_arn (str, optional): IAM role ARN for Neptune access
        """
        self.endpoint = endpoint
        self.port = port
        self.region = region
        self.iam_role_arn = iam_role_arn
        self.session = boto3.Session()
        self.credentials = self.session.get_credentials()
        
        # Base URLs
        self.http_url = f"https://{endpoint}:{port}"
    
    def _create_signed_request(self, method: str, endpoint_path: str, data: Optional[Dict] = None) -> requests.Request:
        """
        Create a signed request for Neptune REST API.
        
        Args:
            method (str): HTTP method (GET, POST, etc.)
            endpoint_path (str): API endpoint path
            data (Dict, optional): Request data
            
        Returns:
            requests.Request: Signed request
        """
        url = f"{self.http_url}/{endpoint_path}"
        
        headers = {
            'Content-Type': 'application/json'
        }
        
        # Create an AWS request
        request = AWSRequest(
            method=method,
            url=url,
            data=json.dumps(data) if data else None,
            headers=headers
        )
        
        # Sign the request with SigV4
        SigV4Auth(self.credentials, 'neptune-db', self.region).add_auth(request)
        prepared_request = request.prepare()
        
        return prepared_request
    
    def execute_sparql_query(self, query: str) -> Dict:
        """
        Execute a SPARQL query against Neptune.
        
        Args:
            query (str): SPARQL query to execute
            
        Returns:
            Dict: Query results
        """
        sparql_path = "sparql"
        
        # Create a signed request
        prepared_request = self._create_signed_request('POST', sparql_path)
        
        # Determine the appropriate Accept header based on query type
        # CONSTRUCT and DESCRIBE queries return RDF data, while SELECT and ASK return result sets
        accept_header = "application/sparql-results+json"  # Default for SELECT/ASK
        if "CONSTRUCT" in query.upper() or "DESCRIBE" in query.upper():
            accept_header = "application/ld+json"  # For CONSTRUCT/DESCRIBE
        
        try:
            # Send the signed request
            response = requests.post(
                f"{self.http_url}/{sparql_path}",
                data=query,
                headers={
                    **dict(prepared_request.headers),
                    'Content-Type': 'application/sparql-query',
                    'Accept': accept_header  # Request JSON response
                },
                timeout=30,
                verify=False  # Disable SSL certificate verification
            )
            
            if response.status_code != 200:
                logger.warning(f"NEPTUNE DIAGNOSTIC: Error response: {response.text[:200]}")
                
            response.raise_for_status()
            
            # Only try to parse JSON if there's content
            if response.text.strip():
                try:
                    return response.json()
                except json.JSONDecodeError:
                    logger.warning(f"Received non-JSON response despite requesting JSON format. Content-Type: {response.headers.get('Content-Type')}")
                    # Return the raw text and headers so services.py can handle it
                    return {
                        "raw_text": response.text,
                        "headers": dict(response.headers),
                        "status_code": response.status_code
                    }
            else:
                logger.warning("Empty response received from Neptune")
                return {}
        except Exception as e:
            raise 