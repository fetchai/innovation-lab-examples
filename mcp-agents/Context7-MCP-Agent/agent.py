"""
Context7 MCP Agent for Agentverse

Provides up-to-date documentation and code examples for any library or framework
via Context7 MCP server integration. Makes it discoverable on ASI:One LLM.
"""

import os
import asyncio
import time
from typing import Dict, Any, Optional, List, Tuple
from contextlib import AsyncExitStack
import mcp
from mcp.client.stdio import stdio_client
import anthropic
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

# --- Agent Configuration ---

# Load environment variables from a .env file
load_dotenv()

# Get API keys
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
if not ANTHROPIC_API_KEY:
    raise ValueError("ANTHROPIC_API_KEY not found in .env file")

AGENT_NAME = "context7_agent"
AGENT_PORT = 8007

# User sessions store: session_id -> {authenticated, last_activity}
user_sessions: Dict[str, Dict[str, Any]] = {}

# Session timeout (30 minutes)
SESSION_TIMEOUT = 30 * 60

# --- Enhanced MCP Client Logic ---

class Context7MCPClient:
    """
    Enhanced Context7 MCP Client with iterative search refinement.
    Automatically tries multiple search strategies to find the best library match.
    """
    
    def __init__(self, ctx: Context):
        self._ctx = ctx
        self._session: mcp.ClientSession = None
        self._exit_stack = AsyncExitStack()
        self.anthropic = Anthropic(api_key=ANTHROPIC_API_KEY)
        self.tools = []  # Will be populated after connection
        
        # Search refinement strategies
        self.search_strategies = [
            self._strategy_exact_match,
            self._strategy_add_framework_context,
            self._strategy_add_language_context,
            self._strategy_try_popular_alternatives,
            self._strategy_extract_keywords,
        ]
    
    async def connect(self):
        """Connect to Context7 MCP server via local npx execution"""
        try:
            self._ctx.logger.info("Connecting to Context7 MCP server via npx...")
            
            # Use npx to run Context7 MCP server locally
            params = mcp.StdioServerParameters(
                command="npx",
                args=["-y", "@upstash/context7-mcp"]
            )
            
            read_stream, write_stream = await self._exit_stack.enter_async_context(
                stdio_client(params)
            )
            
            self._session = await self._exit_stack.enter_async_context(
                mcp.ClientSession(read_stream, write_stream)
            )
            
            await self._session.initialize()
            
            # List available tools
            list_tools_result = await self._session.list_tools()
            self.tools = list_tools_result.tools
            
            self._ctx.logger.info(f"Connected to Context7 MCP server with {len(self.tools)} tools")
            for tool in self.tools:
                self._ctx.logger.info(f"Available tool: {tool.name}")
                
        except Exception as e:
            self._ctx.logger.error(f"Failed to connect to Context7 MCP server: {e}")
            raise
    
    def _convert_mcp_tools_to_anthropic_format(self, mcp_tools):
        """Convert MCP tool definitions to Anthropic tool format"""
        anthropic_tools = []
        for tool in mcp_tools:
            anthropic_tool = {
                "name": tool.name,
                "description": tool.description or f"Context7 tool: {tool.name}",
                "input_schema": tool.inputSchema or {"type": "object", "properties": {}}
            }
            anthropic_tools.append(anthropic_tool)
        return anthropic_tools
    
    async def process_query(self, query: str) -> str:
        """
        Enhanced query processing with iterative search refinement.
        Tries multiple search strategies until finding relevant results.
        """
        try:
            query = query.strip()
            self._ctx.logger.info(f"Processing query: '{query}'")
            
            # Try each search strategy until we find good results
            for i, strategy in enumerate(self.search_strategies, 1):
                self._ctx.logger.info(f"Attempt {i}: Trying {strategy.__name__}")
                
                # Generate search terms for this strategy
                search_terms = await strategy(query)
                
                # Try each search term from this strategy
                for term in search_terms:
                    self._ctx.logger.info(f"  Searching for: '{term}'")
                    
                    # Step 1: Search for libraries
                    library_result = await self._session.call_tool(
                        "resolve-library-id", 
                        {"libraryName": term}
                    )
                    
                    # Step 2: Evaluate result quality
                    evaluation = await self._evaluate_search_results(
                        query, term, library_result.content
                    )
                    
                    if evaluation["is_relevant"]:
                        self._ctx.logger.info(f"✅ Found relevant results with term: '{term}'")
                        
                        # Step 3: Select best library ID
                        library_id = evaluation["selected_library_id"]
                        
                        # Step 4: Get documentation with enhanced search
                        docs_result = await self._get_targeted_documentation(library_id, query, term)
                        
                        # Step 5: Format response
                        return await self._format_documentation_response(
                            query, docs_result.content, library_id, term
                        )
                    else:
                        self._ctx.logger.info(f"❌ No relevant results for: '{term}'")
            
            # If we get here, no strategy worked
            return await self._generate_no_results_response(query)
                    
        except Exception as e:
            self._ctx.logger.error(f"Error processing query: {e}")
            return f"❌ Error processing your query: {str(e)}"
    
    # === Enhanced Library Documentation Retrieval ===
    
    async def _get_targeted_documentation(self, library_id: str, original_query: str, search_term: str) -> Any:
        """
        Get targeted documentation from a library using optimized search parameters.
        This is the key improvement that adds the 'topic' parameter for better results.
        """
        try:
            # Strategy 1: Use original query as topic (most specific)
            self._ctx.logger.info(f"Searching {library_id} with topic: '{original_query}'")
            
            docs_result = await self._session.call_tool(
                "get-library-docs",
                {
                    "context7CompatibleLibraryID": library_id,
                    "tokens": 12000,  # High token count for comprehensive results
                    "topic": original_query  # This is the game-changer!
                }
            )
            
            # Check if we got good results
            content_quality = await self._assess_content_quality(docs_result.content, original_query)
            
            if content_quality["is_sufficient"]:
                self._ctx.logger.info(f"✅ High-quality content found with topic: '{original_query}'")
                return docs_result
            
            # Strategy 2: Try with just keywords if original query was too specific
            self._ctx.logger.info(f"Trying keyword-based search...")
            keywords = await self._extract_search_keywords(original_query)
            
            for keyword in keywords:
                self._ctx.logger.info(f"  Trying keyword: '{keyword}'")
                docs_result = await self._session.call_tool(
                    "get-library-docs",
                    {
                        "context7CompatibleLibraryID": library_id,
                        "tokens": 10000,
                        "topic": keyword
                    }
                )
                
                content_quality = await self._assess_content_quality(docs_result.content, original_query)
                if content_quality["is_sufficient"]:
                    self._ctx.logger.info(f"✅ Good content found with keyword: '{keyword}'")
                    return docs_result
            
            # Strategy 3: Fallback to general search (no topic filter)
            self._ctx.logger.info(f"Fallback: General search without topic filter")
            docs_result = await self._session.call_tool(
                "get-library-docs",
                {
                    "context7CompatibleLibraryID": library_id,
                    "tokens": 8000  # Lower tokens since we're getting broader results
                }
            )
            
            return docs_result
            
        except Exception as e:
            self._ctx.logger.error(f"Error getting documentation: {e}")
            # Fallback to simple call if enhanced search fails
            return await self._session.call_tool(
                "get-library-docs", 
                {"context7CompatibleLibraryID": library_id}
            )

    async def _assess_content_quality(self, content: Any, original_query: str) -> Dict[str, Any]:
        """
        Assess if the retrieved content is sufficient for the user's query.
        """
        try:
            text_content = self._extract_text_content(content)
            
            if len(text_content.strip()) < 100:  # Too little content
                return {"is_sufficient": False, "reason": "Insufficient content"}
            
            # Use Claude to assess relevance
            assessment_prompt = f"""
User's original query: "{original_query}"

Retrieved content preview:
{text_content[:1500]}...

Quick assessment:
1. Does this content contain information relevant to the user's query?
2. Are there code examples or specific details that would help answer the question?
3. Is there enough substance to provide a useful response?

Respond with:
SUFFICIENT: [YES/NO]
REASON: [Brief explanation]
"""
            
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.anthropic.messages.create(
                    model="claude-3-5-sonnet-20241022",
                    max_tokens=100,
                    messages=[{"role": "user", "content": assessment_prompt}]
                )
            )
            
            result_text = response.content[0].text.strip()
            
            is_sufficient = "SUFFICIENT: YES" in result_text
            reason = "Good quality content found"
            
            for line in result_text.split('\n'):
                if line.startswith('REASON:'):
                    reason = line.split(':', 1)[1].strip()
            
            return {
                "is_sufficient": is_sufficient,
                "reason": reason
            }
            
        except Exception as e:
            self._ctx.logger.error(f"Error assessing content quality: {e}")
            return {"is_sufficient": True, "reason": "Assessment failed, proceeding"}

    async def _extract_search_keywords(self, query: str) -> List[str]:
        """
        Extract key search terms from the user's query for fallback searches.
        """
        try:
            keyword_prompt = f"""
Extract 2-3 key technical terms from this query that could be used as search topics: "{query}"

Focus on:
- Technology names (uAgent, React, MongoDB, etc.)
- Technical concepts (REST, handlers, authentication, etc.)
- Action words (get, post, create, setup, etc.)

Return just the terms, one per line:
"""
            
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.anthropic.messages.create(
                    model="claude-3-5-sonnet-20241022",
                    max_tokens=80,
                    messages=[{"role": "user", "content": keyword_prompt}]
                )
            )
            
            keywords = [line.strip() for line in response.content[0].text.strip().split('\n') if line.strip()]
            return keywords[:3]
            
        except Exception as e:
            self._ctx.logger.error(f"Error extracting keywords: {e}")
            # Fallback to simple word extraction
            words = query.split()
            return [word for word in words if len(word) > 3][:3]
    
    # === Search Strategies ===
    
    async def _strategy_exact_match(self, query: str) -> List[str]:
        """Strategy 1: Try the query exactly as provided"""
        return [query]
    
    async def _strategy_add_framework_context(self, query: str) -> List[str]:
        """Strategy 2: Add common framework contexts"""
        # Use Claude to intelligently add framework context
        context_prompt = f"""
Given this user query: "{query}"

Generate 3 alternative search terms that add relevant framework or platform context.
Examples:
- "routing" → "next.js routing", "react router", "express routing"
- "authentication" → "passport.js authentication", "firebase auth", "oauth authentication"
- "database" → "mongodb database", "postgresql database", "prisma database"
- "uAgent" → "fetch.ai uAgent", "autonomous agent", "uagents framework"

Respond with just the search terms, one per line:
"""
        
        try:
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.anthropic.messages.create(
                    model="claude-3-5-sonnet-20241022",
                    max_tokens=150,
                    messages=[{"role": "user", "content": context_prompt}]
                )
            )
            
            terms = [line.strip() for line in response.content[0].text.strip().split('\n') if line.strip()]
            return terms[:3]  # Limit to 3 terms
            
        except Exception as e:
            self._ctx.logger.error(f"Error generating framework context: {e}")
            # Fallback to basic framework additions
            frameworks = ["react", "next.js", "node.js", "python", "javascript", "fetch.ai"]
            return [f"{framework} {query}" for framework in frameworks[:2]]
    
    async def _strategy_add_language_context(self, query: str) -> List[str]:
        """Strategy 3: Add programming language context"""
        languages = ["python", "javascript", "typescript", "java", "go", "rust"]
        return [f"{query} {lang}" for lang in languages[:3]]
    
    async def _strategy_try_popular_alternatives(self, query: str) -> List[str]:
        """Strategy 4: Try popular alternatives for common terms"""
        alternatives_map = {
            "agent": ["uagent", "fetch.ai", "autonomous agent", "uagents framework"],
            "uagent": ["fetch.ai uagent", "uagents python", "autonomous agent"],
            "rest": ["fastapi rest", "express rest", "flask rest", "rest api"],
            "api": ["rest api", "graphql api", "api framework"],
            "database": ["mongodb", "postgresql", "sqlite"],
            "auth": ["authentication", "authorization", "oauth"],
            "ml": ["machine learning", "tensorflow", "pytorch"],
            "web": ["web framework", "frontend", "backend"],
            "handlers": ["message handlers", "event handlers", "request handlers"]
        }
        
        query_lower = query.lower()
        for key, alternatives in alternatives_map.items():
            if key in query_lower:
                return alternatives
        
        return []
    
    async def _strategy_extract_keywords(self, query: str) -> List[str]:
        """Strategy 5: Extract and search individual keywords"""
        # Use Claude to extract key terms
        extraction_prompt = f"""
Extract the most important technical keywords from this query: "{query}"

Return 2-3 individual keywords that could be library or framework names.
Focus on:
- Technology names (React, Node.js, MongoDB, uAgent, etc.)
- Technical concepts (authentication, routing, database, handlers, etc.)
- Tool names (Docker, Kubernetes, fetch.ai, etc.)

Respond with just the keywords, one per line:
"""
        
        try:
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.anthropic.messages.create(
                    model="claude-3-5-sonnet-20241022",
                    max_tokens=100,
                    messages=[{"role": "user", "content": extraction_prompt}]
                )
            )
            
            keywords = [line.strip() for line in response.content[0].text.strip().split('\n') if line.strip()]
            return keywords[:3]
            
        except Exception as e:
            self._ctx.logger.error(f"Error extracting keywords: {e}")
            # Fallback to simple word splitting
            words = query.split()
            return [word for word in words if len(word) > 2][:3]
    
    # === Result Evaluation ===
    
    async def _evaluate_search_results(self, original_query: str, search_term: str, content: Any) -> Dict[str, Any]:
        """
        Evaluate search results to determine if they're relevant to the original query.
        Returns evaluation with selected library ID if relevant.
        """
        try:
            # Extract text content
            text_content = self._extract_text_content(content)
            
            if not text_content.strip():
                return {"is_relevant": False, "reason": "No results found"}
            
            # Use Claude to evaluate relevance and select best library
            evaluation_prompt = f"""
Original user query: "{original_query}"
Search term used: "{search_term}"

Library search results:
{text_content}

Please evaluate these results and determine:
1. Are these results relevant to the original user query?
2. If relevant, which library ID is the best match?

Respond in this exact format:
RELEVANT: [YES/NO]
LIBRARY_ID: [Context7-compatible library ID like "/fetchai/docs" or "NONE"]
REASON: [Brief explanation]

Focus on finding libraries that would help answer the original query, even if the search term was different.
"""
            
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.anthropic.messages.create(
                    model="claude-3-5-sonnet-20241022",
                    max_tokens=200,
                    messages=[{"role": "user", "content": evaluation_prompt}]
                )
            )
            
            result_text = response.content[0].text.strip()
            
            # Parse the response
            lines = result_text.split('\n')
            is_relevant = False
            library_id = None
            reason = "Unknown"
            
            for line in lines:
                if line.startswith('RELEVANT:'):
                    is_relevant = 'YES' in line.upper()
                elif line.startswith('LIBRARY_ID:'):
                    lib_part = line.split(':', 1)[1].strip()
                    if lib_part != "NONE":
                        library_id = lib_part
                elif line.startswith('REASON:'):
                    reason = line.split(':', 1)[1].strip()
            
            return {
                "is_relevant": is_relevant and library_id is not None,
                "selected_library_id": library_id,
                "reason": reason
            }
            
        except Exception as e:
            self._ctx.logger.error(f"Error evaluating results: {e}")
            return {"is_relevant": False, "reason": f"Evaluation error: {str(e)}"}
    
    def _extract_text_content(self, content: Any) -> str:
        """Extract text content from various content formats"""
        text_content = ""
        if isinstance(content, list):
            for item in content:
                if hasattr(item, 'text'):
                    text_content += item.text
                elif isinstance(item, dict) and 'text' in item:
                    text_content += item['text']
                elif isinstance(item, str):
                    text_content += item
        else:
            text_content = str(content)
        return text_content
    
    async def _format_documentation_response(self, original_query: str, raw_content: Any, library_id: str, successful_search_term: str) -> str:
        """Format the final documentation response"""
        text_content = self._extract_text_content(raw_content)
        
        if not text_content or text_content.strip() == "":
            return "No documentation found for your query."
        
        formatting_prompt = f"""
Original User Query: "{original_query}"
Successful Search Term: "{successful_search_term}"

Raw Documentation Snippets:
{text_content}

Please format these raw documentation snippets into a clean, well-organized response for the user's original query.

Requirements:
1. Focus on answering the original query, even though we found results using a different search term
2. Create a comprehensive guide based on the user's needs
3. Organize with clear headings and code examples
4. Remove duplicate information and metadata headers
5. Use markdown formatting for readability
6. Make it clear this answers their original question

Provide a professional response that directly addresses: "{original_query}"
"""
        
        try:
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.anthropic.messages.create(
                    model="claude-3-5-sonnet-20241022",
                    max_tokens=4000,
                    messages=[{"role": "user", "content": formatting_prompt}]
                )
            )
            
            formatted_content = response.content[0].text.strip()
            
            # Add source attribution with search context
            attribution = f"\n\n---\n*Found via search: '{successful_search_term}' | Source: Context7 MCP ({library_id})*"
            
            return formatted_content + attribution
            
        except Exception as e:
            self._ctx.logger.error(f"Error formatting response: {e}")
            return f"# Documentation for {original_query}\n\n{text_content}\n\n---\n*Source: Context7 MCP ({library_id})*"
    
    async def _generate_no_results_response(self, query: str) -> str:
        """Generate a helpful response when no relevant results are found"""
        return f"""❌ **No relevant documentation found for: "{query}"**

I tried multiple search strategies but couldn't find relevant documentation. Here are some suggestions:

🔍 **Try being more specific:**
- Add framework names: "Next.js {query}", "React {query}", "Python {query}"
- Include technology context: "{query} tutorial", "{query} examples", "{query} guide"

🔧 **Popular alternatives to search for:**
- Web frameworks: Next.js, React, Express, FastAPI
- Agent frameworks: uAgent, fetch.ai, CrewAI
- Databases: MongoDB, PostgreSQL, Redis
- Cloud: AWS, Google Cloud, Azure
- DevOps: Docker, Kubernetes, Terraform

📝 **Example queries that work well:**
- "uAgent REST handlers"
- "fetch.ai agent messaging"
- "Next.js routing examples"
- "React hooks documentation" 
- "MongoDB connection tutorial"
- "FastAPI authentication"

Feel free to try a more specific query!"""
    
    async def cleanup(self):
        """Clean up the MCP connection"""
        try:
            if self._exit_stack:
                await self._exit_stack.aclose()
            self._ctx.logger.info("Context7 MCP client cleaned up")
        except Exception as e:
            self._ctx.logger.error(f"Error during cleanup: {e}")

