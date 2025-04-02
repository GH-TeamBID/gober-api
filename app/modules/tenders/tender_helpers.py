
import logging
from typing import Dict, Any, Callable, Optional, List
from datetime import datetime
from app.modules.tenders.schemas import MonetaryValue, Lot, TenderDetail, Identifier, Purpose, SubmissionTerm, ContractTerm, Location, ProcurementDocument, Organization, Address

logger = logging.getLogger(__name__)


def core_mapping():
    core_mapping = {
        "uri": {
            "source": "procedure",
            "converter": lambda v: v.split("/")[-1]
        },
        "title": {
            "source": "title",
            "converter": lambda v: v
        },
        "description": {
            "source": "description",
            "converter": lambda v: v
        },
        "additional_information": {
            "source": "additionalInfo",
            "converter": lambda v: v
        }
    }
    return core_mapping

def map_contracting_entity(row: Dict[str, Any]) -> Optional[Organization]:
    
    org_id = row.get("buyer", {}).get("value").split("-")[-1]
    org_name = row.get("orgName", {}).get("value")
    org_buyer_profile = row.get("orgBuyerProfile", {}).get("value")
    tax_id = row.get("taxIdCode", {}).get("value")
    legal_id = row.get("legalIdCode", {}).get("value")
    party_country_code = row.get("partyCountryCode", {}).get("value")
    party_nuts_code = row.get("partyNutsCode", {}).get("value")
    party_address_area = row.get("country", {}).get("value")
    party_admin_unit = row.get("province", {}).get("value")
    party_post_code = row.get("postCode", {}).get("value")
    party_post_name = row.get("postName", {}).get("value")
    party_thoroughfare = row.get("thoroughfare", {}).get("value")
    
    if org_id and org_name:
        return Organization(
            id=org_id,
            legal_name=org_name,
            buyer_profile=org_buyer_profile,
            tax_identifier=Identifier(notation=tax_id),
            legal_identifier=Identifier(notation=legal_id),
            address=Address(
                country=party_country_code,
                nuts_code=party_nuts_code,
                address_area=party_address_area,
                admin_unit=party_admin_unit,
                post_code=party_post_code,
                post_name=party_post_name,
                thoroughfare=party_thoroughfare
            )
        )
    return None

def monetary_mapping():
    monetary_mapping = {
        "amount": {
            # Se espera que el valor sea un string numérico, se convierte a float.
            "source": "amount",  
            "converter": lambda v: float(v)
        },
        "currency": {
            "source": "currency",
            "converter": lambda v: v
        }
    }
    return monetary_mapping

def map_monetary_value(row: Dict[str, Any], value_field: str, currency_field: str) -> Optional[MonetaryValue]:
    """
    Map a monetary value from a binding row to a MonetaryValue object.
    
    Args:
        row (Dict[str, Any]): The binding row to map.
    """
    value_str = row.get(value_field, {}).get("value")
    currency = row.get(currency_field, {}).get("value")
    if value_str and currency:
        try:
            amount = float(value_str)
            return MonetaryValue(amount=amount, currency=currency)
        except ValueError:
            return None
    return None

def map_purpose(row: Dict[str, Any]) -> Optional[Purpose]:
    """
    Map a binding row to a Purpose object.
    """
    
    main_classifications = []
    additional_classifications = []
    
    for r in row:
        cpv = r.get('cpv', {}).get('value')
        if cpv:
            main_classifications.append(cpv.split("/")[-1])
            additional_classifications = []
    
    if len(main_classifications) > 0:
        return Purpose(main_classifications=main_classifications, additional_classifications=additional_classifications)
    return None

