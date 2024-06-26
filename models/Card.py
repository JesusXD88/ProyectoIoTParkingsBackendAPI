from sqlalchemy import Column, Integer, String, Boolean, DateTime, func
from models import Base


class Card(Base):
    __tablename__ = "cards"

    id = Column(Integer, primary_key=True, index=True)
    uid = Column(String, unique=True, index=True)
    authored_access = Column(Boolean, default=False)
    valid_from = Column(DateTime, default=func.now())
    valid_to = Column(DateTime)
    created_at = Column(DateTime, default=func.now())