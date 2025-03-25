import logging
from typing import Optional, Dict, Any, List
from datetime import datetime
from rdflib import Graph, Namespace, URIRef, BNode, Literal
from app.core.database import get_neptune_client, get_async_db
from app.modules.tenders import schemas
import json
import uuid
from sqlalchemy.exc import IntegrityError
from sqlalchemy import and_, select, text, func, cast, String
from app.modules.tenders.models import UserTender as UserTenderModel, TenderDocuments as TenderSummaryModel
from sqlalchemy.orm import Session

# Configure logging
logger = logging.getLogger(__name__)

# Define namespaces used in the RDF graph
NS = {
    'rdf': Namespace('http://www.w3.org/1999/02/22-rdf-syntax-ns#'),
    'rdfs': Namespace('http://www.w3.org/2000/01/rdf-schema#'),
    'dcterms': Namespace('http://purl.org/dc/terms/'),
    'epo': Namespace('http://data.europa.eu/a4g/ontology#'),
    'locn': Namespace('http://www.w3.org/ns/locn#'),
    'authority': Namespace('http://publications.europa.eu/ontology/authority/'),
    'adms': Namespace('http://www.w3.org/ns/adms#'),
    'm8g': Namespace('http://data.europa.eu/m8g/'),
    'skos': Namespace('http://www.w3.org/2004/02/skos/core#'),
    'xsd': Namespace('http://www.w3.org/2001/XMLSchema#')
}

async def get_tender_detail(tender_id: str) -> schemas.TenderDetail:
    """
    Fetch detailed information about a tender from the Neptune RDF graph.
    
    Args:
        tender_id: The URI or hash identifier of the tender to retrieve
        
    Returns:
        TenderDetail: The full tender details from the RDF graph
        
    Raises:
        ValueError: If the tender is not found
    """
    # Get Neptune client
    neptune_client = get_neptune_client()
    
    logger.info(f"Starting get_tender_detail for ID: {tender_id}")
    
    # Determine if the provided ID is a complete URI or just a hash/identifier
    if tender_id.startswith('http'):
        tender_uri = tender_id
    else:
        # Construct the URI from the hash (using the format from the example)
        tender_uri = f"http://gober.ai/spain/procedure/{tender_id}"
    
    logger.info(f"Using tender URI: {tender_uri}")
    
    # First, verify the tender exists with a simple query
    verify_query = f"""
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    ASK {{ <{tender_uri}> ?p ?o }}
    """
        
    try:
        # Check if tender exists
        verify_result = neptune_client.execute_sparql_query(verify_query)
        
        if not verify_result.get('boolean', False):
            logger.error(f"Tender not found in Neptune: {tender_uri}")            
            raise ValueError(f"Tender with URI {tender_uri} does not exist")
        
        # Now, fetch only the direct properties of the tender
        tender_query = f"""
        PREFIX dcterms: <http://purl.org/dc/terms/>
        PREFIX ns1: <http://data.europa.eu/a4g/ontology#>
        PREFIX ns2: <http://www.w3.org/ns/locn#>
        PREFIX ns3: <http://publications.europa.eu/ontology/authority/>
        PREFIX ns4: <http://www.w3.org/ns/adms#>
        PREFIX ns5: <http://data.europa.eu/m8g/>
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
        PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
        
        CONSTRUCT {{
            <{tender_uri}> ?p ?o .
            ?o ?p2 ?o2 .
            ?o2 ?p3 ?o3 .
        }}
        WHERE {{ 
        {{
            <{tender_uri}> ?p ?o .
        }}
        UNION {{
            <{tender_uri}> ?p ?intermediate .
            ?intermediate ?p2 ?o2 .
            BIND(?intermediate AS ?o)
        }}
        UNION {{
            <{tender_uri}> ?p ?intermediate .
            ?intermediate ?p2 ?o2 .
            ?o2 ?p3 ?o3 .
            BIND(?o2 AS ?o)
        }}
        }}
        """
                
        # Execute the basic query
        logger.info(f"Executing CONSTRUCT query for tender {tender_id}")
        basic_result = neptune_client.execute_sparql_query(tender_query)
        
        logger.info(f"CONSTRUCT result type: {type(basic_result)}")
        
        # Parse into a graph
        g = Graph()
        try:
            # Handle when basic_result is a dict (single JSON-LD object)
            if isinstance(basic_result, dict):
                g.parse(data=json.dumps(basic_result), format="json-ld")
            # Handle when basic_result is a list (array of JSON-LD objects)
            elif isinstance(basic_result, list):
                g.parse(data=json.dumps(basic_result), format="json-ld")
            # Handle raw string data (e.g., Turtle format)
            else:
                g.parse(data=basic_result, format="turtle")
            
            logger.info(f"Graph loaded successfully with {len(g)} triples")
            if len(g) == 0:
                logger.warning(f"Graph has 0 triples for tender {tender_uri}")
        except Exception as e:
            logger.error(f"Error parsing graph data: {str(e)}")
            raise ValueError(f"Failed to parse data from Neptune: {str(e)}")
                
        # Parse the combined graph into a TenderDetail object
        tender = parse_tender_from_graph(g, URIRef(tender_uri))
        
        logger.info(f"Tender successfully parsed")
        
        # Check if a summary exists for this tender URI
        try:
            async with get_async_db() as session:
                # Debug: Log the exact value and type being used in the query
                logger.info(f"Querying for summary with tender_uri: {tender_uri} (type: {type(tender_uri)})")
                
                # Use a text-based comparison instead of a direct equality check
                # This avoids SQL Server's type inference issues
                stmt = (
                    select(TenderSummaryModel)
                    .where(
                        # Use cast or func.varchar to ensure string comparison
                        func.trim(cast(TenderSummaryModel.tender_uri, String)) == 
                        func.trim(cast(text("'" + str(tender_uri) + "'"), String))
                    )
                )
                
                logger.info(f"Executing query: {str(stmt)}")
                result = await session.execute(stmt)
                tender_summary = result.scalar_one_or_none()
                
                # If a summary exists, add it to the tender details
                if tender_summary:
                    logger.info(f"Found summary for tender: {tender_uri}")
                    tender.summary = tender_summary.summary
                else:
                    logger.info(f"No summary found for tender: {tender_uri}")
        except Exception as e:
            # This catches database errors without failing the entire request
            logger.error(f"Error retrieving tender summary: {str(e)}")
            logger.error(f"Details: {type(e).__name__}, {e.args}")
            # Continue without the summary
        
        return tender
        
    except Exception as e:
        logger.error(f"Error retrieving tender {tender_id}: {str(e)}")
        raise

