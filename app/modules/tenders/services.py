import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session
from app.core.database import get_neptune_client, get_meilisearch_client
from app.modules.tenders import models, schemas
from rdflib import Graph, Namespace, URIRef, Literal
import surf
import asyncio
from math import ceil

# Configure logging
logger = logging.getLogger(__name__)

# Define European Procurement Ontology namespace
EPO_NS = "http://data.europa.eu/a4g/ontology#"

# Meilisearch index name for tenders
TENDERS_INDEX = "tenders"

async def get_tenders(
    db: Session, 
    page: int = 1, 
    limit: int = 10, 
    sort_by: str = "publish_date", 
    sort_order: str = "desc", 
    filters: Optional[Dict[str, Any]] = None,
    client_id: Optional[int] = None
) -> schemas.TenderListResponse:
    """
    Get a paginated list of tenders from Neptune with filtering and sorting.
    If search term is provided, use Meilisearch to find matching tender IDs.
    
    Args:
        db: SQL database session
        page: Page number (1-indexed)
        limit: Number of items per page
        sort_by: Field to sort by
        sort_order: Sort direction (asc or desc)
        filters: Dictionary of filter criteria
        client_id: Optional client ID to check if tenders are saved
        
    Returns:
        TenderListResponse: Paginated list of tenders
    """
    if filters is None:
        filters = {}
    
    # Calculate offset
    offset = (page - 1) * limit
    
    # Start with empty list of tender IDs for filtering
    tender_ids = []
    total_hits = 0
    
    # If search term is provided, use Meilisearch to find matching tender IDs
    if filters.get("search"):
        meilisearch = get_meilisearch_client()
        search_results = meilisearch.index(TENDERS_INDEX).search(
            filters.get("search"),
            {
                "limit": 1000,  # Get more results to filter later
                "attributesToRetrieve": ["id"],
                "attributesToHighlight": ["title", "description"],
            }
        )
        
        # Extract tender IDs from search results
        tender_ids = [hit["id"] for hit in search_results["hits"]]
        total_hits = search_results["estimatedTotalHits"]
        
        # If no search results, return empty response
        if not tender_ids:
            return schemas.TenderListResponse(
                items=[],
                total=0,
                page=page,
                size=limit,
                total_pages=0,
                has_next=False,
                has_prev=page > 1
            )
    
    # Get Neptune client
    neptune = get_neptune_client()
    
    # Build SPARQL query with filters
    sparql_query = f"""
    PREFIX epo: <{EPO_NS}>
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    
    SELECT ?id ?title ?description ?type ?status ?organization ?budget ?publishDate ?closeDate ?location ?category
    WHERE {{
        ?tender rdf:type epo:Tender .
        ?tender epo:id ?id .
        ?tender epo:title ?title .
        ?tender epo:description ?description .
        OPTIONAL {{ ?tender epo:procedureType ?type }}
        OPTIONAL {{ ?tender epo:status ?status }}
        OPTIONAL {{ ?tender epo:contractingAuthority ?organization }}
        OPTIONAL {{ ?tender epo:estimatedValue ?budget }}
        OPTIONAL {{ ?tender epo:publicationDate ?publishDate }}
        OPTIONAL {{ ?tender epo:submissionDeadline ?closeDate }}
        OPTIONAL {{ ?tender epo:location ?location }}
        OPTIONAL {{ ?tender epo:category ?category }}
    """
    
    # Add filter for tender IDs from search
    if tender_ids:
        id_values = ", ".join([f'"{id}"' for id in tender_ids])
        sparql_query += f"""
        FILTER(?id IN ({id_values}))
        """
    
    # Add filters based on filter criteria
    if filters.get("type"):
        sparql_query += f"""
        FILTER(?type = "{filters['type']}")
        """
    
    if filters.get("status"):
        sparql_query += f"""
        FILTER(?status = "{filters['status']}")
        """
    
    if filters.get("organization"):
        sparql_query += f"""
        FILTER(CONTAINS(LCASE(?organization), LCASE("{filters['organization']}")))
        """
    
    if filters.get("location"):
        sparql_query += f"""
        FILTER(CONTAINS(LCASE(?location), LCASE("{filters['location']}")))
        """
    
    if filters.get("category"):
        sparql_query += f"""
        FILTER(CONTAINS(LCASE(?category), LCASE("{filters['category']}")))
        """
    
    if filters.get("publication_date_from"):
        date_from = filters["publication_date_from"].strftime("%Y-%m-%dT%H:%M:%S")
        sparql_query += f"""
        FILTER(?publishDate >= "{date_from}"^^xsd:dateTime)
        """
    
    if filters.get("publication_date_to"):
        date_to = filters["publication_date_to"].strftime("%Y-%m-%dT%H:%M:%S")
        sparql_query += f"""
        FILTER(?publishDate <= "{date_to}"^^xsd:dateTime)
        """
    
    # Close the WHERE clause
    sparql_query += "}"
    
    # Add sorting
    sort_direction = "DESC" if sort_order.lower() == "desc" else "ASC"
    sparql_var = f"?{sort_by}" if sort_by != "publish_date" else "?publishDate"
    sparql_query += f"""
    ORDER BY {sort_direction}({sparql_var})
    LIMIT {limit}
    OFFSET {offset}
    """
    
    # Execute count query for pagination
    count_query = sparql_query.split("SELECT")[0] + "SELECT (COUNT(DISTINCT ?tender) as ?count) WHERE {" + sparql_query.split("WHERE {")[1].split("}")[0] + "}"
    
    try:
        # Execute count query if we didn't get count from Meilisearch
        if not total_hits:
            count_result = neptune.execute_sparql_query(count_query)
            if 'results' in count_result and 'bindings' in count_result['results']:
                total_hits = int(count_result['results']['bindings'][0]['count']['value'])
            else:
                total_hits = 0
        
        # Execute main query
        result = neptune.execute_sparql_query(sparql_query)
        
        # Process results
        tenders = []
        
        if 'results' in result and 'bindings' in result['results']:
            for binding in result['results']['bindings']:
                # Convert SPARQL result to Python dict
                tender_data = {
                    "id": binding.get('id', {}).get('value', ''),
                    "title": binding.get('title', {}).get('value', ''),
                    "description": binding.get('description', {}).get('value', ''),
                    "type": binding.get('type', {}).get('value', ''),
                    "status": binding.get('status', {}).get('value', ''),
                    "organization": binding.get('organization', {}).get('value', ''),
                    "budget": float(binding.get('budget', {}).get('value', 0)) if binding.get('budget') else None,
                    "publish_date": datetime.fromisoformat(binding.get('publishDate', {}).get('value', '').replace('Z', '+00:00')) if binding.get('publishDate') else datetime.now(),
                    "close_date": datetime.fromisoformat(binding.get('closeDate', {}).get('value', '').replace('Z', '+00:00')) if binding.get('closeDate') else None,
                    "location": binding.get('location', {}).get('value', ''),
                    "source_url": "",  # Not included in preview
                }
                
                # Check if tender is saved by client
                is_saved = False
                if client_id:
                    saved_tender = db.query(models.ClientTender).filter(
                        models.ClientTender.client_id == client_id,
                        models.ClientTender.tender_id == tender_data["id"]
                    ).first()
                    is_saved = saved_tender is not None
                
                # Add saved status to response
                tender_data["is_saved"] = is_saved
                
                # Create Pydantic model
                tenders.append(schemas.TenderResponse(**tender_data))
        
        # Calculate pagination metadata
        total_pages = ceil(total_hits / limit)
        has_next = page < total_pages
        has_prev = page > 1
        
        # Return paginated response
        return schemas.TenderListResponse(
            items=tenders,
            total=total_hits,
            page=page,
            size=limit,
            total_pages=total_pages,
            has_next=has_next,
            has_prev=has_prev
        )
        
    except Exception as e:
        logger.error(f"Error fetching tenders: {str(e)}")
        raise

