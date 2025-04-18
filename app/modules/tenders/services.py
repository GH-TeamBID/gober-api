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
from app.modules.tenders.models import UserTender as UserTenderModel, TenderDocuments as TenderDocumentsModel
from sqlalchemy.orm import Session
from app.core.database import engine
from app.core.utils.azure_blob_client import AzureBlobStorageClient
from app.modules.tenders.queries_tender_detail import query_core_template, query_identifier, query_contracting_entity, query_monetary_values, query_contractual_terms_and_location, query_cpvs, query_submission_terms, query_legal_documents, query_technical_documents, query_additional_documents, query_lots
from app.modules.tenders.tender_helpers import parse_tender_detail
import aiohttp
import asyncio

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

    # Define multiple SPARQL queries
    named_queries = [
        ("core", query_core_template.format(tender_uri=tender_uri)),
        ("identifier", query_identifier.format(tender_uri=tender_uri)),
        ("contracting_entity", query_contracting_entity.format(tender_uri=tender_uri)),
        ("monetary_values", query_monetary_values.format(tender_uri=tender_uri)),
        ("contractual_terms_and_location", query_contractual_terms_and_location.format(tender_uri=tender_uri)),
        ("cpvs", query_cpvs.format(tender_uri=tender_uri)),
        ("submission_terms", query_submission_terms.format(tender_uri=tender_uri)),
        ("legal_documents", query_legal_documents.format(tender_uri=tender_uri)),
        ("technical_documents", query_technical_documents.format(tender_uri=tender_uri)),
        ("additional_documents", query_additional_documents.format(tender_uri=tender_uri)),
        ("lots", query_lots.format(tender_uri=tender_uri)),
    ]

    try:
        named_results = await neptune_client.execute_named_sparql_queries_parallel(named_queries)
        tender_detail = parse_tender_detail(named_results)

        try:
            # Extract tender hash for database lookup
            tender_hash = tender_id
            if '/' in tender_id:
                tender_hash = tender_id.split('/')[-1]

            # Use synchronous DB session for simpler query
            from sqlalchemy.orm import Session
            from app.core.database import engine

            # Use a synchronous session for simplicity
            with Session(engine) as db:
                # First try exact match on tender_uri
                tender_doc = db.query(TenderDocumentsModel).filter(
                    TenderDocumentsModel.tender_uri == tender_hash
                ).first()
                
                # If not found, try other potential formats
                if not tender_doc and '/' not in tender_id:
                    # Try with full URI
                    tender_doc = db.query(TenderDocumentsModel).filter(
                        TenderDocumentsModel.tender_uri == tender_uri
                    ).first()
                
                # If a record exists, add its data to the tender details
                if tender_doc:
                    logger.info(f"Found TenderDocuments record for {tender_hash}")
                    tender_detail.summary = tender_doc.summary
                    tender_detail.url_document = tender_doc.url_document
                    tender_detail.status = tender_doc.status
                else:
                    logger.info(f"No TenderDocuments record found for tender {tender_hash}")
                    tender_detail.summary = None
                    tender_detail.url_document = None
                    # Leave status as None if not found - don't set a default here
                    
        except Exception as e:
            logger.error(f"Error retrieving TenderDocuments record: {str(e)}")
            # Continue without the summary, url_document, or status
            tender_detail.summary = None
            tender_detail.url_document = None
            # Don't set a default status here

        return tender_detail

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

