from datetime import datetime, timezone
from uuid import uuid4
import os
from dotenv import load_dotenv
from openai import OpenAI
from uagents import Context, Protocol, Agent
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    TextContent,
    chat_protocol_spec,
)
from composio import Composio
import json
import re
from typing import Dict, Any

# Load environment variables
load_dotenv()

# Initialize clients
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
composio_client = Composio(api_key=os.getenv("COMPOSIO_API_KEY"))

# Initialize uAgent
agent = Agent(
    name="LinkedIn-ASI-Agent",
    seed="LinkedIn-ASI-Agent",
    port=8048,
    mailbox=True,
)
protocol = Protocol(spec=chat_protocol_spec)

class LinkedInAgent:
    def __init__(self, user_id: str, auth_config_id: str):
        self.user_id = user_id
        self.auth_config_id = auth_config_id
        self.composio = composio_client
        self.openai_client = openai_client
        self.tools = None
        self.connected_account = None
        self.connection_request = None
        self.author_id = None

    def initiate_auth(self) -> str:
        """Initiate LinkedIn authentication"""
        try:
            print(f"🔐 Initiating LinkedIn auth for {self.user_id}...")
            # Use the correct method signature according to Composio documentation
            self.connection_request = self.composio.connected_accounts.initiate(
                user_id=self.user_id,
                auth_config_id=self.auth_config_id
            )
            return f"Please visit this URL to authenticate LinkedIn: {self.connection_request.redirect_url}\nAfter completing, send 'Auth complete' or your next query."
        except Exception as e:
            return f"Error initiating auth: {str(e)}"

    def complete_auth(self) -> bool:
        """Complete authentication"""
        if not self.connection_request:
            return False
        try:
            print("⏳ Checking for authentication completion...")
            self.connected_account = self.connection_request.wait_for_connection(timeout=5)
            self.tools = self.composio.tools.get(user_id=self.user_id, toolkits=["LINKEDIN"])
            print("✅ LinkedIn authentication successful!")
            return True
        except Exception as e:
            print(f"❌ Auth completion failed: {str(e)}")
            return False

    def is_authenticated(self) -> bool:
        """Check if LinkedIn is authenticated"""
        return self.connected_account is not None and self.tools is not None

    def get_author_id(self) -> str:
        """Get LinkedIn author ID"""
        if self.author_id:
            return self.author_id
        
        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                tools=self.tools,
                messages=[
                    {"role": "system", "content": "Use LINKEDIN_GET_MY_INFO to get profile info."},
                    {"role": "user", "content": "Get my LinkedIn profile"}
                ],
            )
            
            result = self.composio.provider.handle_tool_calls(response=response, user_id=self.user_id)
            
            if result and len(result) > 0:
                item = result[0]
                if item.get("successful", False):
                    data = item.get("data", {})
                    response_data = data.get("response_dict", {})
                    author_id = response_data.get("author_id")
                    if author_id:
                        self.author_id = author_id
                        return author_id
            
            return None
        except Exception as e:
            print(f"Error getting author ID: {e}")
            return None

    def process_query(self, user_query: str) -> Dict[str, Any]:
        """Process user query and execute LinkedIn actions"""
        cleaned_query = re.sub(r'^@composio\s+agent\s+', '', user_query, flags=re.IGNORECASE).strip()
        
        # Simple intent detection
        if "create" in cleaned_query.lower() and "post" in cleaned_query.lower():
            intent = "CREATE_POST"
        elif "delete" in cleaned_query.lower() and "post" in cleaned_query.lower():
            intent = "DELETE_POST"
        elif "info" in cleaned_query.lower() or "profile" in cleaned_query.lower():
            intent = "GET_INFO"
        elif "connect" in cleaned_query.lower() or "authenticate" in cleaned_query.lower():
            intent = "AUTH"
        else:
            intent = "UNKNOWN"

        print(f"🧠 Detected intent: {intent} for query: {cleaned_query}")

        if intent == "AUTH":
            auth_url = self.initiate_auth()
            return {"success": True, "result": auth_url}

        if not self.is_authenticated():
            return {"success": False, "error": "LinkedIn not authenticated. Send 'Authenticate LinkedIn' to start auth."}

        try:
            if intent == "CREATE_POST":
                return self._create_post(cleaned_query)
            elif intent == "DELETE_POST":
                return self._delete_post(cleaned_query)
            elif intent == "GET_INFO":
                return self._get_info()
            else:
                return {"success": False, "error": "Unknown command. Try: create post, delete post, or get info"}
        except Exception as e:
            return {"success": False, "error": f"Error: {str(e)}"}

    def _create_post(self, query: str) -> Dict[str, Any]:
        """Create a LinkedIn post"""
        author_id = self.get_author_id()
        if not author_id:
            return {"success": False, "error": "Could not get author ID"}

        # Generate professional blog-style content
        content = self._generate_blog_content(query)
        
        try:
            # Prepare post parameters
            post_params = f"author={author_id}, commentary='{content}', visibility='PUBLIC', lifecycleState='PUBLISHED'"
            
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                tools=self.tools,
                messages=[
                    {"role": "system", "content": "Use LINKEDIN_CREATE_LINKED_IN_POST to create a post. Use the exact parameters provided."},
                    {"role": "user", "content": f"Create a LinkedIn post with {post_params}"}
                ],
            )
            
            result = self.composio.provider.handle_tool_calls(response=response, user_id=self.user_id)
            
            print(f"🔍 Create post result: {json.dumps(result, indent=2)}")
            
            if result and len(result) > 0:
                item = result[0]
                if item.get("successful", False):
                    data = item.get("data", {})
                    response_data = data.get("response_data", {})
                    
                    # Try different possible keys for share ID
                    share_id = (response_data.get("id") or 
                               response_data.get("shareId") or 
                               response_data.get("share_id"))
                    
                    if share_id:
                        # Convert share ID to activity ID for correct URL format
                        if 'urn:li:share:' in share_id:
                            activity_id = share_id.replace('urn:li:share:', 'urn:li:activity:')
                            post_url = f"https://www.linkedin.com/feed/update/{activity_id}/"
                        else:
                            post_url = f"https://www.linkedin.com/feed/update/{share_id}/"
                        
                        # Format content with proper line breaks for chat interface
                        formatted_content = content.replace('\n', '\\n').replace('\r', '')
                        
                        result_text = f"✅ **LinkedIn Post Created Successfully!**\\n\\n📝 **Share ID:** `{share_id}`\\n🔗 **Post URL:** {post_url}\\n\\n📄 **Post Content:**\\n\\n{formatted_content}"
                        
                        return {
                            "success": True,
                            "result": result_text
                        }
                    else:
                        # Format content with proper line breaks for chat interface
                        formatted_content = content.replace('\n', '\\n').replace('\r', '')
                        
                        result_text = f"✅ **LinkedIn Post Created Successfully!**\\n\\n📄 **Post Content:**\\n\\n{formatted_content}"
                        
                        return {
                            "success": True,
                            "result": result_text
                        }
            
            return {"success": False, "error": "Failed to create post"}
        except Exception as e:
            return {"success": False, "error": f"Error creating post: {str(e)}"}

    def _delete_post(self, query: str) -> Dict[str, Any]:
        """Delete a LinkedIn post"""
        # Extract share ID from query
        share_id_match = re.search(r'(\d+)', query)
        if not share_id_match:
            return {"success": False, "error": "Please provide share ID. Example: delete post 7371239374954356736"}
        
        share_id = share_id_match.group(1)
        
        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                tools=self.tools,
                messages=[
                    {"role": "system", "content": "Use LINKEDIN_DELETE_LINKED_IN_POST to delete a post."},
                    {"role": "user", "content": f"Delete LinkedIn post with share ID: {share_id}"}
                ],
            )
            
            result = self.composio.provider.handle_tool_calls(response=response, user_id=self.user_id)
            
            if result and len(result) > 0:
                item = result[0]
                if item.get("successful", False):
                    return {"success": True, "result": "✅ LinkedIn post deleted successfully!"}
            
            return {"success": False, "error": "Failed to delete post"}
        except Exception as e:
            return {"success": False, "error": f"Error deleting post: {str(e)}"}

    def _get_info(self) -> Dict[str, Any]:
        """Get LinkedIn profile info"""
        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                tools=self.tools,
                messages=[
                    {"role": "system", "content": "Use LINKEDIN_GET_MY_INFO to get profile info."},
                    {"role": "user", "content": "Get my LinkedIn profile information"}
                ],
            )
            
            result = self.composio.provider.handle_tool_calls(response=response, user_id=self.user_id)
            
            print(f"🔍 Profile result: {json.dumps(result, indent=2)}")
            
            if result and len(result) > 0:
                item = result[0]
                if item.get("successful", False):
                    data = item.get("data", {})
                    response_data = data.get("response_dict", {})
                    
                    name = response_data.get("name", "Unknown")
                    given_name = response_data.get("given_name", "")
                    family_name = response_data.get("family_name", "")
                    email = response_data.get("email", "Not provided")
                    email_verified = response_data.get("email_verified", False)
                    author_id = response_data.get("author_id", "Not available")
                    sub_id = response_data.get("sub", "Not available")
                    picture_url = response_data.get("picture", "Not available")
                    locale = response_data.get("locale", {})
                    country = locale.get("country", "Not specified") if isinstance(locale, dict) else "Not specified"
                    language = locale.get("language", "Not specified") if isinstance(locale, dict) else "Not specified"
                    
                    return {
                        "success": True,
                        "result": f"""👤 **LinkedIn Profile Information**

**Name:** {name}
**Given Name:** {given_name}
**Family Name:** {family_name}
**Email:** {email}
**Email Verified:** {'Yes' if email_verified else 'No'}
**Country:** {country}
**Language:** {language}
**Author ID:** {author_id}
**Sub ID:** {sub_id}

**Profile Picture:**
![Profile Picture]({picture_url})
                                 """
                    }
            
            return {"success": False, "error": "Failed to get profile info"}
        except Exception as e:
            return {"success": False, "error": f"Error getting profile: {str(e)}"}

    def _generate_blog_content(self, query: str) -> str:
        """Generate professional blog-style content for LinkedIn post"""
        try:
            # Extract topic from query
            topic = self._extract_topic(query)
            
            # Generate comprehensive blog content within LinkedIn's 3000 character limit
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": """You are a professional LinkedIn content writer. Create comprehensive, detailed blog posts that:
                    - Are 6-8 sentences long (detailed but concise)
                    - Use professional but engaging tone
                    - Include relevant emojis (2-3 max)
                    - Are highly engaging and shareable
                    - Sound authentic and personal
                    - Include key insights, analysis, and examples
                    - Have a clear structure: introduction, main points, and conclusion
                    - Include a call-to-action or question to encourage engagement
                    - Focus on professional insights, achievements, industry trends, or personal experiences
                    - Provide substantial value to the LinkedIn professional community
                    - Include specific examples or statistics when relevant
                    - IMPORTANT: Keep total content under 2800 characters to stay within LinkedIn's 3000 character limit
                    - Make it feel like a comprehensive article but concise enough for LinkedIn"""},
                    {"role": "user", "content": f"Create a comprehensive LinkedIn blog post about: {topic}. Make it detailed and insightful but keep it under 2800 characters total."}
                ],
                max_tokens=800,
                temperature=0.7
            )
            
            generated_content = response.choices[0].message.content.strip()
            
            # Ensure content is within LinkedIn's 3000 character limit
            if len(generated_content) > 2800:
                print(f"⚠️ Content too long ({len(generated_content)} chars), truncating...")
                generated_content = generated_content[:2800] + "..."
            
            print(f"📝 Generated content ({len(generated_content)} chars): {generated_content}")
            return generated_content
            
        except Exception as e:
            print(f"Error generating content: {e}")
            # Fallback content
            topic = self._extract_topic(query)
            return f"Excited to share about {topic}! Looking forward to connecting with the community. 🚀"

    def _extract_topic(self, query: str) -> str:
        """Extract topic from query"""
        # Extract text after "about"
        if "about" in query.lower():
            parts = query.lower().split("about")
            if len(parts) > 1:
                return parts[1].strip()
        
        # Extract text after "post"
        if "post" in query.lower():
            parts = query.lower().split("post")
            if len(parts) > 1:
                topic = parts[1].strip()
                if topic.startswith("about"):
                    topic = topic.replace("about", "").strip()
                return topic
        
        # Default topic
        return "my latest update"

    def get_available_operations(self) -> str:
        """Get available operations and help"""
        return """🤖 **LinkedIn Agent - Available Operations**

