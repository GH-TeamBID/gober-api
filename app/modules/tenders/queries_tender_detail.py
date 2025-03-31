# INFORMACIÓN GENERAL DEL PROCEDIMIENTO
query_core_template = """PREFIX dct: <http://purl.org/dc/terms/>
PREFIX ns1: <http://data.europa.eu/a4g/ontology#>

SELECT ?procedure ?title ?description ?additionalInfo
WHERE {{
  ?procedure a ns1:Procedure .
  VALUES ?procedure {{ <{tender_uri}> }}
  OPTIONAL {{ ?procedure dct:title ?title . }}
  OPTIONAL {{ ?procedure dct:description ?description . }}
  OPTIONAL {{ ?procedure ns1:hasAdditionalInformation ?additionalInfo . }}
}}
"""

# IDENTIFICADOR DEL PROCEDIMIENTO (ID EXPEDIENTE)
query_identifier = """PREFIX ns1: <http://data.europa.eu/a4g/ontology#>
PREFIX ns4: <http://www.w3.org/ns/adms#>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>

SELECT ?procedure ?identifier
WHERE {{
  ?procedure a ns1:Procedure .
  VALUES ?procedure {{ <{tender_uri}> }}
  OPTIONAL {{
    ?procedure ns4:identifier ?idMapping .
    ?idMapping skos:notation ?identifier .
  }}
}}
"""

# DATOS DE LA ORGANIZACIÓN CONTRATANTE
query_contracting_entity = """PREFIX ns1: <http://data.europa.eu/a4g/ontology#>
PREFIX ns5: <http://data.europa.eu/m8g/>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
PREFIX ns3: <http://www.w3.org/ns/locn#>
PREFIX ns4: <http://data.europa.eu/m8g/>

SELECT ?procedure ?buyer 
       (SAMPLE(?orgName) AS ?orgName)
       (SAMPLE(?orgFormType) AS ?orgFormType)
       (SAMPLE(?orgMainAct) AS ?orgMainAct)
       (SAMPLE(?orgBuyerProfile) AS ?orgBuyerProfile)
       (SAMPLE(?legalIdCode) AS ?legalIdCode)
       (SAMPLE(?taxIdCode) AS ?taxIdCode)
       (SAMPLE(?partyCountryCode) AS ?partyCountryCode)
       (SAMPLE(?partyNutsCode) AS ?partyNutsCode)
       (SAMPLE(?country) AS ?country)
       (SAMPLE(?province) AS ?province)
       (SAMPLE(?postCode) AS ?postCode)
       (SAMPLE(?postName) AS ?postName)
       (SAMPLE(?thoroughfare) AS ?thoroughfare)
WHERE {{
  ?procedure a ns1:Procedure .
  VALUES ?procedure {{ <{tender_uri}> }}
  
  OPTIONAL {{
    ?procedure ns1:involvesBuyer ?buyer .
    ?buyer a ns5:PublicOrganisation .
    OPTIONAL {{ ?buyer ns1:hasLegalName ?orgName . }}
    OPTIONAL {{ ?buyer ns1:hasLegalFormType ?orgFormType . }}
    OPTIONAL {{ ?buyer ns1:hasMainActivityDescription ?orgMainAct . }}
    OPTIONAL {{ ?buyer ns1:hasBuyerProfile ?orgBuyerProfile . }}
    OPTIONAL {{ 
      ?buyer ns1:hasLegalIdentifier ?legalId .
      OPTIONAL {{ ?legalId skos:notation ?legalIdCode . }}
    }}
    OPTIONAL {{ 
      ?buyer ns1:hasTaxIdentifier ?taxId .
      OPTIONAL {{ ?taxId skos:notation ?taxIdCode . }}
    }}
    OPTIONAL {{
      ?buyer ns3:address ?address .
      OPTIONAL {{ ?address ns1:hasCountryCode ?partyCountryCode . }}
      OPTIONAL {{ ?address ns1:hasNutsCode ?partyNutsCode . }}
      OPTIONAL {{ ?address ns3:addressArea ?country . }}
      OPTIONAL {{ ?address ns3:adminUnitL1 ?province . }}
      OPTIONAL {{ ?address ns3:postCode ?postCode . }}
      OPTIONAL {{ ?address ns3:postName ?postName . }}
      OPTIONAL {{ ?address ns3:thoroughfare ?thoroughfare . }}
    }}
    OPTIONAL {{
      ?buyer ns4:hasPrimaryContactPoint ?contactPoint .
    }}
  }}
}}
GROUP BY ?procedure ?buyer
"""

