"""Dependencias de autenticacao (JWT) para os endpoints.

Modelo de seguranca da v2:
- Endpoints publicos (feed, descoberta, perfis publicos) continuam abertos.
- Acoes que "agem como" um profissional usam `usuario_atual`, que exige um
  Bearer token valido E verifica que o id do path/body pertence ao token.
- Endpoints de leitura privada usam `usuario_opcional` (permite x-profissional-id
  como fallback legado para nao quebrar o frontend antigo).
"""
from typing import Optional
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.database import ProfissionalDB


def _payload_do_header(authorization: Optional[str]) -> Optional[dict]:
    if not authorization:
        return None
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    return decode_access_token(parts[1])


def get_profissional_atual(
    authorization: Optional[str] = Header(default=None),
    x_profissional_id: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> Optional[ProfissionalDB]:
    """Retorna o profissional autenticado (token) ou None.

    Ordem de resolucao:
    1. Header `Authorization: Bearer <jwt>` (fonte da verdade).
    2. Header `X-Profissional-Id` (compatibilidade com o frontend v1).
    """
    payload = _payload_do_header(authorization)
    prof_id = payload.get("sub") if payload else None

    if not prof_id and x_profissional_id:
        prof_id = x_profissional_id

    if not prof_id:
        return None

    return db.query(ProfissionalDB).filter(ProfissionalDB.id == prof_id).first()


def exigir_profissional(
    atual: Optional[ProfissionalDB] = Depends(get_profissional_atual),
) -> ProfissionalDB:
    """Exige um profissional autenticado (401 se nao houver)."""
    if not atual:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Autenticacao necessaria",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return atual


def garantir_mesmo_usuario(profissional_id: str, atual: ProfissionalDB) -> None:
    """403 se o id pedido nao for do profissional autenticado."""
    if str(profissional_id) != str(atual.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Voce so pode agir em nome do seu proprio perfil",
        )
