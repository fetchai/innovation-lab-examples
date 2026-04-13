def acknowledgement_line(appliance_type: str) -> str:
    if not appliance_type:
        return "Thanks — working on your appliance issue."
    return f"Thanks — reviewing your **{appliance_type}** issue now."
