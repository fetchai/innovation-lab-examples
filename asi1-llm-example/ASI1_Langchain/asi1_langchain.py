import os
import requests
from typing import Optional, List
from pydantic import Field
from langchain_core.language_models.llms import LLM
from langchain_community.utilities.tavily_search import TavilySearchAPIWrapper
from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_classic.agents import initialize_agent, AgentType
from dotenv import load_dotenv

load_dotenv()


class CustomLLM(LLM):
    api_key: str = Field(...)
    api_url: str = Field(...)
    model: str = Field(default="asi1")
    temperature: float = Field(default=0.7)
    fun_mode: bool = Field(default=False)
    web_search: bool = Field(default=False)
    # Renamed to avoid shadowing parent attributes
    enable_stream: bool = Field(default=False)
    max_tokens: int = Field(default=1024)

    @property
    def _llm_type(self) -> str:
        return "custom_llm"

    def _call(self, prompt: str, stop: Optional[List[str]] = None) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": self.temperature,
            "fun_mode": self.fun_mode,
            "web_search": self.web_search,
            "stream": self.enable_stream,
            "max_tokens": self.max_tokens,
        }
        if stop:
            payload["stop"] = stop

        response = requests.post(self.api_url, headers=headers, json=payload)
        response.raise_for_status()
        response_data = response.json()
        print("API Response:", response_data)  # Debug: inspect the API response
        # Adjust the key ("response") as needed to match your API's actual response format.
        # return response_data.get("response", "")
        return (
            response_data.get("choices", [{}])[0].get("message", {}).get("content", "")
        )


def custom_search_handler(data):
    """
    Uses LangChain to process a search query with the custom LLM.
    Expects a JSON payload with the key "search_query" and returns the result.
    """
    search_query = data.get("search_query")
    if not search_query:
        return {"error": "Missing search query"}

    custom_api_key = os.getenv("ASI_LLM_KEY")
    custom_api_url = "https://api.asi1.ai/v1/chat/completions"
    tavily_api_key = os.getenv("TAVILY_API_KEY")
    print("1: ", custom_api_key)
    print("2: ", custom_api_url)
    print("3: ", tavily_api_key)

    if not custom_api_key or not custom_api_url or not tavily_api_key:
        return {"error": "Missing API keys"}

    try:
        # Initialize your custom LLM
        llm = CustomLLM(api_key=custom_api_key, api_url=custom_api_url, temperature=0.7)
        # Initialize the Tavily search tool
        search = TavilySearchAPIWrapper()
        tavily_tool = TavilySearchResults(
            api_wrapper=search, tavily_api_key=tavily_api_key
        )

        # Initialize the agent with your custom LLM and Tavily search tool
        agent_chain = initialize_agent(
            [tavily_tool],
            llm,
            agent=AgentType.STRUCTURED_CHAT_ZERO_SHOT_REACT_DESCRIPTION,
            verbose=True,
        )
        # Run the agent chain with the search query
        result = agent_chain.run({"input": search_query})
        return {"result": result}
    except Exception as e:
        return {"error": str(e)}


if __name__ == "__main__":
    # Example usage with an input search query.
    input_data = {"search_query": "What is agentverse?"}
    output = custom_search_handler(input_data)
    print("\nFinal Output:")
    print(output)
