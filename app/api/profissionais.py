"""Profissionais CRUD API."""
import json
from fastapi import APIRouter, HTTPException, Query, Depends
from sqlalchemy.orm import Session
from sqlalchemy import or_
from app.core.database import get_db
from app.core.config import settings
from app.core.deps import exigir_profissional, garantir_mesmo_usuario
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    token_expira_em,
)
from app.models.database import ProfissionalDB, NotificacaoDB
from app.models.schemas import (
    ProfissionalCreate,
    ProfissionalUpdate,
    ProfissionalOut,
    ProfissionalCard,
    LoginRequest,
    TokenOut,
    ReputacaoOut,
)
from datetime import datetime, timezone

router = APIRouter()


def _json_load(val: str) -> list:
    """Safely parse a JSON string column."""
    if not val:
        return []
    try:
        return json.loads(val)
    except (json.JSONDecodeError, TypeError):
        return []


def _db_to_out(p: ProfissionalDB) -> ProfissionalOut:
    return ProfissionalOut(
        id=p.id,
        nome=p.nome,
        email=p.email,
        foto_url=p.foto_url or "",
        bio=p.bio or "",
        headline=p.headline or "",
        cidade=p.cidade or "",
        estado=p.estado or "",
        skills=_json_load(p.skills),
        objetivos=_json_load(p.objetivos),
        senioridade=p.senioridade or "junior",
        disponibilidade=_json_load(p.disponibilidade),
        areas_interesse=_json_load(p.areas_interesse),
        github=p.github or "",
        linkedin=p.linkedin or "",
        portfolio=p.portfolio or "",
        onboarding_concluido=bool(p.onboarding_concluido),
        perfil_publico=bool(p.perfil_publico) if p.perfil_publico is not None else True,
        score_contribuicao=p.score_contribuicao or 0,
        criado_em=p.criado_em,
        ultimo_acesso=p.ultimo_acesso,
    )


def _db_to_card(p: ProfissionalDB) -> ProfissionalCard:
    return ProfissionalCard(
        id=p.id,
        nome=p.nome,
        foto_url=p.foto_url or "",
        bio=p.bio or "",
        headline=p.headline or "",
        cidade=p.cidade or "",
        estado=p.estado or "",
        skills=_json_load(p.skills),
        senioridade=p.senioridade or "junior",
        objetivos=_json_load(p.objetivos),
        areas_interesse=_json_load(p.areas_interesse),
        score_contribuicao=p.score_contribuicao or 0,
    )


@router.post("/api/profissionais", response_model=ProfissionalOut, status_code=201)
def criar_profissional(data: ProfissionalCreate, db: Session = Depends(get_db)):
    """Cadastrar novo profissional."""
    email = data.email.strip().lower()
    existing = db.query(ProfissionalDB).filter(ProfissionalDB.email == email).first()
    if existing:
        raise HTTPException(status_code=409, detail="Email já cadastrado")

    profissional = ProfissionalDB(
        nome=data.nome.strip(),
        email=data.email.strip().lower(),
        senha_hash=hash_password(data.senha),
        foto_url=data.foto_url,
        bio=data.bio,
        headline=data.headline[:200],
        cidade=data.cidade,
        estado=data.estado,
        skills=json.dumps(data.skills, ensure_ascii=False),
        objetivos=json.dumps(data.objetivos, ensure_ascii=False),
        senioridade=data.senioridade,
        disponibilidade=json.dumps(data.disponibilidade, ensure_ascii=False),
        areas_interesse=json.dumps(data.areas_interesse, ensure_ascii=False),
        github=data.github,
        linkedin=data.linkedin,
        portfolio=data.portfolio,
    )
    db.add(profissional)
    db.flush()

    db.add(
        NotificacaoDB(
            profissional_id=profissional.id,
            tipo="boas_vindas",
            titulo="Bem-vindo(a) a ProSync! 🎉",
            mensagem=(
                "Complete seu perfil para receber melhores sugestoes de conexao "
                "e comece explorando o feed inteligente."
            ),
            link="#dashboard",
        )
    )
    db.commit()
    db.refresh(profissional)
    return _db_to_out(profissional)


@router.get("/api/auth/me", response_model=ProfissionalOut)
@router.get("/api/profissionais/me", response_model=ProfissionalOut, include_in_schema=False)
def profissional_autenticado(
    atual: ProfissionalDB = Depends(exigir_profissional),
):
    """Perfil do profissional dono do token (usado para reidratar a sessao)."""
    return _db_to_out(atual)