async def get_tender_detail(db: Session, tender_id: str, client_id: Optional[int] = None) -> schemas.TenderDetail:
    """
    Get detailed information about a specific tender from Neptune.
    
    Args:
        db: SQL database session
        tender_id: The URI/ID of the tender to retrieve
        client_id: Optional client ID to check if tender is saved
        
    Returns:
        TenderDetail: Detailed tender information
    """
    # Get Neptune client
    neptune = get_neptune_client()
    
    # Create full URI if tender_id is not already a URI
    if not tender_id.startswith("http"):
        tender_uri = f"http://data.europa.eu/a4g/resource/tender/{tender_id}"
    else:
        tender_uri = tender_id
    
    # Retrieve tender data using SPARQL CONSTRUCT
    sparql_query = f"""
    PREFIX epo: <{EPO_NS}>
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    
    CONSTRUCT {{ 
        <{tender_uri}> ?p ?o .
        ?o ?p2 ?o2 .
    }}
    WHERE {{ 
        <{tender_uri}> ?p ?o .
        OPTIONAL {{ ?o ?p2 ?o2 . }}
    }}
    """
    
    try:
        # Execute SPARQL query
        result = neptune.execute_sparql_query(sparql_query)
        
        # Create RDFLib graph and parse the result
        g = Graph()
        
        # Handle different result formats
        if isinstance(result, dict):
            # If result is a structured data object, convert to a string and parse
            import json
            g.parse(data=json.dumps(result), format="json-ld")
        else:
            # If result is serialized RDF, parse directly
            g.parse(data=result, format="turtle")
        
        # Initialize SuRF
        # Register namespaces
        surf.namespace.register(epo=EPO_NS)
        
        # Create a SuRF store and session with our RDFLib graph
        store = surf.Store(reader="rdflib", writer="rdflib", rdflib_store=g)
        session = surf.Session(store)
        
        # Get the Tender class and load the resource
        TenderClass = session.get_class(surf.ns.EPO.Tender)
        tender_resource = session.get_resource(tender_uri, TenderClass)
        
        # Check if tender exists
        if not tender_resource:
            logger.error(f"Tender with ID {tender_id} not found")
            raise ValueError(f"Tender with ID {tender_id} not found")
        
        # Extract all available metadata from the resource
        tender_data = {
            "id": tender_id,
            "title": str(tender_resource.epo_title.first or ""),
            "description": str(tender_resource.epo_description.first or ""),
            "type": str(tender_resource.epo_procedureType.first or ""),
            "status": str(tender_resource.epo_status.first or ""),
            "organization": str(tender_resource.epo_contractingAuthority.first or ""),
            "budget": float(tender_resource.epo_estimatedValue.first) if hasattr(tender_resource, "epo_estimatedValue") and tender_resource.epo_estimatedValue.first else None,
            "publish_date": tender_resource.epo_publicationDate.first.toPython() if hasattr(tender_resource, "epo_publicationDate") and tender_resource.epo_publicationDate.first else datetime.now(),
            "close_date": tender_resource.epo_submissionDeadline.first.toPython() if hasattr(tender_resource, "epo_submissionDeadline") and tender_resource.epo_submissionDeadline.first else None,
            "source_url": str(tender_resource.epo_sourceUrl.first or ""),
            "location": str(tender_resource.epo_location.first or ""),
            "category": str(tender_resource.epo_category.first or ""),
        }
        
        # Extract additional fields for detailed view
        if hasattr(tender_resource, "epo_requirements"):
            tender_data["requirements"] = [str(req) for req in tender_resource.epo_requirements]
        
        if hasattr(tender_resource, "epo_attachments"):
            tender_data["attachments"] = []
            for attachment in tender_resource.epo_attachments:
                attachment_data = {}
                if hasattr(attachment, "epo_fileName"):
                    attachment_data["name"] = str(attachment.epo_fileName.first or "")
                if hasattr(attachment, "epo_fileUrl"):
                    attachment_data["url"] = str(attachment.epo_fileUrl.first or "")
                if attachment_data:
                    tender_data["attachments"].append(attachment_data)
        
        if hasattr(tender_resource, "epo_contactInfo"):
            contact = tender_resource.epo_contactInfo.first
            if contact:
                tender_data["contact_info"] = {}
                if hasattr(contact, "epo_contactName"):
                    tender_data["contact_info"]["name"] = str(contact.epo_contactName.first or "")
                if hasattr(contact, "epo_contactEmail"):
                    tender_data["contact_info"]["email"] = str(contact.epo_contactEmail.first or "")
                if hasattr(contact, "epo_contactPhone"):
                    tender_data["contact_info"]["phone"] = str(contact.epo_contactPhone.first or "")
        
        if hasattr(tender_resource, "epo_awardCriteria"):
            tender_data["award_criteria"] = []
            for criterion in tender_resource.epo_awardCriteria:
                criterion_data = {}
                if hasattr(criterion, "epo_criterionName"):
                    criterion_data["name"] = str(criterion.epo_criterionName.first or "")
                if hasattr(criterion, "epo_criterionWeight"):
                    criterion_data["weight"] = float(criterion.epo_criterionWeight.first or 0)
                if criterion_data:
                    tender_data["award_criteria"].append(criterion_data)
        
        if hasattr(tender_resource, "epo_cpvCodes"):
            tender_data["cpv_codes"] = [str(code) for code in tender_resource.epo_cpvCodes]
        
        # Create metadata dictionary for any additional properties
        tender_data["metadata"] = {}
        for predicate, obj in tender_resource.predicate_objects():
            pred_name = predicate.split("#")[-1]
            # Skip properties already included in main fields
            if pred_name not in ["id", "title", "description", "procedureType", "status", 
                                "contractingAuthority", "estimatedValue", "publicationDate", 
                                "submissionDeadline", "sourceUrl", "location", "category",
                                "requirements", "attachments", "contactInfo", "awardCriteria", "cpvCodes"]:
                tender_data["metadata"][pred_name] = str(obj)
        
        # Check if tender is saved by client
        is_saved = False
        if client_id:
            saved_tender = db.query(models.ClientTender).filter(
                models.ClientTender.client_id == client_id,
                models.ClientTender.tender_id == tender_id
            ).first()
            is_saved = saved_tender is not None
        
        # Create Pydantic model from the data
        tender_detail = schemas.TenderDetail(**tender_data)
        
        return tender_detail
        
    except Exception as e:
        logger.error(f"Error retrieving tender {tender_id}: {str(e)}")
        raise

