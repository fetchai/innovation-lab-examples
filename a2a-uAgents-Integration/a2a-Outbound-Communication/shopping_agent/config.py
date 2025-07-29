from typing import List
from uagents_adapter import A2AAgentConfig

# Shopping Agent configuration
def get_shopping_agent_config() -> List[A2AAgentConfig]:
    return [
        A2AAgentConfig(
            name="shopping_partner", # This name must match the key in main.py's executors dict
            description="AI Shopping Agent for finding laptops and recommending products on trusted e-commerce platforms",
            url="http://localhost:10020",
            port=10020,
            specialties=["e-commerce", "product search", "laptop recommendations", "budget shopping"],
            priority=3
        )
    ]
