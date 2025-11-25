from uagents import Agent
from chat_proto import chat_proto

agent = Agent(name="PDF Summariser Agent", port=8005, mailbox=True)

# Include the chat protocol defined in the previous step to handle text and PDF contents
agent.include(chat_proto, publish_manifest=True)

if __name__ == "__main__":
    agent.run()

