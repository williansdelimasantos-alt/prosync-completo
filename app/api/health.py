"""Health check endpoint."""
from fastapi import APIRouter
from sqlalchemy import text

from app.core.config import settings
from app.core.database import engine
from app.services.ai import ia_status

router = APIRouter()


@router.get("/api/health")
def health():
    return {
        "status": "ok",
        "service": "prosync",
        "version": settings.version,
    }


@router.get("/api/health/detalhado")
def health_detalhado():
    """Diagnostico completo (usado por scripts/health_check.py e monitoracao)."""
    db_ok = True
    db_erro = ""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:  # pragma: no cover - defensivo
        db_ok = False
        db_erro = str(exc)

    return {
        "status": "ok" if db_ok else "degradado",
        "service": "prosync",
        "version": settings.version,
        "database": {"ok": db_ok, "backend": settings.database_backend, "erro": db_erro},
        "ia": ia_status(),
        "producao": settings.is_production,
    }
