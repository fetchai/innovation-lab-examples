# Financial Investment Advisor Agent - Fetch.ai Example

A demonstration of how to integrate **SingularityNET's MeTTa Knowledge Graph** with **Fetch.ai's uAgents** to create intelligent, autonomous agents that can understand and respond to investment queries using structured financial knowledge reasoning.

## 🤖 What is MeTTa by SingularityNET?

**MeTTa** (Meta Type Talk) is a multi-paradigm language for declarative and functional computations over knowledge (meta)graphs developed by SingularityNET. It provides a powerful framework for:

- **Structured Knowledge Representation**: Organize information in logical, queryable formats
- **Symbolic Reasoning**: Perform complex logical operations and pattern matching
- **Knowledge Graph Operations**: Build, query, and manipulate knowledge graphs

MeTTa uses a space-based architecture where knowledge is stored as atoms in logical spaces, enabling sophisticated querying and reasoning capabilities.

## 🔗 What is Fetch.ai?

**Fetch.ai** provides a complete ecosystem for building, deploying and discovering AI Agents. Key features include:

- **uAgents Framework**: Python-based framework for building autonomous agents
- **Agentverse**: Open marketplace for agent discovery and interaction
- **Chat Protocol**: Standardized communication protocol to make agents discoverable through ASI:One
- **ASI:One**: An agentic LLM that can interact with different agents on Agentverse to answer user queries.

## 🧠 MeTTa Components Explained

### Core MeTTa Elements

#### 1. **Space (Knowledge Container)**
```python
metta = MeTTa()  # Creates a new MeTTa instance with a space
```
The space is where all knowledge atoms are stored and queried.

#### 2. **Atoms (Knowledge Units)**
Atoms are the fundamental units of knowledge in MeTTa:

- **E (Expression)**: Creates logical expressions
- **S (Symbol)**: Represents symbolic atoms
- **ValueAtom**: Stores actual values (strings, numbers, etc.)

#### 3. **Knowledge Graph Structure**
```python
# Risk Profile → Investment Types
metta.space().add_atom(E(S("risk_profile"), S("conservative"), S("bonds")))

# Investment Types → Expected Returns  
metta.space().add_atom(E(S("expected_return"), S("bonds"), ValueAtom("3-5% annually")))

# Investment Types → Risk Levels
metta.space().add_atom(E(S("risk_level"), S("bonds"), ValueAtom("low risk, stable income")))
```

#### 4. **Querying with Pattern Matching**
```python
# Find investment types for risk profile
query_str = '!(match &self (risk_profile conservative $investment) $investment)'
results = metta.run(query_str)
```

### Key MeTTa Concepts

- **`&self`**: References the current space
- **`$variable`**: Pattern matching variables
- **`!(match ...)`**: Query syntax for pattern matching
- **`E(S(...), S(...), ...)`**: Creates logical expressions

