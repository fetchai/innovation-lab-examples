import re
from hyperon import MeTTa, E, S, ValueAtom

class InvestmentRAG:
    def __init__(self, metta_instance: MeTTa):
        self.metta = metta_instance

    def query_risk_profile(self, risk_profile):
        """Find investment types suitable for a risk profile."""
        risk_profile = risk_profile.strip('"')
        query_str = f'!(match &self (risk_profile {risk_profile} $investment) $investment)'
        results = self.metta.run(query_str)
        print(results, query_str)

        unique_investments = list(set(str(r[0]) for r in results if r and len(r) > 0)) if results else []
        return unique_investments

    def get_expected_return(self, investment):
        """Find expected returns for an investment type."""
        investment = investment.strip('"')
        query_str = f'!(match &self (expected_return {investment} $return) $return)'
        results = self.metta.run(query_str)
        print(results, query_str)
        return [r[0].get_object().value for r in results if r and len(r) > 0] if results else []

    def get_risk_level(self, investment):
        """Find risk level of an investment type."""
        investment = investment.strip('"')
        query_str = f'!(match &self (risk_level {investment} $risk) $risk)'
        results = self.metta.run(query_str)
        print(results, query_str)

        return [r[0].get_object().value for r in results if r and len(r) > 0] if results else []

    def get_age_allocation(self, age_group):
        """Get recommended asset allocation for age group."""
        age_group = age_group.strip('"')
        query_str = f'!(match &self (age_allocation {age_group} $allocation) $allocation)'
        results = self.metta.run(query_str)
        print(results, query_str)

        return [r[0].get_object().value for r in results if r and len(r) > 0] if results else []

    def get_goal_strategy(self, goal):
        """Get investment strategy for a specific goal."""
        goal = goal.strip('"')
        query_str = f'!(match &self (goal_strategy {goal} $strategy) $strategy)'
        results = self.metta.run(query_str)
        print(results, query_str)

        return [r[0].get_object().value for r in results if r and len(r) > 0] if results else []

    def query_sector_stocks(self, sector):
        """Get top performing stocks in a sector."""
        sector = sector.strip('"')
        query_str = f'!(match &self (sector_stocks {sector} $stocks) $stocks)'
        results = self.metta.run(query_str)
        print(results, query_str)

        return [r[0].get_object().value for r in results if r and len(r) > 0] if results else []

    def get_mistake_warning(self, mistake):
        """Get warning about common investment mistakes."""
        mistake = mistake.strip('"')
        query_str = f'!(match &self (mistake {mistake} $warning) $warning)'
        results = self.metta.run(query_str)
        print(results, query_str)

        return [r[0].get_object().value for r in results if r and len(r) > 0] if results else []

    def query_faq(self, question):
        """Retrieve investment FAQ answers."""
        query_str = f'!(match &self (faq "{question}" $answer) $answer)'
        results = self.metta.run(query_str)
        print(results, query_str)

        return results[0][0].get_object().value if results and results[0] else None

    def add_knowledge(self, relation_type, subject, object_value):
        """Add new investment knowledge dynamically."""
        if isinstance(object_value, str):
            object_value = ValueAtom(object_value)
        self.metta.space().add_atom(E(S(relation_type), S(subject), object_value))
        return f"Added {relation_type}: {subject} → {object_value}"