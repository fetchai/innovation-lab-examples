from shared_clients.llm_client import shared_llm
from langchain_core.messages import HumanMessage
from brand_agent.audience_onboarder.audience_onboarder_steps import Step
from shared_clients.supabase_client import supabase

def get_milestone_step_statuses(asi_one_id: str, brand_agent_id: str) -> dict[Step, bool]:
    """Get the current step of the onboarding process for the given ASI:One ID"""
    name_verified = False
    role_verified = False
    contact_verified = False

    response = supabase.table("audience_profiles").select("*").eq("audience_asi_one_id", asi_one_id).eq("personal_brand_agent_id", brand_agent_id).execute()

    if response.data and len(response.data) > 0:
        name_verified = response.data[0]["name"] is not None and response.data[0]["name"] != ""  # type: ignore
        role_verified = response.data[0]["role"] is not None and response.data[0]["role"] != ""  # type: ignore
        contact_verified = response.data[0]["contact"] is not None and response.data[0]["contact"] != ""  # type: ignore

    return {
        Step.VERIFY_NAME: name_verified,
        Step.VERIFY_ROLE: role_verified,
        Step.VERIFY_CONTACT: contact_verified,
    }

def get_current_step(milestone_step_completed: dict[Step, bool]) -> Step:
    if not milestone_step_completed[Step.VERIFY_NAME]:
        return Step.ASK_NAME
    if not milestone_step_completed[Step.VERIFY_ROLE]:
        return Step.ASK_ROLE
    if not milestone_step_completed[Step.VERIFY_CONTACT]:
        return Step.ASK_CONTACT

    return Step.COMPLETE

def get_pretty_milestone_step_statuses(milestone_step_completed: dict[Step, bool]) -> str:
    milestone_steps = [Step.VERIFY_NAME, Step.VERIFY_ROLE, Step.VERIFY_CONTACT]
    pretty_statuses = [
        f"{'✅' if milestone_step_completed[milestone_step] else '⬜️'}  {milestone_step.value.replace('_', ' ').title()}"
        for milestone_step in milestone_steps
    ]
    return "\n".join(pretty_statuses)

def is_valid_name(user_input: str) -> bool:
    """Check if the user's message is an answer to 'What is your full name?'"""
    response = shared_llm.invoke([
        HumanMessage(content=f"""
        You are validating user input.

        The user was asked: "What is your full name?"

        Determine if their response below *answers that question* by providing a name 
        (e.g., "My name is John", "I'm Alice Smith", "Call me Peter", etc.).

        Respond with only 'yes' or 'no'.

        User response: "{user_input}"
        """)
    ])
    answer = response.content.strip().lower()  # type: ignore
    return answer == "yes"

def extract_name(user_input: str):
    """Extract the full name from the user's input"""
    response = shared_llm.invoke([
        HumanMessage(content=f"""
        Extract the full name from the following text.
        Respond with only the full name and nothing else.

        Text: "{user_input}"
        """)
    ])

    extracted_name = response.content.strip()  # type: ignore
    return extracted_name

def is_valid_contact(user_input: str) -> bool:
    """Check if the user's message is an answer to 'What is your contact information?' (phone or email)"""
    response = shared_llm.invoke([
        HumanMessage(content=f"""
        You are validating user input.

        The user was asked: "What is your contact information?" (Accept either a phone number or an email address.)

        Determine if their response below *answers that question* by providing either a valid phone number or a valid email address.

        Respond with only 'yes' or 'no'.

        User response: "{user_input}"
        """)
    ])
    answer = response.content.strip().lower()  # type: ignore
    return answer == "yes"

def extract_contact(user_input: str):
    """Extract the contact information (phone number or email) from the user's input"""
    response = shared_llm.invoke([
        HumanMessage(content=f"""
        Extract the contact information from the following text.
        The contact information can be a phone number or an email address.
        Respond with only the contact information (phone number or email address) and nothing else.

        Text: "{user_input}"
        """)
    ])

    extracted_contact = response.content.strip()  # type: ignore
    return extracted_contact

def is_valid_role(user_input: str) -> bool:
    """Check if the user's message is an answer to 'What is your role?'"""
    response = shared_llm.invoke([
        HumanMessage(content=f"""
        You are validating user input.

        The user was asked: "What is your role?"

        Determine if their response below *answers that question* by providing a role or how they relate to the event or organization.
        Accept vague roles such as recruiter, student, hackathon teammate, partner, boss, friend, etc.

        Respond with only 'yes' or 'no'.

        User response: "{user_input}"
        """)
    ])
    answer = response.content.strip().lower()  # type: ignore
    return answer == "yes"

