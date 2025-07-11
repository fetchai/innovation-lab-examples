#!/usr/bin/env python3
"""
Simple Finance Agent A2A Adapter

This mimics the CLI approach: uagents-a2a --agent-address ... --port 9002
No complex signal handling - just like the original CLI.
"""

from uagents_adapter import A2ARegisterTool
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

def main():
    """Start A2A adapter for Perplexity Agent - Simple CLI-like approach."""
    
    print("🔍 Starting Perplexity Agent A2A Adapter (Simple)")
    print("=" * 50)
    
    # Create adapter tool
    adapter = A2ARegisterTool()
    
    # Perplexity Agent configuration - same as CLI
    config = {
        "agent_address": "agent1qdv2qgxucvqatam6nv28qp202f3pw8xqpfm8man6zyegztuzd2t6yem9evl",
        "name": "Finance Q&A Agent",
        "description": "AI-powered financial advisor and Q&A assistant for investment, budgeting, and financial planning guidance",
        "skill_tags": ["finance", "investment", "budgeting", "financial_planning", "assistance"],
        "port": 9009,
        "host": "localhost"
    }
    
    print(f"🔧 Agent Address: {config['agent_address']}")
    print(f"🏷️  Agent Name: {config['name']}")
    print(f"🌐 Port: {config['port']}")
    print("")
    
    
    # Start adapter - this blocks just like CLI does
    try:
        result = adapter.invoke(config)
        if result.get("success"):
            print("✅ A2A Adapter Started Successfully!")
            print(f"🌐 Endpoint: http://localhost:{config['port']}")
            print("")
            
            # This blocks just like the CLI does - uvicorn handles Ctrl+C naturally
            
        else:
            print(f"❌ Failed to start adapter: {result}")
            
    except KeyboardInterrupt:
        print("\n👋 Shutting down...")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    main()