def get_tender(db: Session, tender_id: str, client_id: Optional[int] = None) -> schemas.TenderResponse:
    """
    Get basic information about a specific tender from Neptune using SuRF.
    
    Args:
        db: SQL database session
        tender_id: The URI/ID of the tender to retrieve
        client_id: Optional client ID to check if tender is saved
        
    Returns:
        TenderResponse: Tender details mapped from RDF using SuRF
    """
    # Get Neptune client
    neptune = get_neptune_client()
    
    # Create full URI if tender_id is not already a URI
    if not tender_id.startswith("http"):
        tender_uri = f"http://data.europa.eu/a4g/resource/tender/{tender_id}"
    else:
        tender_uri = tender_id
    
    # Retrieve tender data using SPARQL CONSTRUCT
    sparql_query = f"""
    PREFIX epo: <{EPO_NS}>
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    
    CONSTRUCT {{ 
        <{tender_uri}> ?p ?o .
        ?o ?p2 ?o2 .
    }}
    WHERE {{ 
        <{tender_uri}> ?p ?o .
        OPTIONAL {{ ?o ?p2 ?o2 . }}
    }}
    """
    
    try:
        # Execute SPARQL query
        result = neptune.execute_sparql_query(sparql_query)
        
        # Create RDFLib graph and parse the result
        g = Graph()
        
        # Handle different result formats
        if isinstance(result, dict):
            # If result is a structured data object, convert to a string and parse
            import json
            g.parse(data=json.dumps(result), format="json-ld")
        else:
            # If result is serialized RDF, parse directly
            g.parse(data=result, format="turtle")
        
        # Initialize SuRF
        # Register namespaces
        surf.namespace.register(epo=EPO_NS)
        
        # Create a SuRF store and session with our RDFLib graph
        store = surf.Store(reader="rdflib", writer="rdflib", rdflib_store=g)
        session = surf.Session(store)
        
        # Get the Tender class and load the resource
        TenderClass = session.get_class(surf.ns.EPO.Tender)
        tender_resource = session.get_resource(tender_uri, TenderClass)
        
        # Check if tender exists
        if not tender_resource:
            logger.error(f"Tender with ID {tender_id} not found")
            raise ValueError(f"Tender with ID {tender_id} not found")
        
        # Map SuRF resource to dictionary
        # Using SuRF's attribute access based on the EPO ontology
        tender_data = {
            "id": tender_id,
            "title": str(tender_resource.epo_title.first or ""),
            "description": str(tender_resource.epo_description.first or ""),
            "type": str(tender_resource.epo_procedureType.first or ""),
            "status": str(tender_resource.epo_status.first or ""),
            "organization": str(tender_resource.epo_contractingAuthority.first or ""),
            "budget": float(tender_resource.epo_estimatedValue.first) if hasattr(tender_resource, "epo_estimatedValue") and tender_resource.epo_estimatedValue.first else None,
            "publish_date": tender_resource.epo_publicationDate.first.toPython() if hasattr(tender_resource, "epo_publicationDate") and tender_resource.epo_publicationDate.first else datetime.now(),
            "close_date": tender_resource.epo_submissionDeadline.first.toPython() if hasattr(tender_resource, "epo_submissionDeadline") and tender_resource.epo_submissionDeadline.first else None,
            "source_url": str(tender_resource.epo_sourceUrl.first or ""),
            "location": str(tender_resource.epo_location.first or ""),
        }
        
        # Check if tender is saved by client
        is_saved = False
        if client_id:
            saved_tender = db.query(models.ClientTender).filter(
                models.ClientTender.client_id == client_id,
                models.ClientTender.tender_id == tender_id
            ).first()
            is_saved = saved_tender is not None
        
        # Add saved status to response
        tender_data["is_saved"] = is_saved
        
        # Create Pydantic model from the data
        return schemas.TenderResponse(**tender_data)
        
    except Exception as e:
        logger.error(f"Error retrieving tender {tender_id}: {str(e)}")
        raise

