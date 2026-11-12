
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# MySQL database details
DATABASE_URL = "mysql+pymysql://root:payalkanwar123@localhost:3306/supply_chain_db"

# Create database engine
engine = create_engine(DATABASE_URL)

# Create database session
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# Create base class
Base = declarative_base()

def get_db():
    db=SessionLocal()
    try:
        yield db

    finally:
        db.close()    