def parse_tender_from_graph(g: Graph, tender_uri: URIRef) -> schemas.TenderDetail:
    """
    Parse the RDF graph into a TenderDetail Pydantic object
    
    Args:
        g: RDFLib graph containing tender data
        tender_uri: URI of the tender to parse
        
    Returns:
        TenderDetail: Structured tender data
    """
    # Extract tender ID from URI
    tender_id = str(tender_uri).split('/')[-1] if isinstance(tender_uri, str) else str(tender_uri).split('/')[-1]
    
    # Define direct URI strings for common predicates to match the JSON-LD structure
    DCTERMS_TITLE = URIRef("http://purl.org/dc/terms/title")
    DCTERMS_DESC = URIRef("http://purl.org/dc/terms/description")
    
    # Basic tender information - try both namespace approach and direct URIs
    title = get_literal_value(g, URIRef(tender_uri), DCTERMS_TITLE) or get_literal_value(g, URIRef(tender_uri), NS['dcterms'].title)
    
    description = get_literal_value(g, URIRef(tender_uri), DCTERMS_DESC) or get_literal_value(g, URIRef(tender_uri), NS['dcterms'].description)
    additional_info = get_literal_value(g, URIRef(tender_uri), NS['epo'].hasAdditionalInformation)
    
    # Get identifier - check various patterns
    identifier = None
    adms_identifier = URIRef("http://www.w3.org/ns/adms#identifier")
    for id_node in g.objects(URIRef(tender_uri), adms_identifier):
        # Try both namespaced and direct URI approach
        notation = get_literal_value(g, id_node, NS['skos'].notation) or get_literal_value(g, id_node, URIRef("http://www.w3.org/2004/02/skos/core#notation"))
        if notation:
            identifier = schemas.Identifier(notation=notation)
    
    # Get monetary values - more robust approach
    estimated_value = None
    net_value = None
    gross_value = None
    
    # Direct URI for hasEstimatedValue
    has_estimated_value = URIRef("http://data.europa.eu/a4g/ontology#hasEstimatedValue")
    has_amount_value = URIRef("http://data.europa.eu/a4g/ontology#hasAmountValue")
    currency_uri = URIRef("http://publications.europa.eu/ontology/authority/currency")
    
    for value_node in g.objects(URIRef(tender_uri), has_estimated_value):
        value_type = str(value_node).split('/')[-1]
        amount = get_literal_value(g, value_node, has_amount_value) or get_literal_value(g, value_node, NS['epo'].hasAmountValue)
        currency = get_literal_value(g, value_node, currency_uri) or get_literal_value(g, value_node, NS['authority'].currency)
                
        if amount and currency:
            monetary_value = schemas.MonetaryValue(amount=float(amount), currency=currency)
            
            if 'estimated-overall-contract-amount' in value_type:
                estimated_value = monetary_value
            elif 'net-value' in value_type:
                net_value = monetary_value
            elif 'gross-value' in value_type:
                gross_value = monetary_value
    
    # Get buyer organization - more robust approach
    buyer = None
    involves_buyer = URIRef("http://data.europa.eu/a4g/ontology#involvesBuyer")
    has_legal_name = URIRef("http://data.europa.eu/a4g/ontology#hasLegalName")
    has_buyer_profile = URIRef("http://data.europa.eu/a4g/ontology#hasBuyerProfile")
    has_tax_identifier = URIRef("http://data.europa.eu/a4g/ontology#hasTaxIdentifier")
    has_legal_identifier = URIRef("http://data.europa.eu/a4g/ontology#hasLegalIdentifier")
    locn_address = URIRef("http://www.w3.org/ns/locn#address")
    
    for org_uri in g.objects(URIRef(tender_uri), involves_buyer):
        if not isinstance(org_uri, URIRef):
            continue
            
        legal_name = get_literal_value(g, org_uri, has_legal_name) or get_literal_value(g, org_uri, NS['epo'].hasLegalName)
        buyer_profile = get_literal_value(g, org_uri, has_buyer_profile) or get_literal_value(g, org_uri, NS['epo'].hasBuyerProfile)
        
        # Get tax identifier
        tax_id = None
        for tax_id_node in g.objects(org_uri, has_tax_identifier):
            tax_notation = get_literal_value(g, tax_id_node, NS['skos'].notation) or get_literal_value(g, tax_id_node, URIRef("http://www.w3.org/2004/02/skos/core#notation"))
            if tax_notation:
                tax_id = schemas.Identifier(notation=tax_notation)
        
        # Get legal identifier
        legal_id = None
        for legal_id_node in g.objects(org_uri, has_legal_identifier):
            legal_notation = get_literal_value(g, legal_id_node, NS['skos'].notation) or get_literal_value(g, legal_id_node, URIRef("http://www.w3.org/2004/02/skos/core#notation"))
            if legal_notation:
                legal_id = schemas.Identifier(notation=legal_notation)
        
        # Get address
        address = None
        for addr_uri in g.objects(org_uri, locn_address):
            
            country_code = get_literal_value(g, addr_uri, NS['epo'].hasCountryCode)
            nuts_code = get_literal_value(g, addr_uri, NS['epo'].hasNutsCode)
            address_area = get_literal_value(g, addr_uri, NS['locn'].addressArea)
            admin_unit = get_literal_value(g, addr_uri, NS['locn'].adminUnitL1)
            post_code = get_literal_value(g, addr_uri, NS['locn'].postCode)
            post_name = get_literal_value(g, addr_uri, NS['locn'].postName)
            thoroughfare = get_literal_value(g, addr_uri, NS['locn'].thoroughfare)
            
            address = schemas.Address(
                country_code=country_code,
                nuts_code=nuts_code,
                address_area=address_area,
                admin_unit=admin_unit,
                post_code=post_code,
                post_name=post_name,
                thoroughfare=thoroughfare
            )
        
        # Get contact point
        contact_point = None
        has_primary_contact_point = URIRef("http://data.europa.eu/m8g/hasPrimaryContactPoint")
        for cp_uri in g.objects(org_uri, has_primary_contact_point):
            contact_point = schemas.ContactPoint()
        
        if legal_name:
            buyer = schemas.Organization(
                id=str(org_uri),
                legal_name=legal_name,
                tax_identifier=tax_id,
                legal_identifier=legal_id,
                buyer_profile=buyer_profile,
                address=address,
                contact_point=contact_point
            )
    
    # Get procurement documents
    procurement_documents = []
    is_subject_to = URIRef("http://data.europa.eu/a4g/ontology#isSubjectToProcedureSpecificTerm")
    involves_proc_doc = URIRef("http://data.europa.eu/a4g/ontology#involvesProcurementDocument")
    
    for term_uri in g.objects(URIRef(tender_uri), is_subject_to):
        for doc_uri in g.objects(term_uri, involves_proc_doc):
            title = get_literal_value(g, doc_uri, DCTERMS_TITLE) or get_literal_value(g, doc_uri, NS['dcterms'].title)
            access_url = get_literal_value(g, doc_uri, NS['epo'].hasAccessURL)
            
            # Determine document type
            doc_type = "generic"
            for doc_class in g.objects(doc_uri, NS['rdf'].type):
                doc_class_str = str(doc_class)
                if "TechnicalSpecification" in doc_class_str:
                    doc_type = "technical"
                elif "ProcurementDocument" in doc_class_str:
                    doc_type = "procurement"
            
            if title:
                procurement_documents.append(schemas.ProcurementDocument(
                    id=str(doc_uri),
                    title=title,
                    document_type=doc_type,
                    access_url=access_url
                ))
    
    # Get submission term
    submission_deadline = None
    submission_languages = []
    has_receipt_deadline = URIRef("http://data.europa.eu/a4g/ontology#hasReceiptDeadline")
    has_language = URIRef("http://data.europa.eu/a4g/ontology#hasLanguage")
    
    for term_uri in g.objects(URIRef(tender_uri), is_subject_to):

        for term_type in g.objects(term_uri, NS['rdf'].type):
            if str(term_type) == str(NS['epo'].SubmissionTerm) or "SubmissionTerm" in str(term_type):
                deadline = get_literal_value(g, term_uri, has_receipt_deadline)
                if deadline:
                    submission_deadline = datetime.fromisoformat(deadline.replace('Z', '+00:00'))
                
                for lang_uri in g.objects(term_uri, has_language):
                    submission_languages.append(str(lang_uri))
    
    # Get purpose and classification
    purpose = None
    main_classifications = []
    has_purpose = URIRef("http://data.europa.eu/a4g/ontology#hasPurpose")
    has_main_classification = URIRef("http://data.europa.eu/a4g/ontology#hasMainClassification")
    
    for purpose_uri in g.objects(URIRef(tender_uri), has_purpose):
        for cpv_uri in g.objects(purpose_uri, has_main_classification):
            main_classifications.append(str(cpv_uri))
        
        if main_classifications:
            purpose = schemas.Purpose(main_classifications=main_classifications)
    
    # Get contract term
    contract_term = None
    foresees_contract_term = URIRef("http://data.europa.eu/a4g/ontology#foreseesContractSpecificTerm")
    has_contract_nature = URIRef("http://data.europa.eu/a4g/ontology#hasContractNatureType")
    has_additional_nature = URIRef("http://data.europa.eu/a4g/ontology#hasAdditionalContractNature")
    defines_place = URIRef("http://data.europa.eu/a4g/ontology#definesSpecificPlaceOfPerformance")
    has_country_code = URIRef("http://data.europa.eu/a4g/ontology#hasCountryCode")
    has_nuts_code = URIRef("http://data.europa.eu/a4g/ontology#hasNutsCode")
    geo_name = URIRef("http://www.w3.org/ns/locn#geographicName")
    
    for ct_uri in g.objects(URIRef(tender_uri), foresees_contract_term):
        if not isinstance(ct_uri, URIRef):
            # Skip class definitions and other non-URI objects
            if str(ct_uri) == "http://data.europa.eu/a4g/ontology#ContractTerm":
                continue
        
        contract_nature_type_uri = None
        for nature_uri in g.objects(ct_uri, has_contract_nature):
            contract_nature_type_uri = str(nature_uri)
        
        additional_nature = get_literal_value(g, ct_uri, has_additional_nature)
        
        # Get place of performance
        place_of_performance = None
        for loc_uri in g.objects(ct_uri, defines_place):
            country_code = get_literal_value(g, loc_uri, has_country_code)
            nuts_code = get_literal_value(g, loc_uri, has_nuts_code)
            geographic_name = get_literal_value(g, loc_uri, geo_name)
            
            # Get address
            address = None
            for addr_uri in g.objects(loc_uri, locn_address):
                address = schemas.Address(
                    country_code=get_literal_value(g, addr_uri, has_country_code),
                    nuts_code=get_literal_value(g, addr_uri, has_nuts_code),
                    address_area=get_literal_value(g, addr_uri, NS['locn'].addressArea),
                    admin_unit=get_literal_value(g, addr_uri, NS['locn'].adminUnitL1)
                )
            
            place_of_performance = schemas.Location(
                country_code=country_code,
                nuts_code=nuts_code,
                geographic_name=geographic_name,
                address=address
            )
        
        if contract_nature_type_uri:
            contract_term = schemas.ContractTerm(
                contract_nature_type=contract_nature_type_uri.split('/')[-1],
                additional_contract_nature=additional_nature,
                place_of_performance=place_of_performance
            )
    
    # Get lots
    lots = []
    has_lot = URIRef("http://data.europa.eu/a4g/ontology#hasProcurementScopeDividedIntoLot")
    
    for lot_uri in g.objects(URIRef(tender_uri), has_lot):
        if not isinstance(lot_uri, URIRef) or str(lot_uri) == "http://data.europa.eu/a4g/ontology#Lot":
            continue
        
        lot_id = str(lot_uri).split('/')[-1]
        lots.append(schemas.Lot(id=lot_id))
    
    # Construct the tender detail object
    tender_detail = schemas.TenderDetail(
        id=tender_id,
        uri=str(tender_uri),
        identifier=identifier,
        title=title or "Untitled Tender",
        description=description,
        estimated_value=estimated_value,
        net_value=net_value,
        gross_value=gross_value,
        submission_deadline=submission_deadline,
        buyer=buyer,
        place_of_performance=contract_term.place_of_performance if contract_term else None,
        purpose=purpose,
        contract_term=contract_term,
        submission_term=schemas.SubmissionTerm(
            receipt_deadline=submission_deadline,
            languages=submission_languages
        ) if submission_deadline or submission_languages else None,
        additional_information=additional_info,
        procurement_documents=procurement_documents,
        lots=lots
    )
    
    return tender_detail

