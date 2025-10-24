

# Claude MCP Agent

Connect Claude to ANY MCP (Model Context Protocol) server - GitHub, databases, filesystems, and more! 🔌

## What You'll Build

An AI agent that:
- ✅ Connects to multiple MCP servers simultaneously
- ✅ Auto-discovers tools from each server
- ✅ Uses Claude to intelligently choose and execute tools
- ✅ Easy configuration - just edit JSON
- ✅ Works with ANY MCP server from the ecosystem
- ✅ Integrates with Fetch.ai network via ASI One

## 🎯 Key Concept: MCP (Model Context Protocol)

**MCP** is Anthropic's open protocol for connecting AI models to external data and tools.

**Think of it as:**
- USB for AI - standardized way to connect tools
- Plugin system for Claude
- Bridge between AI and the real world

**Available MCP Servers:**
- 🐙 **GitHub** - Repository access, file reading, issue management
- 📁 **Filesystem** - Read/write local files
- 💾 **SQLite** - Query databases
- 🏠 **Airbnb** - Search properties
- 🌐 **Web** - Fetch URLs
- 📊 **Google Drive** - Document access
- And 100+ more at [modelcontextprotocol/servers](https://github.com/modelcontextprotocol/servers)

## Prerequisites

- Python 3.9+
- Node.js 18+ (for running MCP servers via npx)
- Anthropic API key (from previous guides)
- GitHub Personal Access Token (for GitHub MCP server)

## Quick Start

### Step 1: Install Dependencies

```bash
cd anthropic-quickstart/04-mcp-agent

# Install Python packages
pip install -r requirements.txt

# No need to install MCP servers separately - they run via npx!
```

### Step 2: Configure Environment Variables

Add to your `.env` file:

```bash
# Anthropic (already have this)
ANTHROPIC_API_KEY="sk-ant-..."

# GitHub (new - get from https://github.com/settings/tokens)
GITHUB_TOKEN="ghp_..."
```

**How to get GitHub token:**
1. Go to https://github.com/settings/tokens
2. Click "Generate new token (classic)"
3. Select scopes: `repo`, `read:org`, `read:user`
4. Copy token and add to `.env`

### Step 3: Configure MCP Servers

Edit `mcp_servers.json` to enable servers:

```json
{
  "servers": {
    "github": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": {
        "GITHUB_PERSONAL_ACCESS_TOKEN": "${GITHUB_TOKEN}"
      },
      "description": "GitHub repository access",
      "enabled": true  // ← Set to true
    }
  }
}
```

### Step 4: Run the Agent

```bash
python claude_mcp_agent.py
```
### You will see an inspector link, which you can open on your browser and connect the mailbox.

You should see:

```
🔌 Starting Claude MCP Agent...
📍 Agent address: agent1q...
✅ Claude API configured
🔌 Connecting to MCP servers...
🔌 Connecting to github...
✅ Connected to MCP server: github
📋 Loaded 12 tools from github
✅ Loaded 12 MCP tools
   🔧 create_or_update_file (github)
   🔧 search_repositories (github)
   🔧 create_issue (github)
   ...
```

## Testing the Agent

### Via ASI One

1. Go to [https://asi1.ai](https://asi1.ai)
2. Find your agent
3. Try these queries!

### Example Queries

**GitHub Search:**
```
Search for popular Python machine learning repositories
```

**Read File:**
```
Read the README.md file from microsoft/typescript repository
```

**Create Issue:**
```
Create an issue in my repo username/myproject titled "Bug: Login fails"
```

**Repository Info:**
```
Get information about the react repository from facebook
```

**Multi-step:**
```
Search for FastAPI repositories, then read the main.py from the most popular one
```

## How It Works

### Architecture

```
User (ASI One)
    ↓
    ↓ Fetch.ai Chat Protocol
    ↓
uAgent (claude_mcp_agent.py)
    ├─ Loads mcp_servers.json
    ├─ Connects to enabled MCP servers
    ├─ Discovers available tools
    ├─ Converts to Claude format
    └─ Handles tool execution
    ↓
Claude API
    ├─ Receives tools list
    ├─ Chooses appropriate tools
    └─ Returns tool_use blocks
    ↓
MCP Server (e.g., GitHub)
    ├─ Receives tool call
    ├─ Executes against GitHub API
    └─ Returns results
    ↓
Back to User
```

### Code Flow

**1. Startup - Connect to MCP Servers**

```python
# Load configuration
config = mcp_manager.load_config()

# Connect to each enabled server
for name, server_config in config["servers"].items():
    if server_config["enabled"]:
        await mcp_manager.connect_server(name, server_config)

# Discover tools
mcp_tools = await mcp_manager.get_all_tools()
```

**2. Handle User Message**

```python
# Get MCP tools
mcp_tools = ctx.storage.get("mcp_tools")

# Convert to Claude format
claude_tools = mcp_tools_to_claude_format(mcp_tools)

# Call Claude with tools
response = client.messages.create(
    model=MODEL_NAME,
    tools=claude_tools,  # MCP tools!
    messages=[{"role": "user", "content": user_text}]
)
```

**3. Execute Tool Calls**

```python
if response.stop_reason == "tool_use":
    for tool_use in response.content:
        tool_name = tool_use.name
        tool_input = tool_use.input
        
        # Execute via MCP
        result = await mcp_manager.call_tool(tool_name, tool_input)
```

**4. Return Results**

Claude receives tool results and generates final response.

## Adding New MCP Servers

### Super Easy - 3 Steps!

#### Step 1: Find an MCP Server

Browse: https://github.com/modelcontextprotocol/servers

Popular servers:
- `@modelcontextprotocol/server-github`
- `@modelcontextprotocol/server-filesystem`
- `@modelcontextprotocol/server-sqlite`
- `@modelcontextprotocol/server-postgres`
- `@openbnb/mcp-server-airbnb`
- `@modelcontextprotocol/server-gdrive`

#### Step 2: Add to `mcp_servers.json`

```json
{
  "servers": {
    "your_server_name": {
      "command": "npx",
      "args": ["-y", "@package/mcp-server-name"],
      "env": {
        "API_KEY": "${YOUR_API_KEY}"
      },
      "description": "What this server does",
      "enabled": true
    }
  }
}
```

#### Step 3: Restart the Agent

That's it! The agent will:
- ✅ Connect to the new server
- ✅ Discover its tools automatically
- ✅ Make them available to Claude

### Examples

#### Add Filesystem Server

```json
"filesystem": {
  "command": "npx",
  "args": ["-y", "@modelcontextprotocol/server-filesystem", "/home/user/documents"],
  "env": {},
  "description": "Local filesystem access - read/write files",
  "enabled": true
}
```

Queries:
```
Read the file /home/user/documents/notes.txt
Create a new file called todo.md with my tasks
```

#### Add SQLite Server

```json
"sqlite": {
  "command": "npx",
  "args": ["-y", "@modelcontextprotocol/server-sqlite", "--db-path", "./mydata.db"],
  "env": {},
  "description": "SQLite database access",
  "enabled": true
}
```

Queries:
```
Query the users table and show me the first 10 rows
Count how many orders were placed last month
```

#### Add Airbnb Server

```json
"airbnb": {
  "command": "npx",
  "args": ["-y", "@openbnb/mcp-server-airbnb"],
  "env": {},
  "description": "Airbnb search and listings",
  "enabled": true
}
```

Queries:
```
Search for Airbnb listings in Paris for next weekend
Find apartments in Tokyo under $100/night
```

#### Add Google Drive Server

```json
"gdrive": {
  "command": "npx",
  "args": ["-y", "@modelcontextprotocol/server-gdrive"],
  "env": {
        "GDRIVE_CLIENT_ID": "${GDRIVE_CLIENT_ID}",
        "GDRIVE_CLIENT_SECRET": "${GDRIVE_CLIENT_SECRET}"
  },
  "description": "Google Drive document access",
  "enabled": true
}
```

## Configuration Reference

### Server Configuration Format

```json
{
  "servers": {
    "server_name": {
      "command": "npx",                    // How to run the server
      "args": ["-y", "package-name"],      // Command arguments
      "env": {                              // Environment variables
        "KEY": "${ENV_VAR_NAME}"           // Reference from .env
      },
      "description": "What it does",      // Human-readable description
      "enabled": true                      // Enable/disable
    }
  }
}
```

### Environment Variable Substitution

Use `${VAR_NAME}` syntax to reference variables from `.env`:

```json
"env": {
  "GITHUB_PERSONAL_ACCESS_TOKEN": "${GITHUB_TOKEN}",
  "API_KEY": "${MY_API_KEY}"
}
```

The agent automatically substitutes these at runtime.

### Enable/Disable Servers

Set `"enabled": false` to temporarily disable a server:

```json
"filesystem": {
  "command": "npx",
  "args": [...],
  "enabled": false  // ← Server won't be loaded
}
```

## Available GitHub Tools

When GitHub server is enabled, you get these tools:

### create_or_update_file
Create or update files in a repository

**Parameters:**
- `owner` - Repository owner
- `repo` - Repository name
- `path` - File path
- `content` - File content
- `message` - Commit message
- `branch` - Branch name (optional)
- `sha` - File SHA if updating (optional)

### search_repositories
Search for GitHub repositories

**Parameters:**
- `query` - Search query
- `page` - Page number (optional)
- `perPage` - Results per page (optional)

### create_issue
Create a new issue

**Parameters:**
- `owner` - Repository owner
- `repo` - Repository name
- `title` - Issue title
- `body` - Issue description
- `assignees` - Assignees (optional)
- `labels` - Labels (optional)

### create_pull_request
Create a pull request

**Parameters:**
- `owner` - Repository owner
- `repo` - Repository name
- `title` - PR title
- `body` - PR description
- `head` - Source branch
- `base` - Target branch

### fork_repository
Fork a repository

**Parameters:**
- `owner` - Repository owner
- `repo` - Repository name
- `organization` - Organization to fork to (optional)

### push_files
Push multiple files in one commit

**Parameters:**
- `owner` - Repository owner
- `repo` - Repository name
- `branch` - Branch name
- `files` - Array of file objects
- `message` - Commit message

And more! The agent auto-discovers all tools.

## Troubleshooting

### "MCP SDK not installed"

```bash
pip install mcp
```

### "Failed to connect to github"

**Check:**
- Node.js is installed (`node --version`)
- GitHub token is in `.env`
- Token has correct permissions (repo, read:org)
- Server is enabled in `mcp_servers.json`

### "Tool not found"

**Possible causes:**
- Server didn't connect successfully
- Tool name mismatch
- Server doesn't provide that tool

**Debug:**
Check startup logs for:
```
✅ Connected to MCP server: github
📋 Loaded 12 tools from github
```

### "npx command not found"

Install Node.js:
- macOS: `brew install node`
- Windows: Download from nodejs.org
- Linux: `sudo apt install nodejs npm`

### Agent connects but tools don't work

**Check logs for:**
- Tool execution errors
- API rate limits
- Invalid parameters
- Permission issues

## Best Practices

### 1. Start with One Server

Get one server working before adding more:

```json
{
  "servers": {
    "github": {
      "enabled": true
    },
    "everything_else": {
      "enabled": false  // ← Disable others first
    }
  }
}
```

### 2. Use Environment Variables

Never hardcode secrets:

```json
// ❌ BAD
"env": {
  "API_KEY": "sk-1234567890"
}

// ✅ GOOD
"env": {
  "API_KEY": "${MY_API_KEY}"
}
```

### 3. Test Servers Independently

Before adding to agent, test MCP server directly:

```bash
npx @modelcontextprotocol/server-github
```

### 4. Monitor Logs

Watch startup logs to ensure servers connect:

```
🔌 Connecting to github...
✅ Connected to MCP server: github
📋 Loaded 12 tools from github
```

### 5. Handle Rate Limits

Some servers have rate limits (GitHub API, etc.). The agent handles errors gracefully.

## Advanced Usage

### Custom MCP Server

You can create your own MCP server! See: https://modelcontextprotocol.io/docs/tools/building

```typescript
// my-server.ts
import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";

const server = new Server({
  name: "my-custom-server",
  version: "1.0.0",
});

server.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: [
    {
      name: "my_tool",
      description: "Does something cool",
      inputSchema: { /* ... */ }
    }
  ]
}));

// Start server
const transport = new StdioServerTransport();
await server.connect(transport);
```

Add to config:
```json
"my_server": {
  "command": "node",
  "args": ["my-server.js"],
  "enabled": true
}
```

### Multiple Servers Working Together

Claude can use tools from different servers in one query:

```
User: "Search for Python repos on GitHub and save the top result to results.txt"

→ Claude uses github.search_repositories
→ Then uses filesystem.write_file
→ Returns combined result
```

### Conditional Server Loading

Load different servers based on environment:

```python
# Modify load_config() to filter by environment
if os.getenv("ENV") == "production":
    # Only load production-safe servers
    pass
```

## Security Considerations

### 1. Filesystem Access

Limit directories the filesystem server can access:

```json
"args": ["-y", "@modelcontextprotocol/server-filesystem", "/safe/directory"]
```

### 2. Database Access

Use read-only connections when possible.

### 3. API Tokens

- Store in `.env`, never commit
- Use minimal required permissions
- Rotate regularly

### 4. Command Injection

The agent uses `npx` to run servers. Only add trusted servers.

## Cost Considerations

**MCP Agent costs:**
- Tool definitions: ~500-1000 tokens per request
- Tool results: Varies by tool
- Claude processing: Standard rates

**Typical request:**
- Simple GitHub search: ~$0.002-0.005
- Complex multi-tool: ~$0.01-0.02

Still very affordable!

## What's Next?

1. ✅ **Test with GitHub** - Try repository searches and file operations
2. 🔧 **Add more servers** - Filesystem, SQLite, Airbnb
3. 🎨 **Combine with other agents** - Use with vision/function agents
4. 🚀 **Build custom MCP server** - Create your own tools
5. 🌐 **Deploy** - Make it publicly accessible

## Resources

- [MCP Official Docs](https://modelcontextprotocol.io)
- [MCP Server Directory](https://github.com/modelcontextprotocol/servers)
- [Building MCP Servers](https://modelcontextprotocol.io/docs/tools/building)
- [Claude + MCP Guide](https://docs.anthropic.com/claude/docs/tool-use)

---

**Ready to connect Claude to everything? Start with GitHub and explore!** 🔌✨
