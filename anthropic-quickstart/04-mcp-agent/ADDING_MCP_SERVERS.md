# Adding MCP Servers Guide

Complete guide to adding ANY MCP server to your Claude agent! 🔌

## Quick Reference

**3 Steps to Add Any Server:**
1. Find the MCP server package
2. Add configuration to `mcp_servers.json`
3. Restart agent - done!

## Finding MCP Servers

### Official Repository
Browse: **https://github.com/modelcontextprotocol/servers**

### Popular Servers

| Server | Package | Use Case |
|--------|---------|----------|
| GitHub | `@modelcontextprotocol/server-github` | Repo access, issues, PRs |
| Filesystem | `@modelcontextprotocol/server-filesystem` | Read/write local files |
| SQLite | `@modelcontextprotocol/server-sqlite` | Query SQLite databases |
| PostgreSQL | `@modelcontextprotocol/server-postgres` | Query PostgreSQL databases |
| Google Drive | `@modelcontextprotocol/server-gdrive` | Access Drive documents |
| Slack | `@modelcontextprotocol/server-slack` | Send messages, read channels |
| Puppeteer | `@modelcontextprotocol/server-puppeteer` | Browser automation |
| Memory | `@modelcontextprotocol/server-memory` | Persistent memory storage |
| Airbnb | `@openbnb/mcp-server-airbnb` | Search properties |
| Brave Search | `@modelcontextprotocol/server-brave-search` | Web search |

## Configuration Format

```json
{
  "servers": {
    "server_name": {
      "command": "npx",
      "args": ["-y", "package-name", ...flags],
      "env": {
        "API_KEY": "${ENV_VAR}"
      },
      "description": "What this server does",
      "enabled": true
    }
  }
}
```

### Fields Explained

- **server_name**: Unique identifier for this server (your choice)
- **command**: Usually `"npx"` to run Node packages
- **args**: Array of arguments, always include `"-y"` for auto-accept
- **env**: Environment variables the server needs
- **description**: Human-readable description
- **enabled**: `true` to load, `false` to disable

## Step-by-Step Examples

### Example 1: Add GitHub Server

**What it does:** Access GitHub repos, create issues, read files

**Requirements:**
- GitHub Personal Access Token

**Step 1: Get GitHub Token**
```bash
# Go to: https://github.com/settings/tokens
# Create token with scopes: repo, read:org, read:user
# Add to .env:
GITHUB_TOKEN="ghp_..."
```

**Step 2: Add to `mcp_servers.json`**
```json
{
  "servers": {
    "github": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": {
        "GITHUB_PERSONAL_ACCESS_TOKEN": "${GITHUB_TOKEN}"
      },
      "description": "GitHub repository access - search repos, read files, create issues",
      "enabled": true
    }
  }
}
```

**Step 3: Restart and Test**
```bash
python claude_mcp_agent.py

# Try via ASI One:
"Search for Python machine learning repositories"
"Read the README from facebook/react"
```

### Example 2: Add Filesystem Server

**What it does:** Read and write local files

**Requirements:**
- Specify allowed directory

**Configuration:**
```json
{
  "servers": {
    "filesystem": {
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/server-filesystem",
        "/Users/yourname/Documents"  // ← Directory to allow
      ],
      "env": {},
      "description": "Local filesystem access - read/write files in Documents",
      "enabled": true
    }
  }
}
```

**Security Note:** The server can ONLY access the specified directory!

**Test Queries:**
```
Read the file /Users/yourname/Documents/notes.txt
Create a file called todo.md with my tasks
List all .py files in my Documents folder
```

### Example 3: Add SQLite Server

**What it does:** Query SQLite databases

**Requirements:**
- Path to SQLite database file

**Configuration:**
```json
{
  "servers": {
    "sqlite": {
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/server-sqlite",
        "--db-path",
        "./data.db"  // ← Path to your database
      ],
      "env": {},
      "description": "SQLite database access - query local databases",
      "enabled": true
    }
  }
}
```

**Test Queries:**
```
Show me all tables in the database
Query the users table and show first 10 rows
Count how many orders were placed in December
```

### Example 4: Add Airbnb Server

**What it does:** Search Airbnb listings

**Requirements:**
- None! (Uses public API)

**Configuration:**
```json
{
  "servers": {
    "airbnb": {
      "command": "npx",
      "args": [
        "-y",
        "@openbnb/mcp-server-airbnb"
      ],
      "env": {},
      "description": "Airbnb search and listings - find properties worldwide",
      "enabled": true
    }
  }
}
```

