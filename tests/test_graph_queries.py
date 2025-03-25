from rdflib import Graph, URIRef, Literal
import ssl
import urllib.request
import json
import requests
import warnings
from io import StringIO
from typing import Optional, List, Dict, Any, Union
from pydantic import BaseModel, Field, AnyUrl

# Suppress insecure request warnings
warnings.filterwarnings('ignore', message='Unverified HTTPS request')

# Create a context for SSL connections that doesn't verify certificates
ssl_context = ssl._create_unverified_context()

# Install an opener that uses our custom SSL context
opener = urllib.request.build_opener(
    urllib.request.HTTPSHandler(context=ssl_context)
)
urllib.request.install_opener(opener)

# Configure the store SPARQL with the URL of Neptune
endpoint = "https://ALB-Neptune-560649831.eu-north-1.elb.amazonaws.com:8182/sparql"

# Define common namespaces as URIRefs for easier access
RDF_TYPE = URIRef("http://www.w3.org/1999/02/22-rdf-syntax-ns#type")
DCT_TITLE = URIRef("http://purl.org/dc/terms/title")
DCT_DESCRIPTION = URIRef("http://purl.org/dc/terms/description")
EPO_NS = "http://data.europa.eu/a4g/ontology#"
EPO_HAS_PURPOSE = URIRef(f"{EPO_NS}hasPurpose")
EPO_HAS_ESTIMATED_VALUE = URIRef(f"{EPO_NS}hasEstimatedValue")
EPO_INVOLVES_BUYER = URIRef(f"{EPO_NS}involvesBuyer")
EPO_HAS_PLANNED_PERIOD = URIRef(f"{EPO_NS}hasPlannedPeriod")
EPO_DEFINES_PLACE = URIRef(f"{EPO_NS}definesSpecificPlaceOfPerformance")
EPO_FORESEES_CONTRACT_TERM = URIRef(f"{EPO_NS}foreseesContractSpecificTerm")
EPO_PROCUREMENT_OBJECT = URIRef(f"{EPO_NS}ProcurementObject")
M8G_VALUE = URIRef("http://data.europa.eu/m8g/value")

# Pydantic models for the procurement data
class MonetaryValue(BaseModel):
    """Represents a monetary value in the procurement data"""
    uri: str
    # Add more fields if needed based on your data model

class Period(BaseModel):
    """Represents a time period in the procurement data"""
    uri: str
    # Add more fields if needed based on your data model

class Location(BaseModel):
    """Represents a location in the procurement data"""
    uri: str
    # Add more fields if needed based on your data model

class ContractingParty(BaseModel):
    """Represents a contracting party (buyer) in the procurement data"""
    uri: str
    # Add more fields if needed based on your data model

class ContractTerm(BaseModel):
    """Represents contract terms in the procurement data"""
    uri: str
    # Add more fields if needed based on your data model

class Purpose(BaseModel):
    """Represents the purpose of a procurement project"""
    uri: str
    # Add more fields if needed based on your data model

class ProcurementObject(BaseModel):
    """Pydantic model representing a procurement object from the RDF data"""
    uri: str
    title: Optional[str] = None
    description: Optional[str] = None
    purpose: Optional[Purpose] = None
    estimated_value: Optional[MonetaryValue] = None
    tax_exclusive_value: Optional[MonetaryValue] = None
    total_value: Optional[MonetaryValue] = None
    buyer: Optional[ContractingParty] = None
    planned_period: Optional[Period] = None
    place_of_performance: Optional[Location] = None
    contract_term: Optional[ContractTerm] = None
    
    class Config:
        """Pydantic configuration"""
        arbitrary_types_allowed = True

