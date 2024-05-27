from sqlalchemy.orm import Session
from ..models import Card as models
from ..schemas import Card as schemas

def get_card_by_uid(db: Session, uid: str):
    return db.query(models.Card).filter(models.Card.uid == uid).first()

def create_card(db: Session, card: schemas.CardCreate):
    db_card = models.Card(
        uid=card.uid,
        authored_access=card.authored_access,
        valid_from=card.valid_from,
        valid_to=card.valid_to
    )
    db.add(db_card)
    db.commit()
    db.refresh(db_card)
    return db_card