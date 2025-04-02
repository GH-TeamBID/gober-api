import boto3
import json
import requests
import logging
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from typing import Dict, Any, Optional, List, Tuple
import aiohttp
import asyncio

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
        

    async def execute_sparql_query_async(self, query: str) -> Dict:
        sparql_path = "sparql"
        
        # Crear la solicitud firmada
        prepared_request = self._create_signed_request('POST', sparql_path)
        
        # Determinar el header Accept según el tipo de query
        accept_header = "application/sparql-results+json"
        if "CONSTRUCT" in query.upper() or "DESCRIBE" in query.upper():
            accept_header = "application/ld+json"
        
        # Quitar 'Content-Length' de los headers firmados para que aiohttp lo calcule correctamente
        headers = {k: v for k, v in dict(prepared_request.headers).items() if k.lower() != 'content-length'}
        headers.update({
            'Content-Type': 'application/sparql-query',
            'Accept': accept_header
        })
        
        url = f"{self.http_url}/{sparql_path}"
        
        payload_bytes = query.encode("utf-8")
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(
                    url,
                    data=payload_bytes,
                    headers=headers,
                    ssl=False,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:                    
                    # Leer el texto de la respuesta para depuración
                    resp_text = await response.text()
                    
                    if response.status != 200:
                        logger.warning(f"NEPTUNE DIAGNOSTIC: Error response in async query {query[:200]}: {resp_text}\n")
                    
                    response.raise_for_status()
                    
                    if resp_text.strip():
                        try:
                            json_data = await response.json()
                            return json_data
                        except aiohttp.ContentTypeError:
                            logger.warning("Received non-JSON response despite requesting JSON format")
                            return {
                                "raw_text": resp_text,
                                "headers": dict(response.headers),
                                "status_code": response.status
                            }
                    else:
                        logger.warning("Empty response received from Neptune")
                        return {}
            except Exception as e:
                logger.error(f"Error in execute_sparql_query_async: {str(e)}")
                raise
        
    # Add this method to execute multiple queries in parallel
    async def execute_sparql_queries_parallel(self, queries: List[str]) -> List[Dict]:
        """
        Execute multiple SPARQL queries in parallel.
        
        Args:
            queries (List[str]): List of SPARQL queries to execute
            
        Returns:
            List[Dict]: List of query results in the same order as queries
        """
        tasks = [self.execute_sparql_query_async(query) for query in queries]
        return await asyncio.gather(*tasks, return_exceptions=True)

    # Add this method for named queries (useful when you need to track which result is which)
    async def execute_named_sparql_queries_parallel(self, named_queries: List[Tuple[str, str]]) -> Dict[str, Dict]:
        """
        Execute multiple named SPARQL queries in parallel.
        
        Args:
            named_queries (List[Tuple[str, str]]): List of (name, query) tuples
            
        Returns:
            Dict[str, Dict]: Dictionary mapping query names to results
        """
        async def execute_named_query(name, query):
            result = await self.execute_sparql_query_async(query)
            return name, result
        
        tasks = [execute_named_query(name, query) for name, query in named_queries]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Convert list of (name, result) tuples to dictionary
        return {name: result for name, result in results if not isinstance(result, Exception)}