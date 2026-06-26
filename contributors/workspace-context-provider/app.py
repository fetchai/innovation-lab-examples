import streamlit as st
from openai import OpenAI
import os
from dotenv import load_dotenv
from src.rag_pipeline import LocalRagEngine
from src.watcher import start_directory_watcher

# Load environment variables
load_dotenv()
ASI1_API_KEY = os.getenv("ASI1_API_KEY", "")
WORKSPACE_DIR = os.getenv("WORKSPACE_DIR", "./target_workspace")


# ==========================================
# 1. INITIALIZE RAG & WATCHER (Cached)
# ==========================================
@st.cache_resource
def init_rag_system():
    """Initializes the vector DB and background watcher only once per session."""
    engine = LocalRagEngine()
    # Start the background file watcher thread
    start_directory_watcher(engine, WORKSPACE_DIR)
    return engine


rag_engine = init_rag_system()

# ==========================================
# 2. INITIALIZE ASI:ONE API CLIENT
# ==========================================
# ASI:One uses OpenAI-compatible endpoints.
client = OpenAI(
    api_key=ASI1_API_KEY,
    base_url="https://api.asi1.ai/v1",  # Standard ASI:One endpoint
)

# ==========================================
# 3. STREAMLIT UI SETUP
# ==========================================
st.set_page_config(page_title="Workspace Context Agent", page_icon="🤖", layout="wide")
st.title("🤖 Autonomous Workspace Agent")
st.markdown("*Powered by ASI:One & Local RAG*")

# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# ==========================================
# 4. CHAT LOGIC & RAG INJECTION
# ==========================================
if prompt := st.chat_input("Ask about your codebase... (e.g., 'How does auth work?')"):
    # Display user prompt
    with st.chat_message("user"):
        st.markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})

    # Fetch context from our local RAG pipeline
    with st.spinner("🔍 Scanning local workspace..."):
        local_context = rag_engine.query_context(prompt, top_k=3)

    # Construct the grounded prompt for ASI:One
    system_prompt = f"""
    You are an expert developer AI assistant. 
    Use the following retrieved local workspace context to answer the user's question accurately.
    If the answer isn't in the context, say so.
    
    LOCAL WORKSPACE CONTEXT:
    {local_context}
    """

    # Display assistant response
    with st.chat_message("assistant"):
        message_placeholder = st.empty()

        if not ASI1_API_KEY:
            st.error(
                "⚠️ ASI1_API_KEY is missing in your .env file! Displaying retrieved raw context instead:"
            )
            message_placeholder.code(local_context)
            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "content": f"**Raw Context Retrieved:**\n```\n{local_context}\n```",
                }
            )
        else:
            try:
                # Call ASI:One API
                stream = client.chat.completions.create(
                    model="asi1-mini",  # Replace with specific ASI1 model if needed
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt},
                    ],
                    stream=True,
                )

                full_response = ""
                for chunk in stream:
                    # SAFETY CHECK: Ensure choices list is not empty!
                    if chunk.choices and len(chunk.choices) > 0:
                        if chunk.choices[0].delta.content is not None:
                            full_response += chunk.choices[0].delta.content
                            message_placeholder.markdown(full_response + "▌")

                message_placeholder.markdown(full_response)
                st.session_state.messages.append(
                    {"role": "assistant", "content": full_response}
                )

            except Exception as e:
                st.error(f"API Error: {e}")