**Authentication:**
- `connect to LinkedIn <username>` - Connect your LinkedIn account
- `authenticate LinkedIn <username>` - Alternative auth command

**Post Management:**
- `create post about <topic>` - Create a professional LinkedIn post
- `delete post <share_id>` - Delete a specific post by share ID

**Profile Information:**
- `get info` - Get your LinkedIn profile information
- `profile` - Alternative command for profile info

**Help & Examples:**
- `help` - Show this help message
- `blog examples` - Show example post topics
- `examples` - Show example post topics

**Example Commands:**
- `connect to LinkedIn gautammanak1`
- `create post about my new AI project`
- `create post about remote work best practices`
- `delete post 7371239374954356736`
- `get info`

**Note:** You must authenticate first before creating, deleting, or getting profile info! 🔐"""

    def get_blog_examples(self) -> str:
        """Get example blog post queries"""
        return """📝 **Blog Post Examples:**

**Career & Professional:**
- create post about my new job at Fetch.ai
- create post about completing my AI certification
- create post about speaking at TechConf 2024
- create post about my promotion to Senior Developer

**Industry Insights:**
- create post about AI trends in 2024
- create post about remote work best practices
- create post about sustainable technology
- create post about cybersecurity awareness

**Personal Branding:**
- create post about my coding journey
- create post about lessons learned from failures
- create post about mentoring junior developers
- create post about work-life balance