def get_user_saved_tenders_uris(db: Session, user_id: str) -> List[str]:
    """
    Get the URIs of all tenders saved by a user.
    
    Args:
        db: SQLAlchemy Session
        user_id: The ID of the user
        
    Returns:
        List[str]: List of saved tender URIs for the user
    """
    logger.debug(f"Getting saved tender URIs for user {user_id}")
    
    try:
        # Query only the tender_uri column
        saved_uris = db.query(UserTenderModel.tender_uri).filter(
            UserTenderModel.user_id == user_id
        ).all()
        
        # The result is a list of tuples, extract the first element of each tuple
        return [uri[0] for uri in saved_uris]
        
    except Exception as e:
        logger.error(f"Error retrieving saved tender URIs for user {user_id}: {str(e)}")
        # Return empty list in case of error to avoid breaking the search
        return []

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
            select(TenderDocumentsModel)
            .where(TenderDocumentsModel.tender_uri == tender_uri)
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
            new_summary = TenderDocumentsModel(
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

    # Extract status from SPARQL binding if present, otherwise it will be set later
    status = binding.get('status', {}).get('value') if 'status' in binding else None

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
        cpv_categories=cpv_categories,
        status=status
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
        
        # Get the tender hash for querying the status
        tender_hash = tender_id
        if '/' in tender_id:
            tender_hash = tender_id.split('/')[-1]
            
        # Get status from TenderDocuments table using synchronous session
        try:
            # Import what we need for synchronous DB access            
            with Session(engine) as db:
                # Try with tender hash
                tender_doc = db.query(TenderDocumentsModel).filter(
                    TenderDocumentsModel.tender_uri == tender_hash
                ).first()
                
                # If not found and we're using a hash, try with full URI
                if not tender_doc and '/' not in tender_id:
                    tender_doc = db.query(TenderDocumentsModel).filter(
                        TenderDocumentsModel.tender_uri == tender_uri
                    ).first()
                
                if tender_doc and tender_doc.status:
                    tender_preview.status = tender_doc.status
                    logger.info(f"Found status for tender {tender_hash}: {tender_doc.status}")
                else:
                    # Don't set default status, leave it as None
                    logger.info(f"No status found for tender {tender_hash} in database")
                    
        except Exception as e:
            logger.error(f"Error retrieving tender status: {str(e)}", exc_info=True)
            # Don't set default status, leave it as None
            
        logger.info(f"Final tender preview status: {tender_preview.status}")
        
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

    ## Determine if the provided ID is a complete URI or just a hash/identifier
    #if tender_id.startswith('http'):
    #    tender_uri = tender_id
    #else:
    #    # Construct the URI from the hash
    #    tender_uri = f"http://gober.ai/spain/procedure/{tender_id}"

    tender_uri = tender_id

    try:
        # Query for the summary using SQLAlchemy ORM
        tender_summary = db.query(TenderDocumentsModel).filter(
            TenderDocumentsModel.tender_uri == tender_uri
        ).first()

        if tender_summary:
            tender_summary_data = schemas.TenderSummary(
                id=tender_summary.id,
                tender_uri=tender_summary.tender_uri,
                summary=tender_summary.summary,
                url_document=tender_summary.url_document,
                created_at=tender_summary.created_at,
                updated_at=tender_summary.updated_at
            )
            return tender_summary_data
        else:
            raise ValueError(f"Summary not found for tender with ID: {tender_id}")
    except Exception as e:
        logger.error(f"Error retrieving tender summary: {str(e)}")
        raise

async def get_tender_documents(tender_id: str) -> schemas.TenderDocuments:
    """
    Get the documents for a specific tender.

    This endpoint retrieves the documents for a specific tender from the RDF graph database.
    The tender is identified by either its full URI or its hash identifier.

    Args:
        tender_id: The URI or hash identifier of the tender to retrieve

    Returns:
        TenderDocuments: The documents for the tender

    Raises:
        ValueError: If the tender is not found
    """
    logger.info(f"Fetching tender documents for ID: {tender_id}")

    # Get Neptune client
    neptune_client = get_neptune_client()

    # Determine if the provided ID is a complete URI or just a hash/identifier
    if tender_id.startswith('http'):
        tender_uri = tender_id
    else:
        # Construct the URI from the hash
        tender_uri = f"http://gober.ai/spain/procedure/{tender_id}"

    logger.info(f"Using tender URI: {tender_uri}")

    query = f"""
    PREFIX ns1: <http://data.europa.eu/a4g/ontology#>
    PREFIX dct: <http://purl.org/dc/terms/>

    SELECT ?procedure
        ?UUID_legal ?ID_legal ?fechaPublicacion_legal ?issued_legal ?descripcion_legal ?urlAcceso_legal
        ?UUID_technical ?ID_technical ?fechaPublicacion_technical ?issued_technical ?descripcion_technical ?urlAcceso_technical
    WHERE {{
    VALUES ?procedure {{ <{tender_uri}> }}

    # DOCUMENTOS LEGALES
    OPTIONAL {{
        ?procedure ns1:isSubjectToProcedureSpecificTerm ?legalAccessTerm .
        FILTER(CONTAINS(STR(?legalAccessTerm), "access-term/legal-document"))
        ?legalAccessTerm a ns1:AccessTerm ;
                        ns1:involvesProcurementDocument ?legalDocument .
        OPTIONAL {{ ?legalDocument dct:title ?ID_legal . }}
        OPTIONAL {{ ?legalDocument ns1:hasPublicationDate ?fechaPublicacion_legal . }}
        OPTIONAL {{ ?legalDocument dct:issued ?issued_legal . }}
        OPTIONAL {{ ?legalDocument dct:description ?descripcion_legal . }}
        OPTIONAL {{ ?legalDocument ns1:hasAccessURL ?urlAcceso_legal . }}
        BIND(STR(?legalDocument) AS ?UUID_legal)
    }}

    # DOCUMENTOS TÉCNICOS
    OPTIONAL {{
        ?procedure ns1:isSubjectToProcedureSpecificTerm ?technicalAccessTerm .
        FILTER(CONTAINS(STR(?technicalAccessTerm), "access-term/technical-document"))
        ?technicalAccessTerm a ns1:AccessTerm ;
                            ns1:involvesProcurementDocument ?technicalDocument .
        OPTIONAL {{ ?technicalDocument dct:title ?ID_technical . }}
        OPTIONAL {{ ?technicalDocument ns1:hasPublicationDate ?fechaPublicacion_technical . }}
        OPTIONAL {{ ?technicalDocument dct:issued ?issued_technical . }}
        OPTIONAL {{ ?technicalDocument dct:description ?descripcion_technical . }}
        OPTIONAL {{ ?technicalDocument ns1:hasAccessURL ?urlAcceso_technical . }}
        BIND(STR(?technicalDocument) AS ?UUID_technical)
    }}
    }}
    """

    logger.info(f"Executing query: {query}")

    try:
        # Execute the query
        results = neptune_client.execute_sparql_query(query)

        if not results or 'results' not in results or 'bindings' not in results['results'] or len(results['results']['bindings']) == 0:
            logger.warning(f"Tender not found: {tender_uri}")
            raise ValueError(f"Tender with ID {tender_id} not found")

        # Parse the result into a TenderDocuments object
        binding = results['results']['bindings'][0]
        tender_documents = parse_sparql_binding_to_tender_documents(binding)

        return tender_documents
    except Exception as e:
        logger.error(f"Error retrieving tender documents: {str(e)}")
        raise

def parse_sparql_binding_to_tender_documents(binding: Dict[str, Any]) -> schemas.TenderDocuments:
    """
    Parse a single SPARQL query binding into a TenderDocuments object.

    Args:
        binding: A dictionary containing the SPARQL binding for a tender

    Returns:
        TenderDocuments: The parsed tender documents object
    """
    # Extract the tender URI
    tender_uri = binding.get('procedure', {}).get('value', '')

    # Initialize documents list
    documents = []

    # Parse legal document if present
    if 'UUID_legal' in binding and binding['UUID_legal'].get('value'):
        legal_doc = schemas.Document(
            id=binding.get('ID_legal', {}).get('value', ''),
            uuid=binding.get('UUID_legal', {}).get('value', ''),
            description=binding.get('descripcion_legal', {}).get('value', ''),
            url=binding.get('urlAcceso_legal', {}).get('value', ''),
            doc_type='legal',
            publication_date=None
        )

        # Add publication date if available
        if 'fechaPublicacion_legal' in binding and binding['fechaPublicacion_legal'].get('value'):
            try:
                date_str = binding['fechaPublicacion_legal']['value']
                legal_doc.publication_date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            except (ValueError, TypeError) as e:
                logger.warning(f"Error parsing legal document publication date: {e}")

        # Add to documents list
        documents.append(legal_doc)

    # Parse technical document if present
    if 'UUID_technical' in binding and binding['UUID_technical'].get('value'):
        technical_doc = schemas.Document(
            id=binding.get('ID_technical', {}).get('value', ''),
            uuid=binding.get('UUID_technical', {}).get('value', ''),
            description=binding.get('descripcion_technical', {}).get('value', ''),
            url=binding.get('urlAcceso_technical', {}).get('value', ''),
            doc_type='technical',
            publication_date=None
        )

        # Add publication date if available
        if 'fechaPublicacion_technical' in binding and binding['fechaPublicacion_technical'].get('value'):
            try:
                date_str = binding['fechaPublicacion_technical']['value']
                technical_doc.publication_date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            except (ValueError, TypeError) as e:
                logger.warning(f"Error parsing technical document publication date: {e}")

        # Add to documents list
        documents.append(technical_doc)

    # Create and return TenderDocuments
    return schemas.TenderDocuments(
        tender_uri=tender_uri,
        documents=documents
    )

async def get_ai_documents(tender_id: str, db: Session):
    tender_document = db.query(TenderDocumentsModel).filter_by(tender_uri=tender_id).first()
    if tender_document:
        sas_tokens = await get_ai_document_sas_token(tender_document.url_document)
        ai_doc_sas_token = sas_tokens.get("ai_doc_sas_token")
        combined_chunks_sas_token = sas_tokens.get("combined_chunks_sas_token")
        return {
            "url_document": tender_document.url_document,
            "summary": tender_document.summary,
            "ai_doc_sas_token": ai_doc_sas_token,
            "combined_chunks_sas_token": combined_chunks_sas_token
        }
    else: return None

async def get_ai_document_sas_token(ai_document_url: str) -> str:
    """
    Get a SAS token for a specific tender document.
    """
    azure_client = AzureBlobStorageClient()

    ai_doc_path = f"{ai_document_url}ai_document.md"
    combined_chunks_path = f"{ai_document_url}combined_chunks.json"

    ai_doc_sas_token = azure_client.generate_sas_url(ai_doc_path)
    combined_chunks_sas_token = azure_client.generate_sas_url(combined_chunks_path)

    return {
        "ai_doc_sas_token": ai_doc_sas_token,
        "combined_chunks_sas_token": combined_chunks_sas_token
    }


async def get_ai_tender_documents(tender_id: str, db: Session) -> schemas.TenderDocumentResponse:
    """
    Retrieve the AI document and combined chunks for a specific tender.

    Args:
        tender_id: The unique identifier hash for the tender
        db: SQLAlchemy database session

    Returns:
        TenderDocumentResponse: The AI document content, summary, and combined chunks as JSON

    Raises:
        ValueError: If the tender is not found or has no documents
    """
    logger.info(f"Fetching AI documents for tender ID: {tender_id}")

    # Find the tender in the database
    tender_document = db.query(TenderDocumentsModel).filter_by(tender_uri=tender_id).first()

    if not tender_document:
        logger.warning(f"Tender with ID {tender_id} not found")
        raise ValueError(f"Tender with ID {tender_id} not found")

    # Get the Azure folder path from the database
    azure_folder = tender_document.url_document

    if not azure_folder:
        logger.warning(f"No documents found for tender {tender_id}")
        raise ValueError(f"No documents found for tender {tender_id}")

    # Initialize Azure client
    azure_client = AzureBlobStorageClient()

    try:
        # Fetch the AI document
        ai_doc_path = f"{azure_folder}ai_document.md"
        ai_doc_content = azure_client.download_document(ai_doc_path)

        # Fetch the combined chunks
        chunks_path = f"{azure_folder}combined_chunks.json"
        chunks_content = azure_client.download_document(chunks_path)

        # Convert bytes to strings if needed
        if isinstance(ai_doc_content, bytes):
            ai_doc_content = ai_doc_content.decode('utf-8')

        if isinstance(chunks_content, bytes):
            chunks_content = chunks_content.decode('utf-8')

        # Return the document content, summary, and chunks
        return schemas.TenderDocumentResponse(
            tender_hash=tender_id,
            summary=tender_document.summary,
            ai_document=ai_doc_content,
            combined_chunks=chunks_content
        )

    except Exception as e:
        logger.error(f"Error retrieving AI tender documents: {str(e)}")
        raise ValueError(f"Error retrieving AI tender documents: {str(e)}")

async def _fetch_content_from_url(url: str) -> Optional[str]:
    """Fetches text content from a given URL."""
    if not url:
        logger.warning("Attempted to fetch content from an empty URL.")
        return None
    try:
        async with aiohttp.ClientSession() as session:
            # Note: No ssl=False here. SAS URLs should use HTTPS correctly.
            # Add timeout to prevent hanging indefinitely
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as response:
                response.raise_for_status() # Raises HTTPError for bad responses (4xx or 5xx)
                # Assuming markdown is UTF-8 encoded
                content = await response.text(encoding='utf-8')
                logger.debug(f"Successfully fetched content from {url[:100]}...")
                return content
    except aiohttp.ClientResponseError as http_err:
        logger.error(f"HTTP error fetching content from URL {url[:100]}...: Status {http_err.status}, Message {http_err.message}")
        return None
    except asyncio.TimeoutError:
        logger.error(f"Timeout error fetching content from URL {url[:100]}...")
        return None
    except Exception as e:
        logger.error(f"Generic error fetching content from URL {url[:100]}...: {e}", exc_info=True)
        return None

async def get_ai_document_content_from_azure(tender_id: str, db: Session) -> Optional[Dict[str, Any]]:
    """Gets SAS tokens and fetches AI document markdown and chunks JSON content from Azure."""
    logger.info(f"Attempting to fetch AI document and chunks content for tender ID: {tender_id}")
    try:
        # Use existing function to get metadata including SAS tokens
        ai_metadata = await get_ai_documents(tender_id, db)

        if ai_metadata and ai_metadata.get("ai_doc_sas_token") and ai_metadata.get("combined_chunks_sas_token"):
            ai_doc_sas_url = ai_metadata["ai_doc_sas_token"]
            chunks_sas_url = ai_metadata["combined_chunks_sas_token"]
            
            logger.info(f"Fetching AI content and chunks using SAS URLs for tender {tender_id}")
            
            # Fetch both contents concurrently
            ai_doc_content, chunks_json_content = await asyncio.gather(
                _fetch_content_from_url(ai_doc_sas_url),
                _fetch_content_from_url(chunks_sas_url)
            )

            if ai_doc_content is not None and chunks_json_content is not None:
                logger.info(f"Successfully fetched AI document ({len(ai_doc_content)} chars) and chunks ({len(chunks_json_content)} chars) for tender {tender_id}.")
                # Return both contents
                return {
                    "ai_document": ai_doc_content,
                    "combined_chunks": chunks_json_content # Return as JSON string
                }
            else:
                # Log which part failed
                if ai_doc_content is None:
                    logger.warning(f"Failed to fetch AI document content from SAS URL for tender {tender_id}")
                if chunks_json_content is None:
                     logger.warning(f"Failed to fetch chunks JSON content from SAS URL for tender {tender_id}")
                return None # Let route handle 404
        else:
            logger.warning(f"Missing SAS token(s) for AI document or chunks for tender {tender_id}")
            return None # Let route handle 404
    except ValueError as ve:
         # If get_ai_documents raises ValueError (e.g., tender not found in DB)
         logger.warning(f"Could not find tender or documents for {tender_id}: {ve}")
         return None # Let route handle 404
    except Exception as e:
        # Log unexpected errors during the process
        logger.error(f"Unexpected error getting AI document content for tender {tender_id}: {e}", exc_info=True)
        raise # Re-raise for the route to handle as 500