import os
from uagents import Agent, Context, Model
from uagents.setup import fund_agent_if_low
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain.chains import RetrievalQA
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
AGENTVERSE_API_KEY = os.getenv("AGENTVERSE_API_KEY")
CHROMA_PATH = "./chroma_db"

if not GOOGLE_API_KEY:
    raise ValueError("GOOGLE_API_KEY not found in environment variables.")


# Define request/response models
class QuestionRequest(Model):
    question: str


class AnswerResponse(Model):
    answer: str


# Initialize the RAG components
def initialize_rag():
    embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

    if not os.path.exists(CHROMA_PATH):
        return None

    vectorstore = Chroma(persist_directory=CHROMA_PATH, embedding_function=embeddings)

    llm = ChatGoogleGenerativeAI(
        model="gemini-2.0-flash", google_api_key=GOOGLE_API_KEY
    )

    qa_chain = RetrievalQA.from_chain_type(
        llm=llm,
        chain_type="stuff",
        retriever=vectorstore.as_retriever(search_kwargs={"k": 3}),
    )
    return qa_chain


# Initialize uAgent
agent = Agent(
    name="rag_doc_agent",
    port=8000,
    endpoint=["http://127.0.0.1:8000/submit"],
)

# Fund the agent if needed (optional for local testing)
fund_agent_if_low(agent.wallet.address())

# Global QA Chain
qa_chain = initialize_rag()


@agent.on_event("startup")
async def startup(ctx: Context):
    ctx.logger.info(f"RAG Agent started at {agent.address}")
    if qa_chain is None:
        ctx.logger.warning("ChromaDB not found. Please run 'python ingest.py' first.")
    else:
        ctx.logger.info("RAG Chain initialized and ready.")


@agent.on_message(model=QuestionRequest)
async def handle_question(ctx: Context, sender: str, msg: QuestionRequest):
    ctx.logger.info(f"Received question from {sender}: {msg.question}")

    if qa_chain is None:
        response = "Error: I haven't ingested any documents yet. Please run the ingestion script."
    else:
        try:
            # Get answer from RAG chain
            result = qa_chain.invoke({"query": msg.question})
            response = result["result"]
        except Exception as e:
            ctx.logger.error(f"Error processing RAG query: {e}")
            response = f"I encountered an error while searching the document: {str(e)}"

    # Send back the answer
    await ctx.send(sender, AnswerResponse(answer=response))


if __name__ == "__main__":
    agent.run()
