from enum import Enum

class Step(Enum):
    DESCRIBE_DATA_TO_DELETE = "describe_data_to_delete"
    CONFIRM_DELETE = "confirm_delete"
    COMPLETE = "complete"