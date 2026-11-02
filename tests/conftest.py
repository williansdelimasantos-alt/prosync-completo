"""Pytest configuration — overrides database to a temp SQLite file.

This MUST be imported before any app module that creates the engine.
"""
import os
import tempfile

# Create a temporary database file
_db_fd, _db_path = tempfile.mkstemp(suffix=".db")
os.environ["DATABASE_URL"] = f"sqlite:///{_db_path}"

import sys
from pathlib import Path

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

import json
import random
from datetime import datetime, timezone
from typing import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

# Now safe to import app modules — DATABASE_URL is set
from app.core.database import Base, engine, SessionLocal
from app.core.security import hash_password
from app.models.database import ProfissionalDB
from app.main import app

# Override the startup event — we manage tables ourselves
app.router.on_startup.clear()


@pytest.fixture(autouse=True)
def _setup_db():
    """Create all tables before each test; drop after."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client() -> TestClient:
    """FastAPI TestClient fixture."""
    return TestClient(app)


@pytest.fixture
def db_session() -> Session:
    """Direct SQLAlchemy session for test setup / assertions."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def auth_headers() -> callable:
    """Gera headers Authorization: Bearer <jwt> para um profissional."""
    from app.core.security import create_access_token

    def _make(profissional_id: str) -> dict:
        token = create_access_token({"sub": str(profissional_id)})
        return {"Authorization": f"Bearer {token}"}

    return _make


@pytest.fixture
def criar_profissional(db_session: Session) -> callable:
    """Factory fixture to create professionals quickly."""

    def _make(**kwargs) -> ProfissionalDB:
        data = {
            "nome": "Teste",
            "email": f"teste{random.randint(100000,999999)}@teste.com",
            "senha_hash": hash_password("senha123"),
            "foto_url": "",
            "bio": "",
            "cidade": "São Paulo",
            "estado": "SP",
            "skills": json.dumps(["Python"]),
            "objetivos": json.dumps(["colaborar"]),
            "senioridade": "junior",
            "disponibilidade": json.dumps([]),
            "areas_interesse": json.dumps([]),
            "score_contribuicao": 0,
        }
        data.update(kwargs)
        p = ProfissionalDB(**data)
        db_session.add(p)
        db_session.commit()
        db_session.refresh(p)
        return p

    return _make