def get_literal_value(g: Graph, subject: URIRef, predicate) -> Optional[str]:
    """Helper function to get a literal value from the graph"""
    if not subject or not predicate:
        return None
    
    for obj in g.objects(subject, predicate):
        if isinstance(obj, Literal):
            return str(obj)
        # Handle JSON-LD structure where value might be in @value field
        elif isinstance(obj, BNode):
            # Check if this blank node has a value property
            for s, p, o in g.triples((obj, None, None)):
                if str(p) == 'http://www.w3.org/1999/02/22-rdf-syntax-ns#value' or str(p).endswith('#value'):
                    return str(o)
    return None

def save_tender_for_user(db: Session, tender_data: schemas.UserTenderCreate):
    """
    Save a tender for a user.
    
    Args:
        tender_data: UserTenderCreate with user_id, tender_uri and situation
        
    Returns:
        UserTender: The created user-tender association
    """
    logger.debug(f"Saving tender {tender_data.tender_uri} for user {tender_data.user_id}")
    
    try:
        # First check if this tender is already saved by this user
        existing = db.query(UserTenderModel).filter(
            UserTenderModel.user_id == tender_data.user_id,
            UserTenderModel.tender_uri == tender_data.tender_uri
        ).first()
        
        if existing:
            logger.info(f"Tender {tender_data.tender_uri} already saved by user {tender_data.user_id}")
            
            # Update the situation if needed
            if tender_data.situation and existing.situation != tender_data.situation:
                existing.situation = tender_data.situation
                existing.updated_at = datetime.now()
                db.commit()
                db.refresh(existing)
            
            # Return the existing record
            return schemas.UserTender(
                id=existing.id,
                user_id=existing.user_id,
                tender_uri=existing.tender_uri,
                created_at=existing.created_at,
                updated_at=existing.updated_at,
                situation=existing.situation
            )
        
        # Create a new UserTender record if it doesn't exist
        user_tender = UserTenderModel(
            id=str(uuid.uuid4()),
            user_id=tender_data.user_id,
            tender_uri=tender_data.tender_uri,
            situation=tender_data.situation
        )
        
        # Add debug logging
        logger.debug(f"DEBUG: UserTender object: {user_tender.id}")
        logger.debug(f"DEBUG: UserTender object: {user_tender.user_id}")
        logger.debug(f"DEBUG: UserTender object: {user_tender.tender_uri}")
        logger.debug(f"DEBUG: UserTender object: {user_tender.situation}")
        
        # Save to database
        db.add(user_tender)
        db.commit()
        db.refresh(user_tender)
        
        # Return the schema
        return schemas.UserTender(
            id=user_tender.id,
            user_id=user_tender.user_id,
            tender_uri=user_tender.tender_uri,
            created_at=user_tender.created_at,
            updated_at=user_tender.updated_at,
            situation=user_tender.situation
        )
        
    except IntegrityError as e:
        # Just in case there's a race condition where another request saved it
        # between our check and our insert
        db.rollback()
        logger.warning(f"IntegrityError while saving tender: {str(e)}")
        
        # Try to get the existing record that caused the conflict
        existing = db.query(UserTenderModel).filter(
            UserTenderModel.user_id == tender_data.user_id,
            UserTenderModel.tender_uri == tender_data.tender_uri
        ).first()
        
        if existing:
            return schemas.UserTender(
                id=existing.id,
                user_id=existing.user_id,
                tender_uri=existing.tender_uri,
                created_at=existing.created_at,
                updated_at=existing.updated_at,
                situation=existing.situation
            )
        
        # If we can't find the existing record, re-raise the exception
        raise ValueError(f"Could not save tender: {str(e)}")
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error saving tender: {str(e)}")
        raise ValueError(f"Failed to save tender: {str(e)}")

