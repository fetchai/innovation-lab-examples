def build_parts_query(appliance_type: str, part_name: str) -> str:
    return f"{appliance_type} {part_name} buy site:repairclinic.com OR site:amazon.com"
