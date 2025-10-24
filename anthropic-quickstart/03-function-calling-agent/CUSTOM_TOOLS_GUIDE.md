# Custom Tools Guide

Learn how to add your own tools/functions to the Claude Function Calling Agent! 🔧

## Quick Reference

**3 steps to add any tool:**
1. Define the tool schema
2. Implement the function
3. Register it in `TOOL_FUNCTIONS`

## Step-by-Step Example

Let's add a **cryptocurrency price checker**!

### Step 1: Define Tool Schema

Add to the `TOOLS` list in `claude_function_agent.py`:

```python
{
    "name": "get_crypto_price",
    "description": "Get current cryptocurrency price in USD. Supports Bitcoin, Ethereum, and other major cryptocurrencies.",
    "input_schema": {
        "type": "object",
        "properties": {
            "symbol": {
                "type": "string",
                "description": "Cryptocurrency symbol (e.g., BTC, ETH, SOL, DOGE)"
            },
            "currency": {
                "type": "string",
                "description": "Target currency (USD, EUR, GBP)",
                "default": "USD"
            }
        },
        "required": ["symbol"]
    }
}
```

### Step 2: Implement the Function

Add the implementation (mock version first):

```python
def get_crypto_price(symbol: str, currency: str = "USD") -> dict:
    """Get cryptocurrency price (mock implementation)"""
    
    # Mock prices for demo
    mock_prices = {
        "BTC": 45000.00,
        "ETH": 2500.00,
        "SOL": 100.00,
        "DOGE": 0.08
    }
    
    symbol_upper = symbol.upper()
    
    if symbol_upper in mock_prices:
        price = mock_prices[symbol_upper]
        
        return {
            "symbol": symbol_upper,
            "price": price,
            "currency": currency,
            "formatted": f"${price:,.2f} {currency}",
            "success": True
        }
    else:
        return {
            "symbol": symbol_upper,
            "error": f"Cryptocurrency {symbol} not found",
            "success": False
        }
```

### Step 3: Register the Function

Add to `TOOL_FUNCTIONS` dictionary:

```python
TOOL_FUNCTIONS = {
    "get_weather": get_weather,
    "calculate": calculate,
    "get_current_time": get_current_time,
    "search_web": search_web,
    "get_crypto_price": get_crypto_price  # ← Add here
}
```

### Step 4: Test It!

Run the agent and try:
```
"What's the current price of Bitcoin?"
"How much is ETH worth?"
"Get me the price of SOL in USD"
```

## Real API Implementation

Replace mock with real CoinGecko API:

```python
def get_crypto_price(symbol: str, currency: str = "USD") -> dict:
    """Get real cryptocurrency price from CoinGecko"""
    
    try:
        # Free API, no key required!
        url = "https://api.coingecko.com/api/v3/simple/price"
        
        # Map common symbols to CoinGecko IDs
        symbol_map = {
            "BTC": "bitcoin",
            "ETH": "ethereum",
            "SOL": "solana",
            "DOGE": "dogecoin",
            "ADA": "cardano",
            "DOT": "polkadot"
        }
        
        coin_id = symbol_map.get(symbol.upper())
        if not coin_id:
            return {
                "symbol": symbol,
                "error": f"Cryptocurrency {symbol} not supported",
                "success": False
            }
        
        params = {
            "ids": coin_id,
            "vs_currencies": currency.lower()
        }
        
        response = requests.get(url, params=params, timeout=5)
        response.raise_for_status()
        data = response.json()
        
        price = data[coin_id][currency.lower()]
        
        return {
            "symbol": symbol.upper(),
            "coin_name": coin_id.title(),
            "price": price,
            "currency": currency.upper(),
            "formatted": f"${price:,.2f} {currency.upper()}",
            "success": True
        }
        
    except Exception as e:
        return {
            "symbol": symbol,
            "error": str(e),
            "success": False
        }
```

## More Tool Examples

### 1. Database Query Tool

```python
{
    "name": "query_database",
    "description": "Execute a SQL query on the database. Returns query results.",
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "SQL SELECT query to execute"
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of rows to return",
                "default": 10
            }
        },
        "required": ["query"]
    }
}

def query_database(query: str, limit: int = 10) -> dict:
    """Execute SQL query"""
    import sqlite3
    
    try:
        # Connect to your database
        conn = sqlite3.connect('your_database.db')
        cursor = conn.cursor()
        
        # Add LIMIT to query
        if "LIMIT" not in query.upper():
            query = f"{query} LIMIT {limit}"
        
        cursor.execute(query)
        results = cursor.fetchall()
        columns = [description[0] for description in cursor.description]
        
        conn.close()
        
        return {
            "query": query,
            "columns": columns,
            "rows": results,
            "count": len(results),
            "success": True
        }
    except Exception as e:
        return {
            "query": query,
            "error": str(e),
            "success": False
        }
```