def unsave_tender_for_user(db: Session, user_id: str, tender_uri: str) -> bool:
    """
    Remove a saved tender for a user.
    
    Args:
        user_id: The ID of the user
        tender_uri: The URI of the tender to unsave
        
    Returns:
        bool: True if the tender was unsaved, False if it wasn't saved
    """
    logger.debug(f"Unsaving tender {tender_uri} for user {user_id}")
    
    try:
        # Find the tender record
        user_tender = db.query(UserTenderModel).filter(
            UserTenderModel.user_id == user_id,
            UserTenderModel.tender_uri == tender_uri
        ).first()
        
        if not user_tender:
            logger.warning(f"Tender {tender_uri} is not saved for user {user_id}")
            return False
        
        # Store ID for logging
        tender_id = user_tender.id
        
        # Delete the record
        db.delete(user_tender)
        db.commit()
        
        logger.info(f"Successfully deleted tender {tender_id} for user {user_id}")
        return True
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error unsaving tender: {str(e)}")
        raise ValueError(f"Failed to unsave tender: {str(e)}")

def get_user_saved_tenders(db: Session, user_id: str) -> List[schemas.UserTender]:
    """
    Get all tenders saved by a user.
    
    Args:
        user_id: The ID of the user
        
    Returns:
        List[UserTender]: List of saved tenders for the user
    """
    logger.debug(f"Getting saved tenders for user {user_id}")
    
    user_tenders = db.query(UserTenderModel).filter(
        UserTenderModel.user_id == user_id
    ).all()
    
    return [
        schemas.UserTender(
            id=ut.id,
            user_id=ut.user_id,
            tender_uri=ut.tender_uri,
            created_at=ut.created_at,
            updated_at=ut.updated_at,
            situation=ut.situation
        ) for ut in user_tenders
    ]

