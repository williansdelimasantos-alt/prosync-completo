"""Notificacoes in-app."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import exigir_profissional
from app.models.database import NotificacaoDB, ProfissionalDB
from app.models.schemas_v2 import NotificacaoOut, NotificacoesResumoOut

router = APIRouter()


def criar_notificacao(
    db: Session,
    profissional_id: str,
    tipo: str,
    titulo: str,
    mensagem: str = "",
    link: str = "",
) -> NotificacaoDB:
    """Helper para outros routers criarem notificacoes."""
    n = NotificacaoDB(
        profissional_id=profissional_id,
        tipo=tipo,
        titulo=titulo[:200],
        mensagem=mensagem,
        link=link[:300],
    )
    db.add(n)
    return n


@router.get("/api/notificacoes", response_model=NotificacoesResumoOut)
def listar_notificacoes(
    profissional_id: str = Query(...),
    apenas_nao_lidas: bool = Query(False),
    limit: int = Query(30, ge=1, le=100),
    db: Session = Depends(get_db),
    atual: ProfissionalDB = Depends(exigir_profissional),
):
    if str(atual.id) != profissional_id:
        raise HTTPException(status_code=403, detail="Você só pode ver suas próprias notificações")

    q = db.query(NotificacaoDB).filter(NotificacaoDB.profissional_id == profissional_id)
    if apenas_nao_lidas:
        q = q.filter(NotificacaoDB.lida == False)  # noqa: E712

    itens = q.order_by(NotificacaoDB.criado_em.desc()).limit(limit).all()
    nao_lidas = (
        db.query(NotificacaoDB)
        .filter(NotificacaoDB.profissional_id == profissional_id, NotificacaoDB.lida == False)  # noqa: E712
        .count()
    )
    return NotificacoesResumoOut(
        nao_lidas=nao_lidas,
        itens=[NotificacaoOut.model_validate(n, from_attributes=True) for n in itens],
    )


@router.patch("/api/notificacoes/{notificacao_id}/lida", response_model=NotificacaoOut)
def marcar_lida(
    notificacao_id: str,
    db: Session = Depends(get_db),
    atual: ProfissionalDB = Depends(exigir_profissional),
):
    n = db.query(NotificacaoDB).filter(NotificacaoDB.id == notificacao_id).first()
    if not n:
        raise HTTPException(status_code=404, detail="Notificação não encontrada")
    if str(n.profissional_id) != str(atual.id):
        raise HTTPException(status_code=403, detail="Notificação de outro usuário")
    n.lida = True
    db.commit()
    db.refresh(n)
    return NotificacaoOut.model_validate(n, from_attributes=True)


@router.post("/api/notificacoes/marcar-todas-lidas")
def marcar_todas_lidas(
    profissional_id: str = Query(...),
    db: Session = Depends(get_db),
    atual: ProfissionalDB = Depends(exigir_profissional),
):
    if str(atual.id) != profissional_id:
        raise HTTPException(status_code=403, detail="Você só pode alterar suas próprias notificações")
    atualizadas = (
        db.query(NotificacaoDB)
        .filter(NotificacaoDB.profissional_id == profissional_id, NotificacaoDB.lida == False)  # noqa: E712
        .update({NotificacaoDB.lida: True})
    )
    db.commit()
    return {"atualizadas": atualizadas}
