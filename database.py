from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

Base = declarative_base()
_engines = {}


def init_db(db_path):
    engine = create_engine(f"sqlite:///{db_path}")
    _engines[db_path] = engine
    Base.metadata.create_all(engine)
    return engine


def get_session(db_path):
    engine = _engines.get(db_path)
    if not engine:
        engine = init_db(db_path)
    Session = sessionmaker(bind=engine)
    return Session()
