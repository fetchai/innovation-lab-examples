# Gmail-ASI-Agent 🤖

![uagents](https://img.shields.io/badge/uagents-4A90E2) ![innovationlab](https://img.shields.io/badge/innovationlab-3D8BD3) ![chatprotocol](https://img.shields.io/badge/chatprotocol-1D3BD4) [![X](https://img.shields.io/badge/X-black.svg?logo=X&logoColor=white)](https://x.com/gautammanak02)

Welcome to the **Gmail-ASI-Agent**, an intelligent Gmail assistant powered by the [uAgents framework](https://github.com/fetchai/uAgents), [Composio](https://composio.dev), and OpenAI's GPT-4o-mini. This agent integrates with Gmail via the Composio SDK to perform a comprehensive range of email operations with AI-powered content generation and intelligent intent recognition. Deployed on [AgentVerse](https://agentverse.ai), it processes natural language queries with dynamic authentication and delivers user-friendly, GPT-refined responses.

## Features ✨

- **Comprehensive Gmail Integration**: Supports 28 Gmail tools via Composio with intelligent tool selection:
  - **Email Management**: Create, send, and delete email drafts (`GMAIL_CREATE_EMAIL_DRAFT`, `GMAIL_SEND_DRAFT`, `GMAIL_DELETE_DRAFT`, `GMAIL_LIST_DRAFTS`)
  - **Email Communication**: Send and reply to emails (`GMAIL_SEND_EMAIL`, `GMAIL_REPLY_TO_EMAIL`, `GMAIL_REPLY_TO_THREAD`)
  - **Email Reading**: Read emails with full body content (`GMAIL_FETCH_EMAILS`, `GMAIL_FETCH_MESSAGE_BY_MESSAGE_ID`, `GMAIL_FETCH_MESSAGE_BY_THREAD_ID`)
  - **Label Management**: Complete label operations (`GMAIL_ADD_LABEL_TO_EMAIL`, `GMAIL_CREATE_LABEL`, `GMAIL_REMOVE_LABEL`, `GMAIL_MODIFY_THREAD_LABELS`, `GMAIL_PATCH_LABEL`, `GMAIL_LIST_LABELS`)
  - **Email Organization**: Move emails to trash or delete them (`GMAIL_MOVE_TO_TRASH`, `GMAIL_DELETE_MESSAGE`)
  - **Status Management**: Mark emails as read/unread (`GMAIL_MARK_AS_READ`, `GMAIL_MARK_AS_UNREAD`)
  - **Search Capabilities**: Search emails and people (`GMAIL_SEARCH_EMAILS`, `GMAIL_SEARCH_PEOPLE`)
  - **Contact Management**: Manage contacts and profiles (`GMAIL_GET_CONTACTS`, `GMAIL_GET_PEOPLE`, `GMAIL_GET_PROFILE`)
  - **Thread & Attachment Handling**: Manage email threads and attachments (`GMAIL_LIST_THREADS`, `GMAIL_GET_ATTACHMENT`)

- **AI-Powered Email Content Generation**: Automatically generates professional email content based on subject lines and recipient context
- **Intelligent Intent Recognition**: Advanced GPT-4o-mini-powered intent analysis that maps natural language to specific Gmail tools
- **Dynamic Authentication**: Secure OAuth2 authentication flow with real-time status checking
- **Professional Response Formatting**: GPT-refined responses with emojis, structured formatting, and clear action confirmations
- **Pagination Support**: Smart contact list pagination with navigation controls
- **Error Handling**: Comprehensive error handling with authentication scope detection and recovery suggestions

## Setup Instructions 🛠️

1. **Clone the Repository**:
   ```bash
   git clone https://github.com/gautammanak1/gmail-agent.git
   cd gmail-agent
   ```

2. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Set Up Environment Variables**:
   Create a `.env` file in the project root:
   ```env
   OPENAI_API_KEY=your_openai_api_key
   COMPOSIO_API_KEY=your_composio_api_key
   GMAIL_AUTH_CONFIG_ID=your_gmail_auth_config_id
   ```

4. **Run the Agent**:
   ```bash
   python agent.py
   ```
   The agent starts on port 8001 and provides example commands on successful authentication.

5. **Connect via AgentVerse**:
   - Open AgentVerse and connect to the agent using the address from the startup logs
   - The agent will be available at the address shown in the startup logs

## Usage Examples 📬

### **Authentication**
- Query: `Authenticate Gmail`
- Response: Provides OAuth2 URL for Gmail authentication
- Follow-up: Send `Auth complete` or another query after authenticating

### **AI-Powered Email Sending**
- Query: `Send email to john@example.com with subject 'Project Update'`
- Response:
  ```
  ✅ Email sent successfully!
  📧 Message ID: 18c1234567890abc
  🧵 Thread ID: 18c1234567890abc
  📤 To: john@example.com
  📋 Subject: Project Update
  ```
- **AI Content Generation**: If only subject is provided, the agent automatically generates professional email content based on the subject and recipient

### **Reading Emails with Full Content**
- Query: `Read emails from google-maps-noreply@google.com`
- Response:
  ```
  📧 Found 2 email(s):
  ============================================================
  
  📨 Email #1
  📋 Subject: Your Google Maps Update
  👤 From: google-maps-noreply@google.com
  📅 Date: 2025-08-27 10:00
  📝 Full Content: Your recent activity on Google Maps includes...
  ----------------------------------------
  
  📨 Email #2
  📋 Subject: New Feature Alert
  👤 From: google-maps-noreply@google.com
  📅 Date: 2025-08-26 14:30
  📝 Full Content: Introducing our new navigation feature...
  ----------------------------------------
  ```

### **Contact Management with Pagination**
- Query: `List my contacts`
- Response:
  ```
  👥 Found 25 contact(s):
  📄 Showing contacts 1-10 of 25
  📖 Page 1 of 3
  ============================================================
  
  👤 Contact #1
  🆔 Contact ID: c1234567890
  📛 Full Name: John Doe
  📝 Given Name: John
  📝 Family Name: Doe
  📧 Primary Email: john@example.com
  📞 Primary Phone: +1-555-0123
  🏢 Organization: Tech Corp
  💼 Title: Senior Developer
  ------------------------------------------------------------
  
  📋 **Pagination Navigation:**
  ➡️ **Next Page:** Show contacts 11-20
  
  💡 **Tip:** Say 'Show contacts 11-20' or 'Next page of contacts' to see more contacts!
  ```

### **Label Management**
- Query: `Create a label called 'fetch.ai'`
- Response:
  ```
  ✅ Label created successfully!
  ========================================
  🏷️ Label Name: fetch.ai
  🆔 Label ID: Label_1234567890
  👁️ Label Visibility: labelShow
  📧 Message Visibility: show
  ```

### **Email Organization**
- Query: `Move emails from john@example.com to trash`
- Response: `✅ Operation completed successfully`

- Query: `Delete the email from spam@domain.com`
- Response: `✅ Operation completed successfully`

### **Search and Filter**
- Query: `Search emails from john@example.com`
- Query: `Find emails about 'meeting'`
- Query: `Fetch spam mail`

### **Status Management**
- Query: `Mark emails from john@example.com as read`
- Query: `Mark important emails as unread`

## Advanced Features 🚀

### **AI Email Content Generation**
The agent automatically generates professional email content when only a subject is provided:

- **Context-Aware**: Analyzes subject keywords to determine email type (meeting, update, thank you, urgent, etc.)
- **Tone Adaptation**: Adjusts tone based on email type (professional, collaborative, warm, urgent)
- **Professional Structure**: Includes proper greeting, body content, and closing
- **Recipient Personalization**: Uses recipient name in greetings and adapts formality

### **Intelligent Intent Recognition**
Advanced intent analysis system that maps natural language to specific Gmail tools:

- **Tool-Specific Mapping**: Direct mapping to exact Gmail API tools
- **Parameter Extraction**: Automatically extracts relevant parameters (recipient, subject, sender, etc.)
- **Confidence Scoring**: Provides confidence levels for intent detection
- **Context Understanding**: Distinguishes between similar operations (send vs. draft, profile vs. contacts)

### **Professional Response Formatting**
GPT-powered response refinement for user-friendly output:

- **Structured Formatting**: Uses emojis, headers, and clear sections
- **Action Confirmation**: Provides clear success/failure indicators
- **Error Handling**: Comprehensive error messages with recovery suggestions
- **Pagination Support**: Smart navigation for large datasets

### **Authentication Scope Management**
Intelligent handling of Gmail API permissions:

- **Scope Detection**: Identifies insufficient authentication scopes
- **Recovery Guidance**: Provides specific steps to resolve permission issues
- **Alternative Operations**: Suggests available operations when permissions are limited
- **Real-time Status**: Monitors authentication completion in real-time

## Query Examples 🎯

### **Email Operations**
```
"Send email to john@example.com"
"Send email to team@company.com with subject 'Weekly Update'"
"Read emails from google-maps-noreply@google.com"
"Search emails from john@example.com"
"Find emails about 'meeting'"
"Fetch spam mail"
"Reply to email from boss@company.com"
"Mark emails from john@example.com as read"
"Mark important emails as unread"
"Delete the email from spam@domain.com"
"Move emails from john@example.com to trash"
```

### **Label Management**
```
"Create a label called 'Important'"
"Create label 'Work Projects'"
"Rename label 'Work' to 'Work Projects'"
"Add label 'Important' to emails from boss@company.com"
"Remove label 'Spam' from emails from john@example.com"
"List all labels"
```

### **Contact Management**
```
"List my contacts"
"Show all contacts"
"Get my contact list"
"Show contacts 11-20"
"Next page of contacts"
"More contact list"
```

### **Profile and Information**
```
"Get my profile"
"Show my Gmail profile info"
"Show profile"
"My info"
```

### **Draft Management**
```
"Create draft email to john@example.com"
"Save draft with subject 'Meeting Notes'"
"List all my drafts"
"Show drafts"
"Send draft email"
"Delete draft"
```

## Technical Architecture 🏗️

### **Core Components**
- **uAgents Framework**: Provides agent infrastructure and communication protocols
- **Composio SDK**: Handles Gmail API integration and OAuth2 authentication
- **OpenAI GPT-4o-mini**: Powers natural language understanding, intent analysis, and response generation
- **AgentVerse Integration**: Enables seamless user interaction through the platform

### **Authentication Flow**
1. **Initial Request**: User sends authentication request via AgentVerse
2. **OAuth Initiation**: Agent generates OAuth2 URL through Composio
3. **User Authorization**: User completes authentication in browser
4. **Real-time Monitoring**: Agent monitors authentication completion with timeout handling
5. **Token Management**: Secure connection established for Gmail operations

### **Query Processing Pipeline**
1. **Intent Recognition**: GPT-4o-mini analyzes user query for specific intent
2. **Parameter Extraction**: Relevant parameters identified and extracted
3. **Tool Selection**: Exact Gmail tool selected based on intent analysis
4. **Content Generation**: AI generates email content when needed
5. **API Execution**: Composio SDK executes the selected operation
6. **Response Formatting**: Raw results refined and formatted by GPT-4o-mini
7. **User Delivery**: Formatted response sent back through AgentVerse

### **AI Content Generation System**
- **Subject Analysis**: Analyzes subject keywords to determine email type
- **Tone Selection**: Chooses appropriate tone (professional, collaborative, urgent, etc.)
- **Content Structure**: Generates structured email with greeting, body, and closing
- **Professional Guidelines**: Follows business email best practices

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
- **OpenAI GPT-4o-mini**: Advanced language understanding and generation
- **Intent Analysis**: Sophisticated natural language processing
- **Content Generation**: Professional email content creation
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
- **Port Conflicts**: Ensure port 8001 is available
- **Network Issues**: Check firewall and network configuration
- **Agent Registration**: Verify proper agent registration in AgentVerse
- **Message Protocol**: Ensure proper message acknowledgment

### **Performance Issues**
- **Slow Responses**: Check OpenAI API response times
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
- **OpenAI**: For the powerful GPT-4o-mini model
- **Open Source Community**: For the tools and libraries that make this possible

---

Built with ❤️ for seamless Gmail automation and AI-powered email management!
