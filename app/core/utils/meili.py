import meilisearch
from app.core.utils.helpers import Envs

class MeiliClient:
    # docs: https://www.meilisearch.com/docs/reference/api/documents
    def __init__(self, index_name: str, host: str = "", api_key: str = ""):
        if host == '': host = Envs.get('MEILI_HOST')
        if api_key == '': api_key = Envs.get('MEILI_KEY') if Envs.get('MEILI_KEY') != '' else None
        self.client = meilisearch.Client(host, api_key)
        #if index_name != '': 
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

    def search(self, query, page:int = 1, filters :str | None = None, limit: int | None = 20, hitsPerPage: int = 20):
        return self.client.index(self.index_name).search(query, 
            {"filter": filters, "limit": limit, "page": page, "hitsPerPage": hitsPerPage}
        )

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
