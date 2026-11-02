"""Oportunidades API — vagas, projetos e parcerias."""
import json
from fastapi import APIRouter, HTTPException, Query, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.database import OportunidadeDB, ProfissionalDB
from app.models.schemas import OportunidadeCreate, OportunidadeOut, OportunidadeStatusUpdate
from datetime import datetime, timezone

router = APIRouter()


def _json_load(val: str) -> list:
    if not val:
        return []
    try:
        return json.loads(val)
    except (json.JSONDecodeError, TypeError):
        return []


def _db_to_oportunidade(o: OportunidadeDB, db: Session) -> OportunidadeOut:
    criador = db.query(ProfissionalDB).filter(ProfissionalDB.id == o.criador_id).first()
    return OportunidadeOut(
        id=o.id,
        criador_id=o.criador_id,
        titulo=o.titulo,
        descricao=o.descricao or "",
        tipo=o.tipo or "vaga",
        skills_necessarias=_json_load(o.skills_necessarias),
        contato=o.contato or "",
        status=o.status or "aberta",
        criado_em=o.criado_em,
        criador_nome=criador.nome if criador else "",
        criador_foto=criador.foto_url or "" if criador else "",
    )


@router.post("/api/oportunidades", response_model=OportunidadeOut, status_code=201)
def criar_oportunidade(data: OportunidadeCreate, db: Session = Depends(get_db)):
    """Criar uma nova oportunidade (vaga, projeto ou parceria)."""
    criador = db.query(ProfissionalDB).filter(ProfissionalDB.id == data.criador_id).first()
    if not criador:
        raise HTTPException(status_code=404, detail="Criador não encontrado")

    if data.tipo not in ("vaga", "projeto", "parceria"):
        raise HTTPException(status_code=400, detail="Tipo inválido. Use: vaga, projeto ou parceria")

    oportunidade = OportunidadeDB(
        criador_id=data.criador_id,
        titulo=data.titulo,
        descricao=data.descricao,
        tipo=data.tipo,
        skills_necessarias=json.dumps(data.skills_necessarias, ensure_ascii=False),
        contato=data.contato,
        status="aberta",
    )
    db.add(oportunidade)

    # +5 pontos por criar oportunidade
    criador.score_contribuicao = (criador.score_contribuicao or 0) + 5

    db.commit()
    db.refresh(oportunidade)
    return _db_to_oportunidade(oportunidade, db)


@router.get("/api/oportunidades", response_model=list[OportunidadeOut])
def listar_oportunidades(
    tipo: str | None = Query(None),
    skill: str | None = Query(None),
    status: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """Listar oportunidades com filtros opcionais (tipo, skill, status)."""
    q = db.query(OportunidadeDB)
    if tipo:
        q = q.filter(OportunidadeDB.tipo == tipo)
    if status:
        q = q.filter(OportunidadeDB.status == status)
    if skill:
        q = q.filter(OportunidadeDB.skills_necessarias.ilike(f"%{skill}%"))

    oportunidades = q.order_by(OportunidadeDB.criado_em.desc()).offset(offset).limit(limit).all()
    return [_db_to_oportunidade(o, db) for o in oportunidades]


@router.get("/api/oportunidades/{oportunidade_id}", response_model=OportunidadeOut)
def obter_oportunidade(oportunidade_id: str, db: Session = Depends(get_db)):
    """Obter detalhes de uma oportunidade."""
    o = db.query(OportunidadeDB).filter(OportunidadeDB.id == oportunidade_id).first()
    if not o:
        raise HTTPException(status_code=404, detail="Oportunidade não encontrada")
    return _db_to_oportunidade(o, db)


@router.patch("/api/oportunidades/{oportunidade_id}/status", response_model=OportunidadeOut)
def atualizar_status_oportunidade(
    oportunidade_id: str,
    data: OportunidadeStatusUpdate,
    db: Session = Depends(get_db),
):
    """Atualizar status da oportunidade (aberta → preenchida)."""
    o = db.query(OportunidadeDB).filter(OportunidadeDB.id == oportunidade_id).first()
    if not o:
        raise HTTPException(status_code=404, detail="Oportunidade não encontrada")

    if o.status != "aberta" and data.status == "aberta":
        raise HTTPException(status_code=400, detail="Não é possível reabrir uma oportunidade fechada")
    if o.status == data.status:
        raise HTTPException(status_code=400, detail=f"Oportunidade já está '{data.status}'")

    transicoes = {"aberta": ["preenchida"], "preenchida": []}
    if data.status not in transicoes.get(o.status, []):
        raise HTTPException(
            status_code=400,
            detail=f"Não é possível mudar de '{o.status}' para '{data.status}'",
        )

    o.status = data.status
    db.commit()
    db.refresh(o)
    return _db_to_oportunidade(o, db)