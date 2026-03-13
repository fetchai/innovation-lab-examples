from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from dotenv import load_dotenv
from shared_clients.supabase_client import supabase
from data_management_agent.onboarding_agent.onboarding_types import Step
from shared_clients.chroma_client import chroma_client
from chroma.chroma_constants import FACTS, Source

load_dotenv()

llm = ChatOpenAI(model="gpt-4o-mini")

def get_milestone_step_statuses(asi_one_id: str) -> dict[Step, bool]:
    """Get the current step of the onboarding process for the given ASI:One ID"""
    name_verified = False
    resume_parsed = False

    response = supabase.table("user_profiles").select("*").eq("asi_one_id", asi_one_id).execute()
    if response.data: # type: ignore
        user_profile = response.data[0] # type: ignore
        name = user_profile.get("name") # type: ignore
        name_verified = name is not None and name != ""
    
    resume_facts = chroma_client.get_collection(FACTS).query(
        query_texts=[asi_one_id],
        n_results=1,
        where={"source": Source.RESUME.value}
    )

    if resume_facts["documents"][0] and len(resume_facts["documents"][0]) > 0: # type: ignore
        resume_parsed = True
    
    return {
        Step.VERIFY_NAME: name_verified,
        Step.STORE_FACTS_FROM_RESUME: resume_parsed
    }

def get_current_step(milestone_step_completed: dict[Step, bool]) -> Step:
    if not milestone_step_completed[Step.VERIFY_NAME]:
        return Step.ASK_NAME
    if not milestone_step_completed[Step.STORE_FACTS_FROM_RESUME]:
        return Step.ASK_RESUME

    return Step.COMPLETE

def get_pretty_milestone_step_statuses(milestone_step_completed: dict[Step, bool]) -> str:
    milestone_steps = [Step.VERIFY_NAME, Step.STORE_FACTS_FROM_RESUME]
    pretty_statuses = [
        f"{'✅' if milestone_step_completed[milestone_step] else '⬜️'}  {milestone_step.value.replace('_', ' ').title()}"
        for milestone_step in milestone_steps
    ]
    return "\n".join(pretty_statuses)

def is_valid_name(user_input: str) -> bool:
    """Check if the user's message is an answer to 'What is your full name?'"""
    response = llm.invoke([
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
    response = llm.invoke([
        HumanMessage(content=f"""
        Extract the full name from the following text.
        Respond with only the full name and nothing else.

        Text: "{user_input}"
        """)
    ])

    extracted_name = response.content.strip()  # type: ignore
    return extracted_name

def is_valid_resume(user_input: str) -> bool:
    """Check if the user's message is an answer to 'Please copy paste your resume.'"""
    response = llm.invoke([
        HumanMessage(content=f"""
        You are validating user input.

        The user was asked: "Please copy paste your resume."

        Determine if their response below *answers that question* by providing the content of a resume or the bulk of a CV.
        This generally means it should look like a resume (contains multiple sections like education, skills, experience, job history, formatting or lists, and enough length).
        
        Reject responses that are clearly not a resume (e.g., "I don't have one", "not sure", "Hi", "John Smith", "I'm ready", etc.).
        Accept ONLY if the input is the likely copy-pasted contents of a resume file.

        Respond with only 'yes' or 'no'.

        User response: "{user_input}"
        """)
    ])
    answer = response.content.strip().lower()  # type: ignore
    return answer == "yes"

def parse_resume(resume_contents: str) -> list[str]:
    """
    Given a user's resume contents as raw text, return a prompt for an LLM that instructs it to parse 
    the resume into a flat list of factual statements ("facts") about the user. The LLM should not
    invent or infer, but should reconstruct the facts in a way that is suitable for semantic search 
    or vector embeddings. Each fact should be a single atomic statement and based strictly on information
    present in the original resume.
    """
    prompt = f"""
    You are an expert resume parser.

    You will receive the content of a user's resume (as plain text). 
    Your task is to extract ALL discrete, factual statements ("facts") about the user, listing each fact on its own line.
    Each fact should be self-contained, unambiguous, and include enough contextual information—such as role, technology, organization, dates, awards, outcomes, and numbers—so that it could semantically match common recruiter questions (such as "Tell me about a time you used Next.js", "Have you worked under pressure?", "What teamwork experience do you have?", "Did you use Python?", etc.).

    — Do NOT add, invent, or infer information not explicitly in the original resume text.
    — Do NOT summarize, generalize, or group facts; instead, list each as a stand-alone, atomic fact suitable for semantic search or question-answering.
    — Each fact should be a full, clear sentence that clearly attributes the experience, skill, or achievement to the user, and can be directly matched to a specific recruiter query about their work, technologies, team experience, pressure situations, awards, etc.
    — Include all critical context for each fact. If relevant, spell out the technologies, dates, role titles, organizations, outcomes, or details from the resume, so the fact is understandable and useful without needing to refer to the original text.
    — Rephrase and expand as needed only to maximize clarity and make each fact more likely to match a variety of recruiter questions.

    Output only the list of facts, with each fact on its own line.

    Resume:
    \"\"\"
    {resume_contents}
    \"\"\"
    """
    response = llm.invoke([HumanMessage(content=prompt)])
    return [fact.strip() for fact in response.content.strip().split("\n") if fact.strip() != ""] # type: ignore

if __name__ == "__main__":
    statuses = (get_milestone_step_statuses("agent1q29tg4sgdzg33gr7u63hfemq4hk54thsya3s7kygurrxg3j8p8f2qlnxz9f"))
    current_step = get_current_step(statuses)
    pretty_statuses = get_pretty_milestone_step_statuses(statuses)
    print(pretty_statuses)