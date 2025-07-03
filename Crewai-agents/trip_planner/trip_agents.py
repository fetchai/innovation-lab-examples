from crewai import Agent
from langchain_openai import ChatOpenAI


class TripAgents:
    def __init__(self):
        # Initialize the LLM to be used by all agents
        self.llm = ChatOpenAI(model="gpt-4o", temperature=0.7)

    def city_selection_agent(self):
        return Agent(
            role="City Selection Expert",
            goal="Select the best city based on weather, season, and prices ,provied helpfull link news and photos",
            backstory="An expert in analyzing travel data to pick ideal destinations",
            verbose=True,
            llm=self.llm,
        )

    def local_expert(self):
        return Agent(
            role="Local Expert at this city",
            goal="Provide the BEST insights about the selected city with local tips and photos and links",
            backstory="""A knowledgeable local guide with extensive information
        about the city, it's attractions and customs """,
            verbose=True,
            llm=self.llm,
        )

    def travel_concierge(self):
        return Agent(
            role="Amazing Travel Concierge",
            goal="""Create the most amazing travel itineraries with budget and 
        packing suggestions for the city and provied helpfull link news and photos""",
            backstory="""Specialist in travel planning and logistics with 
        decades of experience""",
            verbose=True,
            llm=self.llm,
        )