async def create_or_update_tender_summary(tender_uri: str, summary: str) -> schemas.TenderSummary:
    """
    Create or update a summary for a tender.
    
    Args:
        tender_uri: The URI of the tender
        summary: The summary text
        
    Returns:
        TenderSummary: The created or updated tender summary
    """
    logger.debug(f"Creating or updating summary for tender: {tender_uri}")
    
    async with get_async_db() as session:
        # Check if a summary already exists
        stmt = (
            select(TenderSummaryModel)
            .where(TenderSummaryModel.tender_uri == tender_uri)
        )
        result = await session.execute(stmt)
        existing_summary = result.scalar_one_or_none()
        
        if existing_summary:
            # Update existing summary
            logger.debug(f"Updating existing summary for tender: {tender_uri}")
            existing_summary.summary = summary
            existing_summary.updated_at = datetime.now()
            await session.commit()
            await session.refresh(existing_summary)
            
            return schemas.TenderSummary(
                id=existing_summary.id,
                tender_uri=existing_summary.tender_uri,
                summary=existing_summary.summary,
                created_at=existing_summary.created_at,
                updated_at=existing_summary.updated_at
            )
        else:
            # Create new summary
            logger.debug(f"Creating new summary for tender: {tender_uri}")
            new_summary = TenderSummaryModel(
                id=str(uuid.uuid4()),
                tender_uri=tender_uri,
                summary=summary
            )
            session.add(new_summary)
            await session.commit()
            await session.refresh(new_summary)
            
            return schemas.TenderSummary(
                id=new_summary.id,
                tender_uri=new_summary.tender_uri,
                summary=new_summary.summary,
                created_at=new_summary.created_at,
                updated_at=new_summary.updated_at
            )

