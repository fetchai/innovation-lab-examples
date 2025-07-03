#!/usr/bin/env python3
"""Code Analyzer script using CrewAI adapter for uAgents."""

import os
from crewai import Crew
from dotenv import load_dotenv
from uagents_adapter import CrewaiRegisterTool
from agents.code_agents import CodeAgents
from tasks.code_tasks import CodeTasks

class CodeAnalyzerCrew:
    def __init__(self, code_snippet="", language="python", error_log="", code_requirements=""):
        self.code_snippet = code_snippet
        self.language = language
        self.error_log = error_log
        self.code_requirements = code_requirements

    def validate_inputs(self):
        """Validate input parameters."""
        if not self.code_snippet and not self.code_requirements:
            raise ValueError("Either code_snippet or code_requirements must be provided")
        if not self.language:
            raise ValueError("Language must be specified")
        if self.language.lower() not in ["python", "javascript", "java",]:  
            raise ValueError(f"Unsupported language: {self.language}")

    def run(self):
        self.validate_inputs()
        agents = CodeAgents()
        tasks = CodeTasks()

        analyzer_agent = agents.code_analyzer_agent()
        debug_agent = agents.debug_agent()
        fixer_agent = agents.bug_fixer_agent()
        writer_agent = agents.code_writer_agent()

        task_list = []
        if self.code_requirements:
            write_task = tasks.write_task(writer_agent, self.code_requirements, self.language)
            task_list.append(write_task)
        if self.code_snippet:
            analyze_task = tasks.analyze_task(analyzer_agent, self.code_snippet, self.language)
            debug_task = tasks.debug_task(debug_agent, self.code_snippet, self.language, self.error_log)
            fix_task = tasks.fix_task(fixer_agent, self.code_snippet, self.language, debug_task.expected_output)
            task_list.extend([analyze_task, debug_task, fix_task])

        crew = Crew(
            agents=[analyzer_agent, debug_agent, fixer_agent, writer_agent],
            tasks=task_list,
            verbose=False,  # Reduced verbosity for production
        )

        result = crew.kickoff()
        return result

    def kickoff(self, inputs=None):
        """Compatibility method for uAgents integration."""
        if inputs:
            self.code_snippet = inputs.get("code_snippet", self.code_snippet)
            self.language = inputs.get("language", self.language)
            self.error_log = inputs.get("error_log", self.error_log)
            self.code_requirements = inputs.get("code_requirements", self.code_requirements)
        return self.run()

def main():
    """Main function to demonstrate Code Analyzer with CrewAI adapter."""
    load_dotenv()
    api_key = os.getenv("AGENTVERSE_API_KEY")
    openai_api_key = os.getenv("OPENAI_API_KEY")

    if not api_key:
        raise EnvironmentError(
            "AGENTVERSE_API_KEY not found. Please set it in .env file or environment. "
            "Get your key from https://agentverse.ai"
        )
    if not openai_api_key:
        raise EnvironmentError(
            "OPENAI_API_KEY not found. Please set it in .env file or environment. "
            "Get your key from https://platform.openai.com"
        )

    os.environ["OPENAI_API_KEY"] = openai_api_key

    code_analyzer_crew = CodeAnalyzerCrew()

    register_tool = CrewaiRegisterTool()

    query_params = {
        "code_snippet": {"type": "str", "required": False},
        "language": {"type": "str", "required": True},
        "error_log": {"type": "str", "required": False},
        "code_requirements": {"type": "str", "required": False},
    }

    try:
        result = register_tool.run(
            tool_input={
                "crew_obj": code_analyzer_crew,
                "name": "Code Analyzer Crew AI Agent",
                "port": 8043,
                "description": "A CrewAI agent that writes, analyzes, debugs, and fixes code",
                "api_token": api_key,
                "mailbox": True,
                "query_params": query_params,
            }
        )
        print(f"\nCrewAI agent registration result: {result}")
    except Exception as e:
        print(f"Error registering agent: {str(e)}")
        return

    try:
        while True:
            import time
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nExiting...")

if __name__ == "__main__":
    main()