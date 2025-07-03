#!/usr/bin/env python3
"""Trip Planner script using CrewAI adapter for uAgents."""

import os

from crewai import Crew
from dotenv import load_dotenv
from uagents_adapter import CrewaiRegisterTool

from trip_agents import TripAgents
from trip_tasks import TripTasks


class TripCrew:
    def __init__(self, origin, cities, date_range, interests):
        self.cities = cities
        self.origin = origin
        self.interests = interests
        self.date_range = date_range

    def run(self):
        agents = TripAgents()
        tasks = TripTasks()

        city_selector_agent = agents.city_selection_agent()
        local_expert_agent = agents.local_expert()
        travel_concierge_agent = agents.travel_concierge()

        identify_task = tasks.identify_task(
            city_selector_agent,
            self.origin,
            self.cities,
            self.interests,
            self.date_range,
        )
        gather_task = tasks.gather_task(local_expert_agent, self.origin, self.interests, self.date_range)
        plan_task = tasks.plan_task(travel_concierge_agent, self.origin, self.interests, self.date_range)

        crew = Crew(
            agents=[city_selector_agent, local_expert_agent, travel_concierge_agent],
            tasks=[identify_task, gather_task, plan_task],
            verbose=True,
        )

        result = crew.kickoff()
        return result

    def kickoff(self, inputs=None):
        """
        Compatibility method for uAgents integration.
        Accepts a dictionary of inputs and calls run() with them.
        """
        if inputs:
            self.origin = inputs.get("origin", self.origin)
            self.cities = inputs.get("cities", self.cities)
            self.date_range = inputs.get("date_range", self.date_range)
            self.interests = inputs.get("interests", self.interests)

        return self.run()


def main():
    """Main function to demonstrate Trip Planner with CrewAI adapter."""

    # Load API key from environment
    load_dotenv()
    api_key = os.getenv("AV_API_KEY")
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("Error: AV_API_KEY not found in environment")
        return

    if not openai_api_key:
        print("Error: OPENAI_API_KEY not found in environment")
        return

    # Set OpenAI API key in environment
    os.environ["OPENAI_API_KEY"] = openai_api_key

    # Create an instance of TripCrew with default empty values
    trip_crew = TripCrew("", "", "", "")

    # Create tool for registering the crew with Agentverse
    register_tool = CrewaiRegisterTool()

    # Define parameters schema for the trip planner
    query_params = {
        "origin": {"type": "str", "required": True},
        "cities": {"type": "str", "required": True},
        "date_range": {"type": "str", "required": True},
        "interests": {"type": "str", "required": True},
    }

    # Register the crew with parameter schema
    result = register_tool.run(
        tool_input={
            "crew_obj": trip_crew,
            "name": "Trip Planner Crew AI Agent adapters testing",
            "port": 8033,
            "description": "A CrewAI agent that helps plan trips based on preferences",
            "api_token": api_key,
            "mailbox": True,
            "query_params": query_params,
            "example_query": "Plan a trip from New York to Paris in June, I'm interested in art and history other than museums.",
            "ai_agent_address": "agent1q0h70caed8ax769shpemapzkyk65uscw4xwk6dc4t3emvp5jdcvqs9xs32y"
        }
    )

    # Get the agent address from the result
    if isinstance(result, dict) and "address" in result:
        result["address"]

    print(f"\nCrewAI agent registration result: {result}")

    # Keep the program running
    try:
        while True:
            import time

            time.sleep(1)
    except KeyboardInterrupt:
        print("\nExiting...")


if __name__ == "__main__":
    main()
