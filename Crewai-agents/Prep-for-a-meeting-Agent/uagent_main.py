#!/usr/bin/env python3
"""Meeting Prep Crew script using CrewAI adapter for uAgents."""

import os
from openai import OpenAI
from typing import Dict, Any
import json
from crewai import Crew
from dotenv import load_dotenv
from uagents_adapter import CrewaiRegisterTool

from agents import MeetingPreparationAgents
from tasks import MeetingPreparationTasks


class MeetingPrepCrew:
    def __init__(self, participants="", context="", objective=""):
        self.participants = participants
        self.context = context
        self.objective = objective

    def parse_input_message(self, message: str) -> Dict[str, str]:
        """
        Parse a natural language message to extract meeting information.
        Uses OpenAI-based intelligent extraction.
        """
        try:
            client = OpenAI()
            
            print(f"Attempting to parse message: {message}")
            
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system", 
                        "content": "You are a helpful assistant that extracts structured information from meeting descriptions. Always respond with valid JSON only."
                    },
                    {
                        "role": "user", 
                        "content": f"""
                        Extract the following information from this meeting description and return as JSON:
                        - participants: array of email addresses found in the text
                        - context: brief summary of the meeting type and context
                        - objective: what the user wants to achieve in the meeting
                        
                        Text: {message}
                        
                        Return format:
                        {{
                            "participants": ["email1@domain.com", "email2@domain.com"],
                            "context": "brief meeting context",
                            "objective": "what user wants to achieve"
                        }}
                        """
                    }
                ],
                temperature=0.1,
                max_tokens=500
            )
            
            print(f"Received response from OpenAI: {response}")
            
            result = json.loads(response.choices[0].message.content)
            
            print(f"Parsed result: {result}")
            
            return {
                "participants": ", ".join(result.get("participants", [])),
                "context": result.get("context", message),
                "objective": result.get("objective", "Prepare thoroughly for the meeting and achieve positive outcomes")
            }
            
        except (Exception, json.JSONDecodeError) as e:
            print(f"Error parsing message with OpenAI: {e}")
            # Fallback to using original message as context
            return {
                "participants": "",
                "context": message,
                "objective": "Prepare thoroughly for the meeting and achieve positive outcomes"
            }

    def run(self):
        """Execute the meeting preparation crew."""
        agents = MeetingPreparationAgents()
        tasks = MeetingPreparationTasks()

        # Create agents
        researcher_agent = agents.research_agent()
        industry_analysis_agent = agents.industry_analysis_agent() 
        meeting_strategist_agent = agents.meeting_strategy_agent()
        briefing_coordinator_agent = agents.summary_and_briefing_agent()

        # Create tasks
        research_task = tasks.research_task(
            researcher_agent,
            self.participants,
            self.context
        )
        
        industry_analysis_task = tasks.industry_analysis_task(
            industry_analysis_agent,
            self.participants,
            self.context
        )
        
        meeting_strategy_task = tasks.meeting_strategy_task(
            meeting_strategist_agent,
            self.context,
            self.objective
        )
        
        summary_task = tasks.summary_and_briefing_task(
            briefing_coordinator_agent,
            self.context,
            self.objective
        )

        # Create crew
        crew = Crew(
            agents=[researcher_agent, industry_analysis_agent, meeting_strategist_agent, briefing_coordinator_agent],
            tasks=[research_task, industry_analysis_task, meeting_strategy_task, summary_task],
            verbose=True
        )

        result = crew.kickoff()
        return result

    def kickoff(self, inputs=None):
        """
        Compatibility method for uAgents integration.
        Accepts a dictionary of inputs or a single message string.
        """
        if inputs:
            if isinstance(inputs, str):
                # Parse natural language input
                parsed = self.parse_input_message(inputs)
                self.participants = parsed["participants"]
                self.context = parsed["context"] 
                self.objective = parsed["objective"]
            elif isinstance(inputs, dict):
                # Handle structured input
                if "message" in inputs:
                    parsed = self.parse_input_message(inputs["message"])
                    self.participants = parsed["participants"]
                    self.context = parsed["context"]
                    self.objective = parsed["objective"]
                else:
                    self.participants = inputs.get("participants", self.participants)
                    self.context = inputs.get("context", self.context)
                    self.objective = inputs.get("objective", self.objective)

        return self.run()


def main():
    """Main function to register Meeting Prep Crew with uAgents."""
    
    # Load environment variables
    load_dotenv()
    api_key = os.getenv("AGENTVERSE_API_KEY")
    openai_api_key = os.getenv("OPENAI_API_KEY")
    exa_api_key = os.getenv("EXA_API_KEY")
    
    if not api_key:
        print("Error: AGENTVERSE_API_KEY not found in environment")
        return
    
    if not openai_api_key:
        print("Error: OPENAI_API_KEY not found in environment")
        return
        
    if not exa_api_key:
        print("Error: EXA_API_KEY not found in environment")
        return

    # Set API keys in environment
    os.environ["OPENAI_API_KEY"] = openai_api_key
    os.environ["EXA_API_KEY"] = exa_api_key

    # Create an instance of MeetingPrepCrew
    meeting_prep_crew = MeetingPrepCrew()

    # Create tool for registering the crew with Agentverse
    register_tool = CrewaiRegisterTool()

    # Define parameters schema - flexible to accept natural language
    query_params = {
        "message": {
            "type": "str", 
            "required": True,
            "description": "Natural language message containing meeting details, participant emails, and objectives"
        }
    }

    # Register the crew with Agentverse
    result = register_tool.run(
        tool_input={
            "crew_obj": meeting_prep_crew,
            "name": "Meeting Preparation AI Assistant",
            "port": 8080,
            "description": "AI assistant that helps you prepare for important meetings by researching participants, analyzing industry trends, and developing strategic talking points.",
            "api_token": api_key,
            "mailbox": True,
            "query_params": query_params,
            "example_query": "I have a meeting with garry@ycombinator.com tomorrow. It's a pitch meeting for YC batch application. My objective is to clearly communicate our problem-solution fit and get valuable feedback on our startup idea.",
        }
    )

    # Print registration result
    print(f"\nMeeting Prep CrewAI agent registration result: {result}")
    
    if isinstance(result, dict) and "address" in result:
        print(f"Agent address: {result['address']}")
        print(f"You can now interact with this agent through ASI:One LLM!")

    # Keep the program running
    try:
        print("\nAgent is now running and discoverable on ASI:One LLM...")
        print("Press Ctrl+C to stop the agent.")
        while True:
            import time
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping agent...")


if __name__ == "__main__":
    main()
