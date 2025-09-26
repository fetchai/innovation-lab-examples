# knowledge.py
from hyperon import MeTTa, E, S, ValueAtom

def initialize_knowledge_graph(metta: MeTTa):
    """Initialize the MeTTa knowledge graph with comprehensive Fetch.ai/uAgents knowledge for real-time queries."""
    
    # Agent Types → Capabilities
    metta.space().add_atom(E(S("capability"), S("uAgent"), S("microservice")))
    metta.space().add_atom(E(S("capability"), S("uAgent"), S("message handling")))
    metta.space().add_atom(E(S("capability"), S("uAgent"), S("event processing")))
    metta.space().add_atom(E(S("capability"), S("uAgent"), S("REST endpoints")))
    metta.space().add_atom(E(S("capability"), S("ASI:One"), S("LLM processing")))
    metta.space().add_atom(E(S("capability"), S("ASI:One"), S("agent querying")))
    metta.space().add_atom(E(S("capability"), S("Agentverse"), S("agent marketplace")))
    metta.space().add_atom(E(S("capability"), S("Agentverse"), S("agent discovery")))
    metta.space().add_atom(E(S("capability"), S("Agentverse"), S("agent deployment")))
    
    # Communication Patterns → Methods
    metta.space().add_atom(E(S("communication"), S("ctx.send"), S("asynchronous")))
    metta.space().add_atom(E(S("communication"), S("ctx.send"), S("fire and forget")))
    metta.space().add_atom(E(S("communication"), S("ctx.send_and_receive"), S("synchronous")))
    metta.space().add_atom(E(S("communication"), S("ctx.send_and_receive"), S("request-response")))
    metta.space().add_atom(E(S("communication"), S("chat protocol"), S("structured messaging")))
    metta.space().add_atom(E(S("communication"), S("chat protocol"), S("acknowledgments")))
    metta.space().add_atom(E(S("communication"), S("REST endpoints"), S("HTTP integration")))
    
    # Agent Deployment → Types
    metta.space().add_atom(E(S("deployment"), S("hosted agents"), S("Agentverse managed")))
    metta.space().add_atom(E(S("deployment"), S("local agents"), S("self-hosted")))
    metta.space().add_atom(E(S("deployment"), S("mailbox agents"), S("hybrid deployment")))
    metta.space().add_atom(E(S("deployment"), S("hosted agents"), S("always running")))
    metta.space().add_atom(E(S("deployment"), S("local agents"), S("full library access")))
    metta.space().add_atom(E(S("deployment"), S("mailbox agents"), S("Agentverse integration")))
    
    # Framework Integration → Adapters
    metta.space().add_atom(E(S("adapter"), S("LangChain"), S("uAgents ecosystem")))
    metta.space().add_atom(E(S("adapter"), S("LangGraph"), S("orchestration")))
    metta.space().add_atom(E(S("adapter"), S("CrewAI"), S("multi-agent collaboration")))
    metta.space().add_atom(E(S("adapter"), S("A2A inbound"), S("external A2A clients")))
    metta.space().add_atom(E(S("adapter"), S("A2A outbound"), S("A2A agent registration")))
    
    # Blockchain Features → Benefits
    metta.space().add_atom(E(S("blockchain"), S("decentralization"), S("trustless interactions")))
    metta.space().add_atom(E(S("blockchain"), S("transparency"), S("auditable transactions")))
    metta.space().add_atom(E(S("blockchain"), S("smart contracts"), S("automated execution")))
    metta.space().add_atom(E(S("blockchain"), S("Almanac"), S("agent registry")))
    metta.space().add_atom(E(S("blockchain"), S("transactions"), S("secure payments")))
    
    # Agentverse Features → Capabilities
    metta.space().add_atom(E(S("capability"), S("Agentverse"), S("continuous uptime")))
    metta.space().add_atom(E(S("capability"), S("Agentverse"), S("easy deployment")))
    metta.space().add_atom(E(S("capability"), S("Agentverse"), S("blockchain integration")))
    metta.space().add_atom(E(S("capability"), S("Agentverse"), S("marketplace discovery")))
    metta.space().add_atom(E(S("capability"), S("Agentverse"), S("mailroom service")))
    metta.space().add_atom(E(S("capability"), S("Agentverse"), S("integrated IDE")))
    metta.space().add_atom(E(S("capability"), S("Agentverse"), S("agent search")))
    metta.space().add_atom(E(S("capability"), S("Agentverse"), S("agent registration")))
    # ASI:One Specific Models
    metta.space().add_atom(E(S("specificInstance"), S("ASI:One"), S("asi1-mini")))
    metta.space().add_atom(E(S("specificInstance"),S("ASI:One"), S("asi1-fast")))

    metta.space().add_atom(E(S("specificInstance"),S("ASI:One"), S("asi1-extended")))

    metta.space().add_atom(E(S("specificInstance"),S("ASI:One"), S("asi1-agentic")))

    metta.space().add_atom(E(S("specificInstance"),S("ASI:One"), S("asi1-graph")))
    # ASI:One Models → Features
    metta.space().add_atom(E(S("capability"), S("asi1-mini"), S("balanced performance")))
    metta.space().add_atom(E(S("capability"), S("asi1-mini"), S("speed optimization")))
    metta.space().add_atom(E(S("capability"), S("asi1-fast"), S("quick responses")))
    metta.space().add_atom(E(S("capability"), S("asi1-extended"), S("complex tasks")))
    metta.space().add_atom(E(S("capability"), S("asi1-agentic"), S("agent interactions")))
    metta.space().add_atom(E(S("capability"), S("asi1-graph"), S("data analytics")))
    metta.space().add_atom(E(S("capability"), S("asi1-graph"), S("graph optimization")))
    
    # ASI:One Core Features
    metta.space().add_atom(E(S("capability"), S("ASI:One"), S("agentic reasoning")))
    metta.space().add_atom(E(S("capability"), S("ASI:One"), S("natural language understanding")))
    metta.space().add_atom(E(S("capability"), S("ASI:One"), S("multi-step task execution")))
    metta.space().add_atom(E(S("capability"), S("ASI:One"), S("contextual memory")))
    metta.space().add_atom(E(S("capability"), S("ASI:One"), S("API-driven integration")))
    metta.space().add_atom(E(S("capability"), S("ASI:One"), S("Web3 native")))
    metta.space().add_atom(E(S("capability"), S("ASI:One"), S("tool calling")))
    metta.space().add_atom(E(S("capability"), S("ASI:One"), S("image generation")))
    metta.space().add_atom(E(S("capability"), S("ASI:One"), S("structured data")))
    metta.space().add_atom(E(S("capability"), S("ASI:One"), S("OpenAI compatible"))) 
    
    # Comprehensive Implementation → Solutions Mappings
    
    # Agent Creation Solutions
    metta.space().add_atom(E(S("solution"), S("create uAgent"), ValueAtom("pip install uagents, define Agent class, add handlers, run agent")))
    metta.space().add_atom(E(S("solution"), S("hosted agent"), ValueAtom("use Agentverse IDE, write Python code, click Start button")))
    metta.space().add_atom(E(S("solution"), S("local agent"), ValueAtom("define port/endpoint, run locally, manage uptime yourself")))
    metta.space().add_atom(E(S("solution"), S("mailbox agent"), ValueAtom("set mailbox=True, connect via Agentverse, hybrid deployment")))
    
    # Communication Solutions
    metta.space().add_atom(E(S("solution"), S("agent messaging"), ValueAtom("use ctx.send for async, ctx.send_and_receive for sync communication")))
    metta.space().add_atom(E(S("solution"), S("chat protocol"), ValueAtom("import chat protocol components, handle ChatMessage and ChatAcknowledgement")))
    metta.space().add_atom(E(S("solution"), S("REST endpoints"), ValueAtom("use @agent.on_rest_get/@agent.on_rest_post decorators")))
    metta.space().add_atom(E(S("solution"), S("event handling"), ValueAtom("use @agent.on_event('startup'/'shutdown') decorators")))
    
    # Integration Solutions
    metta.space().add_atom(E(S("solution"), S("LangChain integration"), ValueAtom("use LangchainRegisterTool adapter, wrap agent function")))
    metta.space().add_atom(E(S("solution"), S("LangGraph integration"), ValueAtom("use LangchainRegisterTool adapter, wrap orchestration function")))
    metta.space().add_atom(E(S("solution"), S("CrewAI integration"), ValueAtom("use CrewaiRegisterTool adapter, wrap crew handler function")))
    metta.space().add_atom(E(S("solution"), S("A2A integration"), ValueAtom("use A2A inbound/outbound adapters for external protocol support")))
    
    # Agentverse Solutions
    metta.space().add_atom(E(S("solution"), S("deploy on Agentverse"), ValueAtom("create agent in Agentverse IDE, write code, click Start button")))
    metta.space().add_atom(E(S("solution"), S("search agents"), ValueAtom("use Agentverse Search API with filters for state, category, agent_type, protocol_digest")))
    metta.space().add_atom(E(S("solution"), S("agent discovery"), ValueAtom("register agents with good readme, include tags and domain descriptions")))
    metta.space().add_atom(E(S("solution"), S("mailroom setup"), ValueAtom("enable mailroom service for offline message handling")))
    metta.space().add_atom(E(S("solution"), S("agent registration"), ValueAtom("register with Agentverse API using identity, URL, agent title, and readme")))
    
    # ASI:One Solutions
    metta.space().add_atom(E(S("solution"), S("ASI:One API setup"), ValueAtom("get API key from asi1.ai, use OpenAI-compatible endpoints")))
    metta.space().add_atom(E(S("solution"), S("model selection"), ValueAtom("choose asi1-mini for balance, asi1-fast for speed, asi1-extended for complexity")))
    metta.space().add_atom(E(S("solution"), S("tool calling"), ValueAtom("enable models to use external tools and APIs through function calling")))
    metta.space().add_atom(E(S("solution"), S("structured responses"), ValueAtom("use JSON schema to get structured model responses")))
    metta.space().add_atom(E(S("solution"), S("agentic reasoning"), ValueAtom("use asi1-agentic model for autonomous planning and execution")))  
    
    # Comprehensive Implementation → Considerations/Limitations Mappings
    
    # Hosted Agent Considerations
    metta.space().add_atom(E(S("consideration"), S("hosted agents"), ValueAtom("limited library support, always running, managed uptime")))
    metta.space().add_atom(E(S("consideration"), S("local agents"), ValueAtom("full library access, self-managed uptime, scaling responsibility")))
    metta.space().add_atom(E(S("consideration"), S("mailbox agents"), ValueAtom("hybrid approach, Agentverse integration, local control")))
    
    # Communication Considerations
    metta.space().add_atom(E(S("consideration"), S("ctx.send"), ValueAtom("fire and forget, no response waiting, suitable for notifications")))
    metta.space().add_atom(E(S("consideration"), S("ctx.send_and_receive"), ValueAtom("synchronous waiting, timeout handling, request-response pattern")))
    metta.space().add_atom(E(S("consideration"), S("chat protocol"), ValueAtom("structured messaging, acknowledgments required, standardized format")))
    
    # Integration Considerations
    metta.space().add_atom(E(S("consideration"), S("LangChain adapter"), ValueAtom("agent wrapping required, function invocation pattern")))
    metta.space().add_atom(E(S("consideration"), S("LangGraph adapter"), ValueAtom("orchestration wrapping, state management considerations")))
    metta.space().add_atom(E(S("consideration"), S("CrewAI adapter"), ValueAtom("team coordination, multi-agent workflow handling")))
    metta.space().add_atom(E(S("consideration"), S("A2A adapters"), ValueAtom("protocol bridging, external client compatibility")))
    
    # Agentverse Considerations
    metta.space().add_atom(E(S("consideration"), S("Agentverse"), ValueAtom("continuous uptime, easy deployment, but limited to supported libraries")))
    metta.space().add_atom(E(S("consideration"), S("agent search"), ValueAtom("powerful discovery, but requires good readme and proper tagging")))
    metta.space().add_atom(E(S("consideration"), S("mailroom service"), ValueAtom("offline message handling, but adds complexity to message flow")))
    metta.space().add_atom(E(S("consideration"), S("integrated IDE"), ValueAtom("convenient development, but limited compared to full IDE features")))
    
    # ASI:One Considerations
    metta.space().add_atom(E(S("consideration"), S("ASI:One"), ValueAtom("Web3-native LLM, but API dependency and token costs")))
    metta.space().add_atom(E(S("consideration"), S("asi1-mini"), ValueAtom("balanced performance, but may not handle complex reasoning")))
    metta.space().add_atom(E(S("consideration"), S("asi1-fast"), ValueAtom("quick responses, but limited capabilities")))
    metta.space().add_atom(E(S("consideration"), S("asi1-extended"), ValueAtom("complex tasks, but slower response times")))
    metta.space().add_atom(E(S("consideration"), S("asi1-agentic"), ValueAtom("autonomous reasoning, but requires careful prompt engineering")))
    metta.space().add_atom(E(S("consideration"), S("tool calling"), ValueAtom("external tool integration, but requires proper function definitions")))
    
    # Blockchain Considerations
    metta.space().add_atom(E(S("consideration"), S("decentralization"), ValueAtom("trustless interactions, transparency, but complexity overhead")))
    metta.space().add_atom(E(S("consideration"), S("Almanac registry"), ValueAtom("agent discovery, but registration overhead")))
    metta.space().add_atom(E(S("consideration"), S("smart contracts"), ValueAtom("automated execution, but gas costs and complexity")))
    
    # Comprehensive FAQ Knowledge Base
    
    # Greetings and General
    metta.space().add_atom(E(S("faq"), S("Hi"), ValueAtom("Hello! I'm your Fetch.ai/uAgents assistant. How can I help you with agent development today?")))
    metta.space().add_atom(E(S("faq"), S("Hello"), ValueAtom("Hi there! I'm here to help with your uAgents and Fetch.ai questions. What can I assist you with?")))
    metta.space().add_atom(E(S("faq"), S("What is Fetch.ai?"), ValueAtom("Fetch.ai is a decentralized AI platform that enables developers to build, connect, and deploy AI agents with blockchain integration.")))
    metta.space().add_atom(E(S("faq"), S("What are uAgents?"), ValueAtom("uAgents are lightweight microservices that can represent data, APIs, services, or ML models, designed for seamless agent communication.")))
    
    # Agent Creation Questions
    metta.space().add_atom(E(S("faq"), S("How do I create a uAgent?"), ValueAtom("Install uagents with pip, define an Agent class with name/port/endpoint, add handlers, and run the agent.")))
    metta.space().add_atom(E(S("faq"), S("What's the difference between hosted and local agents?"), ValueAtom("Hosted agents run on Agentverse with managed uptime but limited libraries. Local agents run on your machine with full library access but self-managed uptime.")))
    metta.space().add_atom(E(S("faq"), S("How do I deploy a mailbox agent?"), ValueAtom("Set mailbox=True in Agent definition, run locally, then connect via Agentverse inspector to create mailbox connection.")))
    
    # Communication Questions
    metta.space().add_atom(E(S("faq"), S("How do agents communicate?"), ValueAtom("Agents use ctx.send for async communication or ctx.send_and_receive for sync communication. Chat protocol provides structured messaging.")))
    metta.space().add_atom(E(S("faq"), S("What is the chat protocol?"), ValueAtom("Chat protocol is a standardized communication framework with ChatMessage, ChatAcknowledgement, and various content types for reliable agent messaging.")))
    metta.space().add_atom(E(S("faq"), S("How do I add REST endpoints?"), ValueAtom("Use @agent.on_rest_get or @agent.on_rest_post decorators with custom routes, request/response models, and return values.")))
    
    # Integration Questions
    metta.space().add_atom(E(S("faq"), S("Can I use LangChain with uAgents?"), ValueAtom("Yes, use the LangchainRegisterTool adapter to wrap LangChain agents and integrate them with the uAgents ecosystem.")))
    metta.space().add_atom(E(S("faq"), S("How do I integrate CrewAI?"), ValueAtom("Use the CrewaiRegisterTool adapter to wrap CrewAI crew handlers and expose them as uAgents for multi-agent collaboration.")))
    metta.space().add_atom(E(S("faq"), S("What are A2A adapters?"), ValueAtom("A2A adapters bridge uAgents with external Agent-to-Agent protocols - inbound exposes uAgents as A2A endpoints, outbound registers A2A agents as uAgents.")))
    
    # Development Questions
    metta.space().add_atom(E(S("faq"), S("How do I discover other agents?"), ValueAtom("Agents register on the Almanac contract for discovery. Use Agentverse marketplace to find and connect with other agents.")))
    metta.space().add_atom(E(S("faq"), S("What is ASI:One?"), ValueAtom("ASI:One is the world's first Web3-native LLM designed for agentic AI, enabling agents to query other agents dynamically.")))
    metta.space().add_atom(E(S("faq"), S("How do I handle events?"), ValueAtom("Use @agent.on_event('startup') and @agent.on_event('shutdown') decorators to handle agent lifecycle events.")))
    
    # Blockchain Questions
    metta.space().add_atom(E(S("faq"), S("What is the Almanac?"), ValueAtom("Almanac is a blockchain-based registry where agents register for discovery and communication with other agents in the network.")))
    metta.space().add_atom(E(S("faq"), S("How does decentralization help?"), ValueAtom("Decentralization provides trustless interactions, transparency, and removes single points of failure in agent communication and transactions.")))
    metta.space().add_atom(E(S("faq"), S("Can agents perform transactions?"), ValueAtom("Yes, uAgents can interact with smart contracts, perform blockchain transactions, and maintain transparency through decentralized infrastructure.")))
    
    # Agentverse Questions
    metta.space().add_atom(E(S("faq"), S("What is Agentverse?"), ValueAtom("Agentverse is a cloud-based platform for creating and hosting autonomous agents with continuous uptime, easy deployment, and blockchain integration.")))
    metta.space().add_atom(E(S("faq"), S("How do I deploy on Agentverse?"), ValueAtom("Create an agent in the Agentverse IDE, write your Python code, and click the Start button for instant deployment.")))
    metta.space().add_atom(E(S("faq"), S("How do I search for agents?"), ValueAtom("Use the Agentverse Search API with filters for state, category, agent_type, and protocol_digest to find specific agents.")))
    metta.space().add_atom(E(S("faq"), S("What is mailroom service?"), ValueAtom("Mailroom service allows agents to receive messages even when offline, retrieving them once they come back online.")))
    metta.space().add_atom(E(S("faq"), S("How do I make my agent discoverable?"), ValueAtom("Write a good readme with descriptive names, tags, domain descriptions, and input/output models for better discoverability.")))
    
    # ASI:One Questions
    metta.space().add_atom(E(S("faq"), S("What is ASI:One?"), ValueAtom("ASI:One is an intelligent AI platform that excels at finding the right AI agents to help solve tasks involving language, reasoning, analysis, and coding.")))
    metta.space().add_atom(E(S("faq"), S("How do I get ASI:One API key?"), ValueAtom("Sign up at asi1.ai, navigate to Developer section, click Create New, and save your API key securely.")))
    metta.space().add_atom(E(S("faq"), S("Which ASI:One model should I use?"), ValueAtom("Use asi1-mini for balanced performance, asi1-fast for quick responses, asi1-extended for complex tasks, asi1-agentic for agent interactions.")))
    metta.space().add_atom(E(S("faq"), S("What is agentic reasoning?"), ValueAtom("Agentic reasoning allows ASI:One to autonomously plan, execute, and adapt its approach based on evolving inputs and goals.")))
    metta.space().add_atom(E(S("faq"), S("How do I use tool calling?"), ValueAtom("Enable models to use external tools and APIs through function calling, defining proper function schemas for tool integration.")))
    metta.space().add_atom(E(S("faq"), S("Is ASI:One OpenAI compatible?"), ValueAtom("Yes, ASI:One provides OpenAI-compatible endpoints, making it easy to integrate with existing OpenAI client libraries.")))
    
    # Architecture Questions
    metta.space().add_atom(E(S("faq"), S("How do I build end-to-end applications?"), ValueAtom("Use a Prime Agent to orchestrate communication between client applications and specialized agents registered in Agentverse.")))
    metta.space().add_atom(E(S("faq"), S("What is agent discovery?"), ValueAtom("Agent discovery allows finding agents by capability through Agentverse search, enabling dynamic agent selection for specific tasks.")))
    metta.space().add_atom(E(S("faq"), S("How do agents communicate in production?"), ValueAtom("Agents communicate through Agentverse using standardized protocols, with Prime Agents orchestrating complex multi-agent workflows.")))
    
    # Troubleshooting Questions
    metta.space().add_atom(E(S("faq"), S("My agent won't start"), ValueAtom("Check port availability, verify endpoint configuration, ensure proper imports, and check for syntax errors in your agent code.")))
    metta.space().add_atom(E(S("faq"), S("Agents can't communicate"), ValueAtom("Verify agent addresses are correct, check network connectivity, ensure both agents are running, and verify message model compatibility.")))
    metta.space().add_atom(E(S("faq"), S("How do I debug agent issues?"), ValueAtom("Use agent inspector URLs, check logs for error messages, verify agent registration on Almanac, and test with simple message exchanges.")))
    metta.space().add_atom(E(S("faq"), S("My agent isn't discoverable"), ValueAtom("Ensure your agent has a comprehensive readme with tags, domain descriptions, and clear input/output models for better search visibility.")))
    metta.space().add_atom(E(S("faq"), S("ASI:One API not working"), ValueAtom("Verify your API key is correct, check rate limits, ensure proper request format, and validate your authentication headers.")))
