import boto3
import json
import requests
import logging
import urllib.parse
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from gremlin_python.driver import client as gremlin_client
from gremlin_python.driver.protocol import GremlinServerError
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
        self.ws_url = f"wss://{endpoint}:{port}/gremlin"
        
    def get_gremlin_client(self) -> gremlin_client.Client:
        """
        Get a Gremlin client for Neptune with SigV4 authentication.
        
        Returns:
            gremlin_client.Client: Authenticated Gremlin client
        """
        try:
            # Create a Gremlin client with SigV4 authentication
            auth = {
                'mode': 'sigv4',
                'region': self.region
            }
            
            return gremlin_client.Client(
                self.ws_url, 
                'g',
                authentication=auth
            )
        except Exception as e:
            logger.error(f"Error creating Gremlin client: {str(e)}")
            raise
    
    def execute_gremlin_query(self, query: str) -> Dict:
        """
        Execute a Gremlin query against Neptune.
        
        Args:
            query (str): Gremlin query to execute
            
        Returns:
            Dict: Query results
        """
        client = self.get_gremlin_client()
        try:
            result = client.submit(query).all().result()
            return result
        except GremlinServerError as e:
            logger.error(f"Gremlin query error: {str(e)}")
            raise
        finally:
            client.close()
    
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
        
        # Send the signed request
        response = requests.post(
            f"{self.http_url}/{sparql_path}",
            data=query,
            headers={
                **dict(prepared_request.headers),
                'Content-Type': 'application/sparql-query'
            },
            timeout=30,
            verify=False  # Disable SSL certificate verification
        )
        
        # Check for errors
        response.raise_for_status()
        
        # Parse the response
        return response.json() 