# CrewAI Meeting Preparation Agent on Agentverse

A comprehensive guide to building, integrating, and deploying a CrewAI-powered meeting preparation assistant on Agentverse with natural language input processing via ASI:One LLM.

## 📋 Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Prerequisites](#prerequisites)
4. [Step-by-Step Build Guide](#step-by-step-build-guide)
5. [uAgent Integration](#uagent-integration)
6. [Deployment to Agentverse](#deployment-to-agentverse)
7. [Usage Examples](#usage-examples)
8. [Troubleshooting](#troubleshooting)

## 🎯 Overview

This project demonstrates how to:
- Build a multi-agent CrewAI system with specialized agents
- Integrate external APIs (OpenAI, Exa Search) 
- Wrap CrewAI as a uAgent for Agentverse deployment
- Enable natural language input processing
- Make the agent discoverable on ASI:One LLM

The system processes natural language meeting descriptions and generates comprehensive briefing documents including participant research, industry analysis, and strategic recommendations.

## 🏗️ Architecture

### Core Components

```
┌─────────────────────────────────────────────────────┐
│                   ASI:One LLM                       │
│            (Natural Language Interface)             │
└─────────────────┬───────────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────────┐
│                Agentverse                           │
│              (Agent Discovery)                      │
└─────────────────┬───────────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────────┐
│               uAgent Main                           │
│          (CrewaiRegisterTool)                       │
│                                                     │
│  ┌─────────────────────────────────────────────┐    │
│  │            OpenAI Parser                    │    │
│  │     (Natural Language → Structured)        │    │
│  └─────────────┬───────────────────────────────┘    │
│                │                                    │
│  ┌─────────────▼───────────────────────────────┐    │
│  │           MeetingPrepCrew                   │    │
│  │                                             │    │
│  │  ┌─────────────┬─────────────┬───────────┐  │    │
│  │  │ Research    │ Industry    │ Strategy  │  │    │
│  │  │ Agent       │ Analyst     │ Agent     │  │    │
│  │  └─────────────┴─────────────┴───────────┘  │    │
│  │                     │                       │    │
│  │  ┌─────────────────▼─────────────────────┐  │    │
│  │  │       Briefing Coordinator           │  │    │
│  │  └─────────────────────────────────────────┘  │    │
│  └─────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────┘
```

### Agent Roles

1. **Research Agent**: Investigates meeting participants and companies
2. **Industry Analysis Agent**: Analyzes market trends and opportunities  
3. **Strategy Agent**: Develops talking points and strategic questions
4. **Briefing Coordinator**: Compiles everything into a final briefing

## 🔧 Prerequisites

### Required Accounts & API Keys

1. **OpenAI Account**: [platform.openai.com](https://platform.openai.com)
   - Get API key for GPT-4o model access
   - Used for natural language parsing and CrewAI agents

2. **Exa Account**: [exa.ai](https://exa.ai) 
   - Get API key for web search functionality
   - Used by agents to research participants and companies

3. **Agentverse Account**: [agentverse.ai](https://agentverse.ai)
   - Get API key for agent registration
   - Required to deploy agent for discovery

### Development Environment

```bash
Python 3.8+
pip or conda package manager
```

## 🚀 Step-by-Step Build Guide

### Step 1: Project Setup

```bash
# Create project directory
mkdir meeting-prep-agent
cd meeting-prep-agent

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Create requirements.txt
cat > requirements.txt << EOF
crewai==0.28.8
crewai-tools==0.1.6
exa_py==1.0.9
langchain==0.1.13
uagents-adapter==0.1.0
uagents==0.12.0
openai==1.12.0
python-dotenv==1.0.0
pydantic==2.6.3
EOF

# Install dependencies
pip install -r requirements.txt
```

### Step 2: Environment Configuration

```bash
# Create .env file
cat > .env << EOF
OPENAI_API_KEY=your_openai_api_key_here
EXA_API_KEY=your_exa_api_key_here
AGENTVERSE_API_KEY=your_agentverse_api_key_here
EOF

# Create .env.example for sharing
cat > .env.example << EOF
OPENAI_API_KEY=sk-...
EXA_API_KEY=...
AGENTVERSE_API_KEY=...
EOF
```

### Step 3: Build External Tools

Create `tools/ExaSearchTool.py`:

```python
from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from exa_py import Exa
import os

class ExaAPI:
    _instance = None
    
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            api_key = os.getenv("EXA_API_KEY")
            if not api_key:
                raise ValueError("EXA_API_KEY not found in environment")
            cls._instance = Exa(api_key=api_key)
        return cls._instance

# Define Pydantic schemas for tool arguments
class SearchSchema(BaseModel):
    query: str = Field(description="Search query to find relevant information")

class FindSimilarSchema(BaseModel):
    url: str = Field(description="URL to find similar content for")

class GetContentsSchema(BaseModel):
    url: str = Field(description="URL to get page contents from")

# Tool implementations
class ExaSearchTool(BaseTool):
    name: str = "search"
    description: str = "Search the web for information about people, companies, or topics"
    args_schema: type[BaseModel] = SearchSchema
    
    def _run(self, query: str) -> str:
        try:
            results = ExaAPI.get_instance().search(query, use_autoprompt=True, num_results=3)
            return str(results)
        except Exception as e:
            return f"Error searching: {str(e)}"

class ExaFindSimilarTool(BaseTool):
    name: str = "find_similar"
    description: str = "Find similar content to a given URL"
    args_schema: type[BaseModel] = FindSimilarSchema
    
    def _run(self, url: str) -> str:
        try:
            results = ExaAPI.get_instance().find_similar(url, num_results=3)
            return str(results)
        except Exception as e:
            return f"Error finding similar content: {str(e)}"

class ExaGetContentsTool(BaseTool):
    name: str = "get_contents"
    description: str = "Get the contents of a specific URL"
    args_schema: type[BaseModel] = GetContentsSchema
    
    def _run(self, url: str) -> str:
        try:
            results = ExaAPI.get_instance().get_contents([url])
            return str(results)
        except Exception as e:
            return f"Error getting contents: {str(e)}"

def tools():
    """Return a list of tool instances for use in agents."""
    return [ExaSearchTool(), ExaFindSimilarTool(), ExaGetContentsTool()]
```

### Step 4: Define CrewAI Agents

Create `agents.py`:

```python
from textwrap import dedent
from crewai import Agent
from tools.ExaSearchTool import tools

class MeetingPreparationAgents():
    def research_agent(self):
        return Agent(
            role='Research Specialist',
            goal='Conduct thorough research on people and companies involved in the meeting',
            tools=tools(),
            backstory=dedent("""\
                As a Research Specialist, your mission is to uncover detailed information
                about the individuals and entities participating in the meeting. Your insights
                will lay the groundwork for strategic meeting preparation."""),
            verbose=True
        )

    def industry_analysis_agent(self):
        return Agent(
            role='Industry Analyst',
            goal='Analyze the current industry trends, challenges, and opportunities',
            tools=tools(),
            backstory=dedent("""\
                As an Industry Analyst, your analysis will identify key trends,
                challenges facing the industry, and potential opportunities that
                could be leveraged during the meeting for strategic advantage."""),
            verbose=True
        )

    def meeting_strategy_agent(self):
        return Agent(
            role='Meeting Strategy Advisor',
            goal='Develop talking points, questions, and strategic angles for the meeting',
            tools=tools(),
            backstory=dedent("""\
                As a Strategy Advisor, your expertise will guide the development of
                talking points, insightful questions, and strategic angles
                to ensure the meeting's objectives are achieved."""),
            verbose=True
        )

    def summary_and_briefing_agent(self):
        return Agent(
            role='Briefing Coordinator',
            goal='Compile all gathered information into a concise, informative briefing document',
            tools=tools(),
            backstory=dedent("""\
                As the Briefing Coordinator, your role is to consolidate the research,
                analysis, and strategic insights."""),
            verbose=True
        )
```

### Step 5: Define CrewAI Tasks

Create `tasks.py`:

```python
from textwrap import dedent
from crewai import Task

class MeetingPreparationTasks():
    def research_task(self, agent, participants, context):
        return Task(
            description=dedent(f"""\
                Conduct comprehensive research on each of the individuals and companies
                involved in the upcoming meeting. Gather information on recent
                news, achievements, professional background, and any relevant
                business activities.

                Participants: {participants}
                Meeting Context: {context}"""),
            expected_output=dedent("""\
                A detailed report summarizing key findings about each participant
                and company, highlighting information that could be relevant for the meeting."""),
            async_execution=True,
            agent=agent
        )

    def industry_analysis_task(self, agent, participants, context):
        return Task(
            description=dedent(f"""\
                Analyze the current industry trends, challenges, and opportunities
                relevant to the meeting's context. Consider market reports, recent
                developments, and expert opinions to provide a comprehensive
                overview of the industry landscape.

                Participants: {participants}
                Meeting Context: {context}"""),
            expected_output=dedent("""\
                An insightful analysis that identifies major trends, potential
                challenges, and strategic opportunities."""),
            async_execution=True,
            agent=agent
        )

    def meeting_strategy_task(self, agent, context, objective):
        return Task(
            description=dedent(f"""\
                Develop strategic talking points, questions, and discussion angles
                for the meeting based on the research and industry analysis conducted

                Meeting Context: {context}
                Meeting Objective: {objective}"""),
            expected_output=dedent("""\
                Complete report with a list of key talking points, strategic questions
                to ask to help achieve the meetings objective during the meeting."""),
            agent=agent
        )

    def summary_and_briefing_task(self, agent, context, objective):
        return Task(
            description=dedent(f"""\
                Compile all the research findings, industry analysis, and strategic
                talking points into a concise, comprehensive briefing document for
                the meeting.
                Ensure the briefing is easy to digest and equips the meeting
                participants with all necessary information and strategies.

                Meeting Context: {context}
                Meeting Objective: {objective}"""),
            expected_output=dedent("""\
                A well-structured briefing document that includes sections for
                participant bios, industry overview, talking points, and
                strategic recommendations."""),
            agent=agent
        )
```

## 🔌 uAgent Integration

### Step 6: Create the uAgent Wrapper

Create `uagent_main.py`:

```python
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
    """Meeting Preparation Crew using CrewAI."""
    
    def __init__(self):
        self.participants = ""
        self.context = ""
        self.objective = ""
    
    def parse_input_message(self, message: str) -> Dict[str, str]:
        """
        Parse a natural language message to extract meeting information.
        Uses OpenAI-based intelligent extraction.
        """
        try:
            client = OpenAI()
            
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
            
            result = json.loads(response.choices[0].message.content)
            
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
        Main entry point for uAgents adapter.
        Expected to receive natural language message.
        """
        if isinstance(inputs, dict) and "message" in inputs:
            message = inputs["message"]
        elif isinstance(inputs, str):
            message = inputs
        else:
            return "Please provide a meeting description with participants, context, and objectives."
        
        # Parse the natural language input
        parsed = self.parse_input_message(message)
        
        # Set the parsed values
        self.participants = parsed["participants"]
        self.context = parsed["context"] 
        self.objective = parsed["objective"]
        
        # Run the crew
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
    
    # Set environment variables for CrewAI
    os.environ["OPENAI_API_KEY"] = openai_api_key
    os.environ["EXA_API_KEY"] = exa_api_key
    
    # Create instance of meeting prep crew
    meeting_crew = MeetingPrepCrew()
    
    # Register with uAgents adapter
    tool = CrewaiRegisterTool(
        name="Meeting Preparation AI Assistant",
        crew=meeting_crew,
        parameters=["message"],
        description="AI assistant that prepares comprehensive meeting briefs including participant research, industry analysis, and strategic recommendations based on natural language input.",
        api_key=api_key
    )
    
    result = tool.register()
    print(f"Meeting Prep CrewAI agent registration result: {result}")
    
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
```

## 🚀 Deployment to Agentverse

### Step 7: Deploy Your Agent

```bash
# Ensure all environment variables are set
source .env

# Run the uAgent
python uagent_main.py
```

**Expected Output:**
```
INFO:     [Meeting Preparation AI Assistant]: Starting agent with address: agent1q...
INFO:     [Meeting Preparation AI Assistant]: Agent inspector available at https://agentverse.ai/inspect/...
INFO:     [uagents.registration]: Registration on Almanac API successful
Connecting agent 'Meeting Preparation AI Assistant' to Agentverse...
Successfully connected agent 'Meeting Preparation AI Assistant' to Agentverse

Meeting Prep CrewAI agent registration result: Agent 'Meeting Preparation AI Assistant' registered with address: agent1q... with mailbox (Parameters: message)

Agent is now running and discoverable on ASI:One LLM...
Press Ctrl+C to stop the agent.
```

### Step 8: Verify Deployment

1. **Check Agent Inspector**: Open the inspector URL shown in logs
2. **Verify Agentverse**: Visit [agentverse.ai](https://agentverse.ai) and check your agents
3. **Test on ASI:One**: Your agent should be discoverable on ASI:One LLM

## 💬 Usage Examples

### Natural Language Input

```
"I have a meeting with garry@ycombinator.com tomorrow. It's a pitch meeting for YC batch application. My objective is to clearly communicate our problem-solution fit and get valuable feedback on our startup idea."
```

### Expected Output

```
## Meeting Preparation Brief

**Participant Bios:**
- **Garry Tan**: President and CEO of Y Combinator, known for fostering successful startup growth, especially in tech and AI sectors.

**Industry Overview:**
- Y Combinator is a leading startup accelerator that offers mentorship, funding, and networking opportunities for early-stage startups.
- Current trends emphasize the integration of AI and digital transformation, with economic uncertainties prompting innovation.

**Key Talking Points:**
1. **Problem-Solution Fit**: Clearly articulate the unique problem addressed, supported by relevant case studies/examples.
2. **Market Analysis**: Focus on technology adoption trends and how they create a favorable environment for your startup's innovation.
3. **Unique Value Proposition**: Distinguish your startup by showcasing innovative solutions and highlights of your progress.

**Strategic Questions to Ask:**
1. What do you believe makes a compelling problem-solution fit?
2. What key indicators do you prioritize in evaluating startup applications?
3. How does Y Combinator perceive investments beyond AI?

**Discussion Angles:**
- Highlight the advantages of joining YC for mentorship and guidance.
- Cite examples of successful YC alumni who have excelled through AI innovations.
```

## 🔧 Troubleshooting

### Common Issues

1. **API Key Errors**
   ```bash
   Error: OPENAI_API_KEY not found in environment
   ```
   **Solution**: Check your `.env` file and ensure all API keys are properly set.

2. **Agent Method Errors**
   ```bash
   Error: 'MeetingPreparationAgents' object has no attribute 'industry_analyst_agent'
   ```
   **Solution**: Ensure method names match exactly between `agents.py` and `uagent_main.py`:
   - Use `industry_analysis_agent()` not `industry_analyst_agent()`

3. **OpenAI API Version Errors**
   ```bash
   You tried to access openai.ChatCompletion, but this is no longer supported in openai>=1.0.0
   ```
   **Solution**: Use modern OpenAI client syntax:
   ```python
   from openai import OpenAI
   client = OpenAI()
   response = client.chat.completions.create(...)
   ```

4. **Tool Import Errors**
   ```bash
   ModuleNotFoundError: No module named 'tools.ExaSearchTool'
   ```
   **Solution**: Ensure the `tools/` directory exists and contains `__init__.py`:
   ```bash
   mkdir tools
   touch tools/__init__.py
   ```

5. **Crew Execution Errors**
   ```bash
   Error running crew: ...
   ```
   **Solution**: Check that all agents are created with proper tools and task dependencies are correct.

### Performance Tips

1. **Optimize API Calls**: Use appropriate `max_tokens` limits for OpenAI calls
2. **Handle Rate Limits**: Implement retry logic for API calls
3. **Cache Results**: Consider caching research results for repeated queries
4. **Monitor Costs**: Track API usage for OpenAI and Exa services

## 🎯 Next Steps

### Enhancements You Can Add

1. **Memory System**: Add persistent storage for meeting histories
2. **Calendar Integration**: Connect to Google Calendar or Outlook
3. **Email Integration**: Parse meeting invitations directly
4. **Voice Interface**: Add speech-to-text for voice commands
5. **Report Templates**: Create customizable briefing formats
6. **Team Collaboration**: Multi-user support with shared briefings

### Advanced Features

1. **Real-time Updates**: Monitor participant social media for recent updates
2. **Sentiment Analysis**: Analyze public sentiment about companies/people
3. **Competitive Intelligence**: Research competitor activities
4. **Follow-up Actions**: Generate post-meeting action items
5. **Integration Hub**: Connect with CRM systems and note-taking tools

## 📚 Additional Resources

- [CrewAI Documentation](https://docs.crewai.com/)
- [uAgents Documentation](https://docs.fetch.ai/uAgents/)
- [Agentverse Platform](https://agentverse.ai/)
- [OpenAI API Documentation](https://platform.openai.com/docs/)
- [Exa Search API](https://docs.exa.ai/)

---

**Built with ❤️ using CrewAI and uAgents**
