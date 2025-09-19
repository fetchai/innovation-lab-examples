from hyperon import MeTTa, E, S, ValueAtom

def initialize_investment_knowledge(metta: MeTTa):
    """Initialize the MeTTa knowledge graph with investment, risk, portfolio, and strategy data."""
    
    # Risk Profile → Investment Types
    metta.space().add_atom(E(S("risk_profile"), S("conservative"), S("bonds")))
    metta.space().add_atom(E(S("risk_profile"), S("conservative"), S("dividend_stocks")))
    metta.space().add_atom(E(S("risk_profile"), S("moderate"), S("index_funds")))
    metta.space().add_atom(E(S("risk_profile"), S("moderate"), S("etfs")))
    metta.space().add_atom(E(S("risk_profile"), S("aggressive"), S("growth_stocks")))
    metta.space().add_atom(E(S("risk_profile"), S("aggressive"), S("cryptocurrency")))
    metta.space().add_atom(E(S("risk_profile"), S("conservative"), S("savings_accounts")))
    metta.space().add_atom(E(S("risk_profile"), S("moderate"), S("real_estate")))
    metta.space().add_atom(E(S("risk_profile"), S("aggressive"), S("options")))
    
    # Investment Types → Expected Returns
    metta.space().add_atom(E(S("expected_return"), S("bonds"), ValueAtom("3-5% annually")))
    metta.space().add_atom(E(S("expected_return"), S("dividend_stocks"), ValueAtom("5-7% annually")))
    metta.space().add_atom(E(S("expected_return"), S("index_funds"), ValueAtom("6-10% annually")))
    metta.space().add_atom(E(S("expected_return"), S("etfs"), ValueAtom("5-12% annually")))
    metta.space().add_atom(E(S("expected_return"), S("growth_stocks"), ValueAtom("8-15% annually")))
    metta.space().add_atom(E(S("expected_return"), S("cryptocurrency"), ValueAtom("highly volatile, -50% to +200%")))
    metta.space().add_atom(E(S("expected_return"), S("savings_accounts"), ValueAtom("1-2% annually")))
    metta.space().add_atom(E(S("expected_return"), S("real_estate"), ValueAtom("4-8% annually")))
    metta.space().add_atom(E(S("expected_return"), S("options"), ValueAtom("high risk, unlimited gains/losses")))
    
    # Investment Types → Risk Levels
    metta.space().add_atom(E(S("risk_level"), S("bonds"), ValueAtom("low risk, stable income")))
    metta.space().add_atom(E(S("risk_level"), S("dividend_stocks"), ValueAtom("low-moderate risk, regular dividends")))
    metta.space().add_atom(E(S("risk_level"), S("index_funds"), ValueAtom("moderate risk, diversified")))
    metta.space().add_atom(E(S("risk_level"), S("etfs"), ValueAtom("low-moderate risk, liquid")))
    metta.space().add_atom(E(S("risk_level"), S("growth_stocks"), ValueAtom("high risk, growth potential")))
    metta.space().add_atom(E(S("risk_level"), S("cryptocurrency"), ValueAtom("very high risk, extreme volatility")))
    metta.space().add_atom(E(S("risk_level"), S("savings_accounts"), ValueAtom("no risk, FDIC insured")))
    metta.space().add_atom(E(S("risk_level"), S("real_estate"), ValueAtom("moderate risk, inflation hedge")))
    metta.space().add_atom(E(S("risk_level"), S("options"), ValueAtom("very high risk, leveraged exposure")))
    
    # Age Group → Recommended Asset Allocation
    metta.space().add_atom(E(S("age_allocation"), S("20s"), ValueAtom("80% stocks, 20% bonds")))
    metta.space().add_atom(E(S("age_allocation"), S("30s"), ValueAtom("70% stocks, 30% bonds")))
    metta.space().add_atom(E(S("age_allocation"), S("40s"), ValueAtom("60% stocks, 40% bonds")))
    metta.space().add_atom(E(S("age_allocation"), S("50s"), ValueAtom("50% stocks, 50% bonds")))
    metta.space().add_atom(E(S("age_allocation"), S("60s"), ValueAtom("40% stocks, 60% bonds")))
    
    # Investment Goals → Strategies
    metta.space().add_atom(E(S("goal_strategy"), S("retirement"), ValueAtom("diversified index funds, 401k maxing")))
    metta.space().add_atom(E(S("goal_strategy"), S("emergency_fund"), ValueAtom("high-yield savings, money market")))
    metta.space().add_atom(E(S("goal_strategy"), S("house_down_payment"), ValueAtom("CDs, short-term bonds")))
    metta.space().add_atom(E(S("goal_strategy"), S("wealth_building"), ValueAtom("growth stocks, REITs")))
    metta.space().add_atom(E(S("goal_strategy"), S("passive_income"), ValueAtom("dividend stocks, bonds")))
    
    # Market Sectors → Top Performers
    metta.space().add_atom(E(S("sector_stocks"), S("technology"), ValueAtom("Apple, Microsoft, Google")))
    metta.space().add_atom(E(S("sector_stocks"), S("healthcare"), ValueAtom("Johnson & Johnson, Pfizer")))
    metta.space().add_atom(E(S("sector_stocks"), S("finance"), ValueAtom("JPMorgan Chase, Berkshire Hathaway")))
    metta.space().add_atom(E(S("sector_stocks"), S("energy"), ValueAtom("ExxonMobil, Chevron")))
    
    # Common Investment Mistakes → Warnings
    metta.space().add_atom(E(S("mistake"), S("timing_market"), ValueAtom("avoid trying to time market peaks and valleys")))
    metta.space().add_atom(E(S("mistake"), S("lack_diversification"), ValueAtom("don't put all money in one stock or sector")))
    metta.space().add_atom(E(S("mistake"), S("emotional_trading"), ValueAtom("avoid panic selling or FOMO buying")))
    metta.space().add_atom(E(S("mistake"), S("high_fees"), ValueAtom("watch out for expensive mutual fund fees")))
    
    # Investment FAQs
    metta.space().add_atom(E(S("faq"), S("How much should I invest?"), ValueAtom("Invest 10-20% of income after emergency fund")))
    metta.space().add_atom(E(S("faq"), S("When should I start investing?"), ValueAtom("Start as early as possible for compound growth")))
    metta.space().add_atom(E(S("faq"), S("What is diversification?"), ValueAtom("Spreading investments across different assets to reduce risk")))
    metta.space().add_atom(E(S("faq"), S("Should I pay off debt first?"), ValueAtom("Pay off high-interest debt before investing")))