"""Matches API - sugestao, aceite e recusa de conexoes com IA.

A analise de compatibilidade vive em `app.services.ai` (Gemini + fallback
heuristico + cache). Aqui cuidamos apenas do ciclo de vida do match.
"""
import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.notificacoes import criar_notificacao
from app.core.database import get_db
from app.core.deps import exigir_profissional
from app.models.database import MatchDB, ProfissionalDB
from app.models.schemas import MatchCreate, MatchOut
from app.services import ai

router = APIRouter()


def _json_load(val: str) -> list:
    if not val:
        return []
    try:
        data = json.loads(val)
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


def _db_to_match(m: MatchDB) -> MatchOut:
    return MatchOut(
        id=m.id,
        profissional_a_id=m.profissional_a_id,
        profissional_b_id=m.profissional_b_id,
        status=m.status,
        score_ia=m.score_ia or 0.0,
        skills_match=_json_load(m.skills_match),
        motivo_ia=m.motivo_ia or "",
        forcas_ia=_json_load(m.forcas_ia),
        fonte_ia=m.fonte_ia or "heuristica",
        iniciado_por=m.iniciado_por,
        criado_em=m.criado_em,
        atualizado_em=m.atualizado_em,
    )


def _outro_lado(match: MatchDB, usuario_id: str) -> str:
    """Retorna o id do outro participante do match em relacao a `usuario_id`."""
    return (
        match.profissional_b_id
        if str(match.profissional_a_id) == str(usuario_id)
        else match.profissional_a_id
    )


@router.post("/api/matches", response_model=MatchOut, status_code=201)
async def sugerir_match(data: MatchCreate, db: Session = Depends(get_db)):
    """Sugerir um match entre dois profissionais com analise de IA."""
    if data.profissional_a_id == data.profissional_b_id:
        raise HTTPException(status_code=400, detail="Nao e possivel criar match com si mesmo")

    a = db.query(ProfissionalDB).filter(ProfissionalDB.id == data.profissional_a_id).first()
    b = db.query(ProfissionalDB).filter(ProfissionalDB.id == data.profissional_b_id).first()
    if not a or not b:
        raise HTTPException(status_code=404, detail="Profissional nao encontrado")

    existente = (
        db.query(MatchDB)
        .filter(
            (
                (MatchDB.profissional_a_id == data.profissional_a_id)
                & (MatchDB.profissional_b_id == data.profissional_b_id)
            )
            | (
                (MatchDB.profissional_a_id == data.profissional_b_id)
                & (MatchDB.profissional_b_id == data.profissional_a_id)
            )
        )
        .first()
    )
    if existente:
        return _db_to_match(existente)

    resultado = await ai.analisar_match(a, b)

    match = MatchDB(
        profissional_a_id=data.profissional_a_id,
        profissional_b_id=data.profissional_b_id,
        status="pendente",
        score_ia=resultado.score,
        skills_match=json.dumps(resultado.skills_complementares, ensure_ascii=False),
        motivo_ia=resultado.motivo,
        forcas_ia=json.dumps(resultado.forcas or [], ensure_ascii=False),
        fonte_ia=resultado.fonte,
        iniciado_por=data.profissional_a_id,
    )
    db.add(match)

    # Notificar o outro lado: "alguém quer se conectar com você"
    criar_notificacao(
        db,
        profissional_id=b.id,
        tipo="match_sugerido",
        titulo=f"{a.nome} quer se conectar com você",
        mensagem=resultado.motivo,
        link=f"#perfil-{a.id}",
    )

    db.commit()
    db.refresh(match)
    return _db_to_match(match)