@router.get("/api/profissionais", response_model=list[ProfissionalCard])
def listar_profissionais(
    skill: str | None = Query(None),
    cidade: str | None = Query(None),
    senioridade: str | None = Query(None),
    search: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """Listar profissionais com filtros opcionais."""
    q = db.query(ProfissionalDB)

    if skill:
        q = q.filter(ProfissionalDB.skills.ilike(f"%{skill}%"))
    if cidade:
        q = q.filter(ProfissionalDB.cidade.ilike(f"%{cidade}%"))
    if senioridade:
        q = q.filter(ProfissionalDB.senioridade == senioridade)
    if search:
        q = q.filter(
            or_(
                ProfissionalDB.nome.ilike(f"%{search}%"),
                ProfissionalDB.bio.ilike(f"%{search}%"),
                ProfissionalDB.cidade.ilike(f"%{search}%"),
                ProfissionalDB.skills.ilike(f"%{search}%"),
            )
        )

    profissionais = q.order_by(ProfissionalDB.criado_em.desc()).offset(offset).limit(limit).all()
    return [_db_to_card(p) for p in profissionais]


@router.get("/api/profissionais/mentores", response_model=list[ProfissionalCard])
def listar_mentores(
    skill: str | None = Query(None),
    db: Session = Depends(get_db),
):
    """Listar profissionais que aceitam mentorar (objetivos contém 'mentorar')."""
    q = db.query(ProfissionalDB).filter(ProfissionalDB.objetivos.ilike("%mentorar%"))
    if skill:
        q = q.filter(ProfissionalDB.skills.ilike(f"%{skill}%"))

    mentores = q.order_by(ProfissionalDB.criado_em.desc()).all()
    return [_db_to_card(p) for p in mentores]


@router.get("/api/profissionais/{profissional_id}/card", response_model=ProfissionalCard)
def obter_card(profissional_id: str, db: Session = Depends(get_db)):
    """Versao publica do perfil (sem email) - usada nos cards e embeds."""
    p = db.query(ProfissionalDB).filter(ProfissionalDB.id == profissional_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Profissional não encontrado")
    return _db_to_card(p)


@router.get("/api/profissionais/{profissional_id}", response_model=ProfissionalOut)
def obter_profissional(profissional_id: str, db: Session = Depends(get_db)):
    """Obter perfil completo de um profissional."""
    p = db.query(ProfissionalDB).filter(ProfissionalDB.id == profissional_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Profissional não encontrado")
    return _db_to_out(p)


@router.patch("/api/profissionais/{profissional_id}", response_model=ProfissionalOut)
def atualizar_profissional(
    profissional_id: str,
    data: ProfissionalUpdate,
    db: Session = Depends(get_db),
    atual: ProfissionalDB = Depends(exigir_profissional),
):
    """Atualizar dados do profissional (somente o dono do perfil)."""
    garantir_mesmo_usuario(profissional_id, atual)
    p = db.query(ProfissionalDB).filter(ProfissionalDB.id == profissional_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Profissional não encontrado")

    update_data = data.model_dump(exclude_unset=True)

    if "senha" in update_data:
        p.senha_hash = hash_password(update_data.pop("senha"))

    if "skills" in update_data:
        update_data["skills"] = json.dumps(update_data["skills"], ensure_ascii=False)
    if "objetivos" in update_data:
        update_data["objetivos"] = json.dumps(update_data["objetivos"], ensure_ascii=False)
    if "disponibilidade" in update_data:
        update_data["disponibilidade"] = json.dumps(update_data["disponibilidade"], ensure_ascii=False)
    if "areas_interesse" in update_data:
        update_data["areas_interesse"] = json.dumps(update_data["areas_interesse"], ensure_ascii=False)

    for key, value in update_data.items():
        setattr(p, key, value)

    p.ultimo_acesso = datetime.now(timezone.utc)
    db.commit()
    db.refresh(p)
    return _db_to_out(p)


@router.post("/api/auth/login", response_model=TokenOut)
def login(data: LoginRequest, db: Session = Depends(get_db)):
    """Autenticar e obter token JWT."""
    email = data.email.strip().lower()
    p = db.query(ProfissionalDB).filter(ProfissionalDB.email == email).first()
    if not p or not verify_password(data.senha, p.senha_hash):
        raise HTTPException(status_code=401, detail="Email ou senha inválidos")

    p.ultimo_acesso = datetime.now(timezone.utc)
    db.commit()
    db.refresh(p)

    token = create_access_token({"sub": p.id, "email": p.email})
    return TokenOut(
        access_token=token,
        profissional_id=p.id,
        expira_em=token_expira_em(),
        profissional=_db_to_out(p),
    )


@router.get("/api/profissionais/{profissional_id}/reputacao", response_model=ReputacaoOut)
def obter_reputacao(profissional_id: str, db: Session = Depends(get_db)):
    """Obter score de contribuição com breakdown."""
    p = db.query(ProfissionalDB).filter(ProfissionalDB.id == profissional_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Profissional não encontrado")

    # Calcular breakdown baseado nas ações do profissional
    from app.models.database import MatchDB, ParticipanteDesafioDB, MentoriaDB, OportunidadeDB

    score = p.score_contribuicao or 0
    breakdown = {"match_aceito": 0, "participou_desafio": 0, "mentor_concluido": 0, "mentorado_concluido": 0, "criou_oportunidade": 0}

    # Matches aceitos (+10 cada)
    matches_aceitos = db.query(MatchDB).filter(
        ((MatchDB.profissional_a_id == profissional_id) | (MatchDB.profissional_b_id == profissional_id)),
        MatchDB.status == "match",
    ).count()
    breakdown["match_aceito"] = matches_aceitos * 10

    # Participações em desafios (+15 cada)
    participacoes = db.query(ParticipanteDesafioDB).filter(
        ParticipanteDesafioDB.profissional_id == profissional_id,
    ).count()
    breakdown["participou_desafio"] = participacoes * 15

    # Mentorias concluídas como mentor (+25 cada)
    mentorias_mentor = db.query(MentoriaDB).filter(
        MentoriaDB.mentor_id == profissional_id,
        MentoriaDB.status == "concluida",
    ).count()
    breakdown["mentor_concluido"] = mentorias_mentor * 25

    # Mentorias concluídas como mentorado (+10 cada)
    mentorias_mentorado = db.query(MentoriaDB).filter(
        MentoriaDB.mentorado_id == profissional_id,
        MentoriaDB.status == "concluida",
    ).count()
    breakdown["mentorado_concluido"] = mentorias_mentorado * 10

    # Oportunidades criadas (+5 cada)
    oportunidades = db.query(OportunidadeDB).filter(
        OportunidadeDB.criador_id == profissional_id,
    ).count()
    breakdown["criou_oportunidade"] = oportunidades * 5

    return ReputacaoOut(
        profissional_id=profissional_id,
        score_contribuicao=score,
        breakdown=breakdown,
    )