# --- uAgent Setup ---

chat_proto = Protocol(spec=chat_protocol_spec)
agent = Agent(name=AGENT_NAME, port=AGENT_PORT, mailbox=True)

# Store MCP clients per session
session_clients: Dict[str, Context7MCPClient] = {}

def is_session_valid(session_id: str) -> bool:
    """Check if session is valid and hasn't expired"""
    if session_id not in user_sessions:
        return False
    
    last_activity = user_sessions[session_id].get('last_activity', 0)
    if time.time() - last_activity > SESSION_TIMEOUT:
        # Session expired, clean it up
        if session_id in user_sessions:
            del user_sessions[session_id]
        return False
    
    return True

async def get_context7_client(ctx: Context, session_id: str) -> Context7MCPClient:
    """Get or create Context7 MCP client for session"""
    if session_id not in session_clients or not is_session_valid(session_id):
        # Create new client
        client = Context7MCPClient(ctx)
        await client.connect()
        session_clients[session_id] = client
    
    return session_clients[session_id]

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
            
            # Update session activity
            if session_id not in user_sessions:
                user_sessions[session_id] = {}
            user_sessions[session_id]['last_activity'] = time.time()
            
            query = item.text.strip()
            
            # Check for help queries
            if any(word in query.lower() for word in ['help', 'what can you do', 'capabilities']):
                response_text = """📚 **Context7 Documentation Agent**

I can help you get up-to-date documentation and code examples for any library or framework using intelligent search strategies!

**🔍 Smart Search Features:**
• **Iterative Refinement**: If your query doesn't match initially, I try multiple search strategies
• **Context Enhancement**: I add framework and language context automatically  
• **Quality Assessment**: I evaluate results to ensure they're relevant to your question
• **Fallback Strategies**: Multiple approaches to find what you're looking for
• **Topic-Focused Search**: I use your exact query to find the most relevant documentation sections

**🛠️ What I can do:**
• Find libraries and resolve them to Context7-compatible IDs
• Get comprehensive documentation with code examples using targeted topic search
• Try alternative search terms if the first attempt doesn't work
• Assess content quality to ensure relevance before responding
• Provide version-specific documentation when available

**✨ Example queries:**
• "uAgent REST handlers" → I'll try "uAgent", "fetch.ai uAgent", "autonomous agent REST", etc.
• "authentication" → I'll try "passport.js authentication", "firebase auth", "oauth", etc.
• "database connection" → I'll try "mongodb connection", "postgresql", "prisma", etc.

**🎯 How it works:**
1. **Exact Match**: Try your query as-is
2. **Framework Context**: Add popular framework names
3. **Language Context**: Add programming language context
4. **Popular Alternatives**: Try common alternatives for your terms
5. **Keyword Extraction**: Search for individual technical terms
6. **Topic-Focused Retrieval**: Use your query as a topic filter for better results
7. **Quality Assessment**: Evaluate content relevance before responding

Just ask me about any library, framework, or technology - I'll find the right documentation!"""
            else:
                try:
                    # Show that we're starting the search process
                    processing_msg = ChatMessage(
                        msg_id=str(uuid4()),
                        timestamp=datetime.now(timezone.utc),
                        content=[TextContent(type="text", text="🔍 Searching for documentation... This may take a moment as I try multiple search strategies with topic-focused retrieval.")]
                    )
                    await ctx.send(sender, processing_msg)
                    
                    # Get Context7 client and process query with enhanced search
                    client = await get_context7_client(ctx, session_id)
                    response_text = await client.process_query(query)
                    
                except Exception as e:
                    ctx.logger.error(f"Error processing query: {e}")
                    response_text = f"""❌ **Error processing your request**

Something went wrong while searching for documentation: {str(e)}

🔧 **Troubleshooting:**
• Check your internet connection
• Try a simpler query
• Make sure the MCP server is running

🆘 **Need help?** Try asking for 'help' to see available features."""
            
            # Create and send final response
            response_msg = ChatMessage(
                msg_id=str(uuid4()),
                timestamp=datetime.now(timezone.utc),
                content=[TextContent(type="text", text=response_text)]
            )
            await ctx.send(sender, response_msg)

@chat_proto.on_message(model=ChatAcknowledgement)
async def handle_chat_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
    pass

@agent.on_event("shutdown")
async def on_shutdown(ctx: Context):
    for client in session_clients.values():
        await client.cleanup()

agent.include(chat_proto)

if __name__ == "__main__":
    print(f"Context7 Agent starting on http://localhost:{AGENT_PORT}")
    print(f"Agent address: {agent.address}")
    print("📚 Ready to provide up-to-date documentation with enhanced search!")
    
    try:
        agent.run()
    except KeyboardInterrupt:
        print("Agent stopped by user")
    except Exception as e:
        print(f"Agent error: {e}")