@router.post("/api/matches/{match_id}/aceitar", response_model=MatchOut)
def aceitar_match(
    match_id: str,
    db: Session = Depends(get_db),
    atual: ProfissionalDB = Depends(exigir_profissional),
):
    """Aceitar um match pendente e atribuir pontos de reputacao."""
    match = db.query(MatchDB).filter(MatchDB.id == match_id).first()
    if not match:
        raise HTTPException(status_code=404, detail="Match nao encontrado")
    if str(atual.id) not in (str(match.profissional_a_id), str(match.profissional_b_id)):
        raise HTTPException(status_code=403, detail="Voce nao faz parte deste match")
    if match.status != "pendente":
        raise HTTPException(status_code=400, detail=f"Match ja esta '{match.status}'")

    match.status = "match"
    match.atualizado_em = datetime.now(timezone.utc)

    a = db.query(ProfissionalDB).filter(ProfissionalDB.id == match.profissional_a_id).first()
    b = db.query(ProfissionalDB).filter(ProfissionalDB.id == match.profissional_b_id).first()
    if a:
        a.score_contribuicao = (a.score_contribuicao or 0) + 10
    if b:
        b.score_contribuicao = (b.score_contribuicao or 0) + 10

    outro_id = _outro_lado(match, atual.id)
    criar_notificacao(
        db,
        profissional_id=outro_id,
        tipo="match_aceito",
        titulo="Conexao aceita! 🎉",
        mensagem=f"{atual.nome} aceitou sua conexao. Envie a primeira mensagem!",
        link="#conversas",
    )

    db.commit()
    db.refresh(match)
    return _db_to_match(match)


@router.post("/api/matches/{match_id}/recusar", response_model=MatchOut)
def recusar_match(
    match_id: str,
    db: Session = Depends(get_db),
    atual: ProfissionalDB = Depends(exigir_profissional),
):
    match = db.query(MatchDB).filter(MatchDB.id == match_id).first()
    if not match:
        raise HTTPException(status_code=404, detail="Match nao encontrado")
    if str(atual.id) not in (str(match.profissional_a_id), str(match.profissional_b_id)):
        raise HTTPException(status_code=403, detail="Voce nao faz parte deste match")
    if match.status != "pendente":
        raise HTTPException(status_code=400, detail=f"Match ja esta '{match.status}'")

    match.status = "recusado"
    match.atualizado_em = datetime.now(timezone.utc)
    db.commit()
    db.refresh(match)
    return _db_to_match(match)


@router.get("/api/profissionais/{profissional_id}/matches", response_model=list[MatchOut])
def listar_matches(
    profissional_id: str,
    status: str | None = None,
    db: Session = Depends(get_db),
):
    """Listar matches do profissional (opcionalmente filtrando por status)."""
    q = db.query(MatchDB).filter(
        (MatchDB.profissional_a_id == profissional_id)
        | (MatchDB.profissional_b_id == profissional_id)
    )
    if status:
        q = q.filter(MatchDB.status == status)

    matches = q.order_by(MatchDB.atualizado_em.desc()).all()
    return [_db_to_match(m) for m in matches]


@router.get("/api/matches/{match_id}/analise")
async def analise_match(match_id: str, db: Session = Depends(get_db)):
    """Reanalisa (ou detalha) a compatibilidade de um match existente."""
    match = db.query(MatchDB).filter(MatchDB.id == match_id).first()
    if not match:
        raise HTTPException(status_code=404, detail="Match nao encontrado")
    a = db.query(ProfissionalDB).filter(ProfissionalDB.id == match.profissional_a_id).first()
    b = db.query(ProfissionalDB).filter(ProfissionalDB.id == match.profissional_b_id).first()
    if not a or not b:
        raise HTTPException(status_code=404, detail="Profissional nao encontrado")

    resultado = await ai.analisar_match(a, b)
    return {
        "match_id": match_id,
        "score": resultado.score,
        "score_registrado": match.score_ia,
        "motivo": resultado.motivo,
        "forcas": resultado.forcas or [],
        "skills_complementares": resultado.skills_complementares,
        "fonte": resultado.fonte,
        "modo_ia": ai.ia_status(),
    }