async def index_tender(tender_id: str) -> bool:
    """
    Index a tender in Meilisearch for full-text search.
    
    Args:
        tender_id: The ID of the tender to index
        
    Returns:
        bool: True if indexing was successful
    """
    try:
        # Get tender details
        neptune = get_neptune_client()
        
        # Create full URI if tender_id is not already a URI
        if not tender_id.startswith("http"):
            tender_uri = f"http://data.europa.eu/a4g/resource/tender/{tender_id}"
        else:
            tender_uri = tender_id
            
        # Extract ID from URI if necessary
        if tender_id.startswith("http"):
            tender_id = tender_id.split("/")[-1]
        
        # Get tender details using SPARQL
        sparql_query = f"""
        PREFIX epo: <{EPO_NS}>
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        
        SELECT ?title ?description ?type ?status ?organization ?location ?category
        WHERE {{
            <{tender_uri}> epo:title ?title .
            OPTIONAL {{ <{tender_uri}> epo:description ?description }}
            OPTIONAL {{ <{tender_uri}> epo:procedureType ?type }}
            OPTIONAL {{ <{tender_uri}> epo:status ?status }}
            OPTIONAL {{ <{tender_uri}> epo:contractingAuthority ?organization }}
            OPTIONAL {{ <{tender_uri}> epo:location ?location }}
            OPTIONAL {{ <{tender_uri}> epo:category ?category }}
        }}
        """
        
        # Execute SPARQL query
        result = neptune.execute_sparql_query(sparql_query)
        
        # Extract tender data
        if 'results' in result and 'bindings' in result['results'] and result['results']['bindings']:
            binding = result['results']['bindings'][0]
            
            # Prepare document for Meilisearch
            document = {
                "id": tender_id,
                "title": binding.get('title', {}).get('value', ''),
                "description": binding.get('description', {}).get('value', ''),
                "type": binding.get('type', {}).get('value', ''),
                "status": binding.get('status', {}).get('value', ''),
                "organization": binding.get('organization', {}).get('value', ''),
                "location": binding.get('location', {}).get('value', ''),
                "category": binding.get('category', {}).get('value', ''),
            }
            
            # Index in Meilisearch
            meilisearch = get_meilisearch_client()
            index = meilisearch.index(TENDERS_INDEX)
            
            # Add or update document
            result = index.add_documents([document])
            
            # Wait for indexing to complete
            update_id = result["updateId"]
            meilisearch.wait_for_task(update_id)
            
            return True
        else:
            logger.error(f"Tender with ID {tender_id} not found or has missing required data")
            return False
            
    except Exception as e:
        logger.error(f"Error indexing tender {tender_id}: {str(e)}")
        return False

