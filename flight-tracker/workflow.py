from agents import WebSearchTool, Agent, ModelSettings, TResponseInputItem, Runner, RunConfig
from openai.types.shared.reasoning import Reasoning
from pydantic import BaseModel

# Tool definitions
web_search_preview = WebSearchTool(
  user_location={
    "type": "approximate",
    "country": None,
    "region": None,
    "city": None,
    "timezone": None
  },
  search_context_size="high"
)
my_agent = Agent(
  name="My agent",
  instructions="""You are FlightStatusAgent. Your job is to fetch today’s live flight status for the flight number mentioned by the user, using Web Search to find up-to-date data (Flightradar24, FlightAware, Flight.info, etc.).

Output format (Markdown only, no citations or notes):
**<Airline> <Flight> — <Day, Date>**  - 

- **Status:** <status>  
- **Route:** <Origin (IATA)> → <Destination (IATA)>   
- **Local Times:**     
- **Departure (scheduled):** <e.g., Oct 13 2025 20:55 EDT (JFK)>     
- **Departure (actual):** <e.g., Oct 13 2025 23:16 EDT (JFK)>     
- **Arrival (scheduled):** <e.g., Oct 15 2025 07:45 NZDT (AKL)>     
- **Arrival (actual):** <if available>   
- **Aircraft:** <model>; registration <reg>   
- **Terminals / Gates / Baggage:** <include any available info>   
- **Sources:**     - [Flightradar24](https://www.flightradar24.com/data/flights/{flight_num})     - [Flight.info](https://www.flight.info/{flight_num}?utm_source=openai) 


Rules:
Never show citations or reference markers.
Show times in local time with 3-letter timezone abbreviation (e.g., PST, EDT, NZDT).
If a field (gate, baggage, actual time, etc.) is missing, omit it entirely — do not guess.
Always include Flightradar24 link with the {flight_num} placeholder at the end.
Keep output concise, factual, and visually clean.
Don’t include internal reasoning, sources list beyond the visible Markdown links, or citations.""",
  model="gpt-5",
  tools=[
    web_search_preview
  ],
  model_settings=ModelSettings(
    store=True,
    reasoning=Reasoning(
      effort="low",
      summary="auto"
    )
  )
)


class WorkflowInput(BaseModel):
  input_as_text: str


# Main code entrypoint
async def run_workflow(workflow_input: WorkflowInput):
  workflow = workflow_input.model_dump()
  conversation_history: list[TResponseInputItem] = [
    {
      "role": "user",
      "content": [
        {
          "type": "input_text",
          "text": workflow["input_as_text"]
        }
      ]
    }
  ]
  my_agent_result_temp = await Runner.run(
    my_agent,
    input=[
      *conversation_history
    ],
    run_config=RunConfig(trace_metadata={
      "__trace_source__": "agent-builder",
      "workflow_id": "wf_68ee256af5f48190a7cb98d6309861eb0e505757706e1cf6"
    })
  )

  conversation_history.extend([item.to_input_item() for item in my_agent_result_temp.new_items])

  my_agent_result = {
    "output_text": my_agent_result_temp.final_output_as(str)
  }
  return my_agent_result


