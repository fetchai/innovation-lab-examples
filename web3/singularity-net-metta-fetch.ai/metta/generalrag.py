# generalrag.py
import re
from hyperon import MeTTa, E, S, ValueAtom

class GeneralRAG:
    def __init__(self, metta_instance: MeTTa):
        self.metta = metta_instance

    def query_capability(self, capability):
        """Find capabilities linked to a concept."""
        capability = capability.strip('"')
        query_str = f'!(match &self (capability {capability} $feature) $feature)'
        results = self.metta.run(query_str)
        print(results, query_str)

        unique_features = list(set(str(r[0]) for r in results if r and len(r) > 0)) if results else []
        return unique_features

    def get_solution(self, problem):
        """Find solutions for a problem."""
        problem = problem.strip('"')
        query_str = f'!(match &self (solution {problem} $solution) $solution)'
        results = self.metta.run(query_str)
        print(results, query_str)
        return [r[0].get_object().value for r in results if r and len(r) > 0] if results else []

    def get_consideration(self, topic):
        """Find considerations/limitations for a topic."""
        topic = topic.strip('"')
        query_str = f'!(match &self (consideration {topic} $consideration) $consideration)'
        results = self.metta.run(query_str)
        print(results, query_str)

        return [r[0].get_object().value for r in results if r and len(r) > 0] if results else []

    def query_faq(self, question):
        """Retrieve FAQ answers."""
        query_str = f'!(match &self (faq "{question}" $answer) $answer)'
        results = self.metta.run(query_str)
        print(results, query_str)

        return results[0][0].get_object().value if results and results[0] else None

    def add_knowledge(self, relation_type, subject, object_value):
        """Add new knowledge dynamically."""
        if isinstance(object_value, str):
            object_value = ValueAtom(object_value)
        self.metta.space().add_atom(E(S(relation_type), S(subject), object_value))
        return f"Added {relation_type}: {subject} → {object_value}"
    
    def get_specific_models(self, model: str):
        """get specific instances of models from the knowldege graphs"""
        query_str = f'!(match &self (specificInstance {model} $specific_model) $specific_model)'
        results = self.metta.run(query_str)
        
        return [r[0].get_object().value for r in results if r and len(r) > 0] if results else []