def map_contract_term(row: Dict[str, Any]) -> Optional[ContractTerm]:
    """
    Map a binding row to a ContractTerm object.
    """
        
    contract_nature_type = row.get("contractType", {}).get("value")
    additional_contract_nature = row.get("contractSubType", {}).get("value")
    
    country_code = row.get("contractCountryCode", {}).get("value")
    nuts_code = row.get("contractNutsCode", {}).get("value")
    country = row.get("country", {}).get("value")
    province = row.get("province", {}).get("value")
    post_code = row.get("postCode", {}).get("value")
    post_name = row.get("postName", {}).get("value")
    thoroughfare = row.get("thoroughfare", {}).get("value")
    
        
    return ContractTerm(
                        contract_nature_type=contract_nature_type.split("/")[-1], 
                        additional_contract_nature=additional_contract_nature.split("/")[-1] if additional_contract_nature else None, 
                        place_of_performance=Location(
                            country_code=country_code.split("/")[-1],
                            nuts_code=nuts_code.split("/")[-1],
                            address=Address(
                                country=country,
                                nuts_code=nuts_code.split("/")[-1],
                                admin_unit=province,
                                post_code=post_code,
                                post_name=post_name,
                                thoroughfare=thoroughfare
                            )
                        )
                    )

def map_submission_deadline(row: Dict[str, Any]) -> Optional[SubmissionTerm]:
    """
    Map a binding row to a SubmissionTerm object.
    """
    
    receipt_deadline = row.get("submissionDeadline", {}).get("value")
    language = row.get("submissionLanguage", {}).get("value")
    
    if receipt_deadline:
        try:
            receipt_deadline = datetime.strptime(receipt_deadline, "%Y-%m-%dT%H:%M:%S.%fZ")
            return SubmissionTerm(receipt_deadline=receipt_deadline, language=language)
        except ValueError:
            logger.error(f"Failed to parse receipt deadline: {receipt_deadline}")
            return None
    return None

def map_lots(row: Dict[str, Any], separator: str = "||") -> List[Lot]:
    """
    Map a binding row to a list of Lot objects.
    Assumes that fields are concatenated with a separator.
    
    Args:
        row (Dict[str, Any]): The binding row to map.
    """
    
    if len(row) <= 1:
        return []
    
    lots = []
    for r in row:
        lot_id = r.get("lot", {}).get("value").split("/")[-1]
        lot_title = r.get("lotTitle", {}).get("value")
        lot_description = r.get("lotDesc", {}).get("value")
        lot_estimated = r.get("lotEstimated", {}).get("value")
        lot_gross = r.get("lotGross", {}).get("value")
        lot_net = r.get("lotNet", {}).get("value")
        
        if lot_id and lot_title:
            lots.append(Lot(
                id=lot_id,
                title=lot_title,
                description=lot_description,
                estimated_value=MonetaryValue(amount=lot_estimated, currency="EUR") if lot_estimated else None,
                gross_value=MonetaryValue(amount=lot_gross, currency="EUR") if lot_gross else None,
                net_value=MonetaryValue(amount=lot_net, currency="EUR") if lot_net else None
        ))
        
    return lots


def map_documents(row: Dict[str, Any], document_type: str) -> List[ProcurementDocument]:
    """
    Map a binding row to a list of Document objects.
    """

    if "||" in str(row):
        title = f"ID_{document_type}"
        url_access = f"urlAcceso_{document_type}"
        titles = row.get(title, {}).get("value").split("||")
        access_urls = row.get(url_access, {}).get("value").split("||")
        
        results = []
        
        if len(titles) == len(access_urls):
            for title, access_url in zip(titles, access_urls):
                results.append(ProcurementDocument(
                    title=title,
                    document_type=document_type,
                    access_url=access_url))
        else:
            logger.error(f"Titles and access URLs have different lengths: {len(titles)} != {len(access_urls)}")
            return []
        
        return results
            
    else:
        title = f"ID_{document_type}"
        url_access = f"urlAcceso_{document_type}"
        title = row.get(title, {}).get("value")
        access_url = row.get(url_access, {}).get("value")
        
        if title and access_url:
            return [ProcurementDocument(
                title=title,
                document_type=document_type,
                access_url=access_url
            )]
        else:
            return []


