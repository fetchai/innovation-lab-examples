# schemas/schemas.py
from typing import List, Optional
from pydantic import BaseModel, Field, EmailStr

class Passenger(BaseModel):
    id: Optional[str] = None
    given_name: str
    family_name: str
    born_on: str   # format: YYYY-MM-DD
    gender: str    # e.g., "M", "F", "X"
    email: EmailStr
    phone_number: str

class OfferSummary(BaseModel):
    id: str
    airline: str
    total_amount: float
    total_currency: str
    total_amount_usdc: Optional[float] = None
    total_amount_fet: Optional[float] = None
    itinerary: str

class OrderSummary(BaseModel):
    id: str
    booking_reference: Optional[str]
    total_amount: float
    total_currency: str
    awaiting_payment: bool

class SessionState(BaseModel):
    origin: Optional[str] = None
    destination: Optional[str] = None
    date: Optional[str] = None
    pax: Optional[int] = None
    selected_offer_id: Optional[str] = None
    passenger: Optional[Passenger] = None
    services: Optional[List[dict]] = None            # Optional services like bags etc.
    payment_status: Optional[str] = None             # e.g., "requested", "completed"
    order_summary: Optional[OrderSummary] = None
    history: List[dict] = Field(default_factory=list) # full convo history or meta-history