**Optional: Ignore robots.txt**
```json
"args": [
  "-y",
  "@openbnb/mcp-server-airbnb",
  "--ignore-robots-txt"  // ← For testing only
]
```

**Test Queries:**
```
Search for Airbnb apartments in Paris for next weekend
Find beach houses in California under $200/night
Get details for Airbnb listing ID 12345
```

### Example 5: Add PostgreSQL Server

**What it does:** Query PostgreSQL databases

**Requirements:**
- PostgreSQL connection string

**Step 1: Add to `.env`**
```bash
POSTGRES_URL="postgresql://user:password@localhost:5432/dbname"
```

**Step 2: Configuration**
```json
{
  "servers": {
    "postgres": {
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/server-postgres",
        "${POSTGRES_URL}"
      ],
      "env": {},
      "description": "PostgreSQL database access",
      "enabled": true
    }
  }
}
```

**Test Queries:**
```
Show me the schema of the users table
Query products where price > 100
Count active customers by country
```

### Example 6: Add Google Drive Server

**What it does:** Access Google Drive files

**Requirements:**
- Google OAuth credentials

**Step 1: Get OAuth Credentials**
```
1. Go to: https://console.cloud.google.com
2. Create project
3. Enable Google Drive API
4. Create OAuth 2.0 credentials
5. Download client_secret.json
```

**Step 2: Add to `.env`**
```bash
GDRIVE_CLIENT_ID="your-client-id"
GDRIVE_CLIENT_SECRET="your-client-secret"
```

**Step 3: Configuration**
```json
{
  "servers": {
    "gdrive": {
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/server-gdrive"
      ],
      "env": {
        "GDRIVE_CLIENT_ID": "${GDRIVE_CLIENT_ID}",
        "GDRIVE_CLIENT_SECRET": "${GDRIVE_CLIENT_SECRET}"
      },
      "description": "Google Drive document access",
      "enabled": true
    }
  }
}
```

**Test Queries:**
```
List all my Google Drive files
Read the content of my document called "Notes"
Search for spreadsheets modified last week
```

## Multiple Servers Example

You can enable multiple servers at once:

```json
{
  "servers": {
    "github": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": {"GITHUB_PERSONAL_ACCESS_TOKEN": "${GITHUB_TOKEN}"},
      "enabled": true
    },
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
      "env": {},
      "enabled": true
    },
    "sqlite": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-sqlite", "--db-path", "./data.db"],
      "env": {},
      "enabled": true
    }
  }
}
```

**Multi-server queries:**
```
Search GitHub for database projects, then save results to a file
Query my database and create a report in a text file
Read a CSV file and import it into my SQLite database
```

Claude will intelligently use tools from different servers!

## Environment Variable Reference

### Using Variables

In `mcp_servers.json`, reference `.env` variables with `${VAR_NAME}`:

```json
"env": {
  "API_KEY": "${MY_API_KEY}",
  "DATABASE_URL": "${DB_URL}"
}
```

### In Command Args

You can also use variables in args:

```json
"args": [
  "-y",
  "@modelcontextprotocol/server-postgres",
  "${POSTGRES_URL}"  // ← Substituted from .env
]
```

### Common Variables

```bash
# .env file

# GitHub
GITHUB_TOKEN="ghp_..."

# Databases
POSTGRES_URL="postgresql://..."
MYSQL_URL="mysql://..."

# APIs
OPENAI_API_KEY="sk-..."
ANTHROPIC_API_KEY="sk-ant-..."

# Google
GDRIVE_CLIENT_ID="..."
GDRIVE_CLIENT_SECRET="..."
```

## Troubleshooting

### Server Won't Connect

**Check:**
```bash
# 1. Test server independently
npx @modelcontextprotocol/server-github

# 2. Check Node.js is installed
node --version  # Should be 18+

# 3. Check package name is correct
npm info @modelcontextprotocol/server-github

# 4. Check environment variables
cat .env | grep GITHUB_TOKEN
```

### Tools Not Appearing

**Check startup logs:**
```
✅ Connected to MCP server: github
📋 Loaded 12 tools from github  // ← Should see this
```

If tools don't load:
- Server connection failed
- Server doesn't provide tools
- Server requires additional setup

### Permission Errors

