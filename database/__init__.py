from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from google.cloud.sql.connector import Connector
import os
from dotenv import load_dotenv,find_dotenv

load_dotenv(find_dotenv())

user = os.getenv("DATABASE_USER")
password = os.getenv("DATABASE_PASSWORD")
dbname = os.getenv("DATABASE_NAME")
instance_connection_name = os.getenv("DATABASE_INSTANCE_CONNECTION_NAME")

connector = Connector()


def get_connection():
    conn = connector.connect(
        instance_connection_name,
        "pymysql",
        user=user,
        password=password,
        db=dbname
    )
    return conn


engine = create_engine("mysql+pymysql://", creator=get_connection)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()