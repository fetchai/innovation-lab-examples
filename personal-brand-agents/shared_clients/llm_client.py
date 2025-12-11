# llm_config.py
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv

load_dotenv()
shared_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
