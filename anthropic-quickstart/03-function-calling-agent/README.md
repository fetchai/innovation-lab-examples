# Claude Function Calling Agent

Build an AI agent that can use tools and take actions using Claude's function calling! 🛠️

## What You'll Build

An AI agent that:
- ✅ Uses Claude's native function calling/tool use
- ✅ Has access to multiple tools (weather, calculator, time, search)
- ✅ Automatically decides which tools to use
- ✅ Chains multiple function calls together
- ✅ Returns results in conversational format
- ✅ Works seamlessly with ASI One

## 🎯 Key Concept: Function Calling

**Function calling** (also called "tool use") lets Claude:
1. **Understand** when a user needs external information or actions
2. **Choose** the right tool for the job
3. **Extract** the necessary parameters
4. **Execute** the function
5. **Use** the results to answer the user

**Example:**
```
User: "What's the weather in Tokyo and what time is it there?"

Claude thinks:
- Needs weather → calls get_weather(city="Tokyo")
- Needs time → calls get_current_time(timezone="Asia/Tokyo")
- Gets results → formats nice response

Claude: "In Tokyo, it's currently 72°F and clear. 
        The local time is 10:30 PM JST."
```

## Prerequisites

- Python 3.9+
- Anthropic API key (same from Guide 01)
- Completed Guide 01 (Basic Claude Agent)

## Quick Start

### Step 1: Install Dependencies

```bash
cd anthropic-quickstart/03-function-calling-agent

# Use existing venv or create new one
source ../01-basic-claude-agent/venv/bin/activate

# Install packages (includes pytz for timezones)
pip install -r requirements.txt
```

### Step 2: Run the Agent

```bash
python claude_function_agent.py
```
### You will see an inspector link, which you can open on your browser and connect the mailbox.

You should see:

```
🛠️ Starting Claude Function Calling Agent...
📍 Agent address: agent1q...
✅ Claude Function Calling API configured
   Using model: claude-3-5-sonnet-20241022

🔧 Available Tools:
   • get_weather: Get current weather information for a specific city...
   • calculate: Perform mathematical calculations...
   • get_current_time: Get the current date and time...
   • search_web: Search the web for information...

🎯 Example Queries:
   • What's the weather in San Francisco?
   • Calculate 15 * 23 + 100
   • What time is it in Tokyo?
   • Search for latest AI news

✅ Agent is running!
```

## Testing the Agent

### Via ASI One

1. Go to [https://asi1.ai](https://asi1.ai)
2. Find your agent
3. Try these queries!

### Example Queries

**Weather:**
```
What's the weather in San Francisco?
```

```
How's the weather in London? Give me celsius please
```

**Calculator:**
```
Calculate 15 * 23 + 100
```

```
What's the square root of 144?
```

```
Calculate 2 to the power of 8
```

**Time:**
```
What time is it in Tokyo?
```

```
What's the current time in New York?
```

**Search:**
```
Search for latest AI news
```

```
Find information about quantum computing
```

**Multi-tool (Complex!):**
```
What's the weather in Paris and what time is it there?
```

```
Calculate 50 * 20, then tell me the weather in that temperature
```

## Available Tools

### 1. get_weather
**Get weather for any city**

Parameters:
- `city` (required): City name
- `units` (optional): "celsius" or "fahrenheit" (default)

Example:
```
"What's the weather in Tokyo?"
→ Calls get_weather(city="Tokyo", units="fahrenheit")
```

### 2. calculate
**Perform math calculations**

Parameters:
- `expression` (required): Math expression to evaluate

Supports:
- Basic math: `+`, `-`, `*`, `/`, `**` (power)
- Functions: `sqrt()`, `sin()`, `cos()`, `log()`, `exp()`
- Constants: `pi`, `e`

Example:
```
"Calculate sqrt(16) + 2 ** 3"
→ Calls calculate(expression="sqrt(16) + 2 ** 3")
→ Result: 12.0
```

### 3. get_current_time
**Get current date/time in any timezone**

Parameters:
- `timezone` (optional): Timezone name or "UTC"

Example:
```
"What time is it in London?"
→ Calls get_current_time(timezone="Europe/London")
```

Common timezones:
- `America/New_York`
- `Europe/London`
- `Asia/Tokyo`
- `Australia/Sydney`
- `UTC`

### 4. search_web
**Search the web (mock implementation)**

Parameters:
- `query` (required): Search query
- `num_results` (optional): Number of results (1-10)

Example:
```
"Search for Python tutorials"
→ Calls search_web(query="Python tutorials", num_results=5)
```

**Note:** Currently returns mock data. Replace with real search API in production!

## How It Works

### The Function Calling Flow

```
User sends query
    ↓
Agent receives message
    ↓
Call Claude with tools definition
    ↓
Claude analyzes query
    ↓
    ├─ No tools needed → Returns answer directly
    │
    └─ Tools needed:
        ↓
        Claude returns tool_use blocks
        ↓
        Agent executes tool(s)
        ↓
        Returns results to Claude
        ↓
        Claude uses results → Returns final answer
        ↓
Agent sends response to user
```

### Code Walkthrough

**1. Define Tools**

```python
TOOLS = [
    {
        "name": "get_weather",
        "description": "Get current weather for a city",
        "input_schema": {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "City name"},
                "units": {"type": "string", "enum": ["celsius", "fahrenheit"]}
            },
            "required": ["city"]
        }
    },
    # ... more tools
]
```

**2. Implement Tool Functions**

```python
def get_weather(city: str, units: str = "fahrenheit") -> dict:
    """Actual implementation of the tool"""
    # ... fetch weather data
    return {
        "city": city,
        "temperature": "65°F",
        "condition": "Partly Cloudy"
    }
```

**3. Call Claude with Tools**

```python
response = client.messages.create(
    model=MODEL_NAME,
    tools=TOOLS,  # ← Pass tools here
    messages=[{
        "role": "user",
        "content": user_text
    }]
)
```

**4. Handle Tool Use**

```python
if response.stop_reason == "tool_use":
    # Claude wants to use tools
    for tool_use in response.content:
        if tool_use.type == "tool_use":
            tool_name = tool_use.name
            tool_input = tool_use.input
            
            # Execute the tool
            result = TOOL_FUNCTIONS[tool_name](**tool_input)
            
            # Return result to Claude
            # ... (see code for full implementation)
```

## Multi-Step Function Calling

Claude can chain multiple tools together!

**Example:**

```
User: "What's 10 + 15, and what's the weather where that temperature is common?"

Step 1: Claude calls calculate(expression="10 + 15")
        → Result: 25

Step 2: Claude processes result, calls get_weather(city="Miami")
        → Result: 75°F, Sunny

Step 3: Claude combines results:
        "10 + 15 equals 25. That's quite cool! 
         In Miami, where temperatures are typically warm (75°F), 
         the weather is currently sunny."
```

The agent handles this automatically with a loop that continues until Claude provides a final answer!

## Adding Your Own Tools

### Step 1: Define the Tool

Add to `TOOLS` list:

```python
{
    "name": "get_stock_price",
    "description": "Get current stock price for a company",
    "input_schema": {
        "type": "object",
        "properties": {
            "symbol": {
                "type": "string",
                "description": "Stock ticker symbol (e.g., AAPL, GOOGL)"
            }
        },
        "required": ["symbol"]
    }
}
```

### Step 2: Implement the Function

```python
def get_stock_price(symbol: str) -> dict:
    """Get stock price from API"""
    # Call your stock API here
    # For example: Alpha Vantage, Yahoo Finance, etc.
    
    return {
        "symbol": symbol,
        "price": 150.25,
        "change": "+2.5%",
        "success": True
    }
```

### Step 3: Register the Function

```python
TOOL_FUNCTIONS = {
    "get_weather": get_weather,
    "calculate": calculate,
    "get_current_time": get_current_time,
    "search_web": search_web,
    "get_stock_price": get_stock_price  # ← Add here
}
```

That's it! Claude can now use your tool.

## Real API Integration

### Replace Mock Weather with Real API

```python
def get_weather(city: str, units: str = "fahrenheit") -> dict:
    """Get real weather from OpenWeatherMap"""
    api_key = os.getenv("OPENWEATHER_API_KEY")
    url = f"http://api.openweathermap.org/data/2.5/weather"
    
    params = {
        "q": city,
        "appid": api_key,
        "units": "imperial" if units == "fahrenheit" else "metric"
    }
    
    response = requests.get(url, params=params)
    data = response.json()
    
    return {
        "city": city,
        "temperature": f"{data['main']['temp']}°{units[0].upper()}",
        "condition": data['weather'][0]['description'].title(),
        "humidity": f"{data['main']['humidity']}%",
        "wind_speed": f"{data['wind']['speed']} mph"
    }
```

### Replace Mock Search with DuckDuckGo

```python
from duckduckgo_search import DDGS

def search_web(query: str, num_results: int = 5) -> dict:
    """Real web search using DuckDuckGo"""
    ddgs = DDGS()
    results = list(ddgs.text(query, max_results=num_results))
    
    return {
        "query": query,
        "results": [
            {
                "title": r["title"],
                "snippet": r["body"],
                "url": r["href"]
            }
            for r in results
        ],
        "num_results": len(results),
        "success": True
    }
```

## Tool Ideas to Implement

### Data & Information
- 📊 **Stock prices** - Financial data
- 📰 **News headlines** - Latest news
- 🌐 **Wikipedia lookup** - Knowledge base
- 📈 **Crypto prices** - Cryptocurrency data
- 🗺️ **Maps/Directions** - Location services

### Productivity
- 📧 **Send email** - Email integration
- 📅 **Calendar** - Schedule management
- 📝 **Notes** - Save information
- ✅ **Tasks** - Todo management

### Content
- 🖼️ **Image generation** - Create images (combine with Gemini!)
- 📄 **PDF creation** - Generate documents
- 🎵 **Music info** - Song/artist lookup
- 🎬 **Movie data** - Film information

### Technical
- 💾 **Database query** - SQL execution
- 🌐 **API calls** - External services
- 📦 **Package info** - npm/PyPI lookup
- 🐛 **GitHub** - Repository actions

### Smart Home (if you have devices!)
- 💡 **Lights** - Control smart lights
- 🌡️ **Thermostat** - Temperature control
- 🔒 **Locks** - Security systems

## Error Handling

The agent handles errors gracefully:

```python
try:
    result = TOOL_FUNCTIONS[tool_name](**tool_input)
    return json.dumps(result)
except Exception as e:
    return json.dumps({
        "error": str(e),
        "success": False
    })
```

Claude receives the error and can:
- Retry with different parameters
- Ask the user for clarification
- Provide an alternative solution

## Best Practices

### 1. Clear Tool Descriptions
```python
"description": "Get current weather for a city. Returns temp, conditions, humidity, wind."
# ✅ Specific and helpful

"description": "Weather"
# ❌ Too vague
```

### 2. Validate Input
```python
def calculate(expression: str) -> dict:
    if len(expression) > 100:
        return {"error": "Expression too long", "success": False}
    # ... rest of function
```

### 3. Return Consistent Format
```python
# Always include success flag
return {
    "data": result,
    "success": True
}

# Or for errors
return {
    "error": "Something went wrong",
    "success": False
}
```

### 4. Set Iteration Limits
```python
max_iterations = 5  # Prevent infinite loops
```

### 5. Log Tool Calls
```python
ctx.logger.info(f"⚙️ Executing tool: {tool_name}")
ctx.logger.info(f"✅ Tool result: {result[:100]}...")
```

## Troubleshooting

### "Tool not found"
- Check tool name spelling in `TOOLS` and `TOOL_FUNCTIONS`
- Ensure they match exactly

### "Tool returns error"
- Check function implementation
- Validate input parameters
- Test function independently

### "Claude doesn't use tools"
- Make tool descriptions clearer
- Ensure query requires the tool
- Check if tools are passed to API call

### "Max iterations reached"
- Reduce complexity of query
- Check for loops in tool calls
- Increase `max_iterations` if needed

## Cost Considerations

**Function calling costs:**
- Input tokens: Tool definitions + messages
- Output tokens: Responses + tool use blocks
- Tool execution: Free (runs locally)

**Typical costs:**
- Simple query with 1 tool: ~$0.001
- Complex query with multiple tools: ~$0.003-0.005

Still very affordable!

## Next Steps

1. ✅ **Test all tools** - Try each function
2. 🔧 **Add real APIs** - Replace mock implementations
3. 🆕 **Create custom tools** - Build your own
4. 🔗 **Combine agents** - Use with vision/text agents
5. 🚀 **Deploy** - Make it production-ready

## Resources

- [Claude Tool Use Docs](https://docs.anthropic.com/claude/docs/tool-use)
- [Function Calling Guide](https://docs.anthropic.com/claude/docs/tool-use-examples)
- [Best Practices](https://docs.anthropic.com/claude/docs/tool-use-best-practices)

## What's Next?

👉 **Guide 04: Multi-Agent Systems** - Connect multiple agents together! (Coming Soon)

---

**Ready to give Claude superpowers? Start calling functions!** 🛠️✨
