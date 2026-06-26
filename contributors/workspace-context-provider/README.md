# Autonomous Workspace Context Provider

A hybrid AI context provider that continuously indexes your local workspace and exposes it through a Streamlit web interface and an MCP server for AI-powered code understanding.

---

# 1. Overview

The **Autonomous Workspace Context Provider** is a local Retrieval-Augmented Generation (RAG) agent that monitors your workspace, embeds your source code and documentation into a persistent vector database, and provides contextual information through two interfaces:

* **Streamlit Web UI** for chatting with your codebase using the **ASI**** LLM API**
* **Model Context Protocol (MCP) Server** for integrating your local RAG pipeline with AI coding assistants such as VS Code (Cline/Roo Code), cursor, claude Desktop etc.

### Category

MCP, RAG, Tooling, Frontend

### Tech Stack

* Python
* Streamlit
* FastMCP
* ChromaDB
* Sentence Transformers
* Watchdog
* ASI API


---

# 2. Features

* 🔄 Real-time workspace indexing using **watchdog**
* 🧠 Local embeddings with **all-MiniLM-L6-v2**
* 💾 Persistent vector storage using **ChromaDB**
* 🤖 Chat with your codebase through **ASI**
* 🔌 MCP server for IDE integration 
* ⚡ Automatic vector database updates whenever files change

---

# 3. Prerequisites

* Python 3.10+
* pip
* ASI API Key *(optional, required only for Streamlit chat)*

---

# 4. Installation

```bash
cd contributors/workspace-context-provider

python -m venv venv

# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate

pip install -r requirements.txt
```

---

# 5. Environment Variables

Create a `.env` file.

```bash
cp .env.example .env
```

Example `.env.example`

```env
# Required only for Streamlit AI chat
ASI1_API_KEY=your_asi1_api_key_here

# Local directory to monitor and index
WORKSPACE_DIR=./target_workspace
```

### Variables

| Variable        | Description                                                       |
| --------------- | ----------------------------------------------------------------- |
| `ASI1_API_KEY`  | Optional. Used for ASI LLM requests in the Streamlit application. |
| `WORKSPACE_DIR` | Directory that will be monitored and indexed into ChromaDB.       |

---

# 6. Run the Agent

## Streamlit Web UI

```bash
streamlit run app.py
```

The application will automatically begin monitoring the directory specified by `WORKSPACE_DIR`.

---

## MCP Server

Configure your IDE (Cline/Roo Code) by adding the following configuration to `cline_mcp_settings.json`.

```json
{
  "mcpServers": {
    "workspace-rag-provider": {
      "command": "C:/path/to/venv/Scripts/python.exe",
      "args": ["-m", "src.mcp_server"],
      "cwd": "C:/path/to/contributors/workspace-context-provider",
      "env": {
        "WORKSPACE_DIR": "./target_workspace"
      }
    }
  }
}
```

> **Note:** Replace the `command` and `cwd` values with the absolute paths on your machine.

---

# 7. Expected Output

After running the project:

* ✅ Workspace monitoring starts successfully
* ✅ Modified files are automatically indexed
* ✅ Embeddings are stored in ChromaDB
* ✅ Streamlit UI answers questions about your codebase
* ✅ MCP server connects successfully to your IDE
* ✅ AI assistants can retrieve relevant workspace context

---

# 8. Demo

Add screenshots or GIFs demonstrating the project.

```markdown
![Workspace Context Provider Demo](./assets/demo.png)
```

---



# 9. Architecture

```
               Workspace Files
                      │
                      ▼
              Watchdog Observer
                      │
              File Change Events
                      │
                      ▼
        Sentence Transformer Embeddings
          (all-MiniLM-L6-v2 Model)
                      │
                      ▼
                 ChromaDB
          (Persistent Vector Store)
              ▲                 ▲
              │                 │
              │                 │
      Streamlit UI         FastMCP Server
              │                 │
              ▼                 ▼
        ASI:One API      VS Code / Cursor / claude desktop
```

---

# 10. Troubleshooting

### Missing `ASI1_API_KEY`

If using the Streamlit chat interface, ensure the API key is present in your `.env` file.

---

### Workspace not being indexed

* Verify that `WORKSPACE_DIR` exists.
* Ensure the application has permission to access the directory.

---

### MCP server not connecting

* Check the absolute paths in `cline_mcp_settings.json`.
* Restart your IDE after updating the MCP configuration.

---

### Dependency issues

Recreate the virtual environment and reinstall dependencies.

```bash
rm -rf venv

python -m venv venv

pip install -r requirements.txt
```

---

# 12. License

This project follows the license of the parent repository unless stated otherwise.

---

# ✅ Quick Checklist Before PR

* [x] README updated using the repository template
* [x] `.env.example` added
* [ ] Demo image/GIF added under `assets/`
* [ ] Agent profile link included (if available)
* [ ] `ruff check .` passed
* [ ] `ruff format .` applied