# VALORES MONETARIOS DEL PROCEDIMIENTO
query_monetary_values = """PREFIX ns1: <http://data.europa.eu/a4g/ontology#>
PREFIX ns3: <http://publications.europa.eu/ontology/authority/>

SELECT ?procedure ?baseBudgetAmount ?baseBudgetCurrency ?grossBudgetAmount ?grossBudgetCurrency ?netBudgetAmount ?netBudgetCurrency
WHERE {{
  ?procedure a ns1:Procedure .
  VALUES ?procedure {{ <{tender_uri}> }}
  OPTIONAL {{
    ?procedure ns1:hasEstimatedValue ?monetaryValue .
    FILTER(STRENDS(STR(?monetaryValue), "estimated-overall-contract-amount"))
    ?monetaryValue a ns1:MonetaryValue ;
                   ns1:hasAmountValue ?baseBudgetAmount ;
                   ns3:currency ?baseBudgetCurrency .
  }}
  OPTIONAL {{
    ?procedure ns1:hasEstimatedValue ?monetaryValue2 .
    FILTER(STRENDS(STR(?monetaryValue2), "gross-value"))
    ?monetaryValue2 a ns1:MonetaryValue ;
                    ns1:hasAmountValue ?grossBudgetAmount ;
                    ns3:currency ?grossBudgetCurrency .
  }}
  OPTIONAL {{
    ?procedure ns1:hasEstimatedValue ?monetaryValue3 .
    FILTER(STRENDS(STR(?monetaryValue3), "net-value"))
    ?monetaryValue3 a ns1:MonetaryValue ;
                    ns1:hasAmountValue ?netBudgetAmount ;
                    ns3:currency ?netBudgetCurrency .
  }}
}}
"""

# TÉRMINOS CONTRACTUALES Y UBICACIÓN
query_contractual_terms_and_location = """PREFIX ns1: <http://data.europa.eu/a4g/ontology#>
PREFIX dct: <http://purl.org/dc/terms/>
PREFIX ns3: <http://www.w3.org/ns/locn#>


SELECT ?procedure ?contractType ?contractSubType ?locationName ?contractNutsCode ?contractCountryCode ?country ?province ?postCode ?postName ?thoroughfare
WHERE {{
  ?procedure a ns1:Procedure .
  VALUES ?procedure {{ <{tender_uri}> }}
  OPTIONAL {{
    ?procedure ns1:foreseesContractSpecificTerm ?contractTerm .
    OPTIONAL {{ ?contractTerm a ns1:ContractTerm .
               ?contractTerm ns1:hasContractNatureType ?contractType .
               OPTIONAL {{ ?contractTerm ns1:hasAdditionalContractNature ?contractSubType . }}
    }}
  }}
  OPTIONAL {{
    ?procedure ns1:foreseesContractSpecificTerm ?contractTerm .
    ?contractTerm ns1:definesSpecificPlaceOfPerformance ?location .
    OPTIONAL {{ ?location dct:geographicName ?locationName . }}
    OPTIONAL {{ ?location ns1:hasNutsCode ?contractNutsCode . }}
    OPTIONAL {{ ?location ns1:hasCountryCode ?contractCountryCode . }}
  }}
  OPTIONAL {{
    ?procedure ns1:foreseesContractSpecificTerm ?contractTerm .
    ?contractTerm ns1:definesSpecificPlaceOfPerformance ?location .
    ?location ns3:address ?address .
    OPTIONAL {{ ?address ns3:addressArea ?country . }}
    OPTIONAL {{ ?address ns3:adminUnitL1 ?province . }}
    OPTIONAL {{ ?address ns3:postCode ?postCode . }}
    OPTIONAL {{ ?address ns3:postName ?postName . }}
    OPTIONAL {{ ?address ns3:thoroughfare ?thoroughfare . }}
  }}
}}
"""

# CPVs (clasificaciones)
query_cpvs = """PREFIX ns1: <http://data.europa.eu/a4g/ontology#>

SELECT ?procedure ?cpv
WHERE {{
  ?procedure a ns1:Procedure .
  VALUES ?procedure {{ <{tender_uri}> }}
  OPTIONAL {{
    ?procedure ns1:hasPurpose ?purpose .
    ?purpose a ns1:Purpose ;
             ns1:hasMainClassification ?cpv .
  }}
}}
"""

# TÉRMINOS DE SUMISIÓN (PLAZO DE RECEPCIÓN, IDIOMA, ETC.)
query_submission_terms = """PREFIX ns1: <http://data.europa.eu/a4g/ontology#>

SELECT ?procedure ?submissionDeadline ?submissionLanguage
WHERE {{
  ?procedure a ns1:Procedure .
  VALUES ?procedure {{ <{tender_uri}> }}
  OPTIONAL {{
    ?procedure ns1:isSubjectToProcedureSpecificTerm ?submissionTerm .
    ?submissionTerm a ns1:SubmissionTerm ;
                    ns1:hasReceiptDeadline ?submissionDeadline ;
                    ns1:hasLanguage ?submissionLanguage .
  }}
}}
"""

