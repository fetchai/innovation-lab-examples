"""
LLM and Agent construction helpers.
"""

import os
from langchain import hub
from langchain.agents import AgentExecutor, create_openai_functions_agent
from langchain_openai import ChatOpenAI
from typing import Any, Dict
from system_prompt import HUB_PROMPT_NAME


def build_email_agent(tools) -> AgentExecutor:
    prompt = hub.pull(HUB_PROMPT_NAME)
    model_name = os.getenv("OPENAI_MODEL", "gpt-4-turbo")
    llm = ChatOpenAI(model=model_name, temperature=0)
    agent = create_openai_functions_agent(llm, tools, prompt)
    return AgentExecutor(agent=agent, tools=tools, verbose=True, return_intermediate_steps=True)


def run_email_task(agent_executor: AgentExecutor, recipient: str, subject: str, body: str) -> Dict[str, Any]:
    task = (
        f"Send an email to {recipient} with the subject '{subject}' and "
        f"the body '{body}'. Make sure to actually send the email, not create a draft."
    )
    return agent_executor.invoke({"input": task})


def build_fetch_agent(tools) -> AgentExecutor:
    # Reuse the same functions agent prompt
    prompt = hub.pull(HUB_PROMPT_NAME)
    model_name = os.getenv("OPENAI_MODEL", "gpt-4-turbo")
    llm = ChatOpenAI(model=model_name, temperature=0)
    agent = create_openai_functions_agent(llm, tools, prompt)
    return AgentExecutor(agent=agent, tools=tools, verbose=True, return_intermediate_steps=True)


def run_fetch_task(agent_executor: AgentExecutor, max_results: int = 10, label_ids=None) -> Dict[str, Any]:
    label_ids = label_ids or ["INBOX"]
    task = (
        "Fetch the latest emails using the GMAIL_FETCH_EMAILS tool with these parameters: "
        f"ids_only: false, include_payload: true, include_spam_trash: false, "
        f"label_ids: {label_ids}, max_results: {max_results}, user_id: 'me', verbose: true. "
        "Only use the tool; do not summarize; return tool output."
    )
    return agent_executor.invoke({"input": task})


