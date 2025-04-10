from agents import Agent, Runner, function_tool
from app.modules.tenders.schemas import TenderDetail
from app.modules.tenders.services import get_tender_detail
from app.modules.ai_tools.services import answer_tender_question

class AgentTools:
    def __init__(self):
        pass

    @function_tool
    def get_tender_details(self, tender_hash: str) -> TenderDetail:
        """
        Fetch detailed information about a tender from the Neptune RDF graph.
        Returns a TenderDetail object:
        - uri: The URI of the tender
        - identifier: The identifier of the tender
        - title: The title of the tender
        - description: The description of the tender
        - summary: The summary of the tender
        - estimated_value: The estimated value of the tender
        - net_value: The net value of the tender
        - gross_value: The gross value of the tender
        - contract_period: The contract period of the tender
        - planned_period: The planned period of the tender
        - buyer: The buyer of the tender
        - purpose: The purpose of the tender
        - contract_term: The contract term of the tender
        - submission_term: The submission term of the tender
        - additional_information: The additional information of the tender
        - status: The status of the tender
        - procurement_documents: The procurement documents of the tender
        - lots: The lots of the tender
        """
        tender_detail = get_tender_detail(tender_hash)
        return tender_detail

    def answer_tender_question(self, tender_hash: str, question: str) -> str:
        """
        Answer a question about a tender, including information about tender documents with citations.
        """
        return answer_tender_question(tender_hash, question)

    def get_tender_full_summary(self, tender_hash: str) -> str:
        """
        Get a summary of a tender using AI. This is a complete report of the tender,
        including all the information about the tender and attached documents processed by an expert analyst.
        """
        # for developers, this is the ai_document, not this ai_summary,
        # we call it summary since the agent reads the doctype above and its easier to understand.
        pass
