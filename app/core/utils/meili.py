import meilisearch
#from app.core.utils.helpers import Envs
from app.core.config import settings

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

    def search(self, query, filters=None, page:int = 1, size: int = 20):
        """
        Search the MeiliSearch index with the given query and filters
        
        Args:
            query: The search query text
            filters: Filters to apply. Can be:
                - A string (MeiliSearch filter expression)
                - A dictionary (field-value pairs for filtering)
                - None (no filtering)
            page: The page number to return (1-based)
            size: Number of results per page
            
        Returns:
            Search results from MeiliSearch
        """
        search_params = {
            "page": page,
            "hitsPerPage": size
        }
        
        # Add filters if provided
        if filters is not None:
            if isinstance(filters, dict) and filters:
                # Convert dictionary to MeiliSearch filter string
                filter_parts = []
                
                for field, value in filters.items():
                    if value is None:
                        continue
                        
                    # Handle array values (OR condition between values)
                    if isinstance(value, list) and value:
                        # For array fields, we need to check if each item matches any value in the array
                        sub_parts = []
                        for val in value:
                            if isinstance(val, str):
                                sub_parts.append(f"{field} = '{val}'")
                            else:
                                sub_parts.append(f"{field} = {val}")
                        
                        if sub_parts:
                            filter_parts.append(f"({' OR '.join(sub_parts)})")
                    # Handle field with _gte suffix (greater than or equal)
                    elif field.endswith('_gte'):
                        base_field = field[:-4]  # Remove _gte suffix
                        filter_parts.append(f"{base_field} >= {value}")
                    # Handle field with _lte suffix (less than or equal)
                    elif field.endswith('_lte'):
                        base_field = field[:-4]  # Remove _lte suffix
                        filter_parts.append(f"{base_field} <= {value}")
                    # Handle field with _gt suffix (greater than)
                    elif field.endswith('_gt'):
                        base_field = field[:-3]  # Remove _gt suffix
                        filter_parts.append(f"{base_field} > {value}")
                    # Handle field with _lt suffix (less than)
                    elif field.endswith('_lt'):
                        base_field = field[:-3]  # Remove _lt suffix
                        filter_parts.append(f"{base_field} < {value}")
                    # Handle string values
                    elif isinstance(value, str):
                        filter_parts.append(f"{field} = '{value}'")
                    # Handle other values
                    else:
                        filter_parts.append(f"{field} = {value}")
                
                if filter_parts:
                    filters = " AND ".join(filter_parts)
                    print(f"Converted filter dictionary to string: {filters}")
                else:
                    filters = None
            
            # Add the filter string to search parameters if it's not empty
            if filters:
                search_params["filter"] = filters
        
        # Debug
        print(f"MeiliSearch query: '{query}', params: {search_params}")
        
        return self.client.index(self.index_name).search(query, search_params)

class MeiliHelpers:
    OPERATORS = {"=", "!=", "<=", ">=", "<", ">", "TO", "EXISTS", "IN", "NOT", "IS", "IS NOT"}
    @staticmethod
    def parse_params_filters(params_filters: list):
        filters = ""
        for param_filter in params_filters:
            if 'name' not in param_filter or param_filter['name'] == '': return {'error': True, 'message': "Param filter 'name' is required"}
            if 'value' not in param_filter: return {'error': True, 'message': "Param filter 'value' is required"}
            fname = param_filter.get('name')
            fvalue = param_filter.get('value')
            foperator = param_filter.get('operator') if 'operator' in param_filter and param_filter['operator'] != '' else "="
            fexpression = param_filter.get('expression') if 'expression' in param_filter and param_filter['expression'] != '' else "AND"
            if foperator not in MeiliHelpers.OPERATORS: return {'error': True, 'message': f"Param filter '{fname}' operator not valid"}
            if foperator == 'IN' and isinstance(fvalue, list) is False: return {'error': True, 'message': f"Value of filter '{fname}' must be array"}
            if isinstance(fvalue, str) and fvalue != 'EMPTY': fvalue = f"'{fvalue}'"
            filter_str = "" if filters == "" else f" {fexpression} "
            #if isinstance(fvalue, list): fvalue = f"[{', '.join([repr(v) for v in fvalue])}]"
            filter_str += f"{fname} {foperator} {fvalue}"
            filters += filter_str
        
        return {'error': False, 'filters': filters.strip(" ")}
