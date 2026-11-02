"""Database engine and session management."""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import settings

DATABASE_URL = settings.database_url

if DATABASE_URL.startswith("sqlite"):
    # SQLite exige check_same_thread=False (FastAPI usa threads); outros bancos nao aceitam.
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    # Postgres/MySQL: pool_pre_ping evita conexoes mortas apos idle (comum em PaaS).
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """FastAPI dependency that yields a DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create all tables and apply incremental migrations. Safe to call multiple times."""
    import app.models.database as models  # noqa: F401

    Base.metadata.create_all(bind=engine)

    from app.core.migracoes import aplicar_migracoes
    aplicar_migracoes()