# Helper function for direct HTTP requests (used by our wrapper)
def query_neptune_direct(query_string, accept_format="application/sparql-results+json"):
    """Execute a SPARQL query directly against Neptune using HTTP."""
    headers = {
        'Content-Type': 'application/sparql-query',
        'Accept': accept_format
    }
    
    response = requests.post(
        endpoint,
        data=query_string,
        headers=headers,
        verify=False
    )
    
    if response.status_code != 200:
        raise Exception(f"Query failed with status {response.status_code}: {response.text}")
    
    # Return raw response for non-JSON formats
    if accept_format != "application/sparql-results+json":
        return response.text
    
    return response.json()

# Custom GraphWrapper that uses direct HTTP but presents a simplified RDFLib-like interface
class NeptuneGraphWrapper:
    """A simplified Graph-like wrapper that uses direct HTTP for reliability."""
    
    def __init__(self, endpoint):
        self.endpoint = endpoint
    
    def describe_full(self, uri, format="turtle", as_graph=False):
        """Get a complete description of a resource using SPARQL DESCRIBE.
        
        Args:
            uri: The URI of the resource to describe
            format: The RDF format to return (turtle, xml, json-ld, etc.)
            as_graph: If True, returns an RDFLib Graph object instead of a string
        
        Returns:
            Either a string containing the RDF description in the requested format,
            or an RDFLib Graph object if as_graph=True
        """
        query = f"DESCRIBE <{uri}>"
        
        # Map format to MIME type
        format_map = {
            "turtle": "text/turtle",
            "xml": "application/rdf+xml",
            "json-ld": "application/ld+json",
            "n3": "text/n3",
            "ntriples": "application/n-triples"
        }
        
        mime_type = format_map.get(format, "text/turtle")
        
        # Execute the DESCRIBE query with the appropriate Accept header
        rdf_data = query_neptune_direct(query, accept_format=mime_type)
        
        # If the caller wants an RDFLib Graph, parse the RDF data
        if as_graph:
            g = Graph()
            # Use StringIO to create a file-like object from the string
            rdf_stream = StringIO(rdf_data)
            g.parse(rdf_stream, format=format)
            return g
        
        # Otherwise return the raw RDF data as a string
        return rdf_data
    
    def get_procurement_object(self, uri):
        """
        Retrieve a procurement object by URI and convert it to a Pydantic model
        
        Args:
            uri: The URI of the procurement object to retrieve
            
        Returns:
            A ProcurementObject Pydantic model populated with data from the graph
        """
        # Get the RDF graph for this procurement object
        graph = self.describe_full(uri, as_graph=True)
        
        # Convert the graph to a ProcurementObject
        return graph_to_procurement_object(graph, uri)

def graph_to_procurement_object(graph, uri):
    """
    Convert an RDFLib Graph to a ProcurementObject Pydantic model
    
    Args:
        graph: The RDFLib Graph containing the procurement object data
        uri: The URI of the procurement object
        
    Returns:
        A ProcurementObject Pydantic model populated with data from the graph
    """
    # Convert URI to URIRef if it's a string
    if isinstance(uri, str):
        uri_ref = URIRef(uri)
    else:
        uri_ref = uri
    
    # Check if this is actually a ProcurementObject
    types = list(graph.objects(uri_ref, RDF_TYPE))
    if EPO_PROCUREMENT_OBJECT not in types:
        raise ValueError(f"The URI {uri} is not a ProcurementObject")
    
    # Extract basic properties
    title = graph.value(uri_ref, DCT_TITLE)
    description = graph.value(uri_ref, DCT_DESCRIPTION)
    
    # Extract related entities
    purpose_uri = graph.value(uri_ref, EPO_HAS_PURPOSE)
    estimated_value_uri = graph.value(uri_ref, EPO_HAS_ESTIMATED_VALUE)
    buyer_uri = graph.value(uri_ref, EPO_INVOLVES_BUYER)
    planned_period_uri = graph.value(uri_ref, EPO_HAS_PLANNED_PERIOD)
    place_uri = graph.value(uri_ref, EPO_DEFINES_PLACE)
    contract_term_uri = graph.value(uri_ref, EPO_FORESEES_CONTRACT_TERM)
    
    # Find monetary values - there might be multiple with different purposes
    monetary_values = list(graph.objects(uri_ref, M8G_VALUE))
    tax_exclusive_value = None
    total_value = None
    
    # This is a simplification - in a real app, you'd need to examine each value to determine its type
    if len(monetary_values) >= 1:
        tax_exclusive_value = str(monetary_values[0])
    if len(monetary_values) >= 2:
        total_value = str(monetary_values[1])
    
    # Create the ProcurementObject
    procurement_object = ProcurementObject(
        uri=str(uri_ref),
        title=str(title) if title else None,
        description=str(description) if description else None,
        purpose=Purpose(uri=str(purpose_uri)) if purpose_uri else None,
        estimated_value=MonetaryValue(uri=str(estimated_value_uri)) if estimated_value_uri else None,
        tax_exclusive_value=MonetaryValue(uri=tax_exclusive_value) if tax_exclusive_value else None,
        total_value=MonetaryValue(uri=total_value) if total_value else None,
        buyer=ContractingParty(uri=str(buyer_uri)) if buyer_uri else None,
        planned_period=Period(uri=str(planned_period_uri)) if planned_period_uri else None,
        place_of_performance=Location(uri=str(place_uri)) if place_uri else None,
        contract_term=ContractTerm(uri=str(contract_term_uri)) if contract_term_uri else None,
    )
    
    return procurement_object

