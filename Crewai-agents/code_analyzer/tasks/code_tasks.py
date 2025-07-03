from textwrap import dedent
from crewai import Task

class CodeTasks:
    def analyze_task(self, agent, code_snippet, language):
        return Task(
            description=dedent(f"""
                Analyze the provided {language} code snippet for syntax errors, style violations (e.g., PEP 8 for Python), and potential bugs.
                Provide a detailed report listing issues found, their severity, and recommendations for improvement.

                Code Snippet:
                ```{language}
                {code_snippet}
                ```

                Your final answer must be a detailed report in markdown format, including:
                - Syntax errors (if any)
                - Style violations
                - Potential bugs or logical errors
                - Recommendations for improvement
                - Relevant resources from Medium, StackOverflow, and Dev.to (as markdown links)

                {self.__tip_section()}
            """),
            agent=agent,
            expected_output="Detailed markdown report on code analysis with relevant links",
        )

    def debug_task(self, agent, code_snippet, language, error_log):
        return Task(
            description=dedent(f"""
                Debug the provided {language} code snippet using the provided error log.
                Identify the root cause of the errors and explain why they occur.

                Code Snippet:
                ```{language}
                {code_snippet}
                ```

                Error Log:
                ```
                {error_log}
                ```

                Your final answer must be a detailed report in markdown format, including:
                - Root cause of each error
                - Explanation of why the error occurs
                - Suggested fixes
                - Relevant resources from Medium, StackOverflow, and Dev.to (as markdown links)

                {self.__tip_section()}
            """),
            agent=agent,
            expected_output="Detailed markdown report on debugging results with relevant links",
        )

    def fix_task(self, agent, code_snippet, language, debug_report):
        return Task(
            description=dedent(f"""
                Fix the bugs identified in the provided {language} code snippet based on the debug report.
                Provide the corrected code and explain each fix applied.

                Code Snippet:
                ```{language}
                {code_snippet}
                ```

                Debug Report:
                ```
                {debug_report}
                ```

                Your final answer must include:
                - Corrected code snippet in {language}
                - Explanation of each fix applied
                - Verification that the fixes resolve the issues
                - Relevant resources from Medium, StackOverflow, and Dev.to (as markdown links)

                {self.__tip_section()}
            """),
            agent=agent,
            expected_output="Corrected code snippet and explanation of fixes with relevant links",
        )

    def write_task(self, agent, code_requirements, language):
        return Task(
            description=dedent(f"""
                Generate a {language} code snippet based on the provided requirements.
                Ensure the code is clean, follows best practices (e.g., PEP 8 for Python), and is well-documented.

                Requirements:
                {code_requirements}

                Your final answer must include:
                - Generated code snippet in {language}
                - Explanation of the code structure and key components
                - Relevant resources from Medium, StackOverflow, and Dev.to (as markdown links) related to the code or requirements

                {self.__tip_section()}
            """),
            agent=agent,
            expected_output="Generated code snippet, explanation, and relevant links",
        )

    def __tip_section(self):
        return "Code Analysis " 