def parse_sparql_binding_to_tender_preview(binding: Dict[str, Any]) -> schemas.TenderPreview:
    """
    Parse a single SPARQL query binding into a TenderPreview object.
    
    Args:
        binding: A dictionary containing the SPARQL binding for a tender
        
    Returns:
        TenderPreview: The parsed tender preview object
    """
    # Extract the tender hash from the procedure URI
    tender_uri = binding.get('procedure', {}).get('value', '')
    tender_hash = tender_uri.split('/')[-1] if tender_uri else ''
    
    # Extract tender ID
    tender_id = binding.get('id', {}).get('value', '')
    
    # Parse title
    title = binding.get('title', {}).get('value', 'Untitled Tender')
    
    # Parse submission date
    submission_date = None
    if 'submissionDate' in binding and binding['submissionDate'].get('value'):
        try:
            date_str = binding['submissionDate']['value']
            submission_date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        except (ValueError, TypeError) as e:
            logger.warning(f"Error parsing submission date: {e}")
    
    # Parse lot count
    n_lots = 0
    if 'lotCount' in binding and binding['lotCount'].get('value'):
        try:
            n_lots = int(binding['lotCount']['value'])
        except (ValueError, TypeError):
            pass
    
    # Parse organization name
    pub_org_name = binding.get('orgName', {}).get('value')
    
    # Parse budget
    budget = None
    if 'baseBudgetAmount' in binding and 'baseBudgetCurrency' in binding:
        try:
            amount = float(binding['baseBudgetAmount']['value'])
            currency = binding['baseBudgetCurrency']['value']
            budget = schemas.MonetaryValue(amount=amount, currency=currency)
        except (ValueError, KeyError, TypeError):
            pass
    
    # Parse location
    location = binding.get('locationName', {}).get('value')
    
    # Parse contract type - extract the last part of the URI
    contract_type = None
    if 'contractType' in binding and binding['contractType'].get('value'):
        contract_type_uri = binding['contractType']['value']
        contract_type = contract_type_uri.split('/')[-1] if contract_type_uri else None
    
    # Parse CPV codes
    cpv_categories = []
    if 'classifications' in binding and binding['classifications'].get('value'):
        raw_classifications = binding['classifications']['value']
        # Split by commas and extract the CPV code from each URI
        for raw_cpv in raw_classifications.split(', '):
            # Try to extract the CPV code from the URI
            if raw_cpv:
                try:
                    cpv_code = raw_cpv.split('/')[-1]
                    cpv_categories.append(cpv_code)
                except:
                    # If extraction fails, use the raw value
                    cpv_categories.append(raw_cpv)
    
    # Parse description
    description = binding.get('description', {}).get('value')
    
    # Create and return the tender preview
    return schemas.TenderPreview(
        tender_hash=tender_hash,
        tender_id=tender_id,
        title=title,
        description=description,
        submission_date=submission_date,
        n_lots=n_lots,
        pub_org_name=pub_org_name,
        budget=budget,
        location=location,
        contract_type=contract_type,
        cpv_categories=cpv_categories
    )