# # Create our Neptune graph wrapper
# neptune = NeptuneGraphWrapper(endpoint)

# # Test URI
# specific_object_uri = "http://example.com/eprocurement/procurementProject/project-2025-000236356"

# # Test the DESCRIBE query functionality
# print("\nNeptune RDF Graph DESCRIBE Test")
# print("==============================\n")

# # Test 1: Get raw RDF data
# print("1. Raw RDF data (Turtle format):")
# try:
#     describe_rdf = neptune.describe_full(specific_object_uri, format="turtle")
#     # Print first 500 chars to avoid overwhelming output
#     print(describe_rdf[:500] + "..." if len(describe_rdf) > 500 else describe_rdf)
#     print(f"\nTotal length: {len(describe_rdf)} characters")
# except Exception as e:
#     print(f"Error with DESCRIBE query: {e}")

# # Test 2: Get as RDFLib Graph
# print("\n2. Parsed into RDFLib Graph:")
# try:
#     g = neptune.describe_full(specific_object_uri, format="turtle", as_graph=True)
#     print(f"Successfully parsed into Graph with {len(g)} triples")
    
#     # Print all triples in the graph
#     print("\nTriples in the graph:")
#     for i, (s, p, o) in enumerate(g):
#         print(f"{i+1}. {s} {p} {o}")
    
#     # Demonstrate some Graph operations
#     print("\nGraph operations:")
#     print(f"Predicates: {len(list(g.predicates()))} unique predicates")
#     print(f"Objects: {len(list(g.objects()))} unique objects")
    
#     # Find a specific predicate (example)
#     print("\nLooking for specific predicates:")
#     for obj in g.objects(URIRef(specific_object_uri), RDF_TYPE):
#         print(f"Resource is of type: {obj}")
    
# except Exception as e:
#     print(f"Error parsing into Graph: {e}")

# # Test 3: Convert to Pydantic model
# print("\n3. Converted to Pydantic ProcurementObject model:")
# try:
#     # Get the graph
#     g = neptune.describe_full(specific_object_uri, format="turtle", as_graph=True)
    
#     # Convert to ProcurementObject
#     procurement_object = graph_to_procurement_object(g, specific_object_uri)
    
#     # Print the model as JSON
#     print(procurement_object.model_dump_json(indent=2))
    
#     # Demonstrate accessing model properties
#     print("\nAccessing model properties:")
#     print(f"Title: {procurement_object.title}")
#     print(f"Description: {procurement_object.description[:100]}..." if procurement_object.description else "No description")
#     print(f"Buyer: {procurement_object.buyer.uri if procurement_object.buyer else 'None'}")
    
