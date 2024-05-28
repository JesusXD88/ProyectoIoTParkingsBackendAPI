from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import urllib.parse
import os
from dotenv import load_dotenv,find_dotenv

load_dotenv(find_dotenv())

user = os.getenv("DATABASE_USER")
password = os.getenv("DATABASE_PASSWORD")
host = os.getenv("DATABASE_HOST")
port = os.getenv("DATABASE_PORT")
dbname = os.getenv("DATABASE_NAME")

encoded_password = urllib.parse.quote_plus(password)
DATABASE_URL = f"mysql+mysqlconnector://{user}:{encoded_password}@{host}:{port}/{dbname}"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()