async def get_tenders_paginated(page: int = 1, size: int = 10) -> schemas.PaginatedTenderResponse:
    """
    Fetch a paginated list of tenders from the Neptune RDF database.
    
    Args:
        page: The page number (1-based)
        size: The number of items per page
        
    Returns:
        PaginatedTenderResponse: A paginated list of tender previews
    """
    logger.info(f"Fetching tenders page {page} with size {size}")
    
    # Get Neptune client
    neptune_client = get_neptune_client()
    
    # Calculate offset
    offset = (page - 1) * size
    
    # Define the SPARQL query to get tenders with pagination and sorting by submission deadline
    # This query retrieves tender previews with all the fields we need for the listing
    query = f"""
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
    WHERE {{
    ?procedure a ns1:Procedure .
    
    # Id del expediente (identifier)
    OPTIONAL {{ 
        ?procedure ns4:identifier ?identifier .
        ?identifier skos:notation ?id .
    }}
    
    # Título y descripción
    OPTIONAL {{ ?procedure dcterms:title ?title . }}
    OPTIONAL {{ ?procedure dcterms:description ?description . }}
    
    # Fecha de sumisión: desde isSubjectToProcedureSpecificTerm con SubmissionTerm
    OPTIONAL {{ 
        ?procedure ns1:isSubjectToProcedureSpecificTerm ?submissionTerm .
        ?submissionTerm a ns1:SubmissionTerm ;
                        ns1:hasReceiptDeadline ?submissionDate .
    }}
    
    # Número de lotes
    OPTIONAL {{ 
        ?procedure ns1:hasProcurementScopeDividedIntoLot ?lot .
    }}
    
    # Nombre de la organización: a través de involvesBuyer y PublicOrganisation
    OPTIONAL {{ 
        ?procedure ns1:involvesBuyer ?buyer .
        ?buyer a ns5:PublicOrganisation ;
            ns1:hasLegalName ?orgName .
    }}
    
    # Presupuesto base: mediante hasEstimatedValue, filtrando el IRI que termina en "estimated-overall-contract-amount"
    OPTIONAL {{ 
        ?procedure ns1:hasEstimatedValue ?monetaryValue .
        FILTER(STRENDS(STR(?monetaryValue), "estimated-overall-contract-amount"))
        ?monetaryValue ns1:hasAmountValue ?baseBudgetAmount ;
                    ns3:currency ?baseBudgetCurrency .
    }}
    
    # Ubicación y tipo de contrato: desde foreseesContractSpecificTerm y ContractTerm
    OPTIONAL {{ 
        ?procedure ns1:foreseesContractSpecificTerm ?contractTerm .
        ?contractTerm ns1:definesSpecificPlaceOfPerformance ?location ;
                    ns1:hasContractNatureType ?contractType .
        ?location a dcterms:Location ;
                ns2:geographicName ?locationName .
    }}
    
    # Categorías/CPVs: desde hasPurpose y hasMainClassification (puede haber varias)
    OPTIONAL {{ 
        ?procedure ns1:hasPurpose ?purpose .
        ?purpose ns1:hasMainClassification ?classification .
    }}
    }}
    GROUP BY ?procedure ?id ?title ?description ?submissionDate ?orgName ?baseBudgetAmount ?baseBudgetCurrency ?locationName ?contractType
    ORDER BY DESC(?submissionDate)
    LIMIT {size}
    OFFSET {offset}
    """
    
    # Query to get the total count
    count_query = """
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    PREFIX epo: <http://data.europa.eu/a4g/ontology#>
    
    SELECT (COUNT(DISTINCT ?procedure) AS ?total)
    WHERE {
      ?procedure rdf:type epo:ProcurementProject .
    }
    """
    
    try:
        # Execute the main query
        results = neptune_client.execute_sparql_query(query)
        
        if not results or 'results' not in results or 'bindings' not in results['results']:
            logger.warning("No results found or unexpected response format")
            return schemas.PaginatedTenderResponse(
                items=[],
                total=0,
                page=page,
                size=size,
                has_next=False,
                has_prev=(page > 1)
            )
        
        # Parse the results into TenderPreview objects
        tenders = []
        for binding in results['results']['bindings']:
            try:
                tender = parse_sparql_binding_to_tender_preview(binding)
                tenders.append(tender)
            except Exception as e:
                logger.error(f"Error parsing tender from binding: {str(e)}")
                # Continue with the next tender instead of failing the whole request
                continue
        
        # Execute the count query for pagination
        count_result = neptune_client.execute_sparql_query(count_query)
        total_count = 0
        
        if count_result and 'results' in count_result and 'bindings' in count_result['results']:
            try:
                total_count = int(count_result['results']['bindings'][0]['total']['value'])
            except (KeyError, ValueError, IndexError):
                logger.warning("Could not parse total count from query result")
        
        # Calculate pagination information
        has_next = (page * size) < total_count
        has_prev = page > 1
        
        return schemas.PaginatedTenderResponse(
            items=tenders,
            total=total_count,
            page=page,
            size=size,
            has_next=has_next,
            has_prev=has_prev
        )
        
    except Exception as e:
        logger.error(f"Error fetching paginated tenders: {str(e)}")
        raise

