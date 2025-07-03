from crewai import Agent
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate

class CodeAgents:
    def __init__(self):
        # Initialize the LLM with enhanced prompt for fetching relevant links
        self.llm = ChatOpenAI(
            model="gpt-4o",
            temperature=0.7,
            # Add system prompt to include relevant links
            system_prompt=PromptTemplate.from_template("""
                You are an expert code assistant. For every task, provide accurate and high-quality code or analysis. 
                Additionally, include relevant resources from Medium, StackOverflow, and Dev.to related to the query or code.
                Format links as markdown: [Source Title](URL).
                Ensure all code is syntactically correct and follows best practices (e.g., PEP 8 for Python).
            """)
        )

    def code_analyzer_agent(self):
        return Agent(
            role="Code Analyzer",
            goal="Analyze code for syntax errors, style violations, and potential bugs",
            backstory="An expert in code quality assurance with deep knowledge of Python and coding standards",
            verbose=True,
            llm=self.llm,
        )

    def debug_agent(self):
        return Agent(
            role="Debug Specialist",
            goal="Identify and diagnose bugs by analyzing error logs and code behavior",
            backstory="A seasoned debugger skilled in tracing errors and understanding runtime issues",
            verbose=True,
            llm=self.llm,
        )

    def bug_fixer_agent(self):
        return Agent(
            role="Bug Fixer",
            goal="Propose and apply fixes to identified bugs, ensuring code functionality",
            backstory="An experienced developer specializing in writing robust, bug-free code",
            verbose=True,
            llm=self.llm,
        )

    def code_writer_agent(self):
        return Agent(
            role="Code Writer",
            goal="Generate high-quality code based on user requirements",
            backstory="A skilled developer proficient in writing clean, efficient, and well-documented code across multiple languages",
            verbose=True,
            llm=self.llm,
        )