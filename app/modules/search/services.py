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
            - Can be a list of {name, value} objects from request body
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
    meili_filters = {}
    
    if filters is not None:
        print(f"Processing filters: {filters}")
        
        if isinstance(filters, list) and len(filters) > 0:
            # Process list of filter objects from request body
            try:
                print(f"Processing filter list with {len(filters)} items")
                
                for filter_item in filters:
                    if 'name' in filter_item and 'value' in filter_item:
                        filter_name = filter_item['name']
                        filter_value = filter_item['value']
                        
                        # Process specific filter types
                        if filter_name == 'category':
                            # Handle category filters
                            if 'categories' not in meili_filters:
                                meili_filters['categories'] = []
                            meili_filters['categories'].append(filter_value)
                        
                        elif filter_name == 'location':
                            # Handle location filters
                            if 'location' not in meili_filters:
                                meili_filters['location'] = []
                            meili_filters['location'].append(filter_value)
                        
                        elif filter_name == 'status':
                            # Handle status filters
                            if 'status' not in meili_filters:
                                meili_filters['status'] = []
                            meili_filters['status'].append(filter_value)
                        
                        # Date range filters
                        elif filter_name == 'submission_date_from':
                            meili_filters['submission_date_gte'] = filter_value
                        
                        elif filter_name == 'submission_date_to':
                            meili_filters['submission_date_lte'] = filter_value
                        
                        # Budget range filters
                        elif filter_name == 'budget_min':
                            meili_filters['budget_amount_gte'] = float(filter_value)
                        
                        elif filter_name == 'budget_max':
                            meili_filters['budget_amount_lte'] = float(filter_value)
                        
                        else:
                            # Generic filter handling
                            meili_filters[filter_name] = filter_value
                    else:
                        print(f"Invalid filter object format: {filter_item}")
                
                print(f"Processed filters: {meili_filters}")
            except Exception as e:
                print(f"Error processing filters: {str(e)}")
                return {'error': True, 'message': f"Error processing filters: {str(e)}"}
        elif isinstance(filters, str):
            # Handle string filter format if needed
            parse_filters = MeiliHelpers.parse_params_filters(filters)
            if parse_filters['error']: 
                return {'error': True, 'message': parse_filters['message']}
            else: 
                meili_filters = parse_filters['filters']
    
    try:
        # Extract parameters from the request
        match = params['match'] if 'match' in params and params['match'] != '' else ''
        page = int(params['page']) if 'page' in params and params['page'] != '' else 1
        size = int(params['size']) if 'size' in params and params['size'] != '' else 20
        
        # Create search filters from URL parameters if not already in meili_filters
        # Add category filters if present
        if 'categories' in params and params['categories'] and 'categories' not in meili_filters:
            categories = params['categories'] 
            if isinstance(categories, str):
                categories = [categories]
            meili_filters['categories'] = categories
            
        # Add state/location filters if present
        if 'states' in params and params['states'] and 'location' not in meili_filters:
            states = params['states']
            if isinstance(states, str):
                states = [states]
            meili_filters['location'] = states
            
        # Add status filters if present
        if 'status' in params and params['status'] and 'status' not in meili_filters:
            status = params['status']
            if isinstance(status, str):
                status = [status]
            meili_filters['status'] = status
            
        # Add date range filters if present
        if 'date_from' in params and params['date_from'] and 'submission_date_gte' not in meili_filters:
            meili_filters['submission_date_gte'] = params['date_from']
        if 'date_to' in params and params['date_to'] and 'submission_date_lte' not in meili_filters:
            meili_filters['submission_date_lte'] = params['date_to']
            
        # Add budget range filters if present
        if 'budget_min' in params and params['budget_min'] and 'budget_amount_gte' not in meili_filters:
            meili_filters['budget_amount_gte'] = float(params['budget_min'])
        if 'budget_max' in params and params['budget_max'] and 'budget_amount_lte' not in meili_filters:
            meili_filters['budget_amount_lte'] = float(params['budget_max'])
        
        # Debug output
        print(f"Final MeiliSearch filters: {meili_filters}")
        
        # Initialize MeiliSearch client
        index_search = MeiliClient(index)
        
        # Perform the search
        result = index_search.search(match, filters=meili_filters, page=page, size=size)
        
        # Transform the response to match our API format
        result['items'] = result.pop('hits')
        result['total'] = result.pop('totalHits')
        result['size'] = result.pop('hitsPerPage')
        result['has_next'] = result['page'] < result['totalPages']
        result['has_prev'] = False if result['page'] == 1 else result['totalPages'] >= result['page']
        
        return {**result}
    except Exception as e:
        return {'error': True, 'message': f"{e}"}
        