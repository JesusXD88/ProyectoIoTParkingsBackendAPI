from sqlalchemy import Column, Integer, String, Boolean, TIMESTAMP
from models import Base

class Card(Base):
    __tablename__ = "cards"

    id = Column(Integer, primary_key=True, index=True)
    uid = Column(String, unique=True, index=True)
    authored_access = Column(Boolean, default=False)
    valid_from = Column(TIMESTAMP, default="CURRENT_TIMESTAMP")
    valid_until = Column(TIMESTAMP)
    created_at = Column(TIMESTAMP, default="CURRENT_TIMESTAMP")