For more detailed information about MeTTa, visit the [official documentation](https://metta-lang.dev/docs/learn/tutorials/python_use/metta_python_basics.html).

## 🏗️ Project Architecture

### Core Components

1. **`agent.py`**: Main uAgent implementation with Chat Protocol to make the agent queryable through ASI:One.
2. **`knowledge.py`**: MeTTa knowledge graph initialization
3. **`investment_rag.py`**: Investment RAG (Retrieval-Augmented Generation) system
4. **`utils.py`**: LLM integration and query processing logic

### Data Flow

User Query → Intent Classification → MeTTa Query → Knowledge Retrieval → LLM Response → User

## 🔧 Integration with uAgents

### Using This as a Template

This project serves as a template for integrating MeTTa with uAgents. The key integration point is the `process_query` function in `utils.py`, which you can customize for your specific use case.

### Customization Steps

1. **Modify Knowledge Graph** (`knowledge.py`):
   ```python
   def initialize_investment_knowledge(metta: MeTTa):
       # Add your domain-specific knowledge
       metta.space().add_atom(E(S("your_relation"), S("subject"), S("object")))
   ```

2. **Update Query Processing** (`utils.py`):
   ```python
   def process_query(query, rag: InvestmentRAG, llm: LLM):
       # Implement your domain-specific logic
       intent, keyword = get_intent_and_keyword(query, llm)
       # Add your custom processing logic here
   ```

3. **Extend RAG System** (`investment_rag.py`):
   ```python
   class InvestmentRAG:
       def __init__(self, metta_instance: MeTTa):
           self.metta = metta_instance
       
       def query_your_domain(self, query):
           # Implement your domain-specific queries
           query_str = f'!(match &self (your_relation {query} $result) $result)'
           return self.metta.run(query_str)
   ```

## ⚙️ Setup Instructions

### Prerequisites

- Python 3.11+
- ASI:One API key

### Installation

1. **Clone the repository**:
   ```bash
   git clone <your-repo-url>
   cd financial-advisor-agent
   ```

2. **Create virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**:
    To get the ASI:One API Key, login to https://asi1.ai/ and go to **Developer** section, click on **Create New** and copy your API Key. Please refer this [guide](https://innovationlab.fetch.ai/resources/docs/asione/asi-one-quickstart#step-1-get-your-api-key) for detailed steps.

   ```bash
   cp .env.example .env
   # Edit .env with your API keys
   ```

5. **Run the agent**:
   ```bash
   python agent.py
   ```

### Environment Variables

Create a `.env` file with:
```env
ASI_ONE_API_KEY=your_asi_one_api_key_here
```

## 💡 Key Features

### 1. **Dynamic Knowledge Learning**
The agent can learn new information and add it to the MeTTa knowledge graph:
```python
# Automatically adds new knowledge when not found
rag.add_knowledge("risk_profile", "ultra_conservative", "treasury_bills")
```

### 2. **Intent Classification**
Uses ASI:One to classify user intent and extract keywords:
- `risk_profile`: Find investments suitable for risk tolerance
- `investment_advice`: Get investment recommendations
- `returns`: Learn about expected returns
- `allocation`: Age-based asset allocation strategies
- `goal`: Investment strategies for specific goals
- `sector`: Information about market sectors
- `faq`: Answer general investment questions

### 3. **Structured Reasoning**
MeTTa enables complex logical reasoning:
```python
# Find investments for risk profile and get their returns
investments = rag.query_risk_profile("conservative")
returns = rag.get_expected_return(investments[0])
risks = rag.get_risk_level(investments[0])
```

### 4. **Agentverse Integration**
The agent automatically:
- Registers on Agentverse for discovery
- Implements Chat Protocol for ASI:One accessibility
- Provides a web interface for testing

## 🧪 Testing the Agent

1. **Start the agent**:
   ```bash
   python agent.py
   ```

2. **Access the inspector**:
   Visit the URL shown in the console (e.g., `https://agentverse.ai/inspect/?uri=http%3A//127.0.0.1%3A8008&address=agent1qd674kgs3987yh84a309c0lzkuzjujfufwxslpzygcnwnycjs0ppuauektt`) and click on `Connect` and select the `Mailbox` option. For detailed steps for connecting Agents via Mailbox, please refer [here](https://innovationlab.fetch.ai/resources/docs/agent-creation/uagent-creation#mailbox-agents).

3. **Test queries**:

### 🎯 Risk Profile & Investment Recommendations
   - "I'm a conservative investor with low risk tolerance. What should I invest in?"
   - "I have moderate risk tolerance and want balanced growth. What should I invest in?"
   - "I'm young and can take high risks for high returns. What should I invest in?"

### 💰 Expected Returns & Performance
   - "What returns can I expect from index funds?"
   - "How much do bonds typically return per year?"
   - "What's the expected return on cryptocurrency investments?"

### 📊 Age-Based Asset Allocation
   - "I'm 25 years old. How should I allocate my investment portfolio?"
   - "What's the recommended asset allocation for someone in their 40s?"
   - "I'm 55 and planning for retirement. How should I split my investments?"

### 🎯 Goal-Oriented Investment Planning
   - "How should I invest for retirement in my 30s?"
   - "Where should I keep my emergency fund for best returns?"
   - "I'm saving for a house down payment in 3 years. Where should I invest?"

### 📈 Sector-Specific Queries
   - "What are the top technology stocks to consider?"
   - "Which healthcare companies are good investments?"
   - "What financial sector stocks do you recommend?"

### ⚠️ Risk Management & Education
   - "What are the biggest investment mistakes I should avoid?"
   - "How do I avoid timing the market?"
   - "Why is diversification important?"

## Test Agents using Chat with Agent button on Agentverse

1. Once the agent is connected via Mailbox, go to `Agent Profile` and click on `Chat with Agent` 

2. Interact with your agent through the Agentverse chat interface and try sample queries like:
   - "I'm a conservative investor, what should I invest in?"
   - "What returns can I expect from bonds?"
   - "How should a 30-year-old allocate their portfolio?"

3. The agent will use MeTTa knowledge graphs to provide structured investment advice based on:
   - Risk profile analysis
   - Expected return calculations
   - Age-appropriate allocation strategies
   - Goal-oriented planning

4. Agent terminal logs will show intent classification and knowledge retrieval from the MeTTa graph

5. Test the agent with ASI:One platform for natural language investment queries

## 📊 Knowledge Graph Structure

The MeTTa knowledge graph contains financial relationships:

- **Risk Profiles** → Investment Types (conservative → bonds, aggressive → crypto)
- **Investment Types** → Expected Returns (index_funds → "6-10% annually")
- **Investment Types** → Risk Levels (cryptocurrency → "very high risk")
- **Age Groups** → Asset Allocations (30s → "70% stocks, 30% bonds")
- **Investment Goals** → Strategies (retirement → "diversified index funds")
- **Market Sectors** → Top Stocks (technology → "Apple, Microsoft, Google")
- **Common Mistakes** → Warnings (emotional_trading → "avoid panic selling")


## 🔗 Useful Links

- [MeTTa Documentation](https://metta-lang.dev/docs/learn/tutorials/python_use/metta_python_basics.html)
- [Fetch.ai uAgents](https://innovationlab.fetch.ai/resources/docs/examples/chat-protocol/asi-compatible-uagents)
- [Agentverse](https://agentverse.ai/)
- [ASI:One](https://asi1.ai/)