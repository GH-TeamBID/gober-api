from fastapi import APIRouter, HTTPException, Request
from core.utils.meili import MeiliClient, MeiliHelpers

router = APIRouter()

def ErrorResponse(error: int = 500, message: str = "Server error"):
    raise HTTPException(status_code=error, detail={'message': message})

@router.get("/tenders")
def tenders_get(request: Request, input_data: dict):
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
        return {**result} #"filters": filters, "match": match, "data": input_data
    except Exception as e:
        ErrorResponse(500, f"{e}")

@router.post("/tenders")
def tenders_create(request: dict):
    if 'documents' not in request or request['documents'] is None: ErrorResponse(400, "documents field is required")
    if isinstance(request['documents'], list) is False: ErrorResponse(400, "documents must be a list")
    try:
        documents = request['documents']
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
