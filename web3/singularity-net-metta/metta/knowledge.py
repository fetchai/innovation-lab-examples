# knowledge.py
from hyperon import MeTTa, E, S, ValueAtom

def initialize_knowledge_graph(metta: MeTTa):
    """Initialize the MeTTa knowledge graph with symptom, treatment, side effect, and FAQ data."""
    # Symptoms → Diseases
    metta.space().add_atom(E(S("symptom"), S("fever"), S("flu")))
    metta.space().add_atom(E(S("symptom"), S("cough"), S("flu")))
    metta.space().add_atom(E(S("symptom"), S("headache"), S("migraine")))
    metta.space().add_atom(E(S("symptom"), S("fatigue"), S("depression")))
    metta.space().add_atom(E(S("symptom"), S("nausea"), S("flu")))
    metta.space().add_atom(E(S("symptom"), S("dizziness"), S("migraine")))
    metta.space().add_atom(E(S("symptom"), S("anxiety"), S("depression")))
    metta.space().add_atom(E(S("symptom"), S("stomach upset"), S("flu")))
    metta.space().add_atom(E(S("symptom"), S("insomnia"), S("depression"))) 
    
    # Diseases → Treatments 
    metta.space().add_atom(E(S("treatment"), S("flu"), ValueAtom("rest, fluids, antiviral drugs")))
    metta.space().add_atom(E(S("treatment"), S("migraine"), ValueAtom("pain relievers, hydration, dark room")))
    metta.space().add_atom(E(S("treatment"), S("depression"), ValueAtom("therapy, antidepressants")))
    metta.space().add_atom(E(S("treatment"), S("anxiety"), ValueAtom("therapy, medications")))  
    metta.space().add_atom(E(S("treatment"), S("fatigue"), ValueAtom("rest, hydration, balanced diet")))
    metta.space().add_atom(E(S("treatment"), S("insomnia"), ValueAtom("sleep hygiene, medications")))
    metta.space().add_atom(E(S("treatment"), S("stomach upset"), ValueAtom("dietary changes, medications")))
    metta.space().add_atom(E(S("treatment"), S("dizziness"), ValueAtom("hydration, medications")))
    metta.space().add_atom(E(S("treatment"), S("pain relievers"), ValueAtom("rest, hydration")))
    metta.space().add_atom(E(S("treatment"), S("antiviral drugs"), ValueAtom("rest, hydration")))
    metta.space().add_atom(E(S("treatment"), S("antidepressants"), ValueAtom("therapy, lifestyle changes")))
    metta.space().add_atom(E(S("treatment"), S("antidepressants"), ValueAtom("therapy, medications")))  
    
    # Treatments → Side Effects
    metta.space().add_atom(E(S("side_effect"), S("antiviral drugs"), ValueAtom("nausea, dizziness")))
    metta.space().add_atom(E(S("side_effect"), S("pain relievers"), ValueAtom("stomach upset")))
    metta.space().add_atom(E(S("side_effect"), S("antidepressants"), ValueAtom("weight gain, insomnia")))
    metta.space().add_atom(E(S("side_effect"), S("therapy"), ValueAtom("initial discomfort, emotional release")))
    
    # FAQs
    metta.space().add_atom(E(S("faq"), S("Hi"), ValueAtom("Hello! How can I assist you today?")))
    metta.space().add_atom(E(S("faq"), S("What’s wrong with me?"), ValueAtom("I’m not a doctor, but I can help you explore symptoms. What are you feeling?")))
    metta.space().add_atom(E(S("faq"), S("How do I treat a migraine?"), ValueAtom("For migraines, rest in a dark room and stay hydrated. Pain relievers can help.")))