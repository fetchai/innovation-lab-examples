#!/usr/bin/env python3
"""Blood Report Analysis with CrewAI and uAgents Adapter."""

import os
import shutil
from crewai import Crew
from dotenv import load_dotenv
from uagents_adapter import CrewaiRegisterTool
from pdf_downloader import download_pdf_from_drive
from pdf_to_text import pdf_to_text

from agents import BloodReportAgents  
from tasks import BloodReportTasks    

load_dotenv()

class BloodReportCrew:
    def __init__(self, drive_link, text_file):
        self.drive_link = drive_link
        self.text_file = text_file or "input/blood_report.txt"  

    def run(self):
        # Validate inputs
        if not self.drive_link.startswith("https://drive.google.com"):
            return "Error: Invalid Google Drive link."

        # Download and convert PDF
        pdf_path = "input/blood_report.pdf"
        os.makedirs("input", exist_ok=True)
        os.makedirs("output", exist_ok=True)
        download_pdf_from_drive(self.drive_link, pdf_path)
        pdf_to_text(pdf_path, self.text_file)

        # Set up agents and tasks
        agents = BloodReportAgents()
        tasks = BloodReportTasks()

        analyst = agents.blood_report_analyst()
        advisor = agents.health_advisor()

        analyze_task = tasks.analyze_blood_report(analyst, pdf_path)
        recommend_task = tasks.generate_recommendations(advisor, [analyze_task])

        # Create and run crew
        crew = Crew(
            agents=[analyst, advisor],
            tasks=[analyze_task, recommend_task],
            verbose=True
        )
        crew.kickoff()

        # Read summary and recommendations as Markdown
        summary_path = "output/blood_report_summary.md"
        recommendations_path = "output/health_recommendations.md"
        summary_md = ""
        recommendations_md = ""

        # Check if files exist and contain valid content
        try:
            if os.path.exists(summary_path) and os.path.getsize(summary_path) > 0:
                with open(summary_path, 'r', encoding='utf-8') as f:
                    summary_md = f.read().strip()
                    if not summary_md:
                        return f"Error: {summary_path} is empty"
            else:
                return f"Error: {summary_path} does not exist or is empty"

            if os.path.exists(recommendations_path) and os.path.getsize(recommendations_path) > 0:
                with open(recommendations_path, 'r', encoding='utf-8') as f:
                    recommendations_md = f.read().strip()
                    if not recommendations_md:
                        return f"Error: {recommendations_path} is empty"
            else:
                return f"Error: {recommendations_path} does not exist or is empty"

        except Exception as e:
            return f"Error reading output files: {str(e)}"

        # Prepare final response
        response = f"""

Blood Report Analysis Agent Powered by Fetch.ai Innovation Lab


## Summary
{summary_md}

## Recommendations
{recommendations_md}
        """

        # Delete all files in input and output directories, and full db directory
        try:
            for dir_path in ["input", "output"]:
                if os.path.exists(dir_path):
                    for file_name in os.listdir(dir_path):
                        file_path = os.path.join(dir_path, file_name)
                        if os.path.isfile(file_path):
                            os.remove(file_path)
            if os.path.exists("db"):
                shutil.rmtree("db")
        except Exception as e:
            return f"Error deleting files or directory: {str(e)}\n{response}"

        return response

    def kickoff(self, inputs=None):
        """Compatibility method for uAgents integration."""
        if inputs:
            self.drive_link = inputs.get("drive_link", self.drive_link)
            self.text_file = inputs.get("text_file", self.text_file)
        return self.run()

def main():
    """Main function to demonstrate Blood Report Analysis with uAgents adapter."""
    api_key = os.getenv("AGENTVERSE_API_KEY")
    openai_api_key = os.getenv("OPENAI_API_KEY")
    serper_api_key = os.getenv("SERPER_API_KEY")

    if not all([api_key, openai_api_key, serper_api_key]):
        print("Error: Missing required API keys in environment")
        return

    os.environ["OPENAI_API_KEY"] = openai_api_key
    os.environ["SERPER_API_KEY"] = serper_api_key


    crew = BloodReportCrew(
        drive_link="",
        text_file="input/blood_report.txt"
    )

    register_tool = CrewaiRegisterTool()
    query_params = {
        "drive_link": {"type": "str", "required": True},
        "text_file": {"type": "str", "required": False}
    }

    result = register_tool.run(
        tool_input={
            "crew_obj": crew,
            "name": "Blood Report Analysis Crew AI",
            "port": 8026,
            "description": "A CrewAI agent for analyzing blood reports and providing detailed health recommendations, powered by Innovation Lab",
            "api_token": api_key,
            "mailbox": True,
            "query_params": query_params,
            # "example_query": "Analyze a blood report from https://drive.google.com/file/d/1LQYFaXJ9sFTYi4pW4pis5Ln-xzp0jRLq/view?usp=sharing"
        }
    )

    print(f"\nCrewAI agent registration result: {result}")

    try:
        while True:
            import time
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nExiting...")

if __name__ == "__main__":
    main()