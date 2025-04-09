from fastapi import APIRouter, HTTPException, Request
from app.core.utils.meili import MeiliClient, MeiliHelpers
from datetime import datetime
from sqlalchemy.orm import Session
from app.core.database import engine
from app.modules.auth.models import CpvCode

router = APIRouter()

def ErrorResponse(error: int = 500, message: str = "Server error"):
    raise HTTPException(status_code=error, detail={'message': message})

@router.get("/tenders")
def tenders_get(request: Request, input_data: dict = {}):
    qparams = dict(request.query_params)
    filters = None
    if 'filters' in input_data:
        if isinstance(input_data['filters'], list) is False and isinstance(input_data['filters'], str) is False:
            ErrorResponse(400, "Invalida datatype for filters")
        else:
            filters = input_data['filters']
            if isinstance(filters, list): 
                parse_filters = MeiliHelpers.parse_params_filters(filters)
                if parse_filters['error']: ErrorResponse(400, parse_filters['message'])
                else: filters = parse_filters['filters']
    try:
        match = qparams['match'] if 'match' in qparams else ''
        page = int(qparams['page']) if 'page' in qparams and qparams['page'] != '' else 1
        tenders_search = MeiliClient('tenders')
        result = tenders_search.search(match, filters=filters, page=page)
        return {**result}
    except Exception as e:
        ErrorResponse(500, f"{e}")

@router.post("/tenders")
def tenders_create(request: dict):
    if 'documents' not in request or request['documents'] is None: ErrorResponse(400, "documents field is required")
    if isinstance(request['documents'], list) is False: ErrorResponse(400, "documents must be a list")
    try:
        documents = request['documents']
        # Parsing
        for document in documents:
            if 'updated' in document and document['updated'] != '' and document['updated'] is not None:
                format = '%Y-%m-%dT%H:%M:%S.%fZ' if "T" in document['updated'] and "Z" in document['updated'] else '%Y-%m-%d %H:%M:%S'
                xdate = datetime.strptime(document['updated'], format)
                document['updated'] = int(xdate.timestamp())
            if 'submission_date' in document and document['submission_date'] != '' and document['submission_date'] is not None:
                format = '%Y-%m-%dT%H:%M:%S.%fZ' if "T" in document['submission_date'] and "Z" in document['submission_date'] else '%Y-%m-%d %H:%M:%S'
                xdate = datetime.strptime(document['submission_date'], format)
                document['submission_date'] = int(xdate.timestamp())
        tenders_search = MeiliClient('tenders')
        tenders_search.add_documents(documents)
        return {'message': "Tenders saved"}
    except Exception as e:
        ErrorResponse(500, f"{e}")

@router.delete("/tenders")
def tenders_delete(request: dict):
    if 'ids' not in request or request['ids'] is None: ErrorResponse(400, "ids field is required")
    if isinstance(request['ids'], list) is False: ErrorResponse(400, "ids must be a list")
    try:
        ids = request['ids']
        tenders_search = MeiliClient('tenders')
        tenders_search.delete_documents(ids)
        return {'message': "Tenders deleteds"}
    except Exception as e:
        ErrorResponse(500, f"{e}")

@router.post("/tenders/set_filters")
def set_filters(request: dict):
    if 'filters' not in request or request['filters'] is None: ErrorResponse(400, "filters field is required")
    if isinstance(request['filters'], list) is False: ErrorResponse(400, "filters must be a list")
    try:
        rewrite = request['rewrite'] if 'rewrite' in request and request['rewrite'] != '' else False
        filters = request['filters']
        tenders_search = MeiliClient('tenders')
        current_filters = tenders_search.get_filters()
        if rewrite is True: filters = list(dict.fromkeys(current_filters + filters))
        tenders_search.set_filters(filters)
        return {'message': "filters updateds"}
    except Exception as e:
        ErrorResponse(500, f"{e}")

@router.get("/tenders/get_filters")
def set_filters():
    try:
        tenders_search = MeiliClient('tenders')
        filters = tenders_search.get_filters()
        return {'filters': filters}
    except Exception as e:
        ErrorResponse(500, f"{e}")


@router.post("/cpvs")
def load_cpvs():
    try:
        tenders_search = MeiliClient('cpvs')
        #task = tenders_search.get_client().index('cpvs').update_searchable_attributes(["*", "code"]) #"description", "es_description"
        documents = []
        with Session(engine) as session:
            cpvs = session.query(CpvCode).all()
        for cpv in cpvs:
            documents.append(
                {
                    "id": cpv.code,
                    "code": f"{cpv.code}",
                    "description": cpv.description,
                    "es_description": cpv.es_description
                }
            )
        tenders_search.add_documents(documents)
        return {'message': "Cpvs loaded"}
        return {'documents': documents, 'searchables': tenders_search.get_index('cpvs').get_searchable_attributes()}
        documents = [
            {
                "id": "09211640",
                "code": "09211640",
                "description": "Electrical insulating oils",
                "es_description": "Aceites para aislamiento eléctrico"
            },
            {
                "id": "14764000",
                "code": "14764000",
                "description": "Thallium",
                "es_description": "Talio"
            },
            {
                "id": "15131640",
                "code": "15131640",
                "description": "Beefburgers",
                "es_description": "Hamburguesas de carne de vaca"
            },
            {
                "id": "15331464",
                "code": "15331464",
                "description": "Canned whole beans",
                "es_description": "Judías verdes enteras enlatadas"
            },
            {
                "id": "15864000",
                "code": "15864000",
                "description": "Preparations of tea or maté",
                "es_description": "Preparaciones de té o de mate"
            },
            {
                "id": "15864100",
                "code": "15864100",
                "description": "Teabags",
                "es_description": "Bolsitas de té"
            },
            {
                "id": "16400000",
                "code": "16400000",
                "description": "Spraying machinery for agriculture or horticulture",
                "es_description": "Aparatos de pulverizar para la agricultura o la horticultura"
            },
            {
                "id": "16640000",
                "code": "16640000",
                "description": "Bee-keeping machinery",
                "es_description": "Máquinas y aparatos para la apicultura"
            },
            {
                "id": "19640000",
                "code": "19640000",
                "description": "Polythene waste and refuse sacks and bags",
                "es_description": "Sacos y bolsas de polietileno para residuos"
            },
            {
                "id": "24212640",
                "code": "24212640",
                "description": "Copper hydroxide",
                "es_description": "Hidróxido de cobre"
            }
        ]
    except Exception as e:
        ErrorResponse(500, f"{e}")