def map_binding_row(row: Dict[str, Any], mapping_config: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """
    Map a binding row to a dictionary using the provided mapping configuration.
    
    Args:
        row (Dict[str, Any]): The binding row to map.
        mapping_config (Dict[str, Dict[str, Any]]): The mapping configuration.
        
    Returns:
        Dict[str, Any]: The mapped dictionary.
    """
    
    result = {} 
    for dest_field, rules in mapping_config.items():
        source_key: str = rules.get("source")
        converter: Callable[[str], Any] = rules.get("converter", lambda x: x)

        if source_key in row:
            value = row[source_key].get("value")
            result[dest_field] = converter(value)
        else:
            result[dest_field] = None
    
    return result

def parse_tender_detail(named_results: Dict[str, Any]) -> TenderDetail:
    """
    Parse the named results into a TenderDetail object.
    """
    core_data = named_results.get("core", {}).get("results", {}).get("bindings", [])
    identifier_data = named_results.get("identifier", {}).get("results", {}).get("bindings", [])
    monetary_data = named_results.get("monetary_values", {}).get("results", {}).get("bindings", [])
    lots_data = named_results.get("lots", {}).get("results", {}).get("bindings", [])
    submission_terms_data = named_results.get("submission_terms", {}).get("results", {}).get("bindings", [])
    purpose_data = named_results.get("cpvs", {}).get("results", {}).get("bindings", [])
    contract_term_data = named_results.get("contractual_terms_and_location", {}).get("results", {}).get("bindings", [])
    buyer_data = named_results.get("contracting_entity", {}).get("results", {}).get("bindings", [])
    legal_documents_data = named_results.get("legal_documents", {}).get("results", {}).get("bindings", [])
    technical_documents_data = named_results.get("technical_documents", {}).get("results", {}).get("bindings", [])
    additional_documents_data = named_results.get("additional_documents", {}).get("results", {}).get("bindings", [])
    
    # Map core fields using generic mapping function
    core_row = core_data[0] if core_data else {}
    mapped_core = map_binding_row(core_row, core_mapping())
    procedure_uri = mapped_core.get("uri")
    
    # Map identifier field
    notation_id = None
    if identifier_data:
        notation_id = identifier_data[0].get("identifier", {}).get("value")
        
    
    # Map contracting entity
    buyer = None
    if buyer_data:
        buyer = map_contracting_entity(buyer_data[0])
    
    # Map submission terms
    submission_term = None
    if submission_terms_data:
        submission_term = map_submission_deadline(submission_terms_data[0])

    # Map contract term
    contract_term = None
    if contract_term_data:
        contract_term = map_contract_term(contract_term_data[0])

    # Map monetary values
    base_budget = None
    net_budget = None
    gross_budget = None
    if monetary_data:
        row_m = monetary_data[0]
        base_budget = map_monetary_value(row_m, "baseBudgetAmount", "baseBudgetCurrency")
        net_budget = map_monetary_value(row_m, "netBudgetAmount", "netBudgetCurrency")
        gross_budget = map_monetary_value(row_m, "grossBudgetAmount", "grossBudgetCurrency")
                
    
    # Map purpose
    purpose = None
    if purpose_data:
        purpose = map_purpose(purpose_data)
    
    # Map lots
    lots = []
    if lots_data:
        lots = map_lots(lots_data)
    
    # Map documents
    documents = []
    if legal_documents_data:
        documents.extend(map_documents(legal_documents_data[0], "legal"))
    if technical_documents_data:
        documents.extend(map_documents(technical_documents_data[0], "technical"))
    if additional_documents_data:
        documents.extend(map_documents(additional_documents_data[0], "adds"))


    tender_detail = TenderDetail(
        uri=procedure_uri or "",
        identifier=Identifier(notation=notation_id) if notation_id else None,
        title=mapped_core.get("title") or "",
        description=mapped_core.get("description"),
        summary=None,
        estimated_value=base_budget,
        net_value=net_budget,
        gross_value=gross_budget,
        submission_term=submission_term,
        contract_period=None,
        planned_period=None,
        buyer=buyer,
        purpose=purpose,
        contract_term=contract_term,
        additional_information=mapped_core.get("additional_information"),
        status=None,
        procurement_documents=documents,
        lots=lots
    )
    
    return tender_detail
