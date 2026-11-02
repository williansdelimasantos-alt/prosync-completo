"""Mensagens API — chat entre profissionais com match."""
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_
from app.core.database import get_db
from app.models.database import MensagemDB, MatchDB, ProfissionalDB
from app.models.schemas import MensagemCreate, MensagemOut, ConversaOut
from datetime import datetime, timezone

router = APIRouter()


@router.post("/api/mensagens", response_model=MensagemOut, status_code=201)
def enviar_mensagem(data: MensagemCreate, db: Session = Depends(get_db)):
    """Enviar mensagem em uma conversa (match precisa estar com status='match')."""
    # Validar match existe e está ativo
    match = db.query(MatchDB).filter(MatchDB.id == data.match_id).first()
    if not match:
        raise HTTPException(status_code=404, detail="Match não encontrado")
    if match.status != "match":
        raise HTTPException(
            status_code=400,
            detail=f"Não é possível enviar mensagem: match está '{match.status}'",
        )

    # Validar remetente faz parte do match
    if data.remetente_id not in (match.profissional_a_id, match.profissional_b_id):
        raise HTTPException(
            status_code=403,
            detail="Você não faz parte deste match",
        )

    # Validar remetente existe
    remetente = db.query(ProfissionalDB).filter(ProfissionalDB.id == data.remetente_id).first()
    if not remetente:
        raise HTTPException(status_code=404, detail="Remetente não encontrado")

    msg = MensagemDB(
        match_id=data.match_id,
        remetente_id=data.remetente_id,
        conteudo=data.conteudo,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return _db_to_mensagem(msg)


@router.get("/api/mensagens/{match_id}", response_model=list[MensagemOut])
def listar_mensagens(match_id: str, db: Session = Depends(get_db)):
    """Listar mensagens de uma conversa (ordenadas por data)."""
    match = db.query(MatchDB).filter(MatchDB.id == match_id).first()
    if not match:
        raise HTTPException(status_code=404, detail="Match não encontrado")

    mensagens = (
        db.query(MensagemDB)
        .filter(MensagemDB.match_id == match_id)
        .order_by(MensagemDB.criado_em.asc())
        .all()
    )
    return [_db_to_mensagem(m) for m in mensagens]


@router.patch("/api/mensagens/{mensagem_id}/ler", response_model=MensagemOut)
def marcar_como_lida(mensagem_id: str, db: Session = Depends(get_db)):
    """Marcar mensagem como lida."""
    msg = db.query(MensagemDB).filter(MensagemDB.id == mensagem_id).first()
    if not msg:
        raise HTTPException(status_code=404, detail="Mensagem não encontrada")

    msg.lida = True
    db.commit()
    db.refresh(msg)
    return _db_to_mensagem(msg)


@router.get("/api/profissionais/{profissional_id}/conversas", response_model=list[ConversaOut])
def listar_conversas(profissional_id: str, db: Session = Depends(get_db)):
    """Listar conversas ativas de um profissional (matches com última mensagem)."""
    profissional = db.query(ProfissionalDB).filter(ProfissionalDB.id == profissional_id).first()
    if not profissional:
        raise HTTPException(status_code=404, detail="Profissional não encontrado")

    # Buscar todos os matches com status 'match' ou 'pendente'
    matches = (
        db.query(MatchDB)
        .filter(
            or_(
                MatchDB.profissional_a_id == profissional_id,
                MatchDB.profissional_b_id == profissional_id,
            )
        )
        .order_by(MatchDB.atualizado_em.desc())
        .all()
    )

    resultado = []
    for match in matches:
        # Identificar o outro profissional
        outro_id = (
            match.profissional_b_id
            if match.profissional_a_id == profissional_id
            else match.profissional_a_id
        )
        outro = db.query(ProfissionalDB).filter(ProfissionalDB.id == outro_id).first()
        if not outro:
            continue

        # Última mensagem
        ultima = (
            db.query(MensagemDB)
            .filter(MensagemDB.match_id == match.id)
            .order_by(MensagemDB.criado_em.desc())
            .first()
        )

        # Contar não lidas (enviadas pelo outro profissional)
        nao_lidas = 0
        if match.status == "match":
            nao_lidas = (
                db.query(MensagemDB)
                .filter(
                    MensagemDB.match_id == match.id,
                    MensagemDB.remetente_id == outro_id,
                    MensagemDB.lida == False,
                )
                .count()
            )

        resultado.append(
            ConversaOut(
                match_id=match.id,
                match_status=match.status,
                score_ia=match.score_ia,
                profissional_id=outro.id,
                profissional_nome=outro.nome,
                profissional_foto=outro.foto_url or "",
                ultima_mensagem=ultima.conteudo if ultima else None,
                ultima_mensagem_em=ultima.criado_em if ultima else None,
                nao_lidas=nao_lidas,
            )
        )

    return resultado


def _db_to_mensagem(m: MensagemDB) -> MensagemOut:
    return MensagemOut(
        id=m.id,
        match_id=m.match_id,
        remetente_id=m.remetente_id,
        conteudo=m.conteudo,
        lida=m.lida,
        criado_em=m.criado_em,
    )