# DOCUMENTOS LEGALES
query_legal_documents = """PREFIX ns1: <http://data.europa.eu/a4g/ontology#>
PREFIX dct: <http://purl.org/dc/terms/>

SELECT ?procedure ?UUID_legal ?ID_legal ?fechaPublicacion_legal ?issued_legal ?descripcion_legal ?urlAcceso_legal
WHERE {{
  ?procedure a ns1:Procedure .
  VALUES ?procedure {{ <{tender_uri}> }}
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
}}
"""

# DOCUMENTOS TÉCNICOS
query_technical_documents = """PREFIX ns1: <http://data.europa.eu/a4g/ontology#>
PREFIX dct: <http://purl.org/dc/terms/>

SELECT ?procedure ?UUID_technical ?ID_technical ?fechaPublicacion_technical ?issued_technical ?descripcion_technical ?urlAcceso_technical
WHERE {{
  ?procedure a ns1:Procedure .
  VALUES ?procedure {{ <{tender_uri}> }}
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

# DOCUMENTOS ADICIONALES
query_additional_documents = """PREFIX ns1: <http://data.europa.eu/a4g/ontology#>
PREFIX dct: <http://purl.org/dc/terms/>

SELECT ?procedure (GROUP_CONCAT(STR(?UUID_add); separator="||") AS ?UUID_adds)
       (GROUP_CONCAT(?ID_add; separator="||") AS ?ID_adds)
       (GROUP_CONCAT(?fechaPublicacion_add; separator="||") AS ?fechaPublicacion_adds)
       (GROUP_CONCAT(?issued_add; separator="||") AS ?issued_adds)
       (GROUP_CONCAT(?descripcion_add; separator="||") AS ?descripcion_adds)
       (GROUP_CONCAT(?urlAcceso_add; separator="||") AS ?urlAcceso_adds)
WHERE {{
  ?procedure a ns1:Procedure .
  VALUES ?procedure {{ <{tender_uri}> }}
  OPTIONAL {{
    ?procedure ns1:isSubjectToProcedureSpecificTerm ?additionalTerm .
    FILTER(CONTAINS(STR(?additionalTerm), "access-term/additional-document"))
    ?additionalTerm a ns1:AccessTerm ;
                    ns1:involvesProcurementDocument ?additionalDoc .
    BIND(STR(?additionalDoc) AS ?UUID_add)
    OPTIONAL {{ ?additionalDoc dct:title ?ID_add . }}
    OPTIONAL {{ ?additionalDoc ns1:hasPublicationDate ?fechaPublicacion_add . }}
    OPTIONAL {{ ?additionalDoc dct:issued ?issued_add . }}
    OPTIONAL {{ ?additionalDoc dct:description ?descripcion_add . }}
    OPTIONAL {{ ?additionalDoc ns1:hasAccessURL ?urlAcceso_add . }}
  }}
}}
GROUP BY ?procedure
"""

# INFORMACIÓN DE LOTES
query_lots = """PREFIX ns1: <http://data.europa.eu/a4g/ontology#>
PREFIX dct: <http://purl.org/dc/terms/>
PREFIX ns2: <http://www.w3.org/ns/locn#>

SELECT ?procedure ?lot 
       (SAMPLE(?lotTitle) AS ?lotTitle)
       (SAMPLE(?lotDesc) AS ?lotDesc)
       (SAMPLE(?contractNature) AS ?contractNature)
       (SAMPLE(?lotLocationName) AS ?lotLocationName)
       (SAMPLE(?lotEstimated) AS ?lotEstimated)
       (SAMPLE(?lotGross) AS ?lotGross)
       (SAMPLE(?lotNet) AS ?lotNet)
WHERE {{
  ?procedure a ns1:Procedure .
  VALUES ?procedure {{ <{tender_uri}> }}  
  ?procedure ns1:hasProcurementScopeDividedIntoLot ?lot .
  ?lot a ns1:Lot .
  OPTIONAL {{ ?lot dct:title ?lotTitle . }}
  OPTIONAL {{ ?lot dct:description ?lotDesc . }}
  OPTIONAL {{
    ?lot ns1:foreseesContractSpecificTerm ?ct .
    OPTIONAL {{ ?ct a ns1:ContractTerm ;
                     ns1:hasContractNatureType ?contractNature . }}
    OPTIONAL {{
      ?ct ns1:definesSpecificPlaceOfPerformance ?loc .
      OPTIONAL {{ ?loc ns2:geographicName ?lotLocationName . }}
    }}
  }}
  OPTIONAL {{
    ?lot ns1:hasEstimatedValue ?est .
    ?est a ns1:MonetaryValue ;
         ns1:hasAmountValue ?lotEstimated .
  }}
  OPTIONAL {{
    ?lot ns1:hasEstimatedValue ?gross .
    ?gross a ns1:MonetaryValue ;
           ns1:hasAmountValue ?lotGross .
  }}
  OPTIONAL {{
    ?lot ns1:hasEstimatedValue ?net .
    ?net a ns1:MonetaryValue ;
         ns1:hasAmountValue ?lotNet .
  }}
}}
GROUP BY ?procedure ?lot
"""