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
import base64
import re
from typing import Optional, Dict, Any, List

# Load environment variables
load_dotenv()

# Initialize clients
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
if not os.getenv("OPENAI_API_KEY"):
    raise ValueError("OPENAI_API_KEY environment variable is required.")

composio_client = Composio(api_key=os.getenv("COMPOSIO_API_KEY"))

# Initialize uAgent
agent = Agent(
    name="Gmail-ASI-Agent",
    seed="Gmail-ASI-Agent",
    port=8001,
    mailbox=True,
)
protocol = Protocol(spec=chat_protocol_spec)

class GmailAgent:
    def __init__(self, user_email: str, auth_config_id: str):
        """
        Initialize the Gmail Agent
        Args:
            user_email: User's email address
            auth_config_id: Gmail auth config ID from Composio dashboard
        """
        self.user_email = user_email
        self.auth_config_id = auth_config_id
        self.composio = composio_client
        self.openai_client = openai_client
        self.tools = None
        self.connected_account = None
        self.connection_request = None
        self.gmail_tools = [
            "GMAIL_CREATE_EMAIL_DRAFT",
            "GMAIL_DELETE_DRAFT",
            "GMAIL_DELETE_MESSAGE",
            "GMAIL_FETCH_EMAILS",
            "GMAIL_FETCH_MESSAGE_BY_MESSAGE_ID",
            "GMAIL_GET_ATTACHMENT",
            "GMAIL_LIST_DRAFTS",
            "GMAIL_MOVE_TO_TRASH",
            "GMAIL_PATCH_LABEL",
            "GMAIL_REPLY_TO_THREAD",
            "GMAIL_SEARCH_PEOPLE",
            "GMAIL_SEND_DRAFT",
            "GMAIL_SEND_EMAIL",
            "GMAIL_ADD_LABEL_TO_EMAIL",
            "GMAIL_CREATE_LABEL",
            "GMAIL_FETCH_MESSAGE_BY_THREAD_ID",
            "GMAIL_GET_CONTACTS",
            "GMAIL_GET_PEOPLE",
            "GMAIL_GET_PROFILE",
            "GMAIL_LIST_LABELS",
            "GMAIL_LIST_THREADS",
            "GMAIL_MODIFY_THREAD_LABELS",
            "GMAIL_REMOVE_LABEL",
            "GMAIL_REPLY_TO_EMAIL",
            "GMAIL_MARK_AS_READ",
            "GMAIL_MARK_AS_UNREAD",
            "GMAIL_SEARCH_EMAILS",
            "GMAIL_CREATE_DRAFT"
        ]

    def initiate_auth(self) -> str:
        """Initiate Gmail authentication and return the URL"""
        try:
            print(f"🔐 Initiating Gmail auth for {self.user_email}...")
            self.connection_request = self.composio.connected_accounts.initiate(
                user_id=self.user_email,
                auth_config_id=self.auth_config_id,
            )
            return f"Please visit this URL to authenticate Gmail: {self.connection_request.redirect_url}\nAfter completing, send 'Auth complete' or your next query."
        except Exception as e:
            return f"Error initiating auth: {str(e)}"

    def complete_auth(self) -> bool:
        """Complete authentication by checking connection status"""
        if not self.connection_request:
            return False
        try:
            print("⏳ Checking for authentication completion...")
            self.connected_account = self.connection_request.wait_for_connection(timeout=5)
            self.tools = self.composio.tools.get(user_id=self.user_email, toolkits=["GMAIL"])
            print("✅ Gmail authentication successful!")
            print(f"📧 Available tools: {len(self.gmail_tools)} Gmail tools loaded")
            print("Example queries:")
            print("- Create a label called 'fetch.ai'")
            print("- Get my profile")
            print("- Read emails from google-maps-noreply@google.com")
            print("- Move emails from john@example.com to trash")
            print("- List my contacts")
            print("- Delete spam mail")
            return True
        except TimeoutError:
            return False
        except Exception as e:
            print(f"❌ Auth completion failed: {str(e)}")
            return False

    def is_authenticated(self) -> bool:
        """Check if Gmail is authenticated"""
        return self.connected_account is not None and self.tools is not None

    def process_query(self, user_query: str) -> Dict[str, Any]:
        """
        Process natural language query and execute appropriate Gmail actions
        Args:
            user_query: Natural language query from user
        Returns:
            Result of the executed action
        """
        # Strip @composio agent prefix
        cleaned_query = re.sub(r'^@composio\s+agent\s+', '', user_query, flags=re.IGNORECASE).strip()
        intent_analysis = self.analyze_user_intent(cleaned_query)
        intent = intent_analysis.get("intent", "UNKNOWN")
        parameters = intent_analysis.get("parameters", {})
        confidence = intent_analysis.get("confidence", 0.0)
        print(f"🧠 Detected intent: {intent} (confidence: {confidence}) for query: {cleaned_query}")

        if intent == "AUTH":
            auth_url = self.initiate_auth()
            return {"success": True, "intent": "AUTH", "formatted_result": auth_url}

        if not self.is_authenticated():
            return {"success": False, "error": "Gmail not authenticated. Send 'Authenticate Gmail' to start auth."}

        try:
            # Handle tool-specific intents directly
            if intent.startswith("GMAIL_"):
                # For GMAIL_SEND_EMAIL, use only that specific tool
                if intent == "GMAIL_SEND_EMAIL":
                    # Get only the GMAIL_SEND_EMAIL tool
                    send_email_tools = self.composio.tools.get(user_id=self.user_email, tools=["GMAIL_SEND_EMAIL"])
                    
                    # Create the email content
                    recipient = parameters.get("recipient", "")
                    subject = parameters.get("subject", "")
                    content = parameters.get("content", "")
                    
                    # If only subject is provided, generate content
                    if subject and not content:
                        content = self._generate_email_content(subject, recipient)
                        print(f"📝 Generated content for '{subject}': {content[:100]}...")
                    
                    # Create the prompt for sending email
                    email_prompt = f"Send an email to {recipient} with the subject '{subject}' and the body '{content}'"
                    
                    response = self.openai_client.chat.completions.create(
                        model="gpt-4o-mini",
                        tools=send_email_tools,
                        messages=[
                            {"role": "system", "content": "You are a helpful assistant. Use the GMAIL_SEND_EMAIL tool to send emails."},
                            {"role": "user", "content": email_prompt}
                        ],
                    )
                else:
                    # For other tools, use the existing approach
                    tool_prompt = self._create_tool_specific_prompt(intent, cleaned_query, parameters)
                    
                    # Use the specific tool directly with detailed instructions
                    system_prompt = f"""You are a Gmail assistant for {self.user_email}. 
                    
                    CRITICAL INSTRUCTION: You MUST use the {intent} tool to handle this request. Do NOT use any other tool.
                    
                    Tool Usage Rules:
                    1. Use ONLY the {intent} tool - no exceptions
                    2. Do NOT call GMAIL_CREATE_EMAIL_DRAFT when user asks to "send email"
                    3. Do NOT call GMAIL_GET_CONTACTS when user asks for profile or other actions
                    4. Provide the correct parameters as specified in the user request
                    5. Execute the tool with the exact parameters needed
                    
                    User request: {cleaned_query}
                    Extracted parameters: {json.dumps(parameters, indent=2) if parameters else 'None'}
                    
                    Remember: If user says "send email", use GMAIL_SEND_EMAIL, NOT GMAIL_CREATE_EMAIL_DRAFT
                    """
                    
                    response = self.openai_client.chat.completions.create(
                        model="gpt-4o-mini",
                        tools=self.tools,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": tool_prompt}
                        ],
                    )
                
                raw_result = self.composio.provider.handle_tool_calls(response=response, user_id=self.user_email)
                
                # Debug: Print the raw result structure for email sending
                print(f"🔍 Email send raw result: {json.dumps(raw_result, indent=2)}")
                
                # For GMAIL_SEND_EMAIL, create a custom formatted result
                if intent == "GMAIL_SEND_EMAIL":
                    formatted_result = self._format_email_send_result(raw_result, cleaned_query)
                    print(f"📧 Email formatted result: {formatted_result}")
                else:
                    formatted_result = self._format_result(raw_result, cleaned_query, parameters)
                
                # Add debug information for contacts
                if intent == "GMAIL_GET_CONTACTS":
                    print(f"🔍 Contacts debug - Raw result: {json.dumps(raw_result, indent=2)}")
                    if raw_result and len(raw_result) > 0:
                        first_item = raw_result[0]
                        print(f"🔍 Contacts debug - First item: {json.dumps(first_item, indent=2)}")
                        if "data" in first_item:
                            data = first_item["data"]
                            print(f"🔍 Contacts debug - Data: {json.dumps(data, indent=2)}")
                            if "response_data" in data:
                                response_data = data["response_data"]
                                print(f"🔍 Contacts debug - Response data: {json.dumps(response_data, indent=2)}")
                
                result = {
                    "success": True,
                    "query": cleaned_query,
                    "intent": intent,
                    "parameters": parameters,
                    "result": raw_result,
                    "formatted_result": formatted_result,
                    "model_response": response.choices[0].message.content or "Action completed successfully"
                }
            else:
                # Fallback for non-tool intents or legacy handling
                system_prompt = f"""You are a Gmail assistant for {self.user_email} with access to all Gmail tools: {', '.join(self.gmail_tools)}.
                Use the most appropriate tool for the user's request. Provide clear, actionable responses."""
                response = self.openai_client.chat.completions.create(
                    model="gpt-4o-mini",
                    tools=self.tools,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": cleaned_query}
                    ],
                )
                raw_result = self.composio.provider.handle_tool_calls(response=response, user_id=self.user_email)
                result = {
                    "success": True,
                    "query": cleaned_query,
                    "intent": intent,
                    "parameters": parameters,
                    "result": raw_result,
                    "formatted_result": self._format_result(raw_result, cleaned_query, parameters),
                    "model_response": response.choices[0].message.content or "Action completed successfully"
                }
            
            refined_result = self.refine_response_with_gpt(result.get("formatted_result", "Action completed successfully"))
            result["formatted_result"] = refined_result
            print(f"📤 Original formatted result: {result.get('formatted_result', 'None')}")
            print(f"📤 Refined result: {refined_result}")
            print(f"📤 Sending response to AgentVerse: {refined_result[:100]}...")
            return result
        except Exception as e:
            error_msg = f"❌ Error processing query: {str(e)}"
            print(error_msg)
            return {"success": False, "error": error_msg, "query": cleaned_query}

    def _create_tool_specific_prompt(self, intent: str, query: str, parameters: Dict[str, Any]) -> str:
        """Create specific prompts for different Gmail tools"""
        base_prompt = f"Execute the {intent} tool with the following request: {query}"
        
        # Add tool-specific instructions and parameters
        if intent == "GMAIL_CREATE_LABEL":
            label_name = parameters.get("label_name", "")
            return f"{base_prompt}\n\nCreate a new Gmail label with the name: '{label_name}'\nUse the GMAIL_CREATE_LABEL tool with the label name parameter."
        
        elif intent == "GMAIL_GET_PROFILE":
            return f"{base_prompt}\n\nGet the user's Gmail profile information using the GMAIL_GET_PROFILE tool."
        
        elif intent == "GMAIL_SEND_EMAIL":
            recipient = parameters.get("recipient", "")
            subject = parameters.get("subject", "")
            content = parameters.get("content", "")
            
            # If only subject is provided, generate professional email content
            if subject and not content:
                email_content = self._generate_email_content(subject, recipient)
                return f"{base_prompt}\n\nIMPORTANT: Use GMAIL_SEND_EMAIL tool (NOT GMAIL_CREATE_EMAIL_DRAFT)\n\nSend an email to: {recipient}\nSubject: {subject}\nGenerated Content: {email_content}\n\nExecute GMAIL_SEND_EMAIL with recipient={recipient}, subject={subject}, content={email_content}"
            else:
                return f"{base_prompt}\n\nIMPORTANT: Use GMAIL_SEND_EMAIL tool (NOT GMAIL_CREATE_EMAIL_DRAFT)\n\nSend an email to: {recipient}\nSubject: {subject}\nContent: {content}\n\nExecute GMAIL_SEND_EMAIL with recipient={recipient}, subject={subject}, content={content}"
        
        elif intent == "GMAIL_FETCH_EMAILS":
            return f"{base_prompt}\n\nFetch recent emails from the user's inbox using the GMAIL_FETCH_EMAILS tool."
        
        elif intent == "GMAIL_SEARCH_EMAILS":
            query_param = parameters.get("query", "")
            sender = parameters.get("sender", "")
            return f"{base_prompt}\n\nSearch for emails matching: {query_param or sender}\nUse the GMAIL_SEARCH_EMAILS tool with appropriate search criteria."
        
        elif intent == "GMAIL_LIST_DRAFTS":
            return f"{base_prompt}\n\nList all draft emails using the GMAIL_LIST_DRAFTS tool."
        
        elif intent == "GMAIL_GET_CONTACTS":
            start_index = parameters.get("start_index", 0)
            end_index = parameters.get("end_index", 10)
            if start_index > 0 or end_index > 10:
                return f"{base_prompt}\n\nGet contacts {start_index + 1}-{end_index} from the user's contact list using the GMAIL_GET_CONTACTS tool."
            else:
                return f"{base_prompt}\n\nGet the user's contact list using the GMAIL_GET_CONTACTS tool."
        
        elif intent == "GMAIL_PATCH_LABEL":
            old_name = parameters.get("old_name", "")
            new_name = parameters.get("new_name", "")
            return f"{base_prompt}\n\nUpdate the label '{old_name}' to '{new_name}' using the GMAIL_PATCH_LABEL tool."
        
        elif intent == "GMAIL_REPLY_TO_EMAIL":
            reply_content = parameters.get("content", "")
            return f"{base_prompt}\n\nReply to the email with: {reply_content}\nUse the GMAIL_REPLY_TO_EMAIL tool."
        
        elif intent == "GMAIL_DELETE_MESSAGE":
            email_id = parameters.get("email_id", "")
            sender = parameters.get("sender", "")
            return f"{base_prompt}\n\nDelete the email from {sender} using the GMAIL_DELETE_MESSAGE tool."
        
        elif intent == "GMAIL_MARK_AS_UNREAD":
            return f"{base_prompt}\n\nMark emails as unread using the GMAIL_MARK_AS_UNREAD tool."
        
        else:
            # Default case for other tools
            return f"{base_prompt}\n\nUse the {intent} tool to handle this request with the provided parameters: {json.dumps(parameters, indent=2) if parameters else 'None'}"

    def _format_email_send_result(self, result: Any, query: str) -> str:
        """Format email sending result specifically"""
        try:
            if not result or not isinstance(result, list):
                return "❌ Email sending failed: No response received"
            
            for item in result:
                if not item.get("successful", False):
                    error = item.get("error", "Unknown error")
                    return f"❌ Email sending failed: {error}"
                
                data = item.get("data", {})
                response_data = data.get("response_data", {})
                
                # Check for successful email sending indicators in response_data
                if "id" in response_data or "threadId" in response_data:
                    response = ["✅ Email sent successfully!"]
                    if "id" in response_data:
                        response.append(f"📧 Message ID: {response_data['id']}")
                    if "threadId" in response_data:
                        response.append(f"🧵 Thread ID: {response_data['threadId']}")
                    
                    # Add email details from the original query
                    # Extract recipient and subject from the query
                    import re
                    recipient_match = re.search(r'to\s+([^\s]+@[^\s]+)', query, re.IGNORECASE)
                    subject_match = re.search(r"subject\s+['\"]([^'\"]+)['\"]", query, re.IGNORECASE)
                    
                    if recipient_match:
                        response.append(f"📤 To: {recipient_match.group(1)}")
                    if subject_match:
                        response.append(f"📋 Subject: {subject_match.group(1)}")
                    
                    return "\n".join(response)
                
                # If no response_data but successful, assume it worked
                if item.get("successful", False):
                    return "✅ Email sent successfully!"
            
            return "❌ Email sending failed: Unexpected response format"
            
        except Exception as e:
            return f"❌ Error formatting email result: {str(e)}"

    def _generate_email_content(self, subject: str, recipient: str) -> str:
        """Generate professional email content based on subject using OpenAI"""
        try:
            # Analyze subject to determine email type and tone
            subject_lower = subject.lower()
            
            # Determine email type and tone based on subject keywords
            if any(word in subject_lower for word in ['meeting', 'call', 'discuss', 'chat', 'sync']):
                email_type = "meeting_request"
                tone = "professional and collaborative"
            elif any(word in subject_lower for word in ['update', 'progress', 'status', 'report', 'milestone']):
                email_type = "progress_update"
                tone = "informative and professional"
            elif any(word in subject_lower for word in ['thank', 'thanks', 'appreciation', 'grateful']):
                email_type = "thank_you"
                tone = "warm and appreciative"
            elif any(word in subject_lower for word in ['urgent', 'asap', 'emergency', 'critical']):
                email_type = "urgent"
                tone = "professional and urgent"
            elif any(word in subject_lower for word in ['invitation', 'invite', 'event', 'join']):
                email_type = "invitation"
                tone = "friendly and welcoming"
            elif any(word in subject_lower for word in ['proposal', 'suggestion', 'recommendation']):
                email_type = "proposal"
                tone = "professional and persuasive"
            else:
                email_type = "general"
                tone = "professional and courteous"
            
            # Create detailed system prompt with specific templates
            system_prompt = f"""You are an expert business email writer with 10+ years of experience. Generate a highly professional email based on the subject line.

Email Type: {email_type}
Tone: {tone}
Recipient: {recipient}
Subject: {subject}

PROFESSIONAL EMAIL GUIDELINES:
1. Use formal business language appropriate for the recipient
2. Include a professional greeting with the recipient's name
3. Write 3-4 well-structured paragraphs (150-250 words total)
4. Use clear, concise sentences
5. Include relevant context and details
6. End with a clear call to action or next steps
7. Use professional closing (Best regards, Sincerely, etc.)
8. Include your name and title if appropriate

EMAIL STRUCTURE:
- Greeting: "Dear [Name],"
- Opening: Professional introduction and context
- Body: Main content with relevant details
- Closing: Summary and next steps
- Signature: Professional closing with your name

TONE REQUIREMENTS:
- {tone}
- Professional but not overly formal
- Engaging and personable
- Clear and actionable

Generate a complete, professional email body that follows these guidelines."""
            
            # Add specific examples for better generation
            user_prompt = f"""Generate a professional email for the following:

Recipient: {recipient}
Subject: {subject}
Email Type: {email_type}

Please create a well-structured, professional email that would be appropriate for business communication. Make it engaging and include relevant details that would be expected for this type of email."""
            
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=500,
                temperature=0.6
            )
            
            generated_content = response.choices[0].message.content.strip()
            print(f"📝 Generated {email_type} email content for subject '{subject}': {generated_content[:100]}...")
            return generated_content
            
        except Exception as e:
            print(f"Error generating email content: {e}")
            # Enhanced professional fallback template
            recipient_name = recipient.split('@')[0] if '@' in recipient else recipient
            sender_name = self.user_email.split('@')[0] if '@' in self.user_email else self.user_email
            
            return f"""Dear {recipient_name},

I hope this email finds you well.

{subject}

I would appreciate your response at your earliest convenience.

Best regards,
{sender_name}"""

        except Exception as e:
            print(f"Error generating email content: {e}")        

    def _format_result(self, result: Any, query: str, parameters: Dict[str, Any] = None) -> str:
        """Format the result into a readable string"""
        try:
            if parameters is None:
                parameters = {}
            if not result or not isinstance(result, list):
                return "No data returned from the operation."
            formatted_output = []
            for item in result:
                if not item.get("successful", False):
                    error = item.get("error", "Unknown error")
                    
                    # Handle specific authentication scope errors
                    if "insufficient authentication scopes" in error.lower() or "403" in error:
                        formatted_output.append("🔐 **Authentication Scope Issue Detected**")
                        formatted_output.append("=" * 50)
                        formatted_output.append("❌ **Error**: Insufficient permissions to perform this action")
                        formatted_output.append("")
                        formatted_output.append("**Required Action**:")
                        formatted_output.append("1. Contact your administrator to update Gmail integration scopes")
                        formatted_output.append("2. Ensure the integration has `https://mail.google.com/` scope")
                        formatted_output.append("3. Re-authenticate your Gmail account")
                        formatted_output.append("")
                        formatted_output.append("**Alternative**: Try other operations like:")
                        formatted_output.append("- List emails (read-only)")
                        formatted_output.append("- Get profile information")
                        formatted_output.append("- List labels")
                        formatted_output.append("")
                        formatted_output.append("**Technical Details**:")
                        formatted_output.append(f"Error: {error}")
                    else:
                        formatted_output.append(f"❌ Error: {error}")
                    continue
                data = item.get("data", {})
                
                # Check for email sending success first
                if "messageId" in data or "threadId" in data:
                    formatted_output.append("✅ Email sent successfully!")
                    if "messageId" in data:
                        formatted_output.append(f"📧 Message ID: {data['messageId']}")
                    if "threadId" in data:
                        formatted_output.append(f"🧵 Thread ID: {data['threadId']}")
                elif "response_data" in data:
                    # Check if response_data contains profile information
                    response_data = data.get("response_data", {})
                    print(f"🔍 Processing response_data: {json.dumps(response_data, indent=2)}")
                    if "emailAddress" in response_data:  # Profile data
                        print("🔍 Detected profile data")
                        formatted_output.append(self._format_profile(response_data))
                    elif "id" in response_data and "name" in response_data and "labelListVisibility" in response_data:  # Label data
                        print("🔍 Detected label data")
                        formatted_output.append(self._format_label_creation(response_data))
                    elif "id" in response_data and "message" in response_data and "labelIds" in response_data.get("message", {}):  # Draft data
                        print("🔍 Detected draft data")
                        formatted_output.append(self._format_draft_creation(response_data))
                    else:
                        print("🔍 Treating as contacts data")
                        # Handle other response_data types (like contacts)
                        # Extract pagination parameters from the query
                        start_index = 0
                        end_index = 10
                        if "start_index" in parameters:
                            start_index = parameters.get("start_index", 0)
                        if "end_index" in parameters:
                            end_index = parameters.get("end_index", 10)
                        
                        # Check if response_data is empty and handle accordingly
                        if not response_data:
                            formatted_output.append("👥 No contacts found or contacts data is empty.")
                            formatted_output.append("💡 **Possible reasons:**")
                            formatted_output.append("- No contacts in your Gmail account")
                            formatted_output.append("- Contacts API access not granted")
                            formatted_output.append("- Authentication scope issue")
                        else:
                            formatted_output.extend(self._format_contacts(response_data, start_index, end_index - start_index))
                elif "emailAddress" in data:  # Direct profile data
                    formatted_output.append(self._format_profile(data))
                elif "messages" in data:
                    formatted_output.extend(self._format_emails(data["messages"]))
                elif "threads" in data:
                    formatted_output.extend(self._format_threads(data["threads"]))
                elif "drafts" in data:
                    formatted_output.extend(self._format_drafts(data["drafts"]))
                elif "labels" in data:
                    formatted_output.extend(self._format_labels(data["labels"]))
                else:
                    formatted_output.append("✅ Operation completed successfully")
            return "\n".join(formatted_output) if formatted_output else "✅ Operation completed successfully"
        except Exception as e:
            return f"Error formatting result: {str(e)}"

    def _format_emails(self, messages: list) -> list:
        """Format emails with basic details"""
        formatted = []
        if not messages:
            formatted.append("📭 No emails found matching your criteria.")
            return formatted
        formatted.append(f"📧 Found {len(messages)} email(s):")
        formatted.append("=" * 60)
        for i, msg in enumerate(messages, 1):
            subject = msg.get("subject", "No Subject")
            sender = msg.get("sender", "Unknown Sender")
            date = msg.get("messageTimestamp", "")
            preview = msg.get("preview", {}).get("body", "")
            if date:
                try:
                    dt = datetime.fromisoformat(date.replace('Z', '+00:00'))
                    formatted_date = dt.strftime("%Y-%m-%d %H:%M")
                except:
                    formatted_date = date
            else:
                formatted_date = "Unknown Date"
            formatted.append(f"\n📨 Email #{i}")
            formatted.append(f"📋 Subject: {subject}")
            formatted.append(f"👤 From: {sender}")
            formatted.append(f"📅 Date: {formatted_date}")
            if preview:
                if len(preview) > 200:
                    preview = preview[:200] + "..."
                formatted.append(f"📝 Preview: {preview}")
            formatted.append("-" * 40)
        return formatted

    def _format_emails_with_full_content(self, messages: list) -> str:
        """Format emails with full body content"""
        formatted = []
        if not messages:
            return "📭 No emails found matching your criteria."
        formatted.append(f"📧 Found {len(messages)} email(s):")
        formatted.append("=" * 60)
        for i, msg in enumerate(messages, 1):
            subject = msg.get("subject", "No Subject")
            sender = msg.get("sender", "Unknown Sender")
            date = msg.get("messageTimestamp", "")
            content = self._extract_email_content(msg)
            if date:
                try:
                    dt = datetime.fromisoformat(date.replace('Z', '+00:00'))
                    formatted_date = dt.strftime("%Y-%m-%d %H:%M")
                except:
                    formatted_date = date
            else:
                formatted_date = "Unknown Date"
            formatted.append(f"\n📨 Email #{i}")
            formatted.append(f"📋 Subject: {subject}")
            formatted.append(f"👤 From: {sender}")
            formatted.append(f"📅 Date: {formatted_date}")
            if content:
                if len(content) > 1000:
                    content = content[:1000] + "..."
                formatted.append(f"📝 Full Content: {content}")
            else:
                formatted.append("📝 No content available")
            formatted.append("-" * 40)
        return "\n".join(formatted)

    def _extract_email_content(self, msg: dict) -> str:
        """Extract full email content (plain text or HTML)"""
        try:
            payload = msg.get("payload", {})
            parts = payload.get("parts", [])
            for part in parts:
                if part.get("mimeType") == "text/plain":
                    body_data = part.get("body", {}).get("data", "")
                    if body_data:
                        body_data = body_data.replace('-', '+').replace('_', '/')
                        while len(body_data) % 4:
                            body_data += '='
                        decoded = base64.b64decode(body_data).decode('utf-8', errors='ignore')
                        return self._clean_email_text(decoded)
                elif part.get("mimeType") == "text/html":
                    body_data = part.get("body", {}).get("data", "")
                    if body_data:
                        body_data = body_data.replace('-', '+').replace('_', '/')
                        while len(body_data) % 4:
                            body_data += '='
                        decoded = base64.b64decode(body_data).decode('utf-8', errors='ignore')
                        clean_text = re.sub('<[^<]+?>', '', decoded)
                        return self._clean_email_text(clean_text)
            body = payload.get("body", {})
            if body.get("data"):
                body_data = body["data"].replace('-', '+').replace('_', '/')
                while len(body_data) % 4:
                    body_data += '='
                decoded = base64.b64decode(body_data).decode('utf-8', errors='ignore')
                return self._clean_email_text(decoded)
            return ""
        except Exception:
            return ""

    def _clean_email_text(self, text: str) -> str:
        """Clean email text for readability"""
        if not text:
            return ""
        text = re.sub(r'\n\s*\n', '\n\n', text)
        text = re.sub(r' +', ' ', text)
        return text.strip()

    def _format_drafts(self, drafts: list) -> list:
        formatted = []
        if not drafts:
            formatted.append("📝 No drafts found.")
            return formatted
        formatted.append(f"📝 Found {len(drafts)} draft(s):")
        formatted.append("=" * 50)
        for i, draft in enumerate(drafts, 1):
            message = draft.get("message", {})
            subject = message.get("subject", "No Subject")
            date = message.get("messageTimestamp", "")
            preview = message.get("preview", {}).get("body", "")
            if date:
                try:
                    dt = datetime.fromisoformat(date.replace('Z', '+00:00'))
                    formatted_date = dt.strftime("%Y-%m-%d %H:%M")
                except:
                    formatted_date = date
            else:
                formatted_date = "Unknown Date"
            formatted.append(f"\n📝 Draft #{i}")
            formatted.append(f"📋 Subject: {subject}")
            formatted.append(f"📅 Created: {formatted_date}")
            if preview:
                if len(preview) > 150:
                    preview = preview[:150] + "..."
                formatted.append(f"📄 Content: {preview}")
            formatted.append("-" * 30)
        return formatted

    def _format_labels(self, labels: list) -> list:
        formatted = []
        if not labels:
            formatted.append("🏷️ No labels found.")
            return formatted
        formatted.append(f"🏷️ Found {len(labels)} label(s):")
        formatted.append("=" * 40)
        system_labels = [label for label in labels if label.get("type") == "system"]
        user_labels = [label for label in labels if label.get("type") != "system"]
        if system_labels:
            formatted.append("\n📋 System Labels:")
            for label in system_labels:
                formatted.append(f"  • {label.get('name', 'Unknown')}")
        if user_labels:
            formatted.append("\n👤 Your Labels:")
            for label in user_labels:
                formatted.append(f"  • {label.get('name', 'Unknown')}")
        return formatted

    def _format_threads(self, threads: list) -> list:
        """Format email threads with details"""
        formatted = []
        if not threads:
            formatted.append("🧵 No email threads found.")
            return formatted
        
        formatted.append(f"🧵 Found {len(threads)} email thread(s):")
        formatted.append("=" * 60)
        
        for i, thread in enumerate(threads, 1):
            thread_id = thread.get("id", "Unknown")
            snippet = thread.get("snippet", "No preview available")
            history_id = thread.get("historyId", "Unknown")
            
            # Clean up the snippet (remove HTML entities and extra spaces)
            import re
            clean_snippet = re.sub(r'&[^;]+;', ' ', snippet)  # Remove HTML entities
            clean_snippet = re.sub(r'\s+', ' ', clean_snippet).strip()  # Clean up whitespace
            
            # Truncate long snippets
            if len(clean_snippet) > 150:
                clean_snippet = clean_snippet[:150] + "..."
            
            formatted.append(f"\n🧵 Thread #{i}")
            formatted.append(f"🆔 Thread ID: {thread_id}")
            formatted.append(f"📝 Snippet: {clean_snippet}")
            formatted.append(f"🕰️ History ID: {history_id}")
            formatted.append("-" * 60)
        
        return formatted

    def _format_contacts(self, response_data: dict, start_index: int = 0, contacts_per_page: int = 10) -> str:
        """Format contacts response into a readable string with pagination"""
        try:
            formatted = []
            
            # Handle empty response data
            if not response_data:
                return "👥 No contacts found.\n\n💡 **Possible reasons:**\n- No contacts in your Gmail account\n- Contacts API access not granted\n- Authentication scope issue\n- Gmail People API not enabled"
            
            # Check for different response structures
            connections = None
            if "connections" in response_data:
                connections = response_data.get("connections", [])
            elif "people" in response_data:
                connections = response_data.get("people", [])
            elif isinstance(response_data, list):
                connections = response_data
            else:
                # Try to find contacts in the response structure
                for key, value in response_data.items():
                    if isinstance(value, list) and value and isinstance(value[0], dict):
                        if any("name" in item or "emailAddresses" in item for item in value):
                            connections = value
                            break
            
            if not connections:
                return "👥 No contacts found in the response.\n\n💡 **Debug Info:**\n- Response structure: " + str(type(response_data)) + "\n- Response keys: " + str(list(response_data.keys()) if isinstance(response_data, dict) else "N/A")
            
            total_contacts = len(connections)
            
            # Calculate pagination
            end_index = min(start_index + contacts_per_page, total_contacts)
            current_page = (start_index // contacts_per_page) + 1
            total_pages = (total_contacts + contacts_per_page - 1) // contacts_per_page
            
            formatted.append(f"👥 Found {total_contacts} contact(s):")
            formatted.append(f"📄 Showing contacts {start_index + 1}-{end_index} of {total_contacts}")
            formatted.append(f"📖 Page {current_page} of {total_pages}")
            formatted.append("=" * 60)
            
            # Show contacts for current page
            for i in range(start_index, end_index):
                person = connections[i]
                contact_number = i + 1
                
                # Get contact ID
                resource_name = person.get("resourceName", "No ID")
                contact_id = resource_name.split('/')[-1] if '/' in resource_name else resource_name
                
                # Get names
                names = person.get("names", [])
                name = names[0].get("displayName", "Unknown") if names else "Unknown"
                given_name = names[0].get("givenName", "") if names else ""
                family_name = names[0].get("familyName", "") if names else ""
                
                # Get emails
                emails = person.get("emailAddresses", [])
                primary_email = emails[0].get("value", "No email") if emails else "No email"
                
                # Get phone numbers
                phones = person.get("phoneNumbers", [])
                primary_phone = phones[0].get("value", "No phone") if phones else "No phone"
                
                # Get organizations
                orgs = person.get("organizations", [])
                org_name = orgs[0].get("name", "No organization") if orgs else "No organization"
                org_title = orgs[0].get("title", "No title") if orgs else "No title"
                
                formatted.append(f"\n👤 Contact #{contact_number}")
                formatted.append(f"🆔 Contact ID: {contact_id}")
                formatted.append(f"📛 Full Name: {name}")
                if given_name or family_name:
                    formatted.append(f"📝 Given Name: {given_name}")
                    formatted.append(f"📝 Family Name: {family_name}")
                formatted.append(f"📧 Primary Email: {primary_email}")
                formatted.append(f"📞 Primary Phone: {primary_phone}")
                formatted.append(f"🏢 Organization: {org_name}")
                formatted.append(f"💼 Title: {org_title}")
                
                # Show all emails if there are multiple
                if len(emails) > 1:
                    formatted.append(f"📧 All Emails ({len(emails)}):")
                    for j, email_info in enumerate(emails, 1):
                        email_value = email_info.get("value", "")
                        email_type = email_info.get("type", "unknown")
                        formatted.append(f"   {j}. {email_value} ({email_type})")
                
                # Show all phone numbers if there are multiple
                if len(phones) > 1:
                    formatted.append(f"📞 All Phones ({len(phones)}):")
                    for j, phone_info in enumerate(phones, 1):
                        phone_value = phone_info.get("value", "")
                        phone_type = phone_info.get("type", "unknown")
                        formatted.append(f"   {j}. {phone_value} ({phone_type})")
                
                formatted.append("-" * 60)
            
            # Add pagination navigation
            formatted.append("\n📋 **Pagination Navigation:**")
            if start_index > 0:
                prev_start = max(0, start_index - contacts_per_page)
                formatted.append(f"⬅️ **Previous Page:** Show contacts {prev_start + 1}-{start_index}")
            
            if end_index < total_contacts:
                next_start = end_index
                next_end = min(next_start + contacts_per_page, total_contacts)
                formatted.append(f"➡️ **Next Page:** Show contacts {next_start + 1}-{next_end}")
            
            formatted.append(f"\n💡 **Tip:** Say 'Show contacts 11-20' or 'Next page of contacts' to see more contacts!")
            
            return "\n".join(formatted)
        except Exception as e:
            return f"Error formatting contacts: {str(e)}"

    def _format_profile(self, profile_data: dict) -> str:
        """Format Gmail profile data"""
        try:
            if not profile_data:
                return "👤 No profile data found."
            email_address = profile_data.get("emailAddress", "Unknown")
            messages_total = profile_data.get("messagesTotal", 0)
            threads_total = profile_data.get("threadsTotal", 0)
            history_id = profile_data.get("historyId", "N/A")
            formatted = [
                "👤 Gmail Profile Information:",
                "=" * 40,
                f"📧 Email Address: {email_address}",
                f"📬 Total Messages: {messages_total}",
                f"🧵 Total Threads: {threads_total}",
                f"🕰️ History ID: {history_id}"
            ]
            return "\n".join(formatted)
        except Exception as e:
            return f"Error formatting profile: {str(e)}"

    def _format_label_creation(self, label_data: dict) -> str:
        """Format label creation result"""
        try:
            if not label_data:
                return "🏷️ Label creation failed: No data received"
            
            label_id = label_data.get("id", "Unknown")
            label_name = label_data.get("name", "Unknown")
            visibility = label_data.get("labelListVisibility", "Unknown")
            message_visibility = label_data.get("messageListVisibility", "Unknown")
            
            formatted = [
                "✅ Label created successfully!",
                "=" * 40,
                f"🏷️ Label Name: {label_name}",
                f"🆔 Label ID: {label_id}",
                f"👁️ Label Visibility: {visibility}",
                f"📧 Message Visibility: {message_visibility}"
            ]
            return "\n".join(formatted)
        except Exception as e:
            return f"Error formatting label creation: {str(e)}"

    def compose_email_with_ai(self, recipient: str, subject: str = "", content: str = "", context: str = "") -> Dict[str, str]:
        try:
            system_prompt = """You are a professional email writing assistant. Compose clear, professional emails based on user input.
            Guidelines:
            - Use a professional but friendly tone
            - Include proper greeting and closing
            - Make the email clear and concise
            - Adapt formality based on recipient and context
            - If no subject is provided, create an appropriate one
            - Expand minimal content professionally
            Return JSON: {"subject": "Subject line", "body": "Email body"}"""
            user_prompt = f"""Compose an email for:
            - Recipient: {recipient}
            - Subject: {subject or 'Please create an appropriate subject'}
            - Content/Context: {content or context}
            - Additional context: {context if context != content else ''}"""
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={"type": "json_object"}
            )
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            print(f"Error composing email: {e}")
            return {
                "subject": subject or "Message",
                "body": content or "Hello,\n\nI hope this email finds you well.\n\nBest regards"
            }

    def refine_response_with_gpt(self, raw_response: str) -> str:
        """Refine raw result with GPT for clean format"""
        try:
            # Check if this is a label creation response and preserve it
            if "Label created successfully" in raw_response or "🏷️ Label Name:" in raw_response:
                return raw_response  # Don't modify label creation responses
            
            # Check if this is a draft creation response and preserve it
            if "Draft email created successfully" in raw_response or "📝 Draft ID:" in raw_response:
                return raw_response  # Don't modify draft creation responses
            
            system_prompt = """You are a response refiner. Take the raw output from a Gmail operation and format it into a user-friendly response:
            - Use bullet points, headers, and emojis for readability.
            - Summarize long content, keeping key details.
            - Maintain a professional, concise tone.
            - IMPORTANT: If the response already contains "✅ Label created successfully" or "✅ Draft email created successfully" or similar success messages, return it unchanged.
            - Example: For profile, list email, message count, thread count; for labels, confirm creation; for drafts, confirm creation.
            Return the refined response as a string."""
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": raw_response}
                ],
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"Error refining response: {e}")
            return raw_response

    def analyze_user_intent(self, message: str) -> Dict[str, Any]:
        """Analyze user intent and map to specific Gmail tools"""
        try:
            system_prompt = """You are a Gmail tool selector. Analyze the user query and determine which specific Gmail tool should be used from the available tools:

            Available Gmail Tools:
            - GMAIL_FETCH_EMAILS: For listing/fetching emails (e.g., 'list my emails', 'show recent emails', 'get my inbox', 'show last 5 emails')
            - GMAIL_SEARCH_EMAILS: For searching emails with specific criteria (e.g., 'find emails from john', 'search for spam emails', 'find emails from IIT Mandi')
            - GMAIL_SEND_EMAIL: For sending new emails immediately (e.g., 'send email to john@example.com', 'compose email', 'send an email to...')
            - GMAIL_REPLY_TO_EMAIL: For replying to specific emails (e.g., 'reply to email', 'respond to message')
            - GMAIL_REPLY_TO_THREAD: For replying to email threads (e.g., 'reply to thread', 'respond to conversation')
            - GMAIL_MARK_AS_READ: For marking emails as read (e.g., 'mark as read', 'mark email read')
            - GMAIL_MARK_AS_UNREAD: For marking emails as unread (e.g., 'mark as unread', 'mark email unread', 'provide me unread mail')
            - GMAIL_DELETE_MESSAGE: For deleting emails (e.g., 'delete email', 'remove message', 'delete the email from sender')
            - GMAIL_MOVE_TO_TRASH: For moving emails to trash (e.g., 'move to trash', 'trash email')
            - GMAIL_FETCH_MESSAGE_BY_MESSAGE_ID: For reading specific email by ID (e.g., 'read email with ID', 'get message by ID')
            - GMAIL_FETCH_MESSAGE_BY_THREAD_ID: For reading specific thread by ID (e.g., 'read thread with ID', 'get thread by ID')
            - GMAIL_GET_PROFILE: For getting user profile info (e.g., 'get my profile', 'show profile', 'my info', 'show my Gmail profile info')
            - GMAIL_CREATE_LABEL: For creating new labels (e.g., 'create label', 'make new label', 'add label called work', 'create a label called Work')
            - GMAIL_ADD_LABEL_TO_EMAIL: For adding labels to emails (e.g., 'add label to email', 'tag email')
            - GMAIL_REMOVE_LABEL: For removing labels from emails (e.g., 'remove label', 'untag email')
            - GMAIL_MODIFY_THREAD_LABELS: For modifying thread labels (e.g., 'modify thread labels', 'update thread tags')
            - GMAIL_PATCH_LABEL: For updating label properties (e.g., 'update label', 'modify label', 'rename label Work to Work Projects')
            - GMAIL_LIST_LABELS: For listing all labels (e.g., 'list labels', 'show labels', 'get labels')
            - GMAIL_GET_CONTACTS: For getting contact list (e.g., 'get contacts', 'list contacts', 'show contacts', 'list my contacts', 'show contacts 11-20', 'next page of contacts')
            - GMAIL_SEARCH_PEOPLE: For searching people (e.g., 'search people', 'find contact', 'look up person')
            - GMAIL_GET_ATTACHMENT: For downloading attachments (e.g., 'get attachment', 'download file', 'save attachment')
            - GMAIL_LIST_THREADS: For listing email threads (e.g., 'list threads', 'show conversations', 'get threads')
            - GMAIL_CREATE_EMAIL_DRAFT: For creating draft emails (e.g., 'create draft', 'save draft', 'draft email')
            - GMAIL_SEND_DRAFT: For sending existing drafts (e.g., 'send draft', 'send saved email')
            - GMAIL_DELETE_DRAFT: For deleting drafts (e.g., 'delete draft', 'remove draft')
            - GMAIL_LIST_DRAFTS: For listing drafts (e.g., 'list drafts', 'show drafts', 'get drafts', 'show all my drafts')
            - GMAIL_GET_PEOPLE: For getting people information (e.g., 'get person info', 'show contact details')

            Special Cases:
            - AUTH: For authentication requests (e.g., 'authenticate gmail', 'connect gmail', 'login to gmail')

            Extract relevant parameters for the selected tool:
            - For GMAIL_SEND_EMAIL: recipient, subject, content
            - For GMAIL_SEARCH_EMAILS: query, sender, is_spam
            - For GMAIL_CREATE_LABEL: label_name (extract the label name from quotes or after "called")
            - For GMAIL_PATCH_LABEL: old_name, new_name (extract both old and new names)
            - For GMAIL_REPLY_TO_EMAIL: content, sender
            - For GMAIL_DELETE_MESSAGE: sender, email_id
            - For GMAIL_MARK_AS_UNREAD: query (for filtering emails)
            - For GMAIL_GET_CONTACTS: start_index, end_index (extract pagination from queries like 'show contacts 11-20', 'next page')
            - For specific email operations: email_id, thread_id
            - For label operations: label_id, email_id

            IMPORTANT: Be very specific about which tool to use. If the query mentions "create a label", use GMAIL_CREATE_LABEL, not GMAIL_GET_CONTACTS.
            If the query mentions "show my profile", use GMAIL_GET_PROFILE, not GMAIL_GET_CONTACTS.
            If the query mentions "show last X emails", use GMAIL_FETCH_EMAILS.
            If the query mentions "rename label", use GMAIL_PATCH_LABEL.
            If the query mentions "delete the email from", use GMAIL_DELETE_MESSAGE.
            If the query mentions "send email" or "send an email", use GMAIL_SEND_EMAIL, NOT GMAIL_CREATE_EMAIL_DRAFT.
            If the query mentions "create draft" or "save draft", use GMAIL_CREATE_EMAIL_DRAFT.

            Parameter extraction examples:
            - "Create a label called 'Work'" → {"intent": "GMAIL_CREATE_LABEL", "parameters": {"label_name": "Work"}}
            - "Rename label 'Work' to 'Work Projects'" → {"intent": "GMAIL_PATCH_LABEL", "parameters": {"old_name": "Work", "new_name": "Work Projects"}}
            - "Delete the email from gomez.nick@joininkeep.com" → {"intent": "GMAIL_DELETE_MESSAGE", "parameters": {"sender": "gomez.nick@joininkeep.com"}}
            - "Send an email to john@example.com" → {"intent": "GMAIL_SEND_EMAIL", "parameters": {"recipient": "john@example.com"}}
            - "Send an email to john@example.com with subject 'Project Update'" → {"intent": "GMAIL_SEND_EMAIL", "parameters": {"recipient": "john@example.com", "subject": "Project Update"}}
            - "Send email to team@company.com subject 'Weekly Report'" → {"intent": "GMAIL_SEND_EMAIL", "parameters": {"recipient": "team@company.com", "subject": "Weekly Report"}}
            - "Show contacts 11-20" → {"intent": "GMAIL_GET_CONTACTS", "parameters": {"start_index": 10, "end_index": 20}}
            - "Next page of contacts" → {"intent": "GMAIL_GET_CONTACTS", "parameters": {"start_index": 10, "end_index": 20}}
            - "More contact list" → {"intent": "GMAIL_GET_CONTACTS", "parameters": {"start_index": 10, "end_index": 20}}

            Return JSON: {"intent": "TOOL_NAME", "parameters": {...}, "confidence": float}
            Use high confidence (0.8-1.0) for clear matches, lower for ambiguous cases."""
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": message}
                ],
                response_format={"type": "json_object"}
            )
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            print(f"Error analyzing intent: {e}")
            return {"intent": "UNKNOWN", "parameters": {}, "confidence": 0.0}

    def get_available_operations(self) -> str:
        """
        Returns a string listing all available Gmail operations and their capabilities.
        """
        operations_list = []
        for tool_name in self.gmail_tools:
            if tool_name == "GMAIL_SEND_EMAIL":
                operations_list.append("✅ `Send Email`: Send a new email to a recipient.")
            elif tool_name == "GMAIL_CREATE_EMAIL_DRAFT":
                operations_list.append("✅ `Create Email Draft`: Save a new email as a draft.")
            elif tool_name == "GMAIL_SEND_DRAFT":
                operations_list.append("✅ `Send Draft`: Send an existing draft email.")
            elif tool_name == "GMAIL_DELETE_DRAFT":
                operations_list.append("✅ `Delete Draft`: Delete a draft email.")
            elif tool_name == "GMAIL_LIST_DRAFTS":
                operations_list.append("✅ `List Drafts`: Show all your draft emails.")
            elif tool_name == "GMAIL_GET_PROFILE":
                operations_list.append("✅ `Get Profile`: Show your Gmail profile information (email, message count, thread count).")
            elif tool_name == "GMAIL_GET_CONTACTS":
                operations_list.append("✅ `List Contacts`: Show your Gmail contacts list.")
            elif tool_name == "GMAIL_SEARCH_EMAILS":
                operations_list.append("✅ `Search Emails`: Search for emails based on criteria (e.g., 'search for spam', 'find emails from john').")
            elif tool_name == "GMAIL_FETCH_EMAILS":
                operations_list.append("✅ `List Emails`: Show recent emails from your inbox.")
            elif tool_name == "GMAIL_MOVE_TO_TRASH":
                operations_list.append("✅ `Move to Trash`: Move emails to the trash folder.")
            elif tool_name == "GMAIL_DELETE_MESSAGE":
                operations_list.append("✅ `Delete Message`: Delete a specific email from a sender.")
            elif tool_name == "GMAIL_MARK_AS_READ":
                operations_list.append("✅ `Mark as Read`: Mark emails as read.")
            elif tool_name == "GMAIL_MARK_AS_UNREAD":
                operations_list.append("✅ `Mark as Unread`: Mark emails as unread.")
            elif tool_name == "GMAIL_REPLY_TO_EMAIL":
                operations_list.append("✅ `Reply to Email`: Reply to a specific email.")
            elif tool_name == "GMAIL_REPLY_TO_THREAD":
                operations_list.append("✅ `Reply to Thread`: Reply to an entire email thread.")
            elif tool_name == "GMAIL_PATCH_LABEL":
                operations_list.append("✅ `Modify Label`: Rename or change visibility of a label.")
            elif tool_name == "GMAIL_MODIFY_THREAD_LABELS":
                operations_list.append("✅ `Modify Thread Labels`: Change labels for an entire email thread.")
            elif tool_name == "GMAIL_CREATE_LABEL":
                operations_list.append("✅ `Create Label`: Create a new Gmail label.")
            elif tool_name == "GMAIL_ADD_LABEL_TO_EMAIL":
                operations_list.append("✅ `Add Label to Email`: Add a label to an existing email.")
            elif tool_name == "GMAIL_REMOVE_LABEL":
                operations_list.append("✅ `Remove Label`: Remove a label from an email.")
            elif tool_name == "GMAIL_FETCH_MESSAGE_BY_MESSAGE_ID":
                operations_list.append("✅ `Get Message by ID`: Read a specific email by its ID.")
            elif tool_name == "GMAIL_FETCH_MESSAGE_BY_THREAD_ID":
                operations_list.append("✅ `Get Thread by ID`: Read a specific email thread by its ID.")
            elif tool_name == "GMAIL_GET_PEOPLE":
                operations_list.append("✅ `Get People`: Get detailed information about a person (e.g., contact details).")
            elif tool_name == "GMAIL_SEARCH_PEOPLE":
                operations_list.append("✅ `Search People`: Search for people in your contacts.")
            elif tool_name == "GMAIL_GET_ATTACHMENT":
                operations_list.append("✅ `Get Attachment`: Download a file attachment from an email.")
            elif tool_name == "GMAIL_LIST_LABELS":
                operations_list.append("✅ `List Labels`: Show all labels in your Gmail account.")
            elif tool_name == "GMAIL_LIST_THREADS":
                operations_list.append("✅ `List Threads`: Show all email threads in your inbox.")
            else:
                operations_list.append(f"✅ `{tool_name}`: (No specific details available)")

        return "\n\nAvailable Gmail Operations:\n" + "\n".join(operations_list)

# Initialize GmailAgent without auth
gmail_agent = GmailAgent(
    user_email="gautam.kumar@fetch.ai",
    auth_config_id=os.getenv("GMAIL_AUTH_CONFIG_ID")
)

@protocol.on_message(ChatMessage)
async def handle_message(ctx: Context, sender: str, msg: ChatMessage):
    """Handle incoming messages from AgentVerse via uAgent"""
    await ctx.send(
        sender,
        ChatAcknowledgement(timestamp=datetime.now(timezone.utc), acknowledged_msg_id=msg.msg_id),
    )
    text = ""
    for item in msg.content:
        if isinstance(item, TextContent):
            text += item.text

    print(f"📥 Received query from AgentVerse: {text}")

    # Check for auth completion if pending
    if gmail_agent.connection_request and not gmail_agent.is_authenticated():
        if gmail_agent.complete_auth():
            response = "✅ Gmail authentication completed successfully! Try commands like 'Create a label called fetch.ai' or 'Get my profile'.\n\n💡 **Need help?** Say 'help' to see what operations are available with your current permissions.\n\n⚠️ **Note**: Some operations like deleting emails may require additional authentication scopes."
        else:
            response = "⏳ Authentication not yet completed. Please complete the auth flow in your browser and try again."
    else:
        # Check for special help commands
        if text.lower().strip() in ["help", "what can i do", "available operations", "permissions", "scopes"]:
            response = gmail_agent.get_available_operations()
        else:
            # Process query
            try:
                result = gmail_agent.process_query(text)
                if result.get("success"):
                    response = result.get("formatted_result", "Action completed successfully")
                else:
                    response = f"❌ Error: {result.get('error', 'Unknown error')}"
            except Exception as e:
                response = f"❌ Sorry, couldn't process that: {str(e)}"

    print(f"📤 Sending response to AgentVerse: {response[:100]}...")
    await ctx.send(
        sender,
        ChatMessage(
            timestamp=datetime.now(timezone.utc),
            msg_id=uuid4(),
            content=[
                TextContent(type="text", text=response),
            ]
        )
    )

@protocol.on_message(ChatAcknowledgement)
async def handle_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
    """Handle acknowledgment from AgentVerse"""
    pass

agent.include(protocol, publish_manifest=True)

if __name__ == "__main__":
    print("🤖 Starting Gmail-ASI-Agent...")
    try:
        agent.run()
    except KeyboardInterrupt:
        print("🛑 Agent stopped gracefully. Goodbye!")
