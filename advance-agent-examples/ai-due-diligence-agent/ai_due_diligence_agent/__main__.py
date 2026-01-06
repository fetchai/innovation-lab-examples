"""
Main entry point for the AI Due Diligence Analyst with uAgents Chat Protocol.
This exposes the agent on Agentverse for discovery and communication.
"""
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from ai_due_diligence_agent.executor import agent, run_agent


def main():
    """Main entry point."""
    try:
        print("🚀 Starting AI Due Diligence Analyst with uAgents Chat Protocol")
        print(f"📍 Agent Address: {agent.address}")
        print(f"🔌 Agent Port: {agent._port}")
        print("💬 Chat protocol enabled - Ready to receive messages!")
        print("-" * 50)
        run_agent()
    except KeyboardInterrupt:
        print("\n👋 AI Due Diligence Analyst shutdown complete!")
    except Exception as e:
        print(f"❌ Error: {e}")
        raise


if __name__ == "__main__":
    main()
