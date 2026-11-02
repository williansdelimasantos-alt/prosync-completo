"""Migracoes incrementais leves (sem Alembic).

`create_all` nao adiciona colunas novas em tabelas que ja existem. Este modulo
faz ALTER TABLE idempotente para cada coluna que falta - roda no startup e e
barato. Funciona tanto em SQLite quanto em Postgres (DDL usado e o subconjunto
comum aos dois).

Para um projeto grande, o ideal e trocar isso por Alembic.
"""
from __future__ import annotations

import logging

from sqlalchemy import inspect, text

from app.core.config import settings
from app.core.database import engine

logger = logging.getLogger("prosync.migracoes")

# DDL de default por backend: Postgres aceita '' e TRUE/FALSE; SQLite aceita 0/1.
_PG = settings.database_backend == "postgresql"
_DEFAULT_TEXTO = "''"
_DEFAULT_BOOL_FALSE = "FALSE" if _PG else "0"
_DEFAULT_BOOL_TRUE = "TRUE" if _PG else "1"

# (tabela, coluna, DDL do tipo + default)
_COLUNAS_NOVAS: list[tuple[str, str, str]] = [
    # profissionais
    ("profissionais", "headline", f"VARCHAR(200) DEFAULT {_DEFAULT_TEXTO}"),
    ("profissionais", "github", f"VARCHAR(200) DEFAULT {_DEFAULT_TEXTO}"),
    ("profissionais", "linkedin", f"VARCHAR(200) DEFAULT {_DEFAULT_TEXTO}"),
    ("profissionais", "portfolio", f"VARCHAR(300) DEFAULT {_DEFAULT_TEXTO}"),
    ("profissionais", "onboarding_concluido", f"BOOLEAN DEFAULT {_DEFAULT_BOOL_FALSE}"),
    ("profissionais", "perfil_publico", f"BOOLEAN DEFAULT {_DEFAULT_BOOL_TRUE}"),
    # matches
    ("matches", "motivo_ia", f"TEXT DEFAULT {_DEFAULT_TEXTO}"),
    ("matches", "forcas_ia", "TEXT DEFAULT '[]'"),
    ("matches", "fonte_ia", f"VARCHAR(20) DEFAULT 'heuristica'"),
    ("matches", "iniciado_por", "VARCHAR(36)"),
]

# Tabelas que podem faltar em bancos antigos (create_all ja cria, mas garantimos
# que o inspector rode depois de create_all no init_db).
_INDICES_NOVOS: list[tuple[str, str, str]] = [
    ("ix_matches_status_par", "matches", "status, profissional_a_id"),
    ("ix_mensagens_match_data", "mensagens", "match_id, criado_em"),
]


def aplicar_migracoes() -> dict:
    """Aplica ALTER TABLE / CREATE INDEX que faltam. Retorna o que foi feito."""
    aplicado: dict[str, list[str]] = {"colunas": [], "indices": []}
    insp = inspect(engine)

    tabelas_existentes = set(insp.get_table_names())

    with engine.begin() as conn:
        for tabela, coluna, ddl in _COLUNAS_NOVAS:
            if tabela not in tabelas_existentes:
                continue
            colunas = {c["name"] for c in insp.get_columns(tabela)}
            if coluna in colunas:
                continue
            try:
                conn.execute(text(f'ALTER TABLE "{tabela}" ADD COLUMN "{coluna}" {ddl}'))
                aplicado["colunas"].append(f"{tabela}.{coluna}")
                logger.info("Coluna adicionada: %s.%s", tabela, coluna)
            except Exception as exc:  # pragma: no cover - defensivo
                logger.warning("Falha ao adicionar %s.%s: %s", tabela, coluna, exc)

        for nome_indice, tabela, colunas in _INDICES_NOVOS:
            if tabela not in tabelas_existentes:
                continue
            try:
                conn.execute(
                    text(f'CREATE INDEX IF NOT EXISTS "{nome_indice}" ON "{tabela}" ({colunas})')
                )
            except Exception as exc:  # pragma: no cover - defensivo
                logger.warning("Falha ao criar indice %s: %s", nome_indice, exc)

    return aplicado
