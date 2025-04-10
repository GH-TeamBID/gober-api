from agents import Agent, Runner, set_tracing_export_api_key, RunContextWrapper
from openai.types.responses import ResponseTextDeltaEvent
from pydantic import BaseModel
from typing import Optional
import asyncio
from agent_tools import AgentTools
from app.core.config import settings

set_tracing_export_api_key(settings.OPENAI_API_KEY)

class MainAgentInput(BaseModel):
    tender_hash: Optional[str] = None
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
            tools=[self.tools.get_tender_details,
                   self.tools.answer_tender_question,
                   self.tools.get_tender_full_summary],
        )

        result = Runner.run_streamed(orchestrator_agent, input=input)
        async for event in result.stream_events():
            if event.type == "raw_response_event" and isinstance(event.data, ResponseTextDeltaEvent):
                print(event.data.delta, end="", flush=True)


if __name__ == "__main__":
    main_agent = MainAgent()
    tender_hash = "2dacf9eb1023f7be51aedf376e476b736b3ecc7e411094629dac0dc97e8f3917"
    asyncio.run(main_agent.run(MainAgentInput(tender_hash=tender_hash, question="What is the name of the tender?")))