async def get_tender_preview(tender_id: str) -> schemas.TenderPreview:
    """
    Fetch a preview of a specific tender from the Neptune RDF database.
    
    Args:
        tender_id: The URI or hash identifier of the tender to retrieve
        
    Returns:
        TenderPreview: A preview of the tender with basic information
        
    Raises:
        ValueError: If the tender is not found
    """
    logger.info(f"Fetching tender preview for ID: {tender_id}")
    
    # Get Neptune client
    neptune_client = get_neptune_client()
    
    # Determine if the provided ID is a complete URI or just a hash/identifier
    if tender_id.startswith('http'):
        tender_uri = tender_id
    else:
        # Construct the URI from the hash
        tender_uri = f"http://gober.ai/spain/procedure/{tender_id}"
    
    logger.info(f"Using tender URI: {tender_uri}")
    
    # Define the SPARQL query to get the tender preview
    # This is the same query as get_tenders_paginated but filtered for a specific procedure
    query = f"""
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
    WHERE {{
    # Filter for the specific procedure
    BIND(<{tender_uri}> as ?procedure)
    ?procedure a ns1:Procedure .
    
    # Id del expediente (identifier)
    OPTIONAL {{ 
        ?procedure ns4:identifier ?identifier .
        ?identifier skos:notation ?id .
    }}
    
    # Título y descripción
    OPTIONAL {{ ?procedure dcterms:title ?title . }}
    OPTIONAL {{ ?procedure dcterms:description ?description . }}
    
    # Fecha de sumisión: desde isSubjectToProcedureSpecificTerm con SubmissionTerm
    OPTIONAL {{ 
        ?procedure ns1:isSubjectToProcedureSpecificTerm ?submissionTerm .
        ?submissionTerm a ns1:SubmissionTerm ;
                        ns1:hasReceiptDeadline ?submissionDate .
    }}
    
    # Número de lotes
    OPTIONAL {{ 
        ?procedure ns1:hasProcurementScopeDividedIntoLot ?lot .
    }}
    
    # Nombre de la organización: a través de involvesBuyer y PublicOrganisation
    OPTIONAL {{ 
        ?procedure ns1:involvesBuyer ?buyer .
        ?buyer a ns5:PublicOrganisation ;
            ns1:hasLegalName ?orgName .
    }}
    
    # Presupuesto base: mediante hasEstimatedValue, filtrando el IRI que termina en "estimated-overall-contract-amount"
    OPTIONAL {{ 
        ?procedure ns1:hasEstimatedValue ?monetaryValue .
        FILTER(STRENDS(STR(?monetaryValue), "estimated-overall-contract-amount"))
        ?monetaryValue ns1:hasAmountValue ?baseBudgetAmount ;
                    ns3:currency ?baseBudgetCurrency .
    }}
    
    # Ubicación y tipo de contrato: desde foreseesContractSpecificTerm y ContractTerm
    OPTIONAL {{ 
        ?procedure ns1:foreseesContractSpecificTerm ?contractTerm .
        ?contractTerm ns1:definesSpecificPlaceOfPerformance ?location ;
                    ns1:hasContractNatureType ?contractType .
        ?location a dcterms:Location ;
                ns2:geographicName ?locationName .
    }}
    
    # Categorías/CPVs: desde hasPurpose y hasMainClassification (puede haber varias)
    OPTIONAL {{ 
        ?procedure ns1:hasPurpose ?purpose .
        ?purpose ns1:hasMainClassification ?classification .
    }}
    }}
    GROUP BY ?procedure ?id ?title ?description ?submissionDate ?orgName ?baseBudgetAmount ?baseBudgetCurrency ?locationName ?contractType
    """
    
    try:
        # Execute the query
        results = neptune_client.execute_sparql_query(query)
        
        if not results or 'results' not in results or 'bindings' not in results['results'] or len(results['results']['bindings']) == 0:
            logger.warning(f"Tender not found: {tender_uri}")
            raise ValueError(f"Tender with ID {tender_id} not found")
        
        # Parse the result into a TenderPreview object
        binding = results['results']['bindings'][0]
        tender_preview = parse_sparql_binding_to_tender_preview(binding)
        
        # Add description field which we're now including
        if 'description' in binding and binding['description'].get('value'):
            tender_preview.description = binding['description']['value']
        
        return tender_preview
        
    except Exception as e:
        logger.error(f"Error retrieving tender preview for {tender_id}: {str(e)}")
        raise

def get_tender_summary(tender_id: str, db: Session):
    """
    Fetch the summary for a tender from the database.
    
    Args:
        tender_id: The URI or hash identifier of the tender
        db: SQLAlchemy database session
        
    Returns:
        TenderSummary: The tender summary if found
        
    Raises:
        ValueError: If the tender summary is not found
    """
    logger.debug(f"Fetching summary for tender ID: {tender_id}")
    
    # Determine if the provided ID is a complete URI or just a hash/identifier
    if tender_id.startswith('http'):
        tender_uri = tender_id
    else:
        # Construct the URI from the hash
        tender_uri = f"http://gober.ai/spain/procedure/{tender_id}"
    
    try:
        # Query for the summary using SQLAlchemy ORM
        tender_summary = db.query(TenderSummaryModel).filter(
            TenderSummaryModel.tender_uri == tender_uri
        ).first()
        
        if tender_summary:
            return schemas.TenderSummary(
                id=tender_summary.id,
                tender_uri=tender_summary.tender_uri,
                summary=tender_summary.summary,
                url_document=tender_summary.url_document,
                created_at=tender_summary.created_at,
                updated_at=tender_summary.updated_at
            )
        else:
            raise ValueError(f"Summary not found for tender with ID: {tender_id}")
    except Exception as e:
        logger.error(f"Error retrieving tender summary: {str(e)}")
        raise
