from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from db_config import get_database_url

engine = create_engine(get_database_url(), echo=True)
Session = sessionmaker(bind=engine)


class Base(DeclarativeBase):
    pass
