from app.core.utils.meili import MeiliClient, MeiliHelpers

def do_search(index: str, params, filters = None):
    if filters is not None:
        if isinstance(filters, list) is False and isinstance(filters, str) is False:
            return {'error': True, 'message': "Invalida datatype for filters"}
        else:
            if isinstance(filters, list): 
                parse_filters = MeiliHelpers.parse_params_filters(filters)
                if parse_filters['error']: return {'error': True, 'message': parse_filters['message']}
                else: filters = parse_filters['filters']
    try:
        match = params['match'] if 'match' in params else ''
        page = int(params['page']) if 'page' in params and params['page'] != '' else 1
        size = int(params['size']) if 'size' in params and params['size'] != '' else 20
        index_search = MeiliClient(index)
        result = index_search.search(match, filters=filters, page=page, size=size)
        result['items'] = result.pop('hits')
        result['total'] = result.pop('totalHits')
        result['size'] = result.pop('hitsPerPage')
        result['has_next'] = result['page'] < result['totalPages']
        result['has_prev'] = False if result['page'] == 1 else result['totalPages'] >= result['page']
        return {**result}
    except Exception as e:
        return {'error': True, 'message': f"{e}"}
        