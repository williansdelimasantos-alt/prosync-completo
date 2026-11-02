"""Configuracao central da aplicacao (lida de variaveis de ambiente).

Todas as settings tem defaults seguros para desenvolvimento local, de forma
que `python -m uvicorn app.main:app` funcione sem nenhum .env. Em producao
basta definir as variaveis de ambiente (ver .env.example).
"""
import os


def _bool(name: str, default: bool = False) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, "").strip() or default)
    except ValueError:
        return default


def _normalizar_url(url: str) -> str:
    """PaaS (Heroku/Railway/Render) as vezes entrega `postgres://`, que o SQLAlchemy 2 rejeita."""
    url = url.strip()
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql://", 1)
    return url


class Settings:
    """Settings tipadas (instanciadas uma unica vez em `settings`)."""

    # --- Identidade / versao ---------------------------------------------
    app_name: str = "ProSync"
    version: str = "2.0.0"

    # --- Banco ------------------------------------------------------------
    database_url: str = _normalizar_url(
        os.getenv("DATABASE_URL", "sqlite:///./prosync.db")
    )
    # Apenas usados quando o banco nao e SQLite.
    db_pool_size: int = _int("DB_POOL_SIZE", 5)
    db_max_overflow: int = _int("DB_MAX_OVERFLOW", 10)

    # --- Seguranca --------------------------------------------------------
    secret_key: str = os.getenv("SECRET_KEY", "prosync-dev-secret-key-change-in-prod")
    algorithm: str = "HS256"
    access_token_expire_minutes: int = _int("ACCESS_TOKEN_EXPIRE_MINUTES", 60 * 24)

    # --- CORS -------------------------------------------------------------
    # Em dev liberamos tudo; em prod defina CORS_ORIGINS com lista separada por virgula.
    # Chave publica: http://localhost:5173,https://app.prosync.com.br
    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",") if o.strip()]

    @property
    def cors_wildcard(self) -> bool:
        """True quando CORS aceita qualquer origem (`*`)."""
        return "*" in self.cors_origins

    # --- IA (Gemini) ------------------------------------------------------
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "").strip()
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-2.0-flash").strip()
    gemini_timeout: float = float(os.getenv("GEMINI_TIMEOUT", "12") or 12)
    # Quando False, a IA nunca e chamada (util em testes / ambientes offline).
    ai_enabled: bool = _bool("AI_ENABLED", True)

    @property
    def gemini_configured(self) -> bool:
        return bool(self.gemini_api_key)

    @property
    def is_production(self) -> bool:
        return _bool("PRODUCTION", False)

    @property
    def database_backend(self) -> str:
        """Nome amigavel do banco (para logs e /api/health)."""
        url = self.database_url
        if url.startswith("sqlite"):
            return "sqlite"
        if url.startswith("postgresql"):
            return "postgresql"
        return url.split(":", 1)[0] or "desconhecido"

    @property
    def secret_key_padrao(self) -> bool:
        """True quando a SECRET_KEY ainda e a de desenvolvimento."""
        return self.secret_key.startswith("prosync-dev-secret")

    def validar_producao(self) -> list[str]:
        """Retorna erros de configuracao que impedem subir em producao.

        Lista vazia significa configuracao aceitavel. Chamado no startup da app.
        """
        erros: list[str] = []
        if self.secret_key_padrao or len(self.secret_key) < 32:
            erros.append(
                "SECRET_KEY insegura: defina uma chave aleatoria com 32+ caracteres "
                "(ex.: python -c \"import secrets; print(secrets.token_urlsafe(48))\")"
            )
        if self.cors_wildcard:
            erros.append(
                "CORS_ORIGINS com `*` em producao: liste as origens permitidas "
                "(ex.: https://app.prosync.com.br)"
            )
        return erros


settings = Settings()