# except Exception as e:
#     print(f"Error converting to Pydantic model: {e}")

# # Test 4: Using the convenience method
# print("\n4. Using the convenience method:")
# try:
#     procurement_object = neptune.get_procurement_object(specific_object_uri)
#     print(f"Successfully retrieved ProcurementObject with title: {procurement_object.title}")
# except Exception as e:
#     print(f"Error using convenience method: {e}")

if __name__ == "__main__":

    query = """
    PREFIX dcterms: <http://purl.org/dc/terms/>
    PREFIX ns1: <http://data.europa.eu/a4g/ontology#>
    PREFIX ns2: <http://www.w3.org/ns/locn#>
    PREFIX ns3: <http://publications.europa.eu/ontology/authority/>
    PREFIX ns4: <http://www.w3.org/ns/adms#>
    PREFIX ns5: <http://data.europa.eu/m8g/>
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
    PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

    SELECT ?procedure ?id ?title ?description ?submissionDate (COUNT(DISTINCT ?lot) AS ?lotCount)
        ?orgName ?baseBudgetAmount ?baseBudgetCurrency ?locationName ?contractType 
        (GROUP_CONCAT(DISTINCT ?classification; separator=", ") AS ?classifications)
    WHERE {
    ?procedure a ns1:Procedure .
    
    # Id del expediente (identifier)
    OPTIONAL { 
        ?procedure ns4:identifier ?identifier .
        ?identifier skos:notation ?id .
    }
    
    # Título y descripción
    OPTIONAL { ?procedure dcterms:title ?title . }
    OPTIONAL { ?procedure dcterms:description ?description . }
    
    # Fecha de sumisión: desde isSubjectToProcedureSpecificTerm con SubmissionTerm
    OPTIONAL { 
        ?procedure ns1:isSubjectToProcedureSpecificTerm ?submissionTerm .
        ?submissionTerm a ns1:SubmissionTerm ;
                        ns1:hasReceiptDeadline ?submissionDate .
    }
    
    # Número de lotes
    OPTIONAL { 
        ?procedure ns1:hasProcurementScopeDividedIntoLot ?lot .
    }
    
    # Nombre de la organización: a través de involvesBuyer y PublicOrganisation
    OPTIONAL { 
        ?procedure ns1:involvesBuyer ?buyer .
        ?buyer a ns5:PublicOrganisation ;
            ns1:hasLegalName ?orgName .
    }
    
    # Presupuesto base: mediante hasEstimatedValue, filtrando el IRI que termina en "estimated-overall-contract-amount"
    OPTIONAL { 
        ?procedure ns1:hasEstimatedValue ?monetaryValue .
        FILTER(STRENDS(STR(?monetaryValue), "estimated-overall-contract-amount"))
        ?monetaryValue ns1:hasAmountValue ?baseBudgetAmount ;
                    ns3:currency ?baseBudgetCurrency .
    }
    
    # Ubicación y tipo de contrato: desde foreseesContractSpecificTerm y ContractTerm
    OPTIONAL { 
        ?procedure ns1:foreseesContractSpecificTerm ?contractTerm .
        ?contractTerm ns1:definesSpecificPlaceOfPerformance ?location ;
                    ns1:hasContractNatureType ?contractType .
        ?location a dcterms:Location ;
                ns2:geographicName ?locationName .
    }
    
    # Categorías/CPVs: desde hasPurpose y hasMainClassification (puede haber varias)
    OPTIONAL { 
        ?procedure ns1:hasPurpose ?purpose .
        ?purpose ns1:hasMainClassification ?classification .
    }
    }
    GROUP BY ?procedure ?id ?title ?description ?submissionDate ?orgName ?baseBudgetAmount ?baseBudgetCurrency ?locationName ?contractType
    ORDER BY ?procedure
    """
    
    results = query_neptune_direct(query, accept_format="application/sparql-results+json")
    print(results)