### 2. Send Email Tool

```python
{
    "name": "send_email",
    "description": "Send an email to a recipient.",
    "input_schema": {
        "type": "object",
        "properties": {
            "to": {
                "type": "string",
                "description": "Recipient email address"
            },
            "subject": {
                "type": "string",
                "description": "Email subject line"
            },
            "body": {
                "type": "string",
                "description": "Email body content"
            }
        },
        "required": ["to", "subject", "body"]
    }
}

def send_email(to: str, subject: str, body: str) -> dict:
    """Send email via SMTP"""
    import smtplib
    from email.mime.text import MIMEText
    
    try:
        smtp_server = os.getenv("SMTP_SERVER")
        smtp_port = int(os.getenv("SMTP_PORT", 587))
        smtp_user = os.getenv("SMTP_USER")
        smtp_pass = os.getenv("SMTP_PASS")
        
        msg = MIMEText(body)
        msg['Subject'] = subject
        msg['From'] = smtp_user
        msg['To'] = to
        
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)
        
        return {
            "to": to,
            "subject": subject,
            "message": "Email sent successfully",
            "success": True
        }
    except Exception as e:
        return {
            "to": to,
            "error": str(e),
            "success": False
        }
```

### 3. GitHub Tool

```python
{
    "name": "github_search_repos",
    "description": "Search GitHub repositories by keyword.",
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query (e.g., 'machine learning python')"
            },
            "language": {
                "type": "string",
                "description": "Programming language filter (optional)"
            },
            "limit": {
                "type": "integer",
                "description": "Number of results (1-10)",
                "default": 5
            }
        },
        "required": ["query"]
    }
}

def github_search_repos(query: str, language: str = None, limit: int = 5) -> dict:
    """Search GitHub repositories"""
    try:
        url = "https://api.github.com/search/repositories"
        
        search_query = query
        if language:
            search_query += f" language:{language}"
        
        params = {
            "q": search_query,
            "sort": "stars",
            "order": "desc",
            "per_page": limit
        }
        
        headers = {
            "Accept": "application/vnd.github.v3+json"
        }
        
        response = requests.get(url, params=params, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        repos = []
        for repo in data["items"][:limit]:
            repos.append({
                "name": repo["full_name"],
                "description": repo["description"],
                "stars": repo["stargazers_count"],
                "language": repo["language"],
                "url": repo["html_url"]
            })
        
        return {
            "query": query,
            "repositories": repos,
            "count": len(repos),
            "success": True
        }
    except Exception as e:
        return {
            "query": query,
            "error": str(e),
            "success": False
        }
```

### 4. Image Generation Tool (Combine with Gemini!)

```python
{
    "name": "generate_image",
    "description": "Generate an image from a text description using AI.",
    "input_schema": {
        "type": "object",
        "properties": {
            "prompt": {
                "type": "string",
                "description": "Text description of the image to generate"
            },
            "style": {
                "type": "string",
                "description": "Image style (realistic, cartoon, artistic)",
                "default": "realistic"
            }
        },
        "required": ["prompt"]
    }
}

def generate_image(prompt: str, style: str = "realistic") -> dict:
    """Generate image using Gemini Imagen"""
    from google import genai
    
    try:
        gemini_key = os.getenv("GEMINI_API_KEY")
        client = genai.Client(api_key=gemini_key)
        
        # Enhance prompt with style
        enhanced_prompt = f"{prompt}, {style} style"
        
        response = client.models.generate_content(
            model='gemini-2.5-flash-image',
            contents=[enhanced_prompt]
        )
        
        # Extract image
        image_data = response.candidates[0].content.parts[0].inline_data.data
        
        # Save or upload image
        # ... implementation here
        
        return {
            "prompt": prompt,
            "style": style,
            "image_url": "https://example.com/generated-image.jpg",
            "message": "Image generated successfully",
            "success": True
        }
    except Exception as e:
        return {
            "prompt": prompt,
            "error": str(e),
            "success": False
        }
```

## Tool Schema Best Practices

### Property Types

```python
"properties": {
    # String
    "name": {
        "type": "string",
        "description": "User's name"
    },
    
    # Integer
    "age": {
        "type": "integer",
        "description": "User's age in years"
    },
    
    # Number (float)
    "temperature": {
        "type": "number",
        "description": "Temperature in celsius"
    },
    
    # Boolean
    "active": {
        "type": "boolean",
        "description": "Whether the user is active"
    },
    
    # Enum (limited choices)
    "size": {
        "type": "string",
        "enum": ["small", "medium", "large"],
        "description": "T-shirt size"
    },
    
    # Array
    "tags": {
        "type": "array",
        "items": {"type": "string"},
        "description": "List of tags"
    }
}
```

