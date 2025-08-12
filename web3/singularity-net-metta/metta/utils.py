
import json
from openai import OpenAI
from .medicalrag import MedicalRAG

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
        "Classify the intent as one of: 'symptom', 'treatment', 'side effect', 'faq', or 'unknown'.\n"
        "Extract the most relevant keyword (e.g., a symptom, disease, or treatment) from the query.\n"
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
    if intent == "symptom":
        prompt = (
            f"Query: '{query}'\n"
            "The symptom '{keyword}' is not in my knowledge base. Suggest a plausible disease it might be linked to.\n"
            "Return *only* the disease name, no additional text."
        )
    elif intent == "treatment":
        prompt = (
            f"Query: '{query}'\n"
            "The disease or condition '{keyword}' has no known treatments in my knowledge base. Suggest a plausible treatment.\n"
            "Return *only* the treatment description, no additional text."
        )
    elif intent == "side effect":
        prompt = (
            f"Query: '{query}'\n"
            "The treatment '{keyword}' has no known side effects in my knowledge base. Suggest plausible side effects.\n"
            "Return *only* the side effects description, no additional text."
        )
    elif intent == "faq":
        prompt = (
            f"Query: '{query}'\n"
            "This is a new FAQ not in my knowledge base. Provide a concise, helpful answer.\n"
            "Return *only* the answer, no additional text."
        )
    else:
        return None
    return llm.create_completion(prompt)

def process_query(query, rag: MedicalRAG, llm: LLM):
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
                "Humanize this for a medical assistant with a friendly tone."
            )
        elif faq_answer:
            prompt = (
                f"Query: '{query}'\n"
                f"FAQ Answer: '{faq_answer}'\n"
                "Humanize this for a medical assistant with a friendly tone."
            )
    elif intent == "symptom" and keyword:
        diseases = rag.query_symptom(keyword)
        if not diseases:
            disease = generate_knowledge_response(query, intent, keyword, llm)
            rag.add_knowledge("symptom", keyword, disease)
            print(f"Knowledge graph updated - Added symptom: '{keyword}' → '{disease}'")
            treatments = rag.get_treatment(disease) or ["rest, consult a doctor"]
            side_effects = [rag.get_side_effects(t) for t in treatments] if treatments else []
            prompt = (
                f"Query: '{query}'\n"
                f"Symptom: {keyword}\n"
                f"Related Disease: {disease}\n"
                f"Treatments: {', '.join(treatments)}\n"
                f"Side Effects: {', '.join([', '.join(se) for se in side_effects if se])}\n"
                "Generate a concise, empathetic response for a medical assistant."
            )
        else:
            disease = diseases[0]
            treatments = rag.get_treatment(disease)
            side_effects = [rag.get_side_effects(t) for t in treatments] if treatments else []
            prompt = (
                f"Query: '{query}'\n"
                f"Symptom: {keyword}\n"
                f"Related Disease: {disease}\n"
                f"Treatments: {', '.join(treatments)}\n"
                f"Side Effects: {', '.join([', '.join(se) for se in side_effects if se])}\n"
                "Generate a concise, empathetic response for a medical assistant."
            )
    elif intent == "treatment" and keyword:
        treatments = rag.get_treatment(keyword)
        if not treatments:
            treatment = generate_knowledge_response(query, intent, keyword, llm)
            rag.add_knowledge("treatment", keyword, treatment)
            print(f"Knowledge graph updated - Added treatment: '{keyword}' → '{treatment}'")
            prompt = (
                f"Query: '{query}'\n"
                f"Disease: {keyword}\n"
                f"Treatments: {treatment}\n"
                "Provide a helpful treatment suggestion."
            )
        else:
            prompt = (
                f"Query: '{query}'\n"
                f"Disease: {keyword}\n"
                f"Treatments: {', '.join(treatments)}\n"
                "Provide a helpful treatment suggestion."
            )
    elif intent == "side effect" and keyword:
        side_effects = rag.get_side_effects(keyword)
        if not side_effects:
            side_effect = generate_knowledge_response(query, intent, keyword, llm)
            rag.add_knowledge("side_effect", keyword, side_effect)
            print(f"Knowledge graph updated - Added side effect: '{keyword}' → '{side_effect}'")
            prompt = (
                f"Query: '{query}'\n"
                f"Treatment: {keyword}\n"
                f"Side Effects: {side_effect}\n"
                "Provide a concise explanation of side effects."
            )
        else:
            prompt = (
                f"Query: '{query}'\n"
                f"Treatment: {keyword}\n"
                f"Side Effects: {', '.join(side_effects)}\n"
                "Provide a concise explanation of side effects."
            )
    
    if not prompt:
        prompt = f"Query: '{query}'\nNo specific info found. Offer general assistance."

    prompt += "\nFormat response as: 'Selected Question: <question>' on first line, 'Humanized Answer: <response>' on second."
    response = llm.create_completion(prompt)
    try:
        selected_q = response.split('\n')[0].replace("Selected Question: ", "").strip()
        answer = response.split('\n')[1].replace("Humanized Answer: ", "").strip()
        return {"selected_question": selected_q, "humanized_answer": answer}
    except IndexError:
        return {"selected_question": query, "humanized_answer": response}