**Project Showcases:**
- create post about my latest web app launch
- create post about contributing to open source
- create post about my startup journey
- create post about my research paper publication

**Networking & Community:**
- create post about attending networking events
- create post about building professional relationships
- create post about giving back to the community
- create post about industry collaboration

**Tips & Advice:**
- create post about productivity hacks
- create post about career development tips
- create post about interview preparation
- create post about leadership skills

Each post will automatically generate professional content and a relevant image! 🖼️"""

# Initialize LinkedInAgent
linkedin_agent = LinkedInAgent(
    user_id="",
    auth_config_id=os.getenv("LINKEDIN_AUTH_CONFIG_ID")
)

def extract_user_id_from_query(text: str) -> str:
    """Extract LinkedIn username from query"""
    patterns = [
        r'linkedin\s+(\w+)',
        r'(\w+)\s+linkedin',
        r'(\w+)$'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            username = match.group(1).strip()
            if username.isalnum() and len(username) >= 3:
                return username
    
    return ""

@protocol.on_message(ChatMessage)
async def handle_message(ctx: Context, sender: str, msg: ChatMessage):
    """Handle incoming messages"""
    await ctx.send(
        sender,
        ChatAcknowledgement(timestamp=datetime.now(timezone.utc), acknowledged_msg_id=msg.msg_id),
    )
    
    text = ""
    for item in msg.content:
        if isinstance(item, TextContent):
            text += item.text

    print(f"📥 Received query: {text}")

    # Check if this is a help request
    if text.lower().strip() in ["help", "what can i do", "available operations", "permissions", "scopes"]:
        response = linkedin_agent.get_available_operations()
    elif text.lower().strip() in ["blog examples", "examples", "blog post examples"]:
        response = linkedin_agent.get_blog_examples()
    else:
        # Check for auth completion
        if linkedin_agent.connection_request and not linkedin_agent.is_authenticated():
            if linkedin_agent.complete_auth():
                response = "✅ LinkedIn authentication completed! Try: create post, delete post, or get info"
            else:
                response = "⏳ Authentication not completed. Please complete auth flow."
        else:
            # Check if authentication request
            if "connect" in text.lower() or "authenticate" in text.lower():
                user_id = extract_user_id_from_query(text)
                if user_id:
                    linkedin_agent.user_id = user_id
                    print(f"🔐 Setting user ID to: {user_id}")
                    result = linkedin_agent.process_query(text)
                    response = result.get("result", "Authentication initiated")
                else:
                    response = "❌ Please provide LinkedIn username. Example: 'connect to LinkedIn gautammanak1'"
            else:
                # Process query
                result = linkedin_agent.process_query(text)
                if result.get("success"):
                    response = result.get("result", "Action completed")
                else:
                    response = f"❌ {result.get('error', 'Unknown error')}"

    print(f"📤 Sending response: {response[:100]}...")
    await ctx.send(
        sender,
        ChatMessage(
            timestamp=datetime.now(timezone.utc),
            msg_id=uuid4(),
            content=[TextContent(type="text", text=response)]
        )
    )

@protocol.on_message(ChatAcknowledgement)
async def handle_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
    """Handle acknowledgment"""
    pass

agent.include(protocol, publish_manifest=True)

if __name__ == "__main__":
    print("🤖 Starting LinkedIn-ASI-Agent...")
    try:
        agent.run()
    except KeyboardInterrupt:
        print("🛑 Agent stopped gracefully. Goodbye!")