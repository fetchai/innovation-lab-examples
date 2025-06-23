from crewai import Agent
from crewai_tools import (
    DirectoryReadTool,
    FileReadTool,
    SerperDevTool,
    WebsiteSearchTool,
    PDFSearchTool
)
import os
os.environ["SERPER_API_KEY"] = "b924f60ae1564e450f297dc464410ff7190abb85"  
class BloodReportAgents:
    def blood_report_analyst(self):
        return Agent(
            role="Senior Blood Report Analyst",
            goal=(
                "Analyze the blood test report and summarize key health indicators with detailed explanations "
                "of their significance and implications. Provide a comprehensive overview of each indicator, "
                "including normal ranges and potential health implications for abnormal results, provided medicine, "
                "and medicine link medications."
            ),
            backstory=(
                "You are an expert medical analyst with over 20 years of experience in interpreting blood test results. "
                "Your precision in identifying health indicators and their implications ensures accurate health insights. "
                "You are adept at translating complex medical data into clear, actionable insights for healthcare "
                "professionals and patients alike."
            ),
            tools=[
                PDFSearchTool(),
                DirectoryReadTool(directory="input")
            ],
            allow_delegation=False,
            verbose=True
        )

    def health_advisor(self):
        return Agent(
            role="Health Advisor",
            goal=(
                "Provide comprehensive health recommendations for each blood test indicator, including what it means, "
                "how to control abnormal results, additional context, dietary advice, exercise routines, potential medications, "
                "and lifestyle changes, with mandatory source citations. Emphasize the importance of consulting healthcare "
                "providers for personalized care. Include related article information and URLs. Citing source URLs is mandatory. "
                "Also provide hospital, clinic, and lab map links according to lab location area city."
            ),
            backstory=(
                "You are a seasoned health advisor who integrates medical data with evidence-based research to deliver "
                "actionable health recommendations. You provide clear explanations and disclaimers for medical advice, "
                "ensuring users understand the importance of consulting healthcare providers for personalized care. "
                "Your expertise lies in translating complex medical information into practical health advice, empowering "
                "individuals to make informed decisions about their health."
            ),
            tools=[
                SerperDevTool(),
                WebsiteSearchTool(),
                FileReadTool(),
                DirectoryReadTool(directory="output")
            ],
            allow_delegation=False,
            verbose=True
        )
