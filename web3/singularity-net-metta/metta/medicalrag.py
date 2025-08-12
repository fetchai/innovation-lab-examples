# medicalrag.py
import re
from hyperon import MeTTa, E, S, ValueAtom

class MedicalRAG:
    def __init__(self, metta_instance: MeTTa):
        self.metta = metta_instance

    def query_symptom(self, symptom):
        """Find diseases linked to a symptom."""
        symptom = symptom.strip('"')
        query_str = f'!(match &self (symptom {symptom} $disease) $disease)'
        results = self.metta.run(query_str)
        print(results,query_str)

        unique_diseases = list(set(str(r[0]) for r in results if r and len(r) > 0)) if results else []
        return unique_diseases

    def get_treatment(self, disease):
        """Find treatments for a disease."""
        disease = disease.strip('"')
        query_str = f'!(match &self (treatment {disease} $treatment) $treatment)'
        results = self.metta.run(query_str)
        print(results,query_str)
        return [r[0].get_object().value for r in results if r and len(r) > 0] if results else []

    def get_side_effects(self, treatment):
        """Find side effects of a treatment."""
        treatment = treatment.strip('"')
        query_str = f'!(match &self (side_effect {treatment} $effect) $effect)'
        results = self.metta.run(query_str)
        print(results,query_str)

        return [r[0].get_object().value for r in results if r and len(r) > 0] if results else []

    def query_faq(self, question):
        """Retrieve FAQ answers."""
        query_str = f'!(match &self (faq "{question}" $answer) $answer)'
        results = self.metta.run(query_str)
        print(results,query_str)

        return results[0][0].get_object().value if results and results[0] else None

    def add_knowledge(self, relation_type, subject, object_value):
        """Add new knowledge dynamically."""
        if isinstance(object_value, str):
            object_value = ValueAtom(object_value)
        self.metta.space().add_atom(E(S(relation_type), S(subject), object_value))
        return f"Added {relation_type}: {subject} → {object_value}"