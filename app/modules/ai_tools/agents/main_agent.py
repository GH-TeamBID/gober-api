from agents import Agent, Runner, set_tracing_export_api_key, RunContextWrapper
from openai.types.responses import ResponseTextDeltaEvent
from pydantic import BaseModel
import asyncio
from agent_tools import AgentTools
from app.core.config import settings

set_tracing_export_api_key(settings.OPENAI_API_KEY)

class MainAgentInput(BaseModel):
    tender_hash: str
    question: str


class MainAgent:
    def __init__(self):
        self.tools = AgentTools()

    async def run(self, input: MainAgentInput):
        orchestrator_agent = Agent(
            name="Tender assistant",
            instructions= """
            You are a smart and helpful assistant. You answer user questions by
            breaking them down into step by step actions and then perform the necessary
            tool calls to complete the tasks.
            """,
            tools=[self.tools.get_tender_details, self.tools.answer_tender_question, self.tools.get_tender_full_summary],
        )

        result = Runner.run_streamed(orchestrator_agent, input=input)
        async for event in result.stream_events():
            if event.type == "raw_response_event" and isinstance(event.data, ResponseTextDeltaEvent):
                print(event.data.delta, end="", flush=True)


if __name__ == "__main__": # TODO remove in production
    main_agent = MainAgent()
    asyncio.run(main_agent.run(MainAgentInput(tender_hash="123", question="What is the name of the tender?")))