**Filesystem:**
```
Error: EACCES: permission denied

Solution: Check directory permissions
chmod +r /path/to/directory
```

**Database:**
```
Error: authentication failed

Solution: Check connection string and credentials
```

### npx Hangs

Some servers require initial setup:

```bash
# First time may prompt for permissions
npx @modelcontextprotocol/server-gdrive

# Or install globally first
npm install -g @modelcontextprotocol/server-gdrive
```

## Advanced Configuration

### Custom Arguments

Some servers accept custom flags:

```json
{
  "airbnb": {
    "args": [
      "-y",
      "@openbnb/mcp-server-airbnb",
      "--ignore-robots-txt",  // ← Custom flag
      "--timeout", "30000"     // ← Another flag
    ]
  }
}
```

Check each server's documentation for available flags.

### Conditional Loading

Modify the agent code to load servers conditionally:

```python
# In claude_mcp_agent.py
def load_config(self) -> Dict:
    config = ...
    
    # Only load certain servers in production
    if os.getenv("ENV") == "production":
        config["servers"]["filesystem"]["enabled"] = False
    
    return config
```

### Server Aliases

Create multiple configs for the same server:

```json
{
  "servers": {
    "work_drive": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-gdrive"],
      "env": {"GDRIVE_CLIENT_ID": "${WORK_GDRIVE_ID}"},
      "enabled": true
    },
    "personal_drive": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-gdrive"],
      "env": {"GDRIVE_CLIENT_ID": "${PERSONAL_GDRIVE_ID}"},
      "enabled": true
    }
  }
}
```

## Creating Your Own MCP Server

Want to create a custom server? Here's a minimal example:

```typescript
// my-server.ts
import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  ListToolsRequestSchema,
  CallToolRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";

const server = new Server(
  {
    name: "my-custom-server",
    version: "1.0.0",
  },
  {
    capabilities: {
      tools: {},
    },
  }
);

// Define tools
server.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: [
    {
      name: "get_random_number",
      description: "Get a random number between min and max",
      inputSchema: {
        type: "object",
        properties: {
          min: { type: "number", description: "Minimum value" },
          max: { type: "number", description: "Maximum value" },
        },
        required: ["min", "max"],
      },
    },
  ],
}));

// Handle tool calls
server.setRequestHandler(CallToolRequestSchema, async (request) => {
  if (request.params.name === "get_random_number") {
    const { min, max } = request.params.arguments;
    const result = Math.floor(Math.random() * (max - min + 1)) + min;
    
    return {
      content: [
        {
          type: "text",
          text: `Random number: ${result}`,
        },
      ],
    };
  }
  
  throw new Error(`Unknown tool: ${request.params.name}`);
});

// Start server
async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
}

main();
```

**Add to config:**
```json
{
  "my_server": {
    "command": "node",
    "args": ["my-server.js"],
    "enabled": true
  }
}
```

Full guide: https://modelcontextprotocol.io/docs/tools/building

## Best Practices

### 1. Start Simple
Enable one server at a time. Get it working, then add more.

### 2. Secure Your Tokens
- Never commit `.env`
- Use minimal permissions
- Rotate regularly

### 3. Limit Access
Filesystem server - only allow necessary directories:
```json
"args": ["-y", "...", "/specific/safe/directory"]
```

### 4. Monitor Performance
Some servers are slower than others. Monitor logs.

### 5. Handle Errors
The agent handles errors gracefully, but test edge cases.

## Server Comparison

| Server | Speed | Setup Complexity | Security Risk | Best For |
|--------|-------|------------------|---------------|----------|
| GitHub | Fast | Easy (token) | Low | Code, repos |
| Filesystem | Very Fast | Easy | Medium | Local files |
| SQLite | Fast | Easy | Low | Local DB |
| PostgreSQL | Medium | Medium (connection) | Medium | Production DB |
| Airbnb | Medium | Easy | Low | Property search |
| Google Drive | Medium | Hard (OAuth) | Medium | Cloud documents |

## Summary Checklist

Adding a new MCP server:

- [ ] Find server package name
- [ ] Check if it needs API keys/tokens
- [ ] Add credentials to `.env`
- [ ] Add server config to `mcp_servers.json`
- [ ] Set `"enabled": true`
- [ ] Restart agent
- [ ] Check logs for successful connection
- [ ] Test with relevant queries
- [ ] Document usage for your team

---

**Ready to connect to everything? Pick a server and add it!** 🔌✨
