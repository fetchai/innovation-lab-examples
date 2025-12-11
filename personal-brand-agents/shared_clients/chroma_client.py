import chromadb
from chroma.chroma_constants import *
import os
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("CHROMA_API_KEY")
TENANT = os.getenv("CHROMA_TENANT_ID")
DATABASE = os.getenv("CHROMA_DATABASE")

# chroma_client = chromadb.PersistentClient()
# chroma_client = chromadb.HttpClient(host='localhost', port=8000)

chroma_client = chromadb.CloudClient(
  api_key=API_KEY,
  tenant=TENANT,
  database=DATABASE
)
facts_collection = chroma_client.get_or_create_collection(name=FACTS)
failed_questions_collection = chroma_client.get_or_create_collection(name=QUESTIONS)