from pydantic import BaseModel
from datetime import datetime

class CardBase(BaseModel):
    uid: str
    authored_access: bool = False
    valid_from: datetime
    valid_to: datetime | None = None

class CardCreate(CardBase):
    pass

class CardUpdate(CardBase):
    pass

class Card(CardBase):
    id: int
    created_at: datetime

    class Config:
        from_attribute = True

class BaseMessage(BaseModel):
    action: str

class UIDMessage(BaseMessage):
    uid: str

class AuthResponse(BaseMessage):
    auth: bool
    barrier_open_sec: int

class BurnResponse(BaseMessage):
    burnSuccessful: bool
    uid: str | None = None

