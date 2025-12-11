from langchain_core.messages import HumanMessage
from data_management_agent.models import AgentState, initialize_agent_state
from data_management_agent.answer_failed_questions_agent.answer_failed_questions_agent import build_answer_failed_questions_graph
from data_management_agent.answer_failed_questions_agent.answer_failed_questions_helpers import (
    get_all_failed_questions,
    delete_all_failed_questions
)
from chroma.chroma_helpers import insert_question

# Test configuration
BRAND_AGENT_ID = "agent1qgerajmgluncfslmdmrgxww463ntt4c90slr0srq4lcc9vmyyavkyg2tzh7"
ASI_ONE_ID = "agent1qdnhwqv3ekrzcuk597nrzc8xh9eyurlwvsrzzrytr6cl87zuwfuayh4xq6g"

def reset_state():
    """Delete all failed questions for the test brand agent"""
    delete_all_failed_questions(BRAND_AGENT_ID)
    print("✓ Reset: Deleted all failed questions")

def add_test_questions():
    """Add some test questions"""
    test_questions = [
        "What is your favorite programming language?",
        "How many years of experience do you have?",
        "What is your biggest achievement?"
    ]
    for question in test_questions:
        insert_question(ASI_ONE_ID, question, BRAND_AGENT_ID)
    print(f"✓ Added {len(test_questions)} test questions")

def test_getting_failed_questions():
    """Test: Just getting the failed questions"""
    print(f"\n{'='*60}")
    print(f"TEST: Getting failed questions")
    print(f"{'='*60}")
    
    reset_state()
    add_test_questions()
    
    graph = build_answer_failed_questions_graph()
    state = initialize_agent_state(ASI_ONE_ID)
    state["messages"].append(HumanMessage(content="what are my remaining questions?"))
    result = graph.invoke(state)
    
    print(f"User: what are my remaining questions?")
    print(f"AI: {result['messages'][-1].content}")
    print(f"\n{'='*60}\n")

def test_picking_random_question():
    """Test: Trying to pick a random one to answer"""
    print(f"\n{'='*60}")
    print(f"TEST: Picking a random question")
    print(f"{'='*60}")
    
    reset_state()
    add_test_questions()
    
    graph = build_answer_failed_questions_graph()
    state = initialize_agent_state(ASI_ONE_ID)
    
    print(f"--- Step 1 ---")
    print(f"User: what are my remaining questions?")
    state["messages"].append(HumanMessage(content="what are my remaining questions?"))
    result = graph.invoke(state)
    state = AgentState(**result)
    print(f"AI: {result['messages'][-1].content}")
    
    print(f"\n--- Step 2 ---")
    print(f"User: random")
    state["messages"].append(HumanMessage(content="random"))
    result = graph.invoke(state)
    print(f"AI: {result['messages'][-1].content}")
    print(f"\n{'='*60}\n")

def test_picking_by_uuid():
    """Test: Picking by UUID"""
    print(f"\n{'='*60}")
    print(f"TEST: Picking by UUID")
    print(f"{'='*60}")
    
    reset_state()
    add_test_questions()
    questions = get_all_failed_questions(BRAND_AGENT_ID)
    
    if not questions:
        print("No questions to test UUID picking")
        print(f"\n{'='*60}\n")
        return
    
    question_id = questions[0]["id"]
    graph = build_answer_failed_questions_graph()
    state = initialize_agent_state(ASI_ONE_ID)
    
    print(f"--- Step 1 ---")
    print(f"User: what are my remaining questions?")
    state["messages"].append(HumanMessage(content="what are my remaining questions?"))
    result = graph.invoke(state)
    state = AgentState(**result)
    print(f"AI: {result['messages'][-1].content}")
    
    print(f"\n--- Step 2 ---")
    print(f"User: {question_id}")
    state["messages"].append(HumanMessage(content=question_id))
    result = graph.invoke(state)
    print(f"AI: {result['messages'][-1].content}")
    print(f"\n{'='*60}\n")

