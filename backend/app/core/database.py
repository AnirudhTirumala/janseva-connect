from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import settings

# Render/Postgres URLs sometimes come as "postgres://" - SQLAlchemy needs "postgresql://"
db_url = settings.DATABASE_URL
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

def connect_args_for(url: str) -> dict:
    """Per-backend DBAPI connection arguments.

    A pure function so it can be tested without reloading this module -
    reloading would rebind Base and silently empty its metadata for every
    test that ran afterwards.
    """
    if url.startswith("sqlite"):
        # The app hands sessions to background threads (audit writes), which
        # SQLite otherwise refuses.
        return {"check_same_thread": False}
    if url.startswith("mysql"):
        # MySQL's DATETIME carries no time zone, so `server_default=func.now()`
        # records the session's LOCAL time even though the column is declared
        # timezone=True. Everything in the app compares against UTC (see
        # app/core/timeutils.py), so on a server set to, say, IST every
        # created_at would sit 5.5 hours off and the rolling 7/30-day dashboard
        # windows would quietly count the wrong rows. Pin the session to UTC.
        return {"init_command": "SET time_zone = '+00:00'"}
    return {}


connect_args = connect_args_for(db_url)

engine = create_engine(db_url, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """Dependency that provides a DB session per-request and closes it after."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
