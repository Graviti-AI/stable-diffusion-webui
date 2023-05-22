from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

SQLALCHEMY_DATABASE_URL = "mysql+mysqldb://root:gwood!nHo13@139.224.188.56:3306/sd_webui_be_dev"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={
    },
    pool_pre_ping=True,
    pool_recycle=3600
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.commit()
        db.close()
