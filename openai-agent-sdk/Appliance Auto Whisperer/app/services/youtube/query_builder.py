def build_query(appliance_type: str, symptoms: str) -> str:
    return f"{appliance_type} repair {symptoms}".strip()
