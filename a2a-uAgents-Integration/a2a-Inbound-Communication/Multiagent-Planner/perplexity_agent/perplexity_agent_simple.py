#!/usr/bin/env python3
"""
Simple Perplexity Agent A2A Adapter

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
        "agent_address": "agent1qgzd0c60d4c5n37m4pzuclv5p9vwsftmfkznksec3drux8qnhmvuymsmshp",
        "name": "Perplexity Search Agent",
        "description": "AI-powered web search and research assistant with real-time information access",
        "skill_tags": ["search", "research", "web", "ai", "information", "news"],
        "port": 9002,
        "host": "localhost"
    }
    
    print(f"🔧 Agent Address: {config['agent_address']}")
    print(f"🏷️  Agent Name: {config['name']}")
    print(f"🌐 Port: {config['port']}")
    print("")
    print("🎯 Features:")
    print("   ✅ No authentication required")
    print("   ✅ Real-time web search")
    print("   ✅ AI-powered research")
    print("   ✅ Cited sources and references")
    print("   ✅ Current information access")
    print("")
    
    # Start adapter - this blocks just like CLI does
    try:
        result = adapter.invoke(config)
        if result.get("success"):
            print("✅ A2A Adapter Started Successfully!")
            print(f"🌐 Endpoint: http://localhost:{config['port']}")
            print("")
            print("🧪 Test with cURL:")
            print("curl -X POST http://localhost:9002 \\")
            print("  -H \"Content-Type: application/json\" \\")
            print("  -d '{")
            print("    \"jsonrpc\": \"2.0\",")
            print("    \"id\": \"perplexity-test-1\",")
            print("    \"method\": \"message/send\",")
            print("    \"params\": {")
            print("      \"message\": {")
            print("        \"role\": \"user\",")
            print("        \"parts\": [{\"kind\": \"text\", \"text\": \"What are the latest developments in AI agents?\"}],")
            print("        \"messageId\": \"msg-1\"")
            print("      },")
            print("      \"contextId\": \"user-research-session\"")
            print("    }")
            print("  }'")
            print("")
            print("🔍 Ready for research queries!")
            print("Press Ctrl+C to stop...")
            
            # This blocks just like the CLI does - uvicorn handles Ctrl+C naturally
            
        else:
            print(f"❌ Failed to start adapter: {result}")
            
    except KeyboardInterrupt:
        print("\n👋 Shutting down...")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    main()
