"""Desafios API — completo com participantes e status."""
import json
from fastapi import APIRouter, HTTPException, Query, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.database import DesafioDB, ParticipanteDesafioDB, ProfissionalDB
from app.models.schemas import DesafioCreate, DesafioOut, DesafioStatusUpdate, ParticipanteDesafioOut
from datetime import datetime

router = APIRouter()


@router.post("/api/desafios", response_model=DesafioOut, status_code=201)
def criar_desafio(data: DesafioCreate, db: Session = Depends(get_db)):
    """Criar um novo desafio colaborativo."""
    prazo = None
    if data.prazo:
        try:
            prazo = datetime.fromisoformat(data.prazo)
        except ValueError:
            raise HTTPException(status_code=400, detail="Formato de prazo inválido. Use ISO datetime.")

    desafio = DesafioDB(
        criador_id=data.criador_id,
        titulo=data.titulo,
        descricao=data.descricao,
        skills_necessarias=json.dumps(data.skills_necessarias, ensure_ascii=False),
        tipo=data.tipo,
        prazo=prazo,
    )
    db.add(desafio)
    db.commit()
    db.refresh(desafio)
    return _db_to_desafio(desafio)


@router.get("/api/desafios", response_model=list[DesafioOut])
def listar_desafios(
    status: str | None = Query(None),
    tipo: str | None = Query(None),
    skill: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """Listar desafios com filtros opcionais (status, tipo, skill)."""
    q = db.query(DesafioDB)
    if status:
        q = q.filter(DesafioDB.status == status)
    if tipo:
        q = q.filter(DesafioDB.tipo == tipo)
    if skill:
        q = q.filter(DesafioDB.skills_necessarias.ilike(f"%{skill}%"))

    desafios = q.order_by(DesafioDB.criado_em.desc()).offset(offset).limit(limit).all()
    return [_db_to_desafio(d) for d in desafios]


@router.get("/api/desafios/{desafio_id}", response_model=DesafioOut)
def obter_desafio(desafio_id: str, db: Session = Depends(get_db)):
    """Obter detalhes de um desafio."""
    d = db.query(DesafioDB).filter(DesafioDB.id == desafio_id).first()
    if not d:
        raise HTTPException(status_code=404, detail="Desafio não encontrado")
    return _db_to_desafio(d)


@router.post("/api/desafios/{desafio_id}/participar", status_code=201)
def participar_desafio(desafio_id: str, profissional_id: str = Query(...), db: Session = Depends(get_db)):
    """Inscrever-se num desafio aberto."""
    desafio = db.query(DesafioDB).filter(DesafioDB.id == desafio_id).first()
    if not desafio:
        raise HTTPException(status_code=404, detail="Desafio não encontrado")

    if desafio.status != "aberto":
        raise HTTPException(status_code=400, detail="Desafio não está aberto para inscrições")

    profissional = db.query(ProfissionalDB).filter(ProfissionalDB.id == profissional_id).first()
    if not profissional:
        raise HTTPException(status_code=404, detail="Profissional não encontrado")

    # Verificar se já está inscrito
    existente = db.query(ParticipanteDesafioDB).filter(
        ParticipanteDesafioDB.desafio_id == desafio_id,
        ParticipanteDesafioDB.profissional_id == profissional_id,
    ).first()
    if existente:
        raise HTTPException(status_code=409, detail="Você já está inscrito neste desafio")

    participante = ParticipanteDesafioDB(
        desafio_id=desafio_id,
        profissional_id=profissional_id,
    )
    db.add(participante)

    # +15 pontos de reputação por participar
    profissional.score_contribuicao = (profissional.score_contribuicao or 0) + 15
    db.commit()

    return {"mensagem": "Inscrição realizada com sucesso", "desafio_id": desafio_id, "profissional_id": profissional_id}


@router.get("/api/desafios/{desafio_id}/participantes", response_model=list[ParticipanteDesafioOut])
def listar_participantes(desafio_id: str, db: Session = Depends(get_db)):
    """Listar participantes de um desafio."""
    desafio = db.query(DesafioDB).filter(DesafioDB.id == desafio_id).first()
    if not desafio:
        raise HTTPException(status_code=404, detail="Desafio não encontrado")

    participantes = db.query(ParticipanteDesafioDB).filter(
        ParticipanteDesafioDB.desafio_id == desafio_id
    ).all()

    resultado = []
    for p in participantes:
        prof = db.query(ProfissionalDB).filter(ProfissionalDB.id == p.profissional_id).first()
        resultado.append(ParticipanteDesafioOut(
            id=p.id,
            desafio_id=p.desafio_id,
            profissional_id=p.profissional_id,
            profissional_nome=prof.nome if prof else "",
            profissional_foto=prof.foto_url or "" if prof else "",
            criado_em=p.criado_em,
        ))

    return resultado


@router.patch("/api/desafios/{desafio_id}/status", response_model=DesafioOut)
def atualizar_status_desafio(
    desafio_id: str,
    data: DesafioStatusUpdate,
    db: Session = Depends(get_db),
):
    """Atualizar status do desafio (aberto → em_andamento → concluido)."""
    desafio = db.query(DesafioDB).filter(DesafioDB.id == desafio_id).first()
    if not desafio:
        raise HTTPException(status_code=404, detail="Desafio não encontrado")

    # Validar transição de status
    transicoes_validas = {
        "aberto": ["em_andamento"],
        "em_andamento": ["concluido"],
        "concluido": [],
    }
    if data.status not in transicoes_validas.get(desafio.status, []):
        raise HTTPException(
            status_code=400,
            detail=f"Não é possível mudar de '{desafio.status}' para '{data.status}'",
        )

    desafio.status = data.status
    db.commit()
    db.refresh(desafio)
    return _db_to_desafio(desafio)


def _db_to_desafio(d: DesafioDB) -> DesafioOut:
    return DesafioOut(
        id=d.id,
        criador_id=d.criador_id,
        titulo=d.titulo,
        descricao=d.descricao or "",
        skills_necessarias=_json_load(d.skills_necessarias),
        tipo=d.tipo or "dupla",
        status=d.status or "aberto",
        prazo=d.prazo,
        criado_em=d.criado_em,
    )


def _json_load(val: str) -> list:
    if not val:
        return []
    try:
        return json.loads(val)
    except (json.JSONDecodeError, TypeError):
        return []