def toggle_save_tender(db: Session, tender_id: str, client_id: int) -> Dict[str, Any]:
    """
    Toggle save/unsave a tender for the current client.
    Creates or removes a relationship in the ClientTender table.
    
    Args:
        db: SQL database session
        tender_id: The ID of the tender to save/unsave
        client_id: The ID of the client
        
    Returns:
        Dict: Response indicating the action taken
    """
    # Check if tender is already saved
    existing = db.query(models.ClientTender).filter(
        models.ClientTender.client_id == client_id,
        models.ClientTender.tender_id == tender_id
    ).first()
    
    if existing:
        # Unsave tender
        db.delete(existing)
        db.commit()
        return {"status": "unsaved", "tender_id": tender_id}
    else:
        # Save tender
        new_saved = models.ClientTender(
            client_id=client_id,
            tender_id=tender_id
        )
        db.add(new_saved)
        db.commit()
        db.refresh(new_saved)
        return {"status": "saved", "tender_id": tender_id}

async def get_saved_tenders(
    db: Session,
    client_id: int,
    page: int = 1,
    limit: int = 10,
    sort_by: str = "saved_at",
    sort_order: str = "desc"
) -> schemas.TenderListResponse:
    """
    Get a paginated list of tenders saved by the current client.
    
    Args:
        db: SQL database session
        client_id: The ID of the client
        page: Page number (1-indexed)
        limit: Number of items per page
        sort_by: Field to sort by
        sort_order: Sort direction (asc or desc)
        
    Returns:
        TenderListResponse: Paginated list of saved tenders
    """
    # Calculate offset
    offset = (page - 1) * limit
    
    # Get saved tender relationships with pagination
    query = db.query(models.ClientTender).filter(models.ClientTender.client_id == client_id)
    
    # Apply sorting
    if sort_by == "saved_at":
        if sort_order.lower() == "desc":
            query = query.order_by(models.ClientTender.saved_at.desc())
        else:
            query = query.order_by(models.ClientTender.saved_at)
    
    # Apply pagination
    saved_tenders = query.offset(offset).limit(limit).all()
    
    # Count total
    total_count = db.query(models.ClientTender).filter(models.ClientTender.client_id == client_id).count()
    
    # Get tender details for each saved tender
    tenders = []
    for saved in saved_tenders:
        try:
            tender = get_tender(db, saved.tender_id, client_id)
            tenders.append(tender)
        except Exception as e:
            logger.error(f"Error fetching saved tender {saved.tender_id}: {str(e)}")
            # Continue with next tender even if one fails
    
    # If sort_by is not saved_at, sort the Python list
    if sort_by != "saved_at" and tenders:
        reverse = sort_order.lower() == "desc"
        tenders.sort(key=lambda x: getattr(x, sort_by, None) or "", reverse=reverse)
    
    # Calculate pagination metadata
    total_pages = ceil(total_count / limit)
    has_next = page < total_pages
    has_prev = page > 1
    
    # Return paginated response
    return schemas.TenderListResponse(
        items=tenders,
        total=total_count,
        page=page,
        size=limit,
        total_pages=total_pages,
        has_next=has_next,
        has_prev=has_prev
    )

