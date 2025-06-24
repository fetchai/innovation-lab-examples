import os
import json
import asyncio
import secrets
import urllib.parse
from typing import Dict, Any, Optional
from contextlib import AsyncExitStack
from cryptography.fernet import Fernet
import time
import mcp
from mcp.client.stdio import stdio_client
from uagents import Agent, Context, Protocol, Model
from uagents_core.contrib.protocols.chat import (
    chat_protocol_spec,
    ChatMessage,
    ChatAcknowledgement,
    TextContent,
    EndSessionContent,
    StartSessionContent,
)
from datetime import datetime, timezone
from uuid import uuid4
from dotenv import load_dotenv
from anthropic import Anthropic
import httpx

# --- Agent Configuration ---

# Load environment variables from a .env file
load_dotenv()

# Get Anthropic API key
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
if not ANTHROPIC_API_KEY:
    raise ValueError("ANTHROPIC_API_KEY not found in .env file")

# GitHub App Configuration (for Device Flow - no secrets needed!)
GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID", "Iv1.b507a08c87ecfe98")  # Public GitHub CLI client ID

AGENT_NAME = "github_agent"
AGENT_PORT = 8005

# User sessions store: session_id -> {access_token, user_info, device_code, user_code}
user_sessions: Dict[str, Dict[str, Any]] = {}

# Initialize Fernet key for token encryption
fernet_key = Fernet.generate_key()
cipher_suite = Fernet(fernet_key)

# Session timeout (30 minutes)
SESSION_TIMEOUT = 30 * 60  # seconds

# --- GitHub Device Flow OAuth Handler ---

