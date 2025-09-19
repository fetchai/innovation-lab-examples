import json
from openai import OpenAI
from .investment_rag import InvestmentRAG

class LLM:
    def __init__(self, api_key):
        self.client = OpenAI(
            api_key=api_key,
            base_url="https://api.asi1.ai/v1"
        )

    def create_completion(self, prompt, max_tokens=200):
        completion = self.client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="asi1-mini",
            max_tokens=max_tokens
        )
        return completion.choices[0].message.content

def get_intent_and_keyword(query, llm):
    """Use ASI:One API to classify investment intent and extract a keyword."""
    prompt = (
        f"Given the investment query: '{query}'\n"
        "Classify the intent as one of: 'risk_profile', 'investment_advice', 'returns', 'allocation', 'goal', 'sector', 'mistake', 'faq', or 'unknown'.\n"
        "Extract the most relevant keyword (e.g., conservative, aggressive, retirement, technology, bonds) from the query.\n"
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
    if intent == "risk_profile":
        prompt = (
            f"Query: '{query}'\n"
            "The risk profile '{keyword}' is not in my knowledge base. Suggest plausible investment types for this risk level.\n"
            "Return *only* the investment types, no additional text."
        )
    elif intent == "investment_advice":
        prompt = (
            f"Query: '{query}'\n"
            "The investment type '{keyword}' has no specific advice in my knowledge base. Provide general investment guidance.\n"
            "Return *only* the advice, no additional text."
        )
    elif intent == "returns":
        prompt = (
            f"Query: '{query}'\n"
            "The investment '{keyword}' has no expected return data in my knowledge base. Suggest realistic return expectations.\n"
            "Return *only* the return information, no additional text."
        )
    elif intent == "allocation":
        prompt = (
            f"Query: '{query}'\n"
            "The age group '{keyword}' has no allocation strategy in my knowledge base. Suggest appropriate asset allocation.\n"
            "Return *only* the allocation recommendation, no additional text."
        )
    elif intent == "goal":
        prompt = (
            f"Query: '{query}'\n"
            "The investment goal '{keyword}' has no strategy in my knowledge base. Suggest appropriate investment approaches.\n"
            "Return *only* the strategy, no additional text."
        )
    elif intent == "faq":
        prompt = (
            f"Query: '{query}'\n"
            "This is a new investment question not in my knowledge base. Provide a helpful, concise answer.\n"
            "Return *only* the answer, no additional text."
        )
    else:
        return None
    return llm.create_completion(prompt)

def process_query(query, rag: InvestmentRAG, llm: LLM):
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
                f"Investment Answer: '{new_answer}'\n"
                "Provide this as professional investment guidance with appropriate disclaimers."
            )
        elif faq_answer:
            prompt = (
                f"Query: '{query}'\n"
                f"Investment Answer: '{faq_answer}'\n"
                "Provide this as professional investment guidance with appropriate disclaimers."
            )
    elif intent == "risk_profile" and keyword:
        investments = rag.query_risk_profile(keyword)
        if not investments:
            investment_types = generate_knowledge_response(query, intent, keyword, llm)
            rag.add_knowledge("risk_profile", keyword, investment_types)
            print(f"Knowledge graph updated - Added risk profile: '{keyword}' → '{investment_types}'")
            prompt = (
                f"Query: '{query}'\n"
                f"Risk Profile: {keyword}\n"
                f"Suitable Investments: {investment_types}\n"
                "Provide professional investment recommendations with risk disclaimers."
            )
        else:
            investment_details = []
            for investment in investments:
                returns = rag.get_expected_return(investment)
                risks = rag.get_risk_level(investment)
                investment_details.append({
                    'type': investment,
                    'returns': returns[0] if returns else 'N/A',
                    'risks': risks[0] if risks else 'N/A'
                })
            
            prompt = (
                f"Query: '{query}'\n"
                f"Risk Profile: {keyword}\n"
                f"Investment Options: {investment_details}\n"
                "Provide professional investment recommendations with expected returns and risk analysis."
            )
    elif intent == "returns" and keyword:
        returns = rag.get_expected_return(keyword)
        risks = rag.get_risk_level(keyword)
        if not returns:
            return_info = generate_knowledge_response(query, intent, keyword, llm)
            rag.add_knowledge("expected_return", keyword, return_info)
            print(f"Knowledge graph updated - Added returns: '{keyword}' → '{return_info}'")
            prompt = (
                f"Query: '{query}'\n"
                f"Investment: {keyword}\n"
                f"Expected Returns: {return_info}\n"
                "Provide return analysis with appropriate risk warnings."
            )
        else:
            prompt = (
                f"Query: '{query}'\n"
                f"Investment: {keyword}\n"
                f"Expected Returns: {', '.join(returns)}\n"
                f"Risk Level: {', '.join(risks) if risks else 'Not specified'}\n"
                "Provide comprehensive return and risk analysis."
            )
    elif intent == "allocation" and keyword:
        allocation = rag.get_age_allocation(keyword)
        if not allocation:
            allocation_advice = generate_knowledge_response(query, intent, keyword, llm)
            rag.add_knowledge("age_allocation", keyword, allocation_advice)
            print(f"Knowledge graph updated - Added allocation: '{keyword}' → '{allocation_advice}'")
            prompt = (
                f"Query: '{query}'\n"
                f"Age Group: {keyword}\n"
                f"Recommended Allocation: {allocation_advice}\n"
                "Provide age-appropriate asset allocation guidance."
            )
        else:
            prompt = (
                f"Query: '{query}'\n"
                f"Age Group: {keyword}\n"
                f"Recommended Allocation: {', '.join(allocation)}\n"
                "Explain the allocation strategy and rationale."
            )
    elif intent == "goal" and keyword:
        strategies = rag.get_goal_strategy(keyword)
        if not strategies:
            strategy = generate_knowledge_response(query, intent, keyword, llm)
            rag.add_knowledge("goal_strategy", keyword, strategy)
            print(f"Knowledge graph updated - Added goal strategy: '{keyword}' → '{strategy}'")
            prompt = (
                f"Query: '{query}'\n"
                f"Investment Goal: {keyword}\n"
                f"Recommended Strategy: {strategy}\n"
                "Provide goal-oriented investment guidance."
            )
        else:
            prompt = (
                f"Query: '{query}'\n"
                f"Investment Goal: {keyword}\n"
                f"Recommended Strategies: {', '.join(strategies)}\n"
                "Provide comprehensive goal-based investment planning."
            )
    elif intent == "sector" and keyword:
        stocks = rag.query_sector_stocks(keyword)
        if not stocks:
            sector_info = generate_knowledge_response(query, intent, keyword, llm)
            rag.add_knowledge("sector_stocks", keyword, sector_info)
            print(f"Knowledge graph updated - Added sector: '{keyword}' → '{sector_info}'")
            prompt = (
                f"Query: '{query}'\n"
                f"Sector: {keyword}\n"
                f"Investment Options: {sector_info}\n"
                "Provide sector-specific investment analysis."
            )
        else:
            prompt = (
                f"Query: '{query}'\n"
                f"Sector: {keyword}\n"
                f"Top Performers: {', '.join(stocks)}\n"
                "Provide sector analysis and investment recommendations."
            )
    
    if not prompt:
        prompt = f"Query: '{query}'\nNo specific investment information found. Provide general investment guidance and suggest consulting a financial advisor."

    prompt += "\nFormat response as: 'Selected Question: <question>' on first line, 'Investment Advice: <response>' on second. Include appropriate disclaimers about consulting financial professionals."
    response = llm.create_completion(prompt, max_tokens=300)
    try:
        selected_q = response.split('\n')[0].replace("Selected Question: ", "").strip()
        answer = response.split('\n')[1].replace("Investment Advice: ", "").strip()
        return {"selected_question": selected_q, "humanized_answer": answer}
    except IndexError:
        return {"selected_question": query, "humanized_answer": response}