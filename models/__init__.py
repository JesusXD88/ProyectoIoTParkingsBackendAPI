from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

from .User import User
from .Card import Card