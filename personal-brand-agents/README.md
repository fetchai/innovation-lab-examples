# Getting Started

## Slides

[Presentation Slides](https://docs.google.com/presentation/d/1Um2kYkj-oJ8d-XHGb2UuVz_AkN2o4hIGoc_y3RN93mA/edit?usp=sharing)

## Prerequisites

- **Supabase CLI**: You'll need the Supabase CLI installed. If you don't have it yet, follow the [installation guide](https://supabase.com/docs/guides/cli/getting-started).
- **Python**: Make sure you have Python installed.

## Setup

### 1. Python Environment

Create a virtual environment and activate it:

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

### 2. Starting Supabase

1. Start the local Supabase instance:

   ```bash
   supabase start
   ```

2. The migration files are already in the project at `supabase/migrations/`. They will be automatically applied when you start Supabase.

3. Once started, you'll see connection details for your local Supabase instance including:
   - API URL
   - Studio URL (for the Supabase dashboard)
   - Secret for making db requests

### 3. Starting Chroma

Chroma is the vector database used for semantically searching data. Start Chroma locally from the root of the project:

```bash
chroma run --path ./chroma
```

## Running Agents

You can start the agents using Python module syntax:

```bash
# Start the data management agent
python -m wrapped_uagents.wrapped_data_management_agent

# Start the brand agent
python -m wrapped_uagents.wrapped_brand_agent
```

## Interacting with Agents

Once your agents are running, you can interact with them via [asi:one](https://asi1.ai/chat). Simply @ mention your agent's ID in the chat to start a conversation with them. The agent ID will be displayed when you start the agent.

## Docker

Start supabase

```
supabase start
```

Build the image

```
docker build -f Dockerfile -t wrapped-data-management-agent .
```

Run it

```
docker run --env-file .env -p 8080:8080 wrapped-data-management-agent:latest
```

Note this app is meant to only containerize the data management agent. Users of the personal brand agent are meant to deploy themselevs, thus there is no docker setup for it.
