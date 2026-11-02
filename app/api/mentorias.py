"""Mentoria API — solicitar, aceitar, concluir mentorias com reputação."""
from fastapi import APIRouter, HTTPException, Query, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.database import MentoriaDB, ProfissionalDB
from app.models.schemas import MentoriaCreate, MentoriaOut
from datetime import datetime, timezone

router = APIRouter()


def _db_to_mentoria(m: MentoriaDB, db: Session) -> MentoriaOut:
    mentor = db.query(ProfissionalDB).filter(ProfissionalDB.id == m.mentor_id).first()
    mentorado = db.query(ProfissionalDB).filter(ProfissionalDB.id == m.mentorado_id).first()
    return MentoriaOut(
        id=m.id,
        mentor_id=m.mentor_id,
        mentorado_id=m.mentorado_id,
        area=m.area or "",
        objetivos=m.objetivos or "",
        status=m.status or "pendente",
        criado_em=m.criado_em,
        concluido_em=m.concluido_em,
        mentor_nome=mentor.nome if mentor else "",
        mentor_foto=mentor.foto_url or "" if mentor else "",
        mentorado_nome=mentorado.nome if mentorado else "",
        mentorado_foto=mentorado.foto_url or "" if mentorado else "",
    )


@router.post("/api/mentorias/solicitar", response_model=MentoriaOut, status_code=201)
def solicitar_mentoria(data: MentoriaCreate, db: Session = Depends(get_db)):
    """Solicitar mentoria — mentorado solicita a um mentor."""
    if data.mentorado_id == data.mentor_id:
        raise HTTPException(status_code=400, detail="Você não pode ser mentor de si mesmo")

    mentor = db.query(ProfissionalDB).filter(ProfissionalDB.id == data.mentor_id).first()
    if not mentor:
        raise HTTPException(status_code=404, detail="Mentor não encontrado")

    mentorado = db.query(ProfissionalDB).filter(ProfissionalDB.id == data.mentorado_id).first()
    if not mentorado:
        raise HTTPException(status_code=404, detail="Mentorado não encontrado")

    # Verificar se já existe solicitação pendente
    existente = db.query(MentoriaDB).filter(
        MentoriaDB.mentor_id == data.mentor_id,
        MentoriaDB.mentorado_id == data.mentorado_id,
        MentoriaDB.status == "pendente",
    ).first()
    if existente:
        raise HTTPException(status_code=409, detail="Já existe uma solicitação de mentoria pendente")

    mentoria = MentoriaDB(
        mentor_id=data.mentor_id,
        mentorado_id=data.mentorado_id,
        area=data.area,
        objetivos=data.objetivos,
        status="pendente",
    )
    db.add(mentoria)
    db.commit()
    db.refresh(mentoria)
    return _db_to_mentoria(mentoria, db)


@router.get("/api/mentorias", response_model=list[MentoriaOut])
def listar_mentorias(
    profissional_id: str = Query(...),
    status: str | None = Query(None),
    db: Session = Depends(get_db),
):
    """Listar mentorias do profissional logado (como mentor ou mentorado)."""
    q = db.query(MentoriaDB).filter(
        (MentoriaDB.mentor_id == profissional_id) | (MentoriaDB.mentorado_id == profissional_id)
    )
    if status:
        q = q.filter(MentoriaDB.status == status)

    mentorias = q.order_by(MentoriaDB.criado_em.desc()).all()
    return [_db_to_mentoria(m, db) for m in mentorias]


@router.patch("/api/mentorias/{mentoria_id}/aceitar", response_model=MentoriaOut)
def aceitar_mentoria(mentoria_id: str, db: Session = Depends(get_db)):
    """Mentor aceita a solicitação de mentoria."""
    mentoria = db.query(MentoriaDB).filter(MentoriaDB.id == mentoria_id).first()
    if not mentoria:
        raise HTTPException(status_code=404, detail="Mentoria não encontrada")
    if mentoria.status != "pendente":
        raise HTTPException(status_code=400, detail=f"Mentoria já está '{mentoria.status}'")

    mentoria.status = "ativa"
    db.commit()
    db.refresh(mentoria)
    return _db_to_mentoria(mentoria, db)


@router.patch("/api/mentorias/{mentoria_id}/concluir", response_model=MentoriaOut)
def concluir_mentoria(mentoria_id: str, db: Session = Depends(get_db)):
    """Marcar mentoria como concluída e atribuir pontos de reputação."""
    mentoria = db.query(MentoriaDB).filter(MentoriaDB.id == mentoria_id).first()
    if not mentoria:
        raise HTTPException(status_code=404, detail="Mentoria não encontrada")
    if mentoria.status != "ativa":
        raise HTTPException(status_code=400, detail=f"Mentoria não está ativa (status: '{mentoria.status}')")

    mentoria.status = "concluida"
    mentoria.concluido_em = datetime.now(timezone.utc)

    # Atribuir pontos de reputação
    mentor = db.query(ProfissionalDB).filter(ProfissionalDB.id == mentoria.mentor_id).first()
    mentorado = db.query(ProfissionalDB).filter(ProfissionalDB.id == mentoria.mentorado_id).first()
    if mentor:
        mentor.score_contribuicao = (mentor.score_contribuicao or 0) + 25
    if mentorado:
        mentorado.score_contribuicao = (mentorado.score_contribuicao or 0) + 10

    db.commit()
    db.refresh(mentoria)
    return _db_to_mentoria(mentoria, db)