### Good Descriptions

```python
# ✅ GOOD
"description": "City name (e.g., 'San Francisco', 'Tokyo', 'London')"

# ✅ GOOD
"description": "Temperature in celsius or fahrenheit. Use celsius for metric countries."

# ❌ BAD
"description": "City"

# ❌ BAD
"description": "temp"
```

### Required Fields

```python
# Mark essential parameters as required
"required": ["city", "date"]

# Optional parameters get defaults
"properties": {
    "city": {"type": "string"},  # Required
    "units": {
        "type": "string",
        "default": "fahrenheit"  # Optional with default
    }
}
```

## Error Handling

Always return consistent format:

```python
def my_tool(param: str) -> dict:
    try:
        # Tool logic here
        result = do_something(param)
        
        return {
            "data": result,
            "success": True
        }
        
    except ValueError as e:
        return {
            "error": f"Invalid input: {str(e)}",
            "success": False
        }
        
    except requests.RequestException as e:
        return {
            "error": f"API error: {str(e)}",
            "success": False
        }
        
    except Exception as e:
        return {
            "error": f"Unexpected error: {str(e)}",
            "success": False
        }
```

## Testing Tools Independently

Before adding to Claude, test your tools:

```python
# test_tools.py

def test_crypto_price():
    result = get_crypto_price("BTC")
    print(f"Result: {result}")
    assert result["success"] == True
    assert "price" in result
    print("✅ Test passed!")

def test_crypto_price_invalid():
    result = get_crypto_price("INVALID")
    print(f"Result: {result}")
    assert result["success"] == False
    assert "error" in result
    print("✅ Error handling works!")

if __name__ == "__main__":
    test_crypto_price()
    test_crypto_price_invalid()
```

Run:
```bash
python test_tools.py
```

## Security Considerations

### 1. Validate Input

```python
def send_email(to: str, subject: str, body: str) -> dict:
    # Validate email
    import re
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    
    if not re.match(email_pattern, to):
        return {
            "error": "Invalid email address",
            "success": False
        }
    
    # Continue with sending...
```

### 2. Rate Limiting

```python
from time import time

last_call = {}

def get_crypto_price(symbol: str, currency: str = "USD") -> dict:
    # Rate limit: 1 call per second per symbol
    now = time()
    if symbol in last_call and now - last_call[symbol] < 1.0:
        return {
            "error": "Rate limit: Please wait 1 second",
            "success": False
        }
    
    last_call[symbol] = now
    
    # Continue with API call...
```

### 3. API Key Protection

```python
# ✅ DO: Use environment variables
api_key = os.getenv("MY_API_KEY")

# ❌ DON'T: Hardcode keys
api_key = "sk-1234567890abcdef"
```

### 4. Sanitize Database Queries

```python
def query_database(query: str, limit: int = 10) -> dict:
    # Only allow SELECT queries
    if not query.strip().upper().startswith("SELECT"):
        return {
            "error": "Only SELECT queries are allowed",
            "success": False
        }
    
    # Prevent dangerous keywords
    dangerous = ["DROP", "DELETE", "UPDATE", "INSERT", "ALTER"]
    if any(keyword in query.upper() for keyword in dangerous):
        return {
            "error": "Query contains forbidden operations",
            "success": False
        }
    
    # Continue with query...
```

## Performance Tips

### 1. Use Timeouts

```python
response = requests.get(url, timeout=5)  # 5 second timeout
```

### 2. Cache Results

```python
from functools import lru_cache

@lru_cache(maxsize=100)
def get_crypto_price(symbol: str, currency: str = "USD") -> str:
    # Results cached for repeated calls
    # ...
    return json.dumps(result)
```

### 3. Async for I/O-Bound Tools

```python
import asyncio
import aiohttp

async def get_weather_async(city: str) -> dict:
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            data = await response.json()
            return data
```

## Summary Checklist

When adding a new tool:

- [ ] Clear, descriptive name
- [ ] Detailed description with examples
- [ ] Well-defined input schema
- [ ] Mark required parameters
- [ ] Provide defaults for optional params
- [ ] Implement the function
- [ ] Return consistent format
- [ ] Handle errors gracefully
- [ ] Test independently
- [ ] Add to TOOL_FUNCTIONS
- [ ] Document usage examples
- [ ] Consider security
- [ ] Add rate limiting if needed
- [ ] Use timeouts for network calls

## Next Steps

1. Choose a tool to add
2. Follow the 3-step process
3. Test it thoroughly
4. Share your creation!

---

**Ready to supercharge your agent? Start building custom tools!** 🚀🔧
