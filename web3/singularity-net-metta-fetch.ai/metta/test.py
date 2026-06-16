from knowledge import *  # noqa: F403
from generalrag import *  # noqa: F403
from hyperon import MeTTa

metta = MeTTa()
initialize_knowledge_graph(metta)  # noqa: F405

rag = GeneralRAG(metta)  # noqa: F405

print(rag.get_specific_models("ASI:One"))
print(rag.query_all_specific_capabilities("ASI:One"))
