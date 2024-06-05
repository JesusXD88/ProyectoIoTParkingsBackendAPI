from typing import Optional
from sqlalchemy.orm import Session
from models import Card
from schemas import CardCreate
from datetime import datetime

def get_card_by_uid(db: Session, uid: str):
    return db.query(Card).filter(Card.uid == uid).execution_options(populate_existing=True).first()

def get_cards(db: Session, skip: int = 0, limit: int = 100):
    return db.query(Card).offset(skip).limit(limit).all()

def create_card(db: Session, card: CardCreate):
    db_card = Card(
        uid=card.uid,
        authored_access=card.authored_access,
        valid_from=card.valid_from,
        valid_to=card.valid_to
    )
    db.add(db_card)
    db.commit()
    db.refresh(db_card)
    return db_card

def update_card(db: Session, uid: str, authored_access: bool, valid_from: datetime, valid_to: Optional[datetime]):
    card = get_card_by_uid(db, uid)
    if card:
        card.authored_access = authored_access
        card.valid_from = valid_from
        card.valid_to = valid_to
        db.commit()
        db.refresh(card)
        return card
    return None

def delete_card(db: Session, card: Card):
    db.delete(card)
    db.commit()
    return card