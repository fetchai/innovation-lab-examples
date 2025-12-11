from pydantic import BaseModel, Field
from datetime import datetime

class ChromaDocument(BaseModel):
    id: str = Field(..., description="Unique identifier for the document")
    asi_one_id: str = Field(..., description="The owner of the document")
    document: str = Field(..., description="The contents of the document")
    source: str = Field(default="unknown", description="Where the fact came from")
    time_logged: datetime = Field(default_factory=lambda: datetime.now().astimezone(), description="Timestamp when the document was logged")

