import uuid


def new_correlation_id() -> str:
    return uuid.uuid4().hex
