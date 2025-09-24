from knowledge import *
from generalrag import *
from hyperon import MeTTa

metta = MeTTa()
initialize_knowledge_graph(metta)

rag = GeneralRAG(metta)

print(rag.get_specific_models("ASI:One"))
print(rag.query_all_specific_capabilities("ASI:One"))


