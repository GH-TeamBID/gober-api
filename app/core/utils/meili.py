import meilisearch
#from app.core.utils.helpers import Envs
from app.core.config import settings
from typing import Optional

class MeiliClient:
    # docs: https://www.meilisearch.com/docs/reference/api/documents
    def __init__(self, index_name: str, host: str = "", api_key: str = ""):
        if host == '': host = settings.MEILISEARCH_HOST #Envs.get('MEILISEARCH_HOST')
        if api_key == '': api_key = settings.MEILISEARCH_API_KEY if settings.MEILISEARCH_API_KEY != '' else None #api_key = Envs.get('MEILISEARCH_API_KEY') if Envs.get('MEILISEARCH_API_KEY') != '' else None
        self.client = meilisearch.Client(host, api_key)
        self.index_name = index_name
        self.index = self.check_index_exists()

    def check_index_exists(self):
        """ Check if index exists, if not then creates it"""
        try:
            return self.client.get_index(self.index_name)
        except:
            return self.client.create_index(uid=self.index_name, options={"primaryKey": "id"})
        
    def set_filters(self, filters: list):
        self.index.update_filterable_attributes(filters) #self.client.index(self.index_name)

    def get_filters(self):
        return self.index.get_filterable_attributes()
    
    def get_client(self):
        return self.client
    
    def create_index(self, index_name: str, primary_key: str = "id"):
        return self.client.create_index(uid=index_name, options={"primaryKey": primary_key})

    def get_index(self, index_name: str):
        return self.client.get_index(index_name)

    def delete_index(self):
        return self.client.index(self.index_name).delete()

    def add_documents(self, documents: list):
        return self.client.index(self.index_name).add_documents(documents)

    def update_documents(self, documents: list):
        return self.client.index(self.index_name).update_documents(documents)

    def delete_documents(self, document_ids: list):
        return self.client.index(self.index_name).delete_documents(document_ids)

    def search(self, query: str, offset: int = 0, limit: int = 20, filter: Optional[str] = None, sort: Optional[list] = None):
        """
        Search the MeiliSearch index with the given query and options.
        
        Args:
            query: The search query text
            offset: Number of documents to skip (default: 0)
            limit: Maximum number of documents to return (default: 20)
            filter: Filter string to apply (MeiliSearch filter syntax)
            sort: List of fields to sort by (e.g., ["submission_date:desc"])
            
        Returns:
            Search results from MeiliSearch
        """
        # Prepare optional parameters for the MeiliSearch library call
        search_params = {}
        if offset is not None:
            search_params['offset'] = offset
        if limit is not None:
            search_params['limit'] = limit
        if filter:
            search_params['filter'] = filter
        if sort:
            search_params['sort'] = sort
        
        # Debug: Print the parameters being sent to MeiliSearch
        print(f"MeiliSearch query: '{query}', params: {search_params}")
        
        # Call the underlying MeiliSearch client's search method
        # Using self.index is slightly more direct than self.client.index(...)
        return self.index.search(query, search_params)

class MeiliHelpers:
    OPERATORS = {"=", "!=", "<=", ">=", "<", ">", "TO", "EXISTS", "IN", "NOT", "IS", "IS NOT"}
    @staticmethod
    def parse_params_filters(params_filters: list):
        filters = ""
        for param_filter in params_filters:
            # Validate required keys
            if not isinstance(param_filter, dict):
                print(f"Warning: Skipping non-dict filter item: {param_filter}")
                continue
            if 'name' not in param_filter or param_filter['name'] == '': 
                return {'error': True, 'message': "Param filter 'name' is required"}
            # Value is not strictly required for operators like EXISTS
            # if 'value' not in param_filter: 
            #     return {'error': True, 'message': "Param filter 'value' is required"}
            
            fname = param_filter.get('name')
            fvalue = param_filter.get('value') # May be None for EXISTS etc.
            foperator = param_filter.get('operator', '=') # Default operator
            fexpression = param_filter.get('expression', 'AND') # Default expression
            
            if foperator not in MeiliHelpers.OPERATORS: 
                return {'error': True, 'message': f"Param filter '{fname}' operator '{foperator}' not valid"}
            
            # Handle specific operator requirements
            if foperator == 'IN' and not isinstance(fvalue, list):
                return {'error': True, 'message': f"Value of filter '{fname}' with operator IN must be an array"}
            if foperator in ["EXISTS", "NOT EXISTS"] and 'value' in param_filter: # Should not have value
                 print(f"Warning: Filter '{fname}' with operator {foperator} should not have a value.")
                 fvalue = None # Ignore value for EXISTS/NOT EXISTS
            elif foperator not in ["EXISTS", "NOT EXISTS"] and 'value' not in param_filter:
                 return {'error': True, 'message': f"Param filter '{fname}' with operator {foperator} requires a value"}

            # Format the value part
            value_str = ""
            if foperator == 'IN':
                # Correctly format IN operator: field IN [val1, val2]
                # Ensure values are quoted if strings
                formatted_values = []
                for v in fvalue:
                    if isinstance(v, str):
                        # Escape single quotes within the string
                        escaped_v = v.replace("'", "\\'") 
                        formatted_values.append(f"'{escaped_v}'")
                    else:
                        formatted_values.append(str(v))
                value_str = f"[{', '.join(formatted_values)}]"
            elif fvalue is not None: # Format value for other operators
                if isinstance(fvalue, str):
                    # Escape single quotes
                    escaped_fvalue = fvalue.replace("'", "\\'")
                    value_str = f"'{escaped_fvalue}'" # Quote strings
                else:
                    value_str = str(fvalue)

            # Build the filter part for this item
            filter_part = f"{fname} {foperator}"
            if value_str: # Add value only if it was formatted (e.g., not for EXISTS)
                filter_part += f" {value_str}"
            
            # Append to the main filters string
            if filters == "":
                filters += filter_part
            else:
                filters += f" {fexpression} {filter_part}"

        print(f"Generated MeiliSearch filter string: {filters}")
        return {'error': False, 'filters': filters.strip()}
