#!/bin/bash

# Scholarship Finder Agent - Startup Script

echo "🎓 Starting Scholarship Finder Agent..."
echo ""

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found!"
    echo "Please run: python3 -m venv venv"
    exit 1
fi

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "❌ .env file not found!"
    echo "Please copy .env.example to .env and add your API keys"
    exit 1
fi

# Activate virtual environment
echo "📦 Activating virtual environment..."
source venv/bin/activate

# Check if dependencies are installed
if ! python -c "import uagents" 2>/dev/null; then
    echo "📥 Installing dependencies..."
    pip install -r requirements.txt
fi

echo "✅ Environment ready!"
echo ""

# Run the agent
echo "🚀 Launching agent..."
echo "📧 Agent will be available via Agentverse mailbox"
echo "💬 Users can chat on ASI-One: https://asi1.ai"
echo ""
echo "Press Ctrl+C to stop"
echo ""

python uagent_bridge.py
