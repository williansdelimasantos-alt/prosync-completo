"""Descoberta inteligente (feed de sugestoes), salvos e dashboard.

Este e o coracao de produto da v2: em vez de uma lista crua de perfis, o usuario
recebe sugestoes ordenadas por compatibilidade, com explicacao ("por que estou
vendo isso?") - que e o que faz apps de rede prosperarem.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import exigir_profissional
from app.models.database import (
    ProfissionalDB,
    MatchDB,
    MensagemDB,
    MentoriaDB,
    ParticipanteDesafioDB,
    ConexaoSalvaDB,
    DesafioDB,
    OportunidadeDB,
)
from app.models.schemas import ProfissionalCard
from app.models.schemas_v2 import (
    SugestaoOut,
    FeedInteligenteOut,
    SalvoOut,
    DashboardOut,
    StatsOut,
)
from app.services import ai

router = APIRouter()

# Quantos candidatos no maximo passam pela IA (custo/limite de quota).
MAX_CANDIDATOS_IA = 12


def _json_load(val: str) -> list:
    if not val:
        return []
    try:
        data = json.loads(val)
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


def _card(p: ProfissionalDB) -> ProfissionalCard:
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


def _ids_ja_conectados(db: Session, profissional_id: str) -> set[str]:
    """Ids com quem o usuario ja tem match (qualquer status)."""
    rows = (
        db.query(MatchDB.profissional_a_id, MatchDB.profissional_b_id)
        .filter(
            (MatchDB.profissional_a_id == profissional_id)
            | (MatchDB.profissional_b_id == profissional_id)
        )
        .all()
    )
    ids: set[str] = set()
    for a, b in rows:
        ids.add(b if a == profissional_id else a)
    ids.discard(profissional_id)
    return ids


def _match_index(db: Session, profissional_id: str) -> dict[str, MatchDB]:
    rows = (
        db.query(MatchDB)
        .filter(
            (MatchDB.profissional_a_id == profissional_id)
            | (MatchDB.profissional_b_id == profissional_id)
        )
        .all()
    )
    idx: dict[str, MatchDB] = {}
    for m in rows:
        outro = m.profissional_b_id if m.profissional_a_id == profissional_id else m.profissional_a_id
        idx[outro] = m
    return idx


@router.get("/api/feed", response_model=FeedInteligenteOut)
async def feed_inteligente(
    profissional_id: str = Query(..., description="Profissional que esta navegando"),
    limit: int = Query(8, ge=1, le=30),
    incluir_ja_conectados: bool = Query(False),
    db: Session = Depends(get_db),
):
    """Feed de sugestoes personalizado com score e justificativa."""
    eu = db.query(ProfissionalDB).filter(ProfissionalDB.id == profissional_id).first()
    if not eu:
        raise HTTPException(status_code=404, detail="Profissional não encontrado")

    conectados = _ids_ja_conectados(db, profissional_id)
    matches = _match_index(db, profissional_id)

    candidatos = (
        db.query(ProfissionalDB)
        .filter(ProfissionalDB.id != profissional_id)
        .order_by(ProfissionalDB.score_contribuicao.desc(), ProfissionalDB.criado_em.desc())
        .limit(200)
        .all()
    )

    if not incluir_ja_conectados:
        candidatos = [c for c in candidatos if c.id not in conectados]

    if not candidatos:
        return FeedInteligenteOut(
            sugestoes=[], total=0, modo=ai.ia_status()["mode"], gerado_em=datetime.now(timezone.utc)
        )

    # Ranking barato primeiro (heuristica), para so mandar os melhores para a IA.
    pre_ranqueados = sorted(
        ((c, ai.analisar_local(eu, c)) for c in candidatos),
        key=lambda par: par[1].score,
        reverse=True,
    )

    modo = ai.ia_status()["mode"]
    sugestoes: list[SugestaoOut] = []

    if modo == "gemini":
        topo = pre_ranqueados[:MAX_CANDIDATOS_IA]
        for cand, _local in topo:
            resultado = await ai.analisar_match(eu, cand)
            m = matches.get(cand.id)
            sugestoes.append(
                SugestaoOut(
                    profissional=_card(cand),
                    score=resultado.score,
                    motivo=resultado.motivo,
                    forcas=resultado.forcas or [],
                    skills_complementares=resultado.skills_complementares,
                    fonte=resultado.fonte,
                    match_id=m.id if m else None,
                    match_status=m.status if m else None,
                )
            )
        # completar o feed com o restante, ja rankeado localmente
        if len(sugestoes) < limit:
            for cand, local in pre_ranqueados[MAX_CANDIDATOS_IA:]:
                m = matches.get(cand.id)
                sugestoes.append(
                    SugestaoOut(
                        profissional=_card(cand),
                        score=local.score,
                        motivo=local.motivo,
                        forcas=local.forcas or [],
                        skills_complementares=local.skills_complementares,
                        fonte=local.fonte,
                        match_id=m.id if m else None,
                        match_status=m.status if m else None,
                    )
                )
    else:
        for cand, local in pre_ranqueados:
            m = matches.get(cand.id)
            sugestoes.append(
                SugestaoOut(
                    profissional=_card(cand),
                    score=local.score,
                    motivo=local.motivo,
                    forcas=local.forcas or [],
                    skills_complementares=local.skills_complementares,
                    fonte=local.fonte,
                    match_id=m.id if m else None,
                    match_status=m.status if m else None,
                )
            )

    sugestoes.sort(key=lambda s: s.score, reverse=True)
    sugestoes = sugestoes[:limit]

    return FeedInteligenteOut(
        sugestoes=sugestoes,
        total=len(sugestoes),
        modo=modo,
        gerado_em=datetime.now(timezone.utc),
    )


# ─── Salvos (bookmarks) ────────────────────────────────────────────────────

@router.post("/api/profissionais/{profissional_id}/salvos/{alvo_id}", response_model=SalvoOut, status_code=201)
def salvar_perfil(
    profissional_id: str,
    alvo_id: str,
    db: Session = Depends(get_db),
    atual: ProfissionalDB = Depends(exigir_profissional),
):
    """Salvar um perfil para ver depois (idempotente)."""
    if str(atual.id) != profissional_id:
        raise HTTPException(status_code=403, detail="Você só pode gerenciar seus próprios salvos")
    if alvo_id == profissional_id:
        raise HTTPException(status_code=400, detail="Você não pode salvar o próprio perfil")

    alvo = db.query(ProfissionalDB).filter(ProfissionalDB.id == alvo_id).first()
    if not alvo:
        raise HTTPException(status_code=404, detail="Profissional não encontrado")

    existente = (
        db.query(ConexaoSalvaDB)
        .filter(
            ConexaoSalvaDB.profissional_id == profissional_id,
            ConexaoSalvaDB.salvo_id == alvo_id,
        )
        .first()
    )
    if existente:
        return SalvoOut(
            id=existente.id,
            salvo_id=existente.salvo_id,
            criado_em=existente.criado_em,
            profissional=_card(alvo),
        )

    salvo = ConexaoSalvaDB(profissional_id=profissional_id, salvo_id=alvo_id)
    db.add(salvo)
    db.commit()
    db.refresh(salvo)
    return SalvoOut(id=salvo.id, salvo_id=salvo.salvo_id, criado_em=salvo.criado_em, profissional=_card(alvo))


@router.delete("/api/profissionais/{profissional_id}/salvos/{alvo_id}", status_code=200)
def remover_salvo(
    profissional_id: str,
    alvo_id: str,
    db: Session = Depends(get_db),
    atual: ProfissionalDB = Depends(exigir_profissional),
):
    if str(atual.id) != profissional_id:
        raise HTTPException(status_code=403, detail="Você só pode gerenciar seus próprios salvos")

    db.query(ConexaoSalvaDB).filter(
        ConexaoSalvaDB.profissional_id == profissional_id,
        ConexaoSalvaDB.salvo_id == alvo_id,
    ).delete()
    db.commit()
    return {"removido": True, "alvo_id": alvo_id}


@router.get("/api/profissionais/{profissional_id}/salvos", response_model=list[SalvoOut])
def listar_salvos(
    profissional_id: str,
    db: Session = Depends(get_db),
    atual: ProfissionalDB = Depends(exigir_profissional),
):
    if str(atual.id) != profissional_id:
        raise HTTPException(status_code=403, detail="Você só pode ver seus próprios salvos")

    rows = (
        db.query(ConexaoSalvaDB)
        .filter(ConexaoSalvaDB.profissional_id == profissional_id)
        .order_by(ConexaoSalvaDB.criado_em.desc())
        .all()
    )
    resultado = []
    for r in rows:
        prof = db.query(ProfissionalDB).filter(ProfissionalDB.id == r.salvo_id).first()
        resultado.append(
            SalvoOut(
                id=r.id,
                salvo_id=r.salvo_id,
                criado_em=r.criado_em,
                profissional=_card(prof) if prof else None,
            )
        )
    return resultado


# ─── Dashboard ─────────────────────────────────────────────────────────────

@router.get("/api/dashboard/{profissional_id}", response_model=DashboardOut)
async def dashboard(
    profissional_id: str,
    db: Session = Depends(get_db),
    atual: ProfissionalDB = Depends(exigir_profissional),
):
    """Painel pessoal com metricas e proximos passos acionaveis."""
    if str(atual.id) != profissional_id:
        raise HTTPException(status_code=403, detail="Você só pode ver seu próprio painel")

    eu = atual

    matches_pendentes = (
        db.query(MatchDB)
        .filter(
            ((MatchDB.profissional_a_id == profissional_id) | (MatchDB.profissional_b_id == profissional_id)),
            MatchDB.status == "pendente",
        )
        .count()
    )
    matches_ativos = (
        db.query(MatchDB)
        .filter(
            ((MatchDB.profissional_a_id == profissional_id) | (MatchDB.profissional_b_id == profissional_id)),
            MatchDB.status == "match",
        )
        .all()
    )
    ids_matches_ativos = [
        m.profissional_b_id if m.profissional_a_id == profissional_id else m.profissional_a_id
        for m in matches_ativos
    ]

    nao_lidas = 0
    if ids_matches_ativos:
        nao_lidas = (
            db.query(MensagemDB)
            .filter(
                MensagemDB.match_id.in_([m.id for m in matches_ativos]),
                MensagemDB.remetente_id != profissional_id,
                MensagemDB.lida == False,  # noqa: E712
            )
            .count()
        )

    mentorias_ativas = (
        db.query(MentoriaDB)
        .filter(
            (MentoriaDB.mentor_id == profissional_id) | (MentoriaDB.mentorado_id == profissional_id),
            MentoriaDB.status.in_(["pendente", "ativa"]),
        )
        .count()
    )
    desafios_participando = (
        db.query(ParticipanteDesafioDB)
        .filter(ParticipanteDesafioDB.profissional_id == profissional_id)
        .count()
    )
    salvos = (
        db.query(ConexaoSalvaDB).filter(ConexaoSalvaDB.profissional_id == profissional_id).count()
    )

    sugestoes: list[SugestaoOut] = []
    try:
        # limit=6 e depois removemos quem ja tem convite pendente (aparecem na lista ao lado)
        feed = await feed_inteligente(profissional_id=profissional_id, limit=6, incluir_ja_conectados=False, db=db)
        pendentes_ids = {
            m.profissional_b_id if m.profissional_a_id == profissional_id else m.profissional_a_id
            for m in db.query(MatchDB)
            .filter(
                ((MatchDB.profissional_a_id == profissional_id) | (MatchDB.profissional_b_id == profissional_id)),
                MatchDB.status == "pendente",
            )
            .all()
        }
        sugestoes = [s for s in feed.sugestoes if s.profissional.id not in pendentes_ids][:3]
    except HTTPException:
        pass

    passos: list[str] = []
    if not (eu.bio or "").strip():
        passos.append("Escreva uma bio curta: perfis com bio recebem 3x mais convites.")
    if not _json_load(eu.skills):
        passos.append("Adicione pelo menos 3 skills para melhorar suas sugestões.")
    if not (eu.cidade or "").strip():
        passos.append("Informe sua cidade para encontrarmos gente perto de você.")
    if matches_pendentes:
        passos.append(f"Você tem {matches_pendentes} conexão(ões) pendente(s) — responda para ganhar +10 pontos.")
    if nao_lidas:
        passos.append(f"Você tem {nao_lidas} mensagem(ns) não lida(s).")
    if not passos:
        passos.append("Perfil completo! Explore o feed e participe de um desafio para engajar a comunidade.")

    return DashboardOut(
        profissional=_card(eu),
        score_contribuicao=eu.score_contribuicao or 0,
        matches_pendentes=matches_pendentes,
        conversas_ativas=len(matches_ativos),
        mensagens_nao_lidas=nao_lidas,
        mentorias_ativas=mentorias_ativas,
        desafios_participando=desafios_participando,
        salvos=salvos,
        sugestoes=sugestoes,
        proximos_passos=passos[:4],
    )


# ─── Stats publicas ────────────────────────────────────────────────────────

@router.get("/api/stats", response_model=StatsOut)
def stats(db: Session = Depends(get_db)):
    """Metricas publicas para a landing page."""
    profissionais = db.query(ProfissionalDB).count()
    matches = db.query(MatchDB).filter(MatchDB.status == "match").count()
    conexoes = db.query(MatchDB).count()
    desafios_abertos = db.query(DesafioDB).filter(DesafioDB.status == "aberto").count()
    oportunidades_abertas = db.query(OportunidadeDB).filter(OportunidadeDB.status == "aberta").count()
    mentorias_ativas = db.query(MentoriaDB).filter(MentoriaDB.status.in_(["pendente", "ativa"])).count()
    cidades = db.query(func.count(func.distinct(ProfissionalDB.cidade))).scalar() or 0

    skills_counter: dict[str, int] = {}
    for (skills_json,) in db.query(ProfissionalDB.skills).all():
        for s in _json_load(skills_json):
            key = str(s).strip()
            if key:
                skills_counter[key] = skills_counter.get(key, 0) + 1
    skills_top = [s for s, _ in sorted(skills_counter.items(), key=lambda kv: kv[1], reverse=True)[:8]]

    return StatsOut(
        profissionais=profissionais,
        conexoes=conexoes,
        matches_ativos=matches,
        desafios_abertos=desafios_abertos,
        oportunidades_abertas=oportunidades_abertas,
        mentorias_ativas=mentorias_ativas,
        cidades=cidades,
        skills_top=skills_top,
        modo_ia=ai.ia_status()["mode"],
    )
