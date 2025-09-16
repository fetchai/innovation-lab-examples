import os
import logging
from datetime import datetime
from uuid import uuid4
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import Agno components for RAG functionality
from agno.agent import Agent as AgnoAgent, AgentKnowledge
from agno.embedder.openai import OpenAIEmbedder
from agno.models.openai import OpenAIChat
from agno.vectordb.pgvector import PgVector, SearchType

# Import uAgent components for chat protocol
from uagents import Context, Protocol, Agent
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    TextContent,
    chat_protocol_spec,
)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RAGChatAgent:
    """Integrated RAG Chat Agent combining Agno RAG with uAgent chat protocol"""
    
    def __init__(self):
        # Initialize the knowledge base with PgVector
        self.db_url = "postgresql+psycopg://ai:ai@localhost:5532/ai"
        self.knowledge = AgentKnowledge(
            vector_db=PgVector(
                table_name="ai_documents",
                db_url=self.db_url,
                search_type=SearchType.hybrid,
                embedder=OpenAIEmbedder(
                    id="text-embedding-3-small",
                    api_key=os.getenv("OPENAI_API_KEY")
                ),
            ),
        )
        
        # Initialize the knowledge base first
        try:
            self.knowledge.load()
            logger.info("Knowledge base initialized successfully")
        except Exception as init_error:
            logger.warning(f"Could not initialize knowledge base: {init_error}")
        
        # Add PDF content to knowledge base
        try:
            from agno.document.reader.pdf_reader import PDFReader
            from agno.document.base import Document
            import uuid
            
            pdf_reader = PDFReader()
            documents = pdf_reader.read("ai.pdf")
            
            # Ensure each document has a proper ID and fix serialization issue
            for i, document in enumerate(documents):
                # Always set a unique ID
                document.id = f"ai_doc_{i+1}_{uuid.uuid4().hex[:8]}"
                
                # Set document name
                document.name = f"ai_document_{i+1}"
                
                # Ensure the document has all required fields
                document.meta_data = {'source': 'ai.pdf', 'page': i+1}
            
            # Load documents using load_documents method
            try:
                self.knowledge.load_documents(documents, upsert=True)
                loaded_count = len(documents)
                logger.info(f"Successfully loaded {loaded_count} documents from ai.pdf to knowledge base")
            except Exception as load_error:
                logger.error(f"Failed to load documents: {load_error}")
                # Try loading documents one by one as fallback
                loaded_count = 0
                for document in documents:
                    try:
                        self.knowledge.load_document(document, upsert=True)
                        loaded_count += 1
                    except Exception as doc_error:
                        logger.error(f"Failed to load document {document.id}: {doc_error}")
            
            # Verify documents are in the knowledge base
            try:
                test_results = self.knowledge.search("AI", num_documents=1)
                logger.info(f"Knowledge base verification: Found {len(test_results)} documents for test query")
            except Exception as verify_error:
                logger.warning(f"Could not verify knowledge base: {verify_error}")
                
        except Exception as e:
            logger.error(f"Failed to add PDF to knowledge base: {e}")
            import traceback
            traceback.print_exc()
        
        # Initialize Agno RAG agent
        self.rag_agent = AgnoAgent(
            model=OpenAIChat(
                id="gpt-4o-mini",
                api_key=os.getenv("OPENAI_API_KEY")
            ),
            knowledge=self.knowledge,
            search_knowledge=True,
            markdown=True,
        )
        
        # Initialize uAgent
        self.uagent = Agent(
            name="RAG-Chat-Agent",
            seed="rag-chat-agent-seed",
            port=8001,
            mailbox=True,
        )
        
        # Set up chat protocol
        self.setup_protocol()
    
    def setup_protocol(self):
        """Set up the chat protocol for the uAgent"""
        protocol = Protocol(spec=chat_protocol_spec)
        
        @protocol.on_message(ChatMessage)
        async def handle_message(ctx: Context, sender: str, msg: ChatMessage):
            """Handle incoming chat messages and generate RAG-powered responses"""
            try:
                # Send acknowledgement
                await ctx.send(
                    sender,
                    ChatAcknowledgement(
                        timestamp=datetime.now(), 
                        acknowledged_msg_id=msg.msg_id
                    ),
                )
                
                # Extract text from message
                user_text = ""
                for item in msg.content:
                    if isinstance(item, TextContent):
                        user_text += item.text
                
                logger.info(f"Received message from {sender}: {user_text}")
                
                # Generate response using RAG agent
                response = await self.generate_rag_response(user_text)
                
                # Send response back
                await ctx.send(sender, ChatMessage(
                    timestamp=datetime.now(),
                    msg_id=uuid4(),
                    content=[
                        TextContent(type="text", text=response),
                    ]
                ))
                
                logger.info(f"Sent response to {sender}")
                
            except Exception as e:
                logger.error(f"Error handling message: {e}")
                # Send error response
                await ctx.send(sender, ChatMessage(
                    timestamp=datetime.now(),
                    msg_id=uuid4(),
                    content=[
                        TextContent(type="text", text=f"Sorry, I encountered an error: {str(e)}"),
                    ]
                ))
        
        @protocol.on_message(ChatAcknowledgement)
        async def handle_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
            """Handle chat acknowledgements"""
            logger.info(f"Received acknowledgement from {sender}")
        
        # Include protocol in uAgent
        self.uagent.include(protocol, publish_manifest=True)
    
    async def generate_rag_response(self, query: str) -> str:
        """Generate a response using the RAG agent"""
        try:
            # First, check if we have documents in the knowledge base
            try:
                search_results = self.knowledge.search(query, num_documents=3)
                logger.info(f"RAG Search found {len(search_results)} relevant documents for query: '{query}'")
                
                if len(search_results) == 0:
                    logger.warning("No documents found in knowledge base for RAG query")
                    return "I don't have any relevant information from the document to answer your question. Please make sure the PDF has been properly loaded into my knowledge base."
                
            except Exception as search_error:
                logger.error(f"Error searching knowledge base: {search_error}")
                return "I encountered an error while searching my knowledge base. Please try again."
            
            # Use the Agno agent to generate a response
            response = self.rag_agent.run(query)
            response_content = response.content if hasattr(response, 'content') else str(response)
            
            # Add a note if the response seems generic
            if not any(word in response_content.lower() for word in ['document', 'pdf', 'text', 'according to', 'based on']):
                response_content += "\n\n[Note: This response is based on my knowledge of the loaded PDF document.]"
            
            return response_content
            
        except Exception as e:
            logger.error(f"Error generating RAG response: {e}")
            import traceback
            traceback.print_exc()
            return f"I'm sorry, I couldn't process your request. Error: {str(e)}"
    
    def run(self):
        """Start the uAgent"""
        logger.info("Starting RAG Chat Agent...")
        logger.info(f"Agent address: {self.uagent.address}")
        self.uagent.run()

# Create and run the integrated agent
if __name__ == "__main__":
    try:
        agent = RAGChatAgent()
        agent.run()
    except KeyboardInterrupt:
        logger.info("Agent stopped by user")
    except Exception as e:
        logger.error(f"Failed to start agent: {e}")