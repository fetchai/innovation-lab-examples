import json
from openai import OpenAI
from .generalrag import GeneralRAG

class LLM:
    def __init__(self, api_key):
        self.client = OpenAI(
            api_key=api_key,
            base_url="https://api.asi1.ai/v1"
        )

    def create_completion(self, prompt, max_tokens=200):
        completion = self.client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="asi1-mini",  # ASI:One model name
            max_tokens=max_tokens
        )
        return completion.choices[0].message.content

def get_intent_and_keyword(query, llm):
    """Use ASI:One API to classify intent and extract a keyword."""
    prompt = (
        f"Given the query: '{query}'\n"
        "Classify the intent as one of: 'capability', 'solution', 'consideration', 'faq', or 'unknown'.\n"
        "Extract the most relevant keyword (e.g., a concept, problem, or topic) from the query.\n"
        "Return *only* the result in JSON format like this, with no additional text:\n"
        "{\n"
        "  \"intent\": \"<classified_intent>\",\n"
        "  \"keyword\": \"<extracted_keyword>\"\n"
        "}"
    )
    response = llm.create_completion(prompt)
    try:
        result = json.loads(response)
        return result["intent"], result["keyword"]
    except json.JSONDecodeError:
        print(f"Error parsing ASI:One response: {response}")
        return "unknown", None

def generate_knowledge_response(query, intent, keyword, llm):
    """Use ASI:One to generate a response for new knowledge based on intent."""
    if intent == "capability":
        prompt = (
            f"Query: '{query}'\n"
            "The concept '{keyword}' is not in my knowledge base. Suggest plausible capabilities it might have.\n"
            "Return *only* the capability description, no additional text."
        )
    elif intent == "solution":
        prompt = (
            f"Query: '{query}'\n"
            "The problem '{keyword}' has no known solutions in my knowledge base. Suggest a plausible solution.\n"
            "Return *only* the solution description, no additional text."
        )
    elif intent == "consideration":
        prompt = (
            f"Query: '{query}'\n"
            "The topic '{keyword}' has no known considerations in my knowledge base. Suggest plausible considerations or limitations.\n"
            "Return *only* the considerations description, no additional text."
        )
    elif intent == "faq":
        prompt = (
            f"Query: '{query}'\n"
            "This is a new FAQ not in my knowledge base. Provide a concise, helpful answer about Fetch.ai/uAgents.\n"
            "Return *only* the answer, no additional text."
        )
    else:
        return None
    return llm.create_completion(prompt)

def process_query(query, rag: GeneralRAG, llm: LLM):
    intent, keyword = get_intent_and_keyword(query, llm)
    print(f"Intent: {intent}, Keyword: {keyword}")
    prompt = ""

    if intent == "faq":
        faq_answer = rag.query_faq(query)
        if not faq_answer and keyword:
            new_answer = generate_knowledge_response(query, intent, keyword, llm)
            rag.add_knowledge("faq", query, new_answer)
            print(f"Knowledge graph updated - Added FAQ: '{query}' → '{new_answer}'")
            prompt = (
                f"Query: '{query}'\n"
                f"FAQ Answer: '{new_answer}'\n"
                "Humanize this for a Fetch.ai/uAgents assistant with a helpful tone."
            )
        elif faq_answer:
            prompt = (
                f"Query: '{query}'\n"
                f"FAQ Answer: '{faq_answer}'\n"
                "Humanize this for a Fetch.ai/uAgents assistant with a helpful tone."
            )
    elif intent == "capability" and keyword:
        capabilities = rag.query_capability(keyword)
        if not capabilities:
            capability = generate_knowledge_response(query, intent, keyword, llm)
            rag.add_knowledge("capability", keyword, capability)
            print(f"Knowledge graph updated - Added capability: '{keyword}' → '{capability}'")
            solutions = rag.get_solution(keyword) or ["consult documentation"]
            considerations = [rag.get_consideration(keyword)] if keyword else []
            prompt = (
                f"Query: '{query}'\n"
                f"Concept: {keyword}\n"
                f"Capabilities: {capability}\n"
                f"Solutions: {', '.join(solutions)}\n"
                f"Considerations: {', '.join([', '.join(c) for c in considerations if c])}\n"
                "Generate a concise, helpful response for a Fetch.ai/uAgents assistant."
            )
        else:
            capability = capabilities[0]
            solutions = rag.get_solution(keyword)
            considerations = [rag.get_consideration(keyword)] if keyword else []
            prompt = (
                f"Query: '{query}'\n"
                f"Concept: {keyword}\n"
                f"Capabilities: {capability}\n"
                f"Solutions: {', '.join(solutions)}\n"
                f"Considerations: {', '.join([', '.join(c) for c in considerations if c])}\n"
                "Generate a concise, helpful response for a Fetch.ai/uAgents assistant."
            )
    elif intent == "solution" and keyword:
        solutions = rag.get_solution(keyword)
        if not solutions:
            solution = generate_knowledge_response(query, intent, keyword, llm)
            rag.add_knowledge("solution", keyword, solution)
            print(f"Knowledge graph updated - Added solution: '{keyword}' → '{solution}'")
            prompt = (
                f"Query: '{query}'\n"
                f"Problem: {keyword}\n"
                f"Solution: {solution}\n"
                "Provide a helpful solution suggestion."
            )
        else:
            prompt = (
                f"Query: '{query}'\n"
                f"Problem: {keyword}\n"
                f"Solutions: {', '.join(solutions)}\n"
                "Provide a helpful solution suggestion."
            )
    elif intent == "consideration" and keyword:
        considerations = rag.get_consideration(keyword)
        if not considerations:
            consideration = generate_knowledge_response(query, intent, keyword, llm)
            rag.add_knowledge("consideration", keyword, consideration)
            print(f"Knowledge graph updated - Added consideration: '{keyword}' → '{consideration}'")
            prompt = (
                f"Query: '{query}'\n"
                f"Topic: {keyword}\n"
                f"Considerations: {consideration}\n"
                "Provide a concise explanation of considerations."
            )
        else:
            prompt = (
                f"Query: '{query}'\n"
                f"Topic: {keyword}\n"
                f"Considerations: {', '.join(considerations)}\n"
                "Provide a concise explanation of considerations."
            )
    
    if not prompt:
        prompt = f"Query: '{query}'\nNo specific info found. Offer general Fetch.ai/uAgents assistance."

    prompt += "\nFormat response as: 'Selected Question: <question>' on first line, 'Humanized Answer: <response>' on second."
    response = llm.create_completion(prompt)
    try:
        selected_q = response.split('\n')[0].replace("Selected Question: ", "").strip()
        answer = response.split('\n')[1].replace("Humanized Answer: ", "").strip()
        return {"selected_question": selected_q, "humanized_answer": answer}
    except IndexError:
        return {"selected_question": query, "humanized_answer": response}