def test_picking_by_uuid_then_answering():
    """Test: Picking by UUID then answering"""
    print(f"\n{'='*60}")
    print(f"TEST: Picking by UUID then answering")
    print(f"{'='*60}")
    
    reset_state()
    add_test_questions()
    questions = get_all_failed_questions(BRAND_AGENT_ID)
    
    if not questions:
        print("No questions to test UUID picking and answering")
        print(f"\n{'='*60}\n")
        return
    
    question_id = questions[0]["id"]
    graph = build_answer_failed_questions_graph()
    state = initialize_agent_state(ASI_ONE_ID)
    
    print(f"--- Step 1 ---")
    print(f"User: what are my remaining questions?")
    state["messages"].append(HumanMessage(content="what are my remaining questions?"))
    result = graph.invoke(state)
    state = AgentState(**result)
    print(f"AI: {result['messages'][-1].content}")
    
    print(f"\n--- Step 2 ---")
    print(f"User: {question_id}")
    state["messages"].append(HumanMessage(content=question_id))
    result = graph.invoke(state)
    state = AgentState(**result)
    print(f"AI: {result['messages'][-1].content}")
    
    print(f"\n--- Step 3 ---")
    answer = "Python is my favorite programming language"
    print(f"User: {answer}")
    state["messages"].append(HumanMessage(content=answer))
    result = graph.invoke(state)
    print(f"AI: {result['messages'][-1].content}")
    print(f"\n{'='*60}\n")

def test_back_and_forth_answering_multiple_questions():
    """Test: User goes back and forth with the LLM answering multiple questions"""
    print(f"\n{'='*60}")
    print(f"TEST: Back and forth answering multiple questions")
    print(f"{'='*60}")
    
    reset_state()
    add_test_questions()
    
    graph = build_answer_failed_questions_graph()
    state = initialize_agent_state(ASI_ONE_ID)
    
    # Step 1: User asks to see questions
    print(f"--- Step 1 ---")
    print(f"User: what are my remaining questions?")
    state["messages"].append(HumanMessage(content="what are my remaining questions?"))
    result = graph.invoke(state)
    state = AgentState(**result)
    print(f"AI: {result['messages'][-1].content}")
    
    # Step 2: User picks a random question
    print(f"\n--- Step 2 ---")
    print(f"User: random")
    state["messages"].append(HumanMessage(content="random"))
    result = graph.invoke(state)
    state = AgentState(**result)
    print(f"AI: {result['messages'][-1].content}")
    
    # Step 3: User answers the first question
    print(f"\n--- Step 3 ---")
    answer1 = "Python is my favorite programming language because it's versatile and easy to learn."
    print(f"User: {answer1}")
    state["messages"].append(HumanMessage(content=answer1))
    result = graph.invoke(state)
    state = AgentState(**result)
    print(f"AI: {result['messages'][-1].content}")
    
    # Step 4: User picks another question by getting the remaining ones and picking by ID
    questions = get_all_failed_questions(BRAND_AGENT_ID)
    if questions:
        question_id = questions[0]["id"]
        print(f"\n--- Step 4 ---")
        print(f"User: {question_id}")
        state["messages"].append(HumanMessage(content=question_id))
        result = graph.invoke(state)
        state = AgentState(**result)
        print(f"AI: {result['messages'][-1].content}")
        
        # Step 5: User answers the second question
        print(f"\n--- Step 5 ---")
        answer2 = "I have 5 years of professional software development experience."
        print(f"User: {answer2}")
        state["messages"].append(HumanMessage(content=answer2))
        result = graph.invoke(state)
        state = AgentState(**result)
        print(f"AI: {result['messages'][-1].content}")
        
        # Step 6: User picks the last question (random)
        questions = get_all_failed_questions(BRAND_AGENT_ID)
        if questions:
            print(f"\n--- Step 6 ---")
            print(f"User: random")
            state["messages"].append(HumanMessage(content="random"))
            result = graph.invoke(state)
            state = AgentState(**result)
            print(f"AI: {result['messages'][-1].content}")
            
            # Step 7: User answers the last question
            print(f"\n--- Step 7 ---")
            answer3 = "My biggest achievement was leading a team of 5 developers to build a scalable microservices architecture that handled 1 million requests per day."
            print(f"User: {answer3}")
            state["messages"].append(HumanMessage(content=answer3))
            result = graph.invoke(state)
            state = AgentState(**result)
            print(f"AI: {result['messages'][-1].content}")
            
            # Step 8: Verify all questions are answered
            remaining = get_all_failed_questions(BRAND_AGENT_ID)
            if remaining:
                print(f"\n⚠️  Warning: {len(remaining)} questions still remain")
            else:
                print(f"\n✓ All questions have been answered!")
    
    print(f"\n{'='*60}\n")

if __name__ == "__main__":
    # Run all tests
    # test_getting_failed_questions()
    # test_picking_random_question()
    # test_picking_by_uuid()
    test_picking_by_uuid_then_answering()
    # test_back_and_forth_answering_multiple_questions()

