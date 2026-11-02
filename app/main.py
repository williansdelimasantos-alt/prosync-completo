"""ProSync - FastAPI application entry point (v2)."""
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.core.database import init_db
from app.services.ai import ia_status

from app.api.health import router as health_router
from app.api.profissionais import router as prof_router
from app.api.matches import router as match_router
from app.api.desafios import router as desafio_router
from app.api.mensagens import router as mensagem_router
from app.api.mentorias import router as mentoria_router
from app.api.oportunidades import router as oportunidade_router
from app.api.discover import router as discover_router
from app.api.notificacoes import router as notificacao_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("prosync")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database tables (and run light migrations) on startup."""
    if settings.is_production:
        erros = settings.validar_producao()
        if erros:
            for erro in erros:
                logger.error("Configuracao invalida: %s", erro)
            raise RuntimeError(
                "Configuracao insegura em producao: " + " | ".join(erros)
            )

    init_db()
    status = ia_status()
    logger.info(
        "ProSync %s iniciado | IA: %s (%s) | banco: %s",
        settings.version,
        status["mode"],
        status["model"],
        settings.database_backend,
    )
    if settings.secret_key_padrao:
        logger.warning(
            "SECRET_KEY padrao em uso (aceitavel apenas em desenvolvimento)."
        )
    yield


app = FastAPI(
    title=f"{settings.app_name} API",
    description="Plataforma de conexao profissional para remotos brasileiros",
    version=settings.version,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    # Browsers recusam `Access-Control-Allow-Origin: *` com credentials; o
    # Starlette nao valida isso, entao desligamos credentials no modo wildcard.
    allow_credentials=not settings.cors_wildcard,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def erro_inesperado(request: Request, exc: Exception):  # pragma: no cover - defensivo
    """Nunca vazar stacktrace para o cliente: loga e devolve JSON amigavel."""
    logger.exception("Erro nao tratado em %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Erro interno. Tente novamente em instantes."},
    )


# Routers
app.include_router(health_router)
app.include_router(prof_router)
app.include_router(match_router)
app.include_router(desafio_router)
app.include_router(mensagem_router)
app.include_router(mentoria_router)
app.include_router(oportunidade_router)
app.include_router(discover_router)
app.include_router(notificacao_router)

# Static files (frontend)
_STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
app.mount("/", StaticFiles(directory=str(_STATIC_DIR), html=True), name="static")
