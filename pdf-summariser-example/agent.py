from dotenv import load_dotenv
from uagents import Agent

# Load .env before importing chat_proto: utils.py reads ASI_ONE_API_KEY at call
# time, but keeping this first means every module sees the same environment.
load_dotenv()

from chat_proto import chat_proto  # noqa: E402

agent = Agent(name="PDF Summariser Agent", port=8005, mailbox=True)

# Include the chat protocol defined in the previous step to handle text and PDF contents
agent.include(chat_proto, publish_manifest=True)

if __name__ == "__main__":
    agent.run()
