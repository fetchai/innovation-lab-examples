"""
Simple Airbnb Agent A2A Adapter

This mimics the CLI approach: uagents-a2a --agent-address ... --port 9001
No complex signal handling - just like the original CLI.
"""

from uagents_adapter import A2ARegisterTool
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

def main():
    """Start A2A adapter for Airbnb Agent - Simple CLI-like approach."""
    
    print("🏠 Starting Airbnb Agent A2A Adapter (Simple)")
    print("=" * 50)
    
    # Create adapter tool
    adapter = A2ARegisterTool()
    
    # Airbnb Agent configuration - same as CLI
    config = {
        "agent_address": "agent1qv4zyd9sta4f5ksyhjp900k8kenp9vczlwqvr00xmmqmj2yetdt4se9ypat",
        "name": "Airbnb Search Agent",
        "description": "AI-powered vacation rental search and property details assistant",
        "skill_tags": ["airbnb", "vacation", "rental", "travel", "accommodation", "booking"],
        "port": 9001,
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
            print("🧪 Test with cURL:")
            print("curl -X POST http://localhost:9001 \\")
            print("  -H \"Content-Type: application/json\" \\")
            print("  -d '{")
            print("    \"jsonrpc\": \"2.0\",")
            print("    \"id\": \"airbnb-test-1\",")
            print("    \"method\": \"message/send\",")
            print("    \"params\": {")
            print("      \"message\": {")
            print("        \"role\": \"user\",")
            print("        \"parts\": [{\"kind\": \"text\", \"text\": \"Find me vacation rentals in San Francisco for 2 guests\"}],")
            print("        \"messageId\": \"msg-1\"")
            print("      },")
            print("      \"contextId\": \"user-booking-session\"")
            print("    }")
            print("  }'")
            print("")
            print("🏠 Ready for vacation rental queries!")
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