def extract_role(user_input: str):
    """Extract the role from the user's input (e.g., recruiter, student, teammate, etc.)"""
    response = shared_llm.invoke([
        HumanMessage(content=f"""
        Extract the role from the following text.
        The role can be general or vague, such as recruiter, student, hackathon teammate, partner, boss, friend, etc.
        Respond with only the role and nothing else.

        Text: "{user_input}"
        """)
    ])

    extracted_role = response.content.strip()  # type: ignore
    return extracted_role


def test_audience_helpers():
    print("=" * 60)
    print("Testing is_valid_name()")
    print("=" * 60)
    
    # Test 1: Valid name
    test_input1 = "My name is John Smith"
    result1 = is_valid_name(test_input1)
    print(f"Input: '{test_input1}'")
    print(f"Result: {result1}\n")
    
    # Test 2: Invalid input (not a name)
    test_input2 = "I like pizza"
    result2 = is_valid_name(test_input2)
    print(f"Input: '{test_input2}'")
    print(f"Result: {result2}\n")
    
    print("=" * 60)
    print("Testing extract_name()")
    print("=" * 60)
    
    # Test 1: Simple name
    test_input3 = "I'm Alice Johnson"
    result3 = extract_name(test_input3)
    print(f"Input: '{test_input3}'")
    print(f"Extracted: '{result3}'\n")
    
    # Test 2: Name with context
    test_input4 = "Call me Peter Parker, nice to meet you"
    result4 = extract_name(test_input4)
    print(f"Input: '{test_input4}'")
    print(f"Extracted: '{result4}'\n")
    
    print("=" * 60)
    print("Testing is_valid_contact()")
    print("=" * 60)
    
    # Test 1: Valid email
    test_input5 = "My email is john@example.com"
    result5 = is_valid_contact(test_input5)
    print(f"Input: '{test_input5}'")
    print(f"Result: {result5}\n")
    
    # Test 2: Valid phone
    test_input6 = "You can reach me at 555-123-4567"
    result6 = is_valid_contact(test_input6)
    print(f"Input: '{test_input6}'")
    print(f"Result: {result6}\n")
    
    # Test 3: Invalid input
    test_input7 = "I prefer texting"
    result7 = is_valid_contact(test_input7)
    print(f"Input: '{test_input7}'")
    print(f"Result: {result7}\n")
    
    print("=" * 60)
    print("Testing extract_contact()")
    print("=" * 60)
    
    # Test 1: Extract email
    test_input8 = "Contact me at alice@company.com for more info"
    result8 = extract_contact(test_input8)
    print(f"Input: '{test_input8}'")
    print(f"Extracted: '{result8}'\n")
    
    # Test 2: Extract phone
    test_input9 = "My number is (555) 987-6543"
    result9 = extract_contact(test_input9)
    print(f"Input: '{test_input9}'")
    print(f"Extracted: '{result9}'\n")
    
    print("=" * 60)
    print("Testing is_valid_role()")
    print("=" * 60)
    
    # Test 1: Valid role
    test_input10 = "I'm a recruiter"
    result10 = is_valid_role(test_input10)
    print(f"Input: '{test_input10}'")
    print(f"Result: {result10}\n")
    
    # Test 2: Valid vague role
    test_input11 = "I'm here as a hackathon teammate"
    result11 = is_valid_role(test_input11)
    print(f"Input: '{test_input11}'")
    print(f"Result: {result11}\n")
    
    # Test 3: Invalid input
    test_input12 = "The weather is nice today"
    result12 = is_valid_role(test_input12)
    print(f"Input: '{test_input12}'")
    print(f"Result: {result12}\n")
    
    print("=" * 60)
    print("Testing extract_role()")
    print("=" * 60)
    
    # Test 1: Simple role
    test_input13 = "I work as a software engineer"
    result13 = extract_role(test_input13)
    print(f"Input: '{test_input13}'")
    print(f"Extracted: '{result13}'\n")
    
    # Test 2: Vague role
    test_input14 = "I'm a friend of the organizer"
    result14 = extract_role(test_input14)
    print(f"Input: '{test_input14}'")
    print(f"Extracted: '{result14}'\n")
    
    print("=" * 60)
    print("All tests completed!")
    print("=" * 60)

if __name__ == "__main__":
    print(get_milestone_step_statuses("user123", "agent1qgerajmgluncfslmdmrgxww463ntt4c90slr0srq4lcc9vmyyavkyg2tzh7"))