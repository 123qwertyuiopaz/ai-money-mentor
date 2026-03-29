import os
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from app.config import get_settings

settings = get_settings()

# Ensure the data directory exists
os.makedirs("data", exist_ok=True)

# SQLite engine with WAL mode for better concurrent reads
engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False},
    echo=settings.debug,
)

# Enable WAL journal mode for SQLite performance
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, _):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI dependency: yields a SQLAlchemy session and ensures cleanup."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create all tables. Called once at startup."""
    from app.database import models  # noqa: F401 — ensures models are registered
    Base.metadata.create_all(bind=engine)