def update_ai_summary(db: Session, tender_id: str, content: str) -> schemas.SummaryResponse:
    """
    Update the AI-generated summary for a tender.
    Inserts or updates a record in the SummaryTender table.
    
    Args:
        db: SQL database session
        tender_id: The ID of the tender
        content: The summary content
        
    Returns:
        SummaryResponse: Updated summary
    """
    # Check if summary already exists
    existing = db.query(models.SummaryTender).filter(models.SummaryTender.tender_id == tender_id).first()
    
    if existing:
        # Update existing summary
        existing.summary_content = content
        existing.updated_at = datetime.now()
        db.commit()
        db.refresh(existing)
        return schemas.SummaryResponse.model_validate(existing)
    else:
        # Create new summary
        new_summary = models.SummaryTender(
            tender_id=tender_id,
            summary_content=content
        )
        db.add(new_summary)
        db.commit()
        db.refresh(new_summary)
        return schemas.SummaryResponse.model_validate(new_summary)

def get_tender_types() -> List[Dict[str, str]]:
    """
    Get a list of available tender types.
    
    Returns:
        List[Dict[str, str]]: List of tender types
    """
    # Get tender types from enum
    types = []
    for type_enum in models.TenderType:
        types.append({
            "id": type_enum.value,
            "name": type_enum.name.title().replace("_", " ")
        })
    return types
    
