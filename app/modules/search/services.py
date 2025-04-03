from app.core.utils.meili import MeiliClient, MeiliHelpers

def do_search(index: str, params, filters = None):
    """
    Perform a search on the specified index with the given parameters and filters.
    
    Args:
        index (str): The search index to query (e.g., 'tenders')
        params (dict): Query parameters including:
            - match: Search term(s) to match against documents
            - page: Page number (1-based)
            - size: Number of results per page
        filters (list|str, optional): Filters to apply to the search
            - Can be a list of {name, value, operator, expression} objects from request body
            - Or a string representation of filters
    
    Returns:
        dict: Search results with the following keys:
            - items: List of matched documents
            - total: Total number of matches
            - page: Current page number
            - size: Number of results per page
            - totalPages: Total number of pages
            - has_next: Whether there are more pages of results
            - has_prev: Whether there are previous pages of results
    """
    if filters is not None:
        print(f"Processing filters: {filters}")
        
        if isinstance(filters, list) is False and isinstance(filters, str) is False:
            return {'error': True, 'message': "Invalid datatype for filters"}
        else:
            if isinstance(filters, list):
                # Pre-process the list to modify budget_min and budget_max filters
                processed_filters = []
                for filter_item in filters:
                    if 'name' in filter_item and 'value' in filter_item:
                        # Handle budget_min - map to budget_amount with >= operator
                        if filter_item['name'] == 'budget_min':
                            processed_filters.append({
                                'name': 'budget_amount',
                                'value': float(filter_item['value']),
                                'operator': '>='
                            })
                        # Handle budget_max - map to budget_amount with <= operator
                        elif filter_item['name'] == 'budget_max':
                            processed_filters.append({
                                'name': 'budget_amount',
                                'value': float(filter_item['value']),
                                'operator': '<='
                            })
                        else:
                            # Pass other filters through unchanged
                            processed_filters.append(filter_item)
                    else:
                        processed_filters.append(filter_item)
                
                # Now parse the processed filters
                parse_filters = MeiliHelpers.parse_params_filters(processed_filters)
                if parse_filters['error']: 
                    return {'error': True, 'message': parse_filters['message']}
                else: 
                    filters = parse_filters['filters']
                    print(f"Parsed filter string: {filters}")
    
    try:
        # Extract parameters from the request
        match = params['match'] if 'match' in params and params['match'] != '' else ''
        page = int(params['page']) if 'page' in params and params['page'] != '' else 1
        size = int(params['size']) if 'size' in params and params['size'] != '' else 20
        
        # Initialize MeiliSearch client
        index_search = MeiliClient(index)
        
        # Perform the search
        result = index_search.search(match, filters=filters, page=page, size=size)
        
        # Transform the response to match our API format
        result['items'] = result.pop('hits')
        result['total'] = result.pop('totalHits')
        result['size'] = result.pop('hitsPerPage')
        result['has_next'] = result['page'] < result['totalPages']
        result['has_prev'] = False if result['page'] == 1 else result['totalPages'] >= result['page']
        
        return {**result}
    except Exception as e:
        return {'error': True, 'message': f"{e}"}
        