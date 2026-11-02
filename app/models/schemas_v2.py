"""Schemas da v2: descoberta inteligente, salvos, notificacoes e metricas."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.models.schemas import ProfissionalCard


# ─── Descoberta / Feed inteligente ─────────────────────────────────────────

class SugestaoOut(BaseModel):
    """Um profissional sugerido, com a explicacao do porque da sugestao."""

    profissional: ProfissionalCard
    score: float = 0.0
    motivo: str = ""
    forcas: list[str] = []
    skills_complementares: list[str] = []
    fonte: str = "heuristica"
    match_id: Optional[str] = None
    match_status: Optional[str] = None


class FeedInteligenteOut(BaseModel):
    sugestoes: list[SugestaoOut]
    total: int
    modo: str = "heuristica"  # gemini | heuristica
    gerado_em: datetime


# ─── Salvos ────────────────────────────────────────────────────────────────

class SalvoOut(BaseModel):
    id: str
    salvo_id: str
    criado_em: datetime
    profissional: Optional[ProfissionalCard] = None

    model_config = {"from_attributes": True}


# ─── Notificacoes ──────────────────────────────────────────────────────────

class NotificacaoOut(BaseModel):
    id: str
    tipo: str
    titulo: str
    mensagem: str
    link: str
    lida: bool
    criado_em: datetime

    model_config = {"from_attributes": True}


class NotificacoesResumoOut(BaseModel):
    nao_lidas: int
    itens: list[NotificacaoOut]


# ─── Metricas ──────────────────────────────────────────────────────────────

class StatsOut(BaseModel):
    profissionais: int
    conexoes: int
    matches_ativos: int
    desafios_abertos: int
    oportunidades_abertas: int
    mentorias_ativas: int
    cidades: int
    skills_top: list[str] = []
    modo_ia: str = "heuristica"


class DashboardOut(BaseModel):
    """Painel "minha home" do profissional logado."""

    profissional: ProfissionalCard
    score_contribuicao: int
    matches_pendentes: int
    conversas_ativas: int
    mensagens_nao_lidas: int
    mentorias_ativas: int
    desafios_participando: int
    salvos: int
    sugestoes: list[SugestaoOut] = []
    proximos_passos: list[str] = []
