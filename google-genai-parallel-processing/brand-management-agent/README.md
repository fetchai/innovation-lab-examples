 # Brand Management Agent - Parallel Processing

The **Brand Management Agent** demonstrates advanced parallel processing capabilities using the Google **genai-processors** library with **uAgents**. It creates comprehensive brand assets (name, tagline, logo, web layout) simultaneously and synthesizes the results into a complete brand package.

---

## 🧩 Overview

### 🔍 Features

- **Parallel Processing**: Executes 4 brand tasks simultaneously using `processor.parallel_concat()`
- **Multimodal Output**: Generates both text content and images (logos via DALL·E)
- **Stream Processing**: Handles results as they complete, not necessarily in order
- **External Storage**: Uploads generated images to Agentverse storage
- **Chat Protocol**: ChatProtocol implementation to query through ASI:One.

### 🚀 Performance Timeline

```
Time 0s: All 4 processors start simultaneously
Time 2s: Brand name processor completes → "EcoThread"
Time 3s: Tagline processor completes → "Style with Purpose"
Time 5s: Web layout processor completes → HTML structure
Time 8s: Logo image processor completes → Logo uploaded to storage
Time 8s: Synthesis processor combines all results
```

---

## 🏗️ Architecture

### Parallel Processing Pipeline

```
User Request ──► Chat Protocol ──► Parallel Concat ──► 4 Processors
    ▲              │                    │
    │              ▼                    ▼
    └────── Synthesis ──◄─── Results Collection
```

**Flow**: User sends brand request → Chat protocol processes → 4 processors run in parallel → Results collected as they complete → AI synthesis creates final output

### Core Components

1. **ASI1MiniProcessor**: Base class for text generation using ASI:One Mini
2. **Specialized Processors**: Brand name, tagline, web layout generation
3. **LogoImageProcessor**: DALL·E image generation + external storage upload
4. **SynthesisProcessor**: Combines all results into final brand package

---

## 🚀 Quick Start

### 1. Create Virtual Environment
```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
# On macOS/Linux:
source venv/bin/activate
# On Windows:
# venv\Scripts\activate
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Set Environment Variables
```bash
# Required for ASI:One Mini integration
export ASI1_API_KEY="your-asi1-api-key"

# Required for DALL·E image generation
export OPENAI_API_KEY="your-openai-api-key"

# Required for Agentverse integration
export AGENTVERSE_API_KEY="your-agentverse-api-key"
```

### 4. Start the Agent
```bash
python agent.py
```

Copy the Agent Inspector Link (https://agentverse.ai/inspect/?uri=http%3A//127.0.0.1%3A8002&address=agent1qwyr5zyn4jde7j0sgu7q5ml6038a00pf6zg6ugefedjrphw0e8l9xk6splq) from the logs and open it in Google Chrome Browser. Click on `Connect` and then select `Mailbx` to connect your Agent to Agentverse. Click on the `Agent Profile` button in the top right corner. This will show the Agent on Agentver, to interact with the agent click on `Chat with Agent` and  send a message like `"build a tech startup"` to see parallel processing in action!

Read more about how to connect an Agent to Agentverse via Mailbox [here](https://innovationlab.fetch.ai/resources/docs/agent-creation/uagent-creation#mailbox-agents).

---

## 📡 Usage Examples

### Example Request from Agentverse
Send a natural language brand request through `Chat with Agent`:
```
build a brand around sustainable clothing
```

## 📡 Usage Examples

### Example Request from Agentverse
Send a natural language brand request through `ASI:One`:
```
please ask @agentaddress to build a brand around sustainable clothing
```

Replace agent address with your agent's address from the log.

### Response
The agent will:
1. **Start 4 parallel tasks** simultaneously
2. **Generate brand name** (e.g., "EcoThread")
3. **Create tagline** (e.g., "Style with Purpose")
4. **Design web layout** (HTML structure)
5. **Generate logo** (DALL·E image + storage upload)
6. **Synthesize final output** with all components

### Expected Output
```
🔄 Starting parallel execution for: 'build a brand around sustainable clothing'
✅ brand_name completed
✅ tagline completed
✅ web_layout completed
✅ logo_image completed
📊 Completed: 4/4 tasks

BRAND NAME: EcoThread
TAGLINE: Style with Purpose
WEB LAYOUT: [Complete HTML structure]
[Logo image attached as resource]
```

---

## 🛠️ Building Your Own Parallel Processing Agent

### **Step 1: Define Your Processors**

Create processor classes for each task you want to run in parallel:

```python
from genai_processors import processor
from genai_processors.processor import ProcessorPart

class MyTaskProcessor(processor.Processor):
    def __init__(self, task_description: str):
        self.task = task_description
    
    async def call(self, content: AsyncIterable[ProcessorPart]):
        # Your task logic here
        result = await self.process_task()
        yield ProcessorPart(
            text=result,
            metadata={"type": "my_task_type"}
        )
```

### **Step 2: Set Up Parallel Execution**

Use `processor.parallel_concat()` to run multiple processors simultaneously:

```python
# Create your parallel processing pipeline
parallel_agent = processor.parallel_concat([
    MyTaskProcessor("task 1"),
    MyTaskProcessor("task 2"),
    MyTaskProcessor("task 3"),
    # Add as many as you need
])
```

### **Step 3: Process Results**

Handle results as they arrive using stream processing:

```python
input_stream = streams.stream_content([ProcessorPart("start")])
collected_results = {}

async for part in parallel_agent(input_stream):
    if part.metadata and not part.metadata.get("error"):
        collected_results[part.metadata["type"]] = part.text
        print(f"✅ {part.metadata['type']} completed")
```

### **Step 4: Synthesize Final Output**

Combine all results into your final output:

```python
final_result = await synthesize_results(collected_results)
```

---

## 📁 Project Structure

```
├── brand_management_agent.py    # Main agent with parallel processing
├── requirements.txt             # Dependencies
└── README.md                   # This file
```

---

## 📋 Requirements

Create a `requirements.txt` file with:

```txt
uagents==0.22.5
genai-processors>=1.0.0
openai>=1.0.0
httpx>=0.24.0
requests>=2.31.0
python-dotenv>=1.0.0
```

---

## 🎯 Use Cases for Parallel Processing

### **Content Creation**
- Generate blog post outline, images, and social media posts simultaneously
- Create video scripts, thumbnails, and descriptions in parallel

### **Data Analysis**
- Process multiple data sources concurrently
- Run different analysis algorithms simultaneously

### **E-commerce**
- Generate product descriptions, images, and pricing simultaneously
- Create marketing materials and inventory updates in parallel

### **Research**
- Search multiple sources, analyze data, and generate reports concurrently
- Process different research methodologies simultaneously

---
---

## 📚 Additional Resources

- [Fetch.ai uAgents Documentation](https://innovationlab.fetch.ai/resources/docs/intro)
- [Chat Protocol Documentation](https://innovationlab.fetch.ai/resources/docs/examples/chat-protocol/asi-compatible-uagents)
- [GenAI Processors Documentation](https://github.com/google-gemini/genai-processors)
- [ASI:One Mini API Reference](https://innovationlab.fetch.ai/resources/docs/asione/asi1-mini-api-reference)
- [OpenAI DALL·E Documentation](https://platform.openai.com/docs/guides/images)

---

**Ready to build faster, more efficient agents? Start with this example and unleash the power of parallel processing! 🚀**
