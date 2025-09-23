# Gmail uAgent (Composio + LangChain + uAgent)
![uagents](https://img.shields.io/badge/uagents-4A90E2) ![innovationlab](https://img.shields.io/badge/innovationlab-3D8BD3) ![chatprotocol](https://img.shields.io/badge/chatprotocol-1D3BD4) [![X](https://img.shields.io/badge/X-black.svg?logo=X&logoColor=white)](https://x.com/gautammanak02)

Welcome to the **Gmail-ASI-Agent**, an intelligent Gmail assistant powered by the [uAgents framework](https://github.com/fetchai/uAgents) and [Composio](https://composio.dev). This agent integrates with Gmail via the Composio SDK to perform a comprehensive range of email operations with intelligent intent recognition. Deployed on [AgentVerse](https://agentverse.ai), it processes natural language queries with dynamic authentication and delivers user-friendly responses.

A Gmail assistant built with uAgents framework, Composio SDK, and LangChain for intelligent email management.

## Quick Start

**Run the agent:**
```bash
python agent.py
```

**Required Environment Variables:**
- `COMPOSIO_API_KEY` - Your Composio API key
- `GMAIL_AUTH_CONFIG_ID` - Your Gmail auth configuration ID

**Basic Usage Examples:**
- **Connect:** `Connect to my mail you@example.com`
- **Send Email:** `Send email to: recipient@example.com, Subject: Hello, Body: How are you?`
- **Fetch Inbox:** `Please fetch 10 emails from my inbox`
- **Reply:** `Reply to: user@example.com, Thread Id: 1995..., Body: Thanks!`
- **Move to Trash:** `Move to trash, Message ID: 1997171166a1b98f`
- **Get Contacts:** `Get contacts`
- **Fetch Thread:** `Fetch thread, Thread Id: 1995...`
- **Get Profile:** `Get profile`
- **Create Draft:** `Create draft, To: user@example.com, Subject: Hello, Body: Hi there`
- **Send Draft:** `Send draft, Draft Id: r123abc`
- **Delete Draft:** `Delete draft, Draft Id: r123abc`

**Key Features:**
- Remembers your authenticated email per chat sender
- Include `From: you@example.com` to switch account (optional)
- Outputs are formatted in Markdown

- **Core Gmail Operations**: Essential Gmail functionality via Composio SDK:
  - **Email Sending**: Send emails with LangChain agent integration (`GMAIL_SEND_EMAIL`)
  - **Email Fetching**: Retrieve emails from inbox with configurable parameters (`GMAIL_FETCH_EMAILS`)
  - **Thread Management**: Reply to email threads (`GMAIL_REPLY_TO_THREAD`)
  - **Email Organization**: Move emails to trash (`GMAIL_MOVE_TO_TRASH`)
  - **Contact Management**: Get contacts and search people (`GMAIL_GET_CONTACTS`, `GMAIL_SEARCH_PEOPLE`)
  - **Profile Access**: Get Gmail profile information (`GMAIL_GET_PROFILE`)
  - **Draft Management**: Create, send, delete, and list drafts (`GMAIL_CREATE_EMAIL_DRAFT`, `GMAIL_SEND_DRAFT`, `GMAIL_DELETE_DRAFT`, `GMAIL_LIST_DRAFTS`)
  - **Thread Messages**: Fetch messages from specific threads (`GMAIL_FETCH_MESSAGE_BY_THREAD_ID`)

- **Intelligent Natural Language Processing**: Advanced intent recognition that maps user queries to specific Gmail operations
- **Dynamic Authentication**: Secure OAuth2 authentication flow with user email management
- **Professional Response Formatting**: Markdown-formatted responses with clear action confirmations
- **Multi-User Support**: Remembers authenticated email per chat sender
- **Flexible Input Parsing**: Supports both comma-separated and multi-line input formats
- **Error Handling**: Comprehensive error handling with helpful user guidance

## Setup Instructions 🛠️

1. **Clone the Repository**:
   ```bash
   git clone https://github.com/fetchai/innovation-lab-examples.git
   cd innovation-lab-examples/Composio/gmail-agent
   ```

2. **Install Dependencies**:
   ```bash
   pip install uagents uagents-core uagents-contrib composio-langchain langchain python-dotenv
   ```

3. **Set Up Environment Variables**:
   Create a `.env` file in the project root:
   ```env
   COMPOSIO_API_KEY=your_composio_api_key
   GMAIL_AUTH_CONFIG_ID=your_gmail_auth_config_id
   ```

4. **Run the Agent**:
   ```bash
   python agent.py
   ```
   The agent starts on port 8028 with mailbox enabled for communication.

5. **Docker Support** (Optional):
   ```bash
   docker-compose up --build
   ```
   The agent will be available on port 8028 when using Docker.

## Usage Examples 📬

### **Authentication**
- Query: `Connect to my mail you@example.com`
- Response: Provides OAuth2 URL for Gmail authentication
- Follow-up: Complete OAuth flow in browser, then use other commands

### **Email Sending**
- Query: `Send email to: john@example.com, Subject: Project Update, Body: Hi John, here's the latest update on our project.`
- Response:
  ```
  ✅ Email sent successfully to john@example.com!

  Email Details:
  - From: you@example.com
  - Subject: Project Update
  - Body: Hi John, here's the latest update on our project.

  Gmail Response:
  - Email ID: 18c1234567890abc
  - Thread ID: 18c1234567890abc
  - Labels: SENT
  - Status: ✅ Sent successfully
  ```

### **Fetching Emails**
- Query: `Please fetch 10 emails from my inbox`
- Response:
  ```
  📥 Fetched Emails (latest)

  - 1. Subject: Your Google Maps Update
    - From: google-maps-noreply@google.com
    - To: you@example.com
    - Time: 2025-01-27 10:00
    - Message ID: 18c1234567890abc
    - Thread ID: 18c1234567890abc
    - Labels: INBOX
    - Body: Your recent activity on Google Maps includes...

  - 2. Subject: New Feature Alert
    - From: google-maps-noreply@google.com
    - To: you@example.com
    - Time: 2025-01-26 14:30
    - Message ID: 18c1234567890def
    - Thread ID: 18c1234567890def
    - Labels: INBOX
    - Body: Introducing our new navigation feature...
  ```

### **Contact Management**
- Query: `Get contacts`
- Response:
  ```
  👥 Contacts

  - 1. Name: John Doe  - Emails: john@example.com
  - 2. Name: Jane Smith  - Emails: jane@example.com
  - 3. Name: Bob Johnson  - Emails: bob@example.com
  ```

### **Search People**
- Query: `Search people, Query: John Doe`
- Response:
  ```
  🔎 People Search Results

  - 1. Name: John Doe  - Emails: john@example.com  - Phones: +1-555-0123
  ```

### **Draft Management**
- Query: `Create draft, To: user@example.com, Subject: Hello, Body: Hi there`
- Response:
  ```
  📝 Draft created

  Draft Details:
  - Draft ID: r123abc
  - Thread ID: 18c1234567890abc
  - To: user@example.com
  - Subject: Hello
  ```

### **Thread Management**
- Query: `Reply to: user@example.com, Thread Id: 1995..., Body: Thanks for your message!`
- Response:
  ```
  ✅ Replied successfully

  Reply Details:
  - To: user@example.comgit status -uno
  - Thread ID: 1995...
  - Message ID: 18c1234567890abc
  - Body: Thanks for your message!
  ```

### **Email Organization**
- Query: `Move to trash, Message ID: 1875f42779f726f2`
- Response:
  ```
  🗑️ Moved to Trash

  Email:
  - Message ID: 1875f42779f726f2
  - Thread ID: 18c1234567890abc
  - Labels: TRASH
  ```

### **Profile Information**
- Query: `Get profile`
- Response:
  ```
  📇 Profile

  - Email: you@example.com
  - Messages Total: 1250
  - Threads Total: 890
  - History ID: 1234567890
  ```

## Advanced Features 🚀

### **Intelligent Intent Recognition**
Advanced natural language processing that maps user queries to specific Gmail operations:

- **Keyword-Based Detection**: Recognizes intent through keyword matching (send, fetch, reply, etc.)
- **Parameter Extraction**: Automatically extracts relevant parameters (recipient, subject, sender, etc.)
- **Flexible Input Parsing**: Supports both comma-separated and multi-line input formats
- **Context Understanding**: Distinguishes between similar operations (send vs. draft, profile vs. contacts)

### **Professional Response Formatting**
Structured markdown formatting for user-friendly output:

- **Consistent Formatting**: Uses emojis, headers, and clear sections
- **Action Confirmation**: Provides clear success/failure indicators
- **Detailed Information**: Shows email IDs, thread IDs, and labels
- **Error Handling**: Comprehensive error messages with recovery suggestions

### **Multi-User Authentication Management**
Intelligent handling of user authentication and email management:

- **Per-User Memory**: Remembers authenticated email per chat sender
- **Dynamic Switching**: Allows switching between accounts using From: parameter
- **OAuth2 Integration**: Secure authentication flow through Composio
- **Real-time Status**: Monitors authentication completion

### **Robust Error Handling**
Comprehensive error handling with helpful user guidance:

- **Tool Availability**: Checks if required tools are available before execution
- **Parameter Validation**: Validates required parameters before API calls
- **Fallback Mechanisms**: Provides alternative approaches when primary methods fail
- **User Guidance**: Clear instructions for resolving common issues

## Technical Architecture 🏗️

### **Core Components**
- **uAgents Framework**: Provides agent infrastructure and communication protocols
- **Composio SDK**: Handles Gmail API integration and OAuth2 authentication
- **LangChain**: Powers email sending with intelligent agent execution

### **Authentication Flow**
1. **Initial Request**: User sends authentication request with email address
2. **OAuth Initiation**: Agent generates OAuth2 URL through Composio
3. **User Authorization**: User completes authentication in browser
4. **Email Memory**: Agent remembers authenticated email per chat sender
5. **Token Management**: Secure connection established for Gmail operations

### **Query Processing Pipeline**
1. **Intent Recognition**: Keyword-based analysis identifies user intent
2. **Parameter Extraction**: Relevant parameters extracted from user input
3. **Tool Selection**: Specific Gmail tool selected based on intent
4. **API Execution**: Composio SDK executes the selected operation
5. **Response Formatting**: Results formatted using markdown templates
6. **User Delivery**: Formatted response sent back to user

### **Agent Structure**
- **Main Agent**: `uagent_app.py` - Handles message processing and routing
- **Tools Module**: `tools.py` - Manages Composio tool integration
- **LLM Module**: `llm.py` - Handles LangChain agent creation and execution
- **Formatting Module**: `formatting.py` - Provides markdown response formatting
- **System Prompts**: `system_prompt.py` - Centralized prompts and constants

## Performance & Reliability 📈

### **Response Time Optimization**
- **Intent Caching**: Frequently used intents cached for faster processing
- **Async Processing**: Non-blocking operations for better user experience
- **Batch Operations**: Efficient handling of multiple email operations
- **Tool-Specific Optimization**: Direct tool calls for faster execution

### **Error Handling & Recovery**
- **Graceful Degradation**: Continues operation even with partial failures
- **Authentication Scope Detection**: Identifies and guides resolution of permission issues
- **Retry Mechanisms**: Automatic retry for transient failures
- **User Feedback**: Clear error messages and recovery suggestions

### **Security & Privacy**
- **OAuth2 Authentication**: Secure, industry-standard authentication
- **Token Management**: Secure storage and rotation of access tokens
- **Data Privacy**: No email content stored or logged unnecessarily
- **Scope Validation**: Validates required permissions before operations

## Integration Capabilities 🔗

### **AgentVerse Platform**
- **Real-time Communication**: Instant query processing and response
- **Multi-user Support**: Handles multiple users simultaneously
- **Session Management**: Maintains user context across interactions
- **Message Acknowledgment**: Proper message acknowledgment protocol

### **Gmail API Features**
- **Full API Coverage**: Access to all 28 Gmail API capabilities
- **Real-time Updates**: Immediate reflection of changes in Gmail
- **Cross-platform Sync**: Changes sync across all Gmail clients
- **Advanced Search**: Support for complex Gmail search queries

### **AI Integration**
- **Intent Analysis**: Sophisticated natural language processing
- **Response Refinement**: User-friendly output formatting

## Troubleshooting 🐞

### **Authentication Issues**
- **OAuth Flow Problems**: Ensure complete browser authentication
- **Token Expiration**: Re-authenticate if tokens become invalid
- **Permission Issues**: Verify Gmail account permissions and scopes
- **Timeout Issues**: Check network connectivity and retry authentication

### **Query Failures**
- **Email Not Found**: Verify sender email exists and has emails
- **Permission Denied**: Check Gmail account access permissions
- **API Limits**: Respect Gmail API rate limits
- **Intent Recognition**: Use clear, specific language for better intent detection

### **AgentVerse Connection Issues**
- **Port Conflicts**: Ensure port 8028 is available
- **Network Issues**: Check firewall and network configuration
- **Agent Registration**: Verify proper agent registration in AgentVerse
- **Message Protocol**: Ensure proper message acknowledgment

### **Performance Issues**
- **Memory Usage**: Monitor agent memory consumption
- **Network Latency**: Consider server location optimization
- **Intent Analysis**: Optimize query language for faster processing

## Best Practices 💡

### **Query Formulation**
- **Be Specific**: Provide clear, detailed instructions
- **Use Natural Language**: Write queries as you would speak them
- **Include Context**: Mention relevant details for better results
- **Avoid Ambiguity**: Use clear language to avoid intent confusion

### **Email Management**
- **Regular Cleanup**: Use the agent for routine inbox maintenance
- **Label Organization**: Implement consistent labeling strategies
- **Contact Maintenance**: Keep contact lists updated and organized
- **Content Generation**: Leverage AI for professional email content

### **Security Considerations**
- **Regular Re-authentication**: Periodically refresh OAuth tokens
- **Permission Review**: Regularly review Gmail app permissions
- **Secure Communication**: Use secure channels for sensitive operations
- **Scope Validation**: Ensure required scopes are granted

## Future Enhancements 🔮

### **Planned Features**
- **Email Templates**: Pre-defined email templates for common use cases
- **Automated Workflows**: Rule-based email processing and organization
- **Analytics Dashboard**: Email usage statistics and insights
- **Multi-language Support**: Support for multiple languages
- **Advanced Search**: Enhanced search with AI-powered filtering

### **Integration Roadmap**
- **Calendar Integration**: Email-to-calendar event creation
- **Task Management**: Convert emails to actionable tasks
- **Document Processing**: Handle email attachments and documents
- **Team Collaboration**: Multi-user email management features
- **Voice Integration**: Voice-to-email capabilities

## Contributing 🤝

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch (`git checkout -b feature/YourFeature`)
3. Commit changes (`git commit -m 'Add YourFeature'`)
4. Push to the branch (`git push origin feature/YourFeature`)
5. Open a pull request

### **Development Guidelines**
- **Code Quality**: Follow Python best practices and PEP 8
- **Testing**: Include tests for new features
- **Documentation**: Update documentation for any changes
- **Security**: Ensure security best practices are followed
- **AI Integration**: Maintain high-quality prompt engineering

## License 📜

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## Contact 📧

For questions, reach out to Gautam Kumar at [gautam.kumar@fetch.ai](mailto:gautam.kumar@fetch.ai) or open an issue on GitHub.

## Acknowledgments 🙏

- **Fetch.ai Team**: For the uAgents framework and continuous support
- **Composio**: For the excellent Gmail integration capabilities
- **AgentVerse**: For the innovative agent deployment platform
- **Open Source Community**: For the tools and libraries that make this possible

---

Built with ❤️ for seamless Gmail automation and intelligent email management!