class GitHubDeviceFlowHandler:
    def __init__(self):
        self.client_id = GITHUB_CLIENT_ID
        self.device_url = "https://github.com/login/device/code"
        self.token_url = "https://github.com/login/oauth/access_token"
        self.api_base = "https://api.github.com"
    
    async def start_device_flow(self, session_id: str) -> Dict[str, str]:
        """Start GitHub Device Flow OAuth"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.device_url,
                data={
                    'client_id': self.client_id,
                    'scope': 'repo user read:org workflow'
                },
                headers={'Accept': 'application/json'}
            )
            
            if response.status_code == 200:
                data = response.json()
                
                # Store device flow data in session
                if session_id not in user_sessions:
                    user_sessions[session_id] = {}
                
                user_sessions[session_id].update({
                    'device_code': data['device_code'],
                    'user_code': data['user_code'],
                    'verification_uri': data['verification_uri'],
                    'expires_in': data['expires_in'],
                    'interval': data['interval']
                })
                
                return data
            else:
                raise Exception(f"Failed to start device flow: {response.text}")
    
    async def poll_for_token(self, session_id: str) -> Optional[str]:
        """Poll GitHub for access token"""
        if session_id not in user_sessions:
            return None
        
        session_data = user_sessions[session_id]
        device_code = session_data.get('device_code')
        
        if not device_code:
            return None
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.token_url,
                data={
                    'client_id': self.client_id,
                    'device_code': device_code,
                    'grant_type': 'urn:ietf:params:oauth:grant-type:device_code'
                },
                headers={'Accept': 'application/json'}
            )
            
            if response.status_code == 200:
                data = response.json()
                if 'access_token' in data:
                    return data['access_token']
                elif data.get('error') == 'authorization_pending':
                    return 'pending'
                elif data.get('error') == 'slow_down':
                    return 'slow_down'
                else:
                    return None
            
        return None
    
    async def get_user_info(self, access_token: str) -> Optional[Dict]:
        """Get GitHub user information"""
        async with httpx.AsyncClient() as client:
            # Get user info
            response = await client.get(
                f"{self.api_base}/user",
                headers={'Authorization': f'token {access_token}'}
            )
            
            if response.status_code == 200:
                user_info = response.json()
                
                # Also check token scopes for debugging
                scopes_response = await client.get(
                    f"{self.api_base}/user",
                    headers={'Authorization': f'token {access_token}'}
                )
                
                # GitHub returns scopes in the X-OAuth-Scopes header
                if 'X-OAuth-Scopes' in scopes_response.headers:
                    scopes = scopes_response.headers['X-OAuth-Scopes']
                    user_info['token_scopes'] = scopes
                    print(f" Token scopes: {scopes}")
                
                return user_info
        return None

# --- MCP Client Logic ---

class GitHubMCPClient:
    def __init__(self, ctx: Context, access_token: str):
        self._ctx = ctx
        self._access_token = access_token
        self._session: mcp.ClientSession = None
        self._exit_stack = AsyncExitStack()
        self.anthropic = Anthropic(api_key=ANTHROPIC_API_KEY)
        self.tools = []  # Will be populated after connection

    async def connect(self):
        """Connects to the GitHub MCP server via Docker with user's access token."""
        self._ctx.logger.info("Connecting to GitHub MCP server with user authentication...")
        try:
            # GitHub MCP server command with user's access token
            docker_args = [
                "run", "-i", "--rm",
                "-e", f"GITHUB_PERSONAL_ACCESS_TOKEN={self._access_token}",
                "ghcr.io/github/github-mcp-server"
            ]
            
            params = mcp.StdioServerParameters(command="docker", args=docker_args)
            read_stream, write_stream = await self._exit_stack.enter_async_context(
                stdio_client(params)
            )
            self._session = await self._exit_stack.enter_async_context(
                mcp.ClientSession(read_stream, write_stream)
            )
            await self._session.initialize()
            
            # Get available tools from GitHub MCP server
            tools_result = await self._session.list_tools()
            self.tools = self._convert_mcp_tools_to_anthropic_format(tools_result.tools)
            
            self._ctx.logger.info(f"Successfully connected to GitHub MCP. Available tools: {[t.name for t in tools_result.tools]}")
        except Exception as e:
            self._ctx.logger.error(f"Failed to connect to GitHub MCP server: {e}")
            raise

    def _convert_mcp_tools_to_anthropic_format(self, mcp_tools) -> list:
        """Convert MCP tool definitions to Anthropic tool format."""
        anthropic_tools = []
        for tool in mcp_tools:
            anthropic_tool = {
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.inputSchema or {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            }
            anthropic_tools.append(anthropic_tool)
        return anthropic_tools

    async def process_query(self, query: str) -> str:
        """Processes a user query using Anthropic for tool selection and then calls the tool."""
        self._ctx.logger.info(f"Processing GitHub query: '{query}'")
        try:
            # Let Claude decide which GitHub tool to use
            response = self.anthropic.messages.create(
                model="claude-3-5-sonnet-20240620",
                max_tokens=2048,
                messages=[{
                    "role": "user", 
                    "content": f"Help me with this GitHub request: {query}"
                }],
                tools=self.tools,
            )

            tool_use = next((content for content in response.content if content.type == 'tool_use'), None)

            # If the model wants to use a tool
            if tool_use:
                tool_name = tool_use.name
                tool_input = tool_use.input
                self._ctx.logger.info(f"Claude selected GitHub tool: {tool_name} with input: {tool_input}")

                # Call the selected tool on the GitHub MCP server
                mcp_response = await self._session.call_tool(tool_name, tool_input)
                
                # Debug: Log the raw MCP response
                self._ctx.logger.info(f"MCP Response type: {type(mcp_response)}")
                self._ctx.logger.info(f"MCP Response content type: {type(mcp_response.content)}")
                self._ctx.logger.info(f"MCP Response content: {mcp_response.content}")
                
                # Format the response for the user
                return self._format_response_for_user(tool_name, mcp_response.content)
            
            # If the model just wants to chat
            text_response = next((content for content in response.content if content.type == 'text'), None)
            if text_response:
                return text_response.text

            return "I can help you with GitHub operations like viewing issues, repositories, pull requests, and more. What would you like to do?"

        except Exception as e:
            self._ctx.logger.error(f"Error processing GitHub query: {e}")
            return f"Sorry, an error occurred while processing your GitHub request: {e}"

    def _format_response_for_user(self, tool_name: str, content: Any) -> str:
        """Formats the response from GitHub MCP server for the user."""
        try:
            # Parse the MCP response content
            if isinstance(content, list) and len(content) > 0:
                # Handle text content from MCP response
                if hasattr(content[0], 'text'):
                    response_text = content[0].text
                    # Parse JSON if it's a string
                    if isinstance(response_text, str):
                        try:
                            data = json.loads(response_text)
                        except json.JSONDecodeError:
                            # If not JSON, treat as plain text
                            return response_text[:1000] + "..." if len(response_text) > 1000 else response_text
                    else:
                        data = response_text
            else:
                data = content

            # Format based on tool type
            if 'repositories' in tool_name or 'search_repositories' in tool_name:
                return self._format_repositories(data)
            elif 'issues' in tool_name:
                return self._format_issues(data)
            elif 'pull_request' in tool_name:
                return self._format_pull_requests(data)
            elif 'user' in tool_name or tool_name == 'get_me':
                return self._format_user_info(data)
            else:
                # For other tools, return a truncated version
                text_data = str(data)
                if len(text_data) > 1000:
                    return f"**{tool_name.replace('_', ' ').title()} Results:**\n\n{text_data[:1000]}...\n\n*Response truncated for readability*"
                return f"**{tool_name.replace('_', ' ').title()} Results:**\n\n{text_data}"

        except Exception as e:
            self._ctx.logger.error(f"Error formatting response: {e}")
            # Fallback to truncated raw content
            content_str = str(content)
            if len(content_str) > 500:
                return f"Raw response (truncated): {content_str[:500]}..."
            return f"Raw response: {content_str}"

    def _format_user_info(self, data: Dict) -> str:
        """Format user information."""
        if isinstance(data, dict):
            return f"""
👤 **GitHub Profile:**
• **Name:** {data.get('name', 'N/A')}
• **Username:** {data.get('login', 'N/A')}
• **Bio:** {data.get('bio', 'N/A')}
• **Public Repos:** {data.get('public_repos', 'N/A')}
• **Followers:** {data.get('followers', 'N/A')}
• **Following:** {data.get('following', 'N/A')}
"""
        return str(data)

    def _format_issues(self, data: Any) -> str:
        """Format issues data."""
        if isinstance(data, list):
            if not data:
                return "No issues found."
            
            formatted = "📋 **GitHub Issues:**\n\n"
            for issue in data[:10]:  # Limit to 10 issues
                formatted += f"**#{issue.get('number')}** {issue.get('title', 'No title')}\n"
                formatted += f"• State: {issue.get('state', 'unknown')}\n"
                formatted += f"• Author: {issue.get('user', {}).get('login', 'unknown')}\n"
                formatted += f"• URL: {issue.get('html_url', 'N/A')}\n\n"
            return formatted
        elif isinstance(data, dict):
            return f"""
📋 **Issue #{data.get('number')}:**
• **Title:** {data.get('title', 'N/A')}
• **State:** {data.get('state', 'N/A')}
• **Author:** {data.get('user', {}).get('login', 'N/A')}
• **Body:** {data.get('body', 'No description')[:200]}...
• **URL:** {data.get('html_url', 'N/A')}
"""
        return str(data)

    def _format_repositories(self, data: Any) -> str:
        """Format repository data."""
        try:
            # Handle GitHub search API response structure
            if isinstance(data, dict) and 'items' in data:
                # This is a search response with pagination info
                repos = data['items']
                total_count = data.get('total_count', len(repos))
                
                if not repos:
                    return "No repositories found."
                    
                formatted = f"📁 **Found {total_count} repositories** (showing top {min(len(repos), 5)}):\n\n"
                for repo in repos[:5]:  # Limit to 5 repos
                    formatted += f"**{repo.get('full_name', repo.get('name', 'Unknown'))}**\n"
                    formatted += f"• Description: {repo.get('description', 'No description')}\n"
                    formatted += f"• Language: {repo.get('language', 'N/A')}\n"
                    formatted += f"• ⭐ {repo.get('stargazers_count', 0)} stars\n"
                    formatted += f"• 🍴 {repo.get('forks_count', 0)} forks\n"
                    formatted += f"• URL: {repo.get('html_url', 'N/A')}\n\n"
                return formatted
                
            elif isinstance(data, list):
                # This is a direct list of repositories
                if not data:
                    return "No repositories found."
                    
                formatted = f"📁 **GitHub Repositories** (showing {min(len(data), 5)}):\n\n"
                for repo in data[:5]:  # Limit to 5 repos
                    formatted += f"**{repo.get('full_name', repo.get('name', 'Unknown'))}**\n"
                    formatted += f"• Description: {repo.get('description', 'No description')}\n"
                    formatted += f"• Language: {repo.get('language', 'N/A')}\n"
                    formatted += f"• ⭐ {repo.get('stargazers_count', 0)} stars\n"
                    formatted += f"• 🍴 {repo.get('forks_count', 0)} forks\n"
                    formatted += f"• URL: {repo.get('html_url', 'N/A')}\n\n"
                return formatted
                
            elif isinstance(data, dict):
                # Single repository
                return f"""
📁 **Repository: {data.get('full_name', 'Unknown')}**
• **Description:** {data.get('description', 'No description')}
• **Language:** {data.get('language', 'N/A')}
• **⭐ Stars:** {data.get('stargazers_count', 0)}
• **🍴 Forks:** {data.get('forks_count', 0)}
• **URL:** {data.get('html_url', 'N/A')}
"""
            else:
                return f"Repository data: {str(data)[:500]}..."
                
        except Exception as e:
            return f"Error formatting repositories: {e}\n\nRaw data: {str(data)[:200]}..."

    def _format_pull_requests(self, data: Any) -> str:
        """Format pull request data."""
        if isinstance(data, list):
            if not data:
                return "No pull requests found."
                
            formatted = "🔀 **Pull Requests:**\n\n"
            for pr in data[:10]:  # Limit to 10 PRs
                formatted += f"**#{pr.get('number')}** {pr.get('title', 'No title')}\n"
                formatted += f"• State: {pr.get('state', 'unknown')}\n"
                formatted += f"• Author: {pr.get('user', {}).get('login', 'unknown')}\n"
                formatted += f"• URL: {pr.get('html_url', 'N/A')}\n\n"
            return formatted
        elif isinstance(data, dict):
            return f"""
🔀 **Pull Request #{data.get('number')}:**
• **Title:** {data.get('title', 'N/A')}
• **State:** {data.get('state', 'N/A')}
• **Author:** {data.get('user', {}).get('login', 'N/A')}
• **Body:** {data.get('body', 'No description')[:200]}...
• **URL:** {data.get('html_url', 'N/A')}
"""
        return str(data)

    async def cleanup(self):
        """Cleans up the MCP connection."""
        self._ctx.logger.info("Cleaning up GitHub MCP connection...")
        await self._exit_stack.aclose()

# --- uAgent Setup ---

chat_proto = Protocol(spec=chat_protocol_spec)
agent = Agent(name=AGENT_NAME, port=AGENT_PORT, mailbox=True)
device_flow_handler = GitHubDeviceFlowHandler()

# This dictionary will hold a client for each user session
session_clients: Dict[str, GitHubMCPClient] = {}

def is_user_authenticated(session_id: str) -> bool:
    """Check if user is authenticated and session hasn't expired"""
    if session_id not in user_sessions:
        return False
    
    session = user_sessions[session_id]
    if 'access_token' not in session:
        return False
    
    # Check session timeout
    last_activity = session.get('last_activity', 0)
    if time.time() - last_activity > SESSION_TIMEOUT:
        # Session expired, clean up
        del user_sessions[session_id]
        return False
    
    # Update last activity
    session['last_activity'] = time.time()
    return True

async def get_authenticated_client(ctx: Context, session_id: str) -> Optional[GitHubMCPClient]:
    """Get or create authenticated MCP client for user session"""
    if session_id in session_clients:
        return session_clients[session_id]
    
    if not is_user_authenticated(session_id):
        return None
    
    # Create new MCP client with user's access token
    access_token = cipher_suite.decrypt(user_sessions[session_id]['access_token'].encode()).decode()
    client = GitHubMCPClient(ctx, access_token)
    await client.connect()
    session_clients[session_id] = client
    return client

async def handle_device_flow_polling(ctx: Context, session_id: str):
    """Handle Device Flow polling for token"""
    session_data = user_sessions[session_id]
    interval = session_data.get('interval', 5)
    expires_in = session_data.get('expires_in', 900)  # 15 minutes
    
    start_time = datetime.now(timezone.utc)
    
    while True:
        # Check if expired
        if (datetime.now(timezone.utc) - start_time).seconds > expires_in:
            ctx.logger.info("Device flow expired")
            break
        
        # Poll for token
        result = await device_flow_handler.poll_for_token(session_id)
        
        if result and result != 'pending' and result != 'slow_down':
            # Got access token!
            access_token = result
            user_info = await device_flow_handler.get_user_info(access_token)
            
            # Store in session
            user_sessions[session_id]['access_token'] = cipher_suite.encrypt(access_token.encode()).decode()
            user_sessions[session_id]['user_info'] = user_info
            user_sessions[session_id]['last_activity'] = time.time()
            
            ctx.logger.info(f" User {user_info.get('login', 'Unknown')} authenticated successfully")
            break
        elif result == 'slow_down':
            interval += 5  # Increase polling interval
        
        await asyncio.sleep(interval)

@chat_proto.on_message(model=ChatMessage)
async def handle_chat_message(ctx: Context, sender: str, msg: ChatMessage):
    session_id = str(ctx.session)

    # Send acknowledgment first
    ack_msg = ChatAcknowledgement(
        timestamp=datetime.now(timezone.utc),
        acknowledged_msg_id=msg.msg_id
    )
    await ctx.send(sender, ack_msg)

    for item in msg.content:
        if isinstance(item, TextContent):
            ctx.logger.info(f"Received message from {sender}: '{item.text}'")
            
            # Check if user is authenticated
            if not is_user_authenticated(session_id):
                # Check if this looks like a GitHub token
                if item.text.startswith('ghp_') and len(item.text) > 20:
                    # User provided a GitHub token directly
                    ctx.logger.info("User provided GitHub token directly")
                    
                    # Validate the token
                    async with httpx.AsyncClient() as client:
                        response = await client.get(
                            "https://api.github.com/user",
                            headers={'Authorization': f'token {item.text}'}
                        )
                        
                        if response.status_code == 200:
                            user_info = response.json()
                            
                            # Also check token scopes for debugging
                            scopes_response = await client.get(
                                device_flow_handler.api_base + "/user",
                                headers={'Authorization': f'token {item.text}'}
                            )
                            
                            # GitHub returns scopes in the X-OAuth-Scopes header
                            if 'X-OAuth-Scopes' in scopes_response.headers:
                                scopes = scopes_response.headers['X-OAuth-Scopes']
                                user_info['token_scopes'] = scopes
                                ctx.logger.info(f"Token validated with required scopes")
                            
                            if 'repo' not in scopes:
                                response_text = "❌ **Token Missing Permissions**\n\nYour token doesn't have 'repo' scope needed to create repositories.\n\nPlease create a new token at https://github.com/settings/tokens/new with these scopes:\n- ✅ repo\n- ✅ user:email\n- ✅ read:user"
                            else:
                                # Store token and user info
                                if session_id not in user_sessions:
                                    user_sessions[session_id] = {}
                                user_sessions[session_id]['access_token'] = cipher_suite.encrypt(item.text.encode()).decode()
                                user_sessions[session_id]['user_info'] = user_info
                                user_sessions[session_id]['last_activity'] = time.time()
                                
                                ctx.logger.info(f"✅ User {user_info.get('login', 'Unknown')} authenticated with manual token")
                                response_text = f"✅ **Authenticated Successfully!**\n\n👤 Welcome {user_info.get('login', 'Unknown')}!\n\nYou can now use all GitHub operations. Try:\n- 'Show my repositories'\n- 'Create a new repository'\n- 'Search for Python projects'"
                        else:
                            response_text = "❌ **Invalid Token**\n\nThe token you provided is invalid. Please check your token and try again.\n\nCreate a new token at: https://github.com/settings/tokens/new"
                    
                    response_msg = ChatMessage(
                        timestamp=datetime.now(timezone.utc),
                        msg_id=str(uuid4()),
                        content=[TextContent(type="text", text=response_text)]
                    )
                    await ctx.send(sender, response_msg)
                    return
                
                # Start OAuth flow if no valid token provided
                ctx.logger.info("Starting GitHub Device Flow authentication...")
                try:
                    device_data = await device_flow_handler.start_device_flow(session_id)
                    
                    # Start polling in background
                    asyncio.create_task(handle_device_flow_polling(ctx, session_id))
                    
                    response_text = f"""
🔐 **GitHub Authentication Required**

Choose one of these authentication methods:

**OPTION 1 (Recommended): Personal Access Token**
1. Visit: https://github.com/settings/tokens/new
2. Create token with scopes: `repo`, `user:email`, `read:user`
3. Copy your token and paste it directly in this chat

**OPTION 2: Device Flow OAuth**  
1. Visit: https://github.com/login/device
2. Enter code: **{device_data['user_code']}**

I'll automatically detect which method you choose!

After authentication, you can use commands like:
• "Show me my profile"
• "Create a new repository" 
• "List issues in microsoft/vscode"
• "Search for Python repositories"
"""
                except Exception as e:
                    response_text = f"Sorry, failed to start GitHub authentication: {e}"
            else:
                # User is authenticated, process their GitHub query
                client = await get_authenticated_client(ctx, session_id)
                if client:
                    response_text = await client.process_query(item.text)
                else:
                    response_text = "Error: Unable to connect to GitHub. Please try authenticating again."
            
            response_msg = ChatMessage(
                timestamp=datetime.now(timezone.utc),
                msg_id=uuid4(),
                content=[TextContent(type="text", text=response_text)]
            )
            await ctx.send(sender, response_msg)
        
        elif isinstance(item, EndSessionContent):
            ctx.logger.info(f"Session ended by {sender}")
            if session_id in session_clients:
                await session_clients[session_id].cleanup()
                del session_clients[session_id]
            if session_id in user_sessions:
                del user_sessions[session_id]
        
        elif isinstance(item, StartSessionContent):
            ctx.logger.info(f"Session started by {sender}")
            # Handle session start

@chat_proto.on_message(model=ChatAcknowledgement)
async def handle_chat_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
    ctx.logger.info(f"Received acknowledgment from {sender}")

@agent.on_event("shutdown")
async def on_shutdown(ctx: Context):
    ctx.logger.info("Agent shutting down, cleaning up all active GitHub sessions.")
    for client in session_clients.values():
        await client.cleanup()

agent.include(chat_proto)

if __name__ == "__main__":
    print(f"GitHub Agent starting on http://localhost:{AGENT_PORT}")
    print(f"Agent address: {agent.address}")
    print("Using GitHub Device Flow OAuth - no callback server needed! ")
    agent.run()
