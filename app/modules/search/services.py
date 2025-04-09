from app.core.utils.meili import MeiliClient, MeiliHelpers
import json # Import json for escaping URIs in filter
from typing import Optional, List, Dict
from datetime import datetime

def do_search(index_name: str, params: dict, body_filters: Optional[List[Dict]] = None, saved_tender_uris: Optional[List[str]] = None):
    """
    Perform a search on the specified index with the given parameters and filters.
    
    Args:
        index_name (str): The search index to query (e.g., 'tenders')
        params (dict): Query parameters including:
            - match: Search term(s) to match against documents
            - offset: Number of results to skip (default: 0)
            - limit: Number of results per page (default: 10, max: 100)
            - sort_field: Field to sort by
            - sort_direction: Sort direction ('asc' or 'desc')
        body_filters (list, optional): Filters from request body.
            - List of {name, value, operator, expression} objects
        saved_tender_uris (list, optional): List of tender URIs/hashes to filter by.
            - If provided, results will be limited to these tenders.
    
    Returns:
        dict: Search results with the following keys:
            - items: List of matched documents
            - total: Total number of matches for the query and filters
            - offset: Offset applied to the search
            - limit: Limit applied to the search
            - has_next: Whether there are more results beyond the current limit
            - has_prev: Whether the offset is greater than 0
            - debug (optional): Debugging information
    """
    combined_filter_string = ""
    filter_parts = []

    # 1. Process body filters (budget mapping, etc.)
    if body_filters is not None:
        print(f"Processing body filters: {body_filters}")
        if not isinstance(body_filters, list):
            # Use return for errors in service functions
            return {'error': True, 'message': "Invalid datatype for body_filters"}
        
        processed_filters = []
        for filter_item in body_filters:
            # Ensure filter_item is a dict and has required keys
            if isinstance(filter_item, dict) and 'name' in filter_item and 'value' in filter_item:
                name = filter_item['name']
                value = filter_item['value']
                # Default operator to '=' if not provided or handle based on MeiliHelpers expectation
                operator = filter_item.get('operator', '=') 
                # expression = filter_item.get('expression', 'AND') # Keep track if needed by helper
                
                try:
                    # Special handling for budget -> budget_amount
                    if name == 'budget_min':
                        processed_filters.append({'name': 'budget_amount', 'value': float(value), 'operator': '>='})
                    elif name == 'budget_max':
                        processed_filters.append({'name': 'budget_amount', 'value': float(value), 'operator': '<='})
                    # Special handling for date ranges -> timestamp
                    elif name == 'submission_date_from':
                        dt = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
                        processed_filters.append({'name': 'submission_date', 'value': int(dt.timestamp()), 'operator': '>='})
                    elif name == 'submission_date_to':
                        dt = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
                        processed_filters.append({'name': 'submission_date', 'value': int(dt.timestamp()), 'operator': '<='})
                    # Generic filter: pass name, value, and operator to helper
                    else:
                        processed_filters.append({
                            'name': name, 
                            'value': value, 
                            'operator': operator
                            # 'expression': expression # Add if helper needs it
                        })
                except ValueError as e:
                    print(f"Warning: Could not parse value for filter '{name}': {value}. Error: {e}")
                    # Decide whether to skip or return error
                    # return {'error': True, 'message': f"Invalid value for filter '{name}': {value}"}
            else:
                # Log or ignore invalid filter items
                print(f"Warning: Skipping invalid filter item format: {filter_item}")
        
        # Parse the processed filters into MeiliSearch filter string using the helper
        # This helper needs to understand the {'name': ..., 'value': ..., 'operator': ...} structure
        parse_result = MeiliHelpers.parse_params_filters(processed_filters)
        if parse_result.get('error'): 
            return {'error': True, 'message': parse_result['message']}
        else: 
            body_filter_string = parse_result.get('filters')
            if body_filter_string: # Add only if it's not empty
                 filter_parts.append(f"({body_filter_string})") # Wrap in parentheses
            print(f"Parsed body filter string: {body_filter_string}")

    # 2. Process saved tender URI filter
    if saved_tender_uris is not None and len(saved_tender_uris) > 0:
        # Assuming the field in MeiliSearch containing the URI/hash is 'id'
        # Escape quotes within URIs if necessary, although unlikely for URIs
        # MeiliSearch expects strings in filters to be double-quoted
        quoted_uris = [json.dumps(uri) for uri in saved_tender_uris]
        saved_filter_string = f"id IN [{', '.join(quoted_uris)}]"
        filter_parts.append(saved_filter_string)
        print(f"Added saved tender filter: {saved_filter_string}")
    elif saved_tender_uris is not None and len(saved_tender_uris) == 0:
        # If filtering by saved but the list is empty, no results are possible.
        # Return early to avoid unnecessary search call.
        print("Filtering by saved tenders, but no saved URIs provided. Returning empty result.")
        return {
            'items': [], 'total': 0, 'offset': params.get('offset', 0),
            'limit': params.get('limit', 10), 'has_next': False, 'has_prev': False
        }

    # 3. Combine filters
    if filter_parts:
        combined_filter_string = " AND ".join(filter_parts)
        print(f"Combined filter string: {combined_filter_string}")

    try:
        # Extract parameters, using new names and defaults
        match = params.get('match', '')
        offset = int(params.get('offset', 0))
        limit = int(params.get('limit', 10))
        
        # Prepare sorting parameter for MeiliSearch
        sort_param = None
        sort_field = params.get('sort_field')
        sort_direction = params.get('sort_direction', 'asc').lower()
        if sort_field and sort_direction in ['asc', 'desc']:
             # Map frontend field names to MeiliSearch field names if necessary
             # Assuming direct mapping for now (e.g., 'submission_date')
             sort_param = [f"{sort_field}:{sort_direction}"]
             print(f"Applying sort: {sort_param}")

        # Initialize MeiliSearch client
        index_search = MeiliClient(index_name)
        
        # Perform the search with offset, limit, and combined filters
        print(f"Executing MeiliSearch with: match='{match}', offset={offset}, limit={limit}, filter='{combined_filter_string}', sort={sort_param}")
        
        # Call search with individual keyword arguments
        result = index_search.search(
            match, 
            offset=offset,
            limit=limit,
            filter=combined_filter_string if combined_filter_string else None,
            sort=sort_param
        )
        
        # Transform the response
        items = result.get('hits', [])
        total_hits = result.get('totalHits')
        # MeiliSearch might return estimatedTotalHits if totalHits is not exact
        total_count = result.get('estimatedTotalHits', total_hits if total_hits is not None else 0)
        
        # Calculate pagination flags
        has_next = (offset + len(items)) < total_count
        has_prev = offset > 0
        
        print(f"Search Result: total={total_count}, offset={offset}, limit={limit}, items_returned={len(items)}")

        # Construct final response
        response_data = {
            'items': items,
            'total': total_count,
            'offset': offset,
            'limit': limit,
            'has_next': has_next,
            'has_prev': has_prev
            # 'debug': result # Optionally include raw MeiliSearch result for debugging
        }
        return response_data

    except Exception as e:
        import traceback
        print(f"Error during search: {traceback.format_exc()}")
        return {'error': True, 'message': f"Search service error: {str(e)}"}
        