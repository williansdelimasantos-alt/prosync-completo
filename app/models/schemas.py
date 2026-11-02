"""Pydantic schemas for request/response validation."""
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional


# ─── Profissional ──────────────────────────────────────────────────────────

class ProfissionalCreate(BaseModel):
    nome: str = Field(..., min_length=2, max_length=150)
    email: str = Field(..., max_length=255)
    senha: str = Field(..., min_length=6, max_length=128)
    foto_url: str = ""
    bio: str = ""
    headline: str = ""
    cidade: str = ""
    estado: str = ""
    skills: list[str] = []
    objetivos: list[str] = []
    senioridade: str = "junior"
    disponibilidade: list[str] = []
    areas_interesse: list[str] = []
    github: str = ""
    linkedin: str = ""
    portfolio: str = ""


class ProfissionalUpdate(BaseModel):
    nome: Optional[str] = Field(None, min_length=2, max_length=150)
    senha: Optional[str] = Field(None, min_length=6, max_length=128)
    foto_url: Optional[str] = None
    bio: Optional[str] = None
    headline: Optional[str] = Field(None, max_length=200)
    cidade: Optional[str] = None
    estado: Optional[str] = None
    skills: Optional[list[str]] = None
    objetivos: Optional[list[str]] = None
    senioridade: Optional[str] = None
    disponibilidade: Optional[list[str]] = None
    areas_interesse: Optional[list[str]] = None
    github: Optional[str] = None
    linkedin: Optional[str] = None
    portfolio: Optional[str] = None
    onboarding_concluido: Optional[bool] = None
    perfil_publico: Optional[bool] = None


class ProfissionalOut(BaseModel):
    id: str
    nome: str
    email: str
    foto_url: str
    bio: str
    headline: str = ""
    cidade: str
    estado: str
    skills: list[str]
    objetivos: list[str]
    senioridade: str
    disponibilidade: list[str]
    areas_interesse: list[str]
    github: str = ""
    linkedin: str = ""
    portfolio: str = ""
    onboarding_concluido: bool = False
    perfil_publico: bool = True
    score_contribuicao: int = 0
    criado_em: datetime
    ultimo_acesso: datetime

    model_config = ConfigDict(from_attributes=True)


class ProfissionalCard(BaseModel):
    """Lightweight version for feed cards - no email exposed."""
    id: str
    nome: str
    foto_url: str
    bio: str
    headline: str = ""
    cidade: str
    estado: str
    skills: list[str]
    senioridade: str
    objetivos: list[str]
    areas_interesse: list[str] = []
    score_contribuicao: int = 0

    model_config = ConfigDict(from_attributes=True)


# ─── Match ─────────────────────────────────────────────────────────────────

class MatchCreate(BaseModel):
    profissional_a_id: str
    profissional_b_id: str


class MatchOut(BaseModel):
    id: str
    profissional_a_id: str
    profissional_b_id: str
    status: str
    score_ia: float
    skills_match: list[str]
    motivo_ia: str = ""
    forcas_ia: list[str] = []
    fonte_ia: str = "heuristica"
    iniciado_por: Optional[str] = None
    criado_em: datetime
    atualizado_em: datetime

    model_config = ConfigDict(from_attributes=True)


# ─── Mensagem ──────────────────────────────────────────────────────────────

class MensagemCreate(BaseModel):
    match_id: str
    remetente_id: str
    conteudo: str = Field(..., min_length=1, max_length=5000)


class MensagemOut(BaseModel):
    id: str
    match_id: str
    remetente_id: str
    conteudo: str
    lida: bool
    criado_em: datetime

    model_config = ConfigDict(from_attributes=True)


class ConversaOut(BaseModel):
    """Match com ultima mensagem e contagem de nao lidas."""
    match_id: str
    match_status: str
    score_ia: float
    profissional_id: str
    profissional_nome: str
    profissional_foto: str
    ultima_mensagem: Optional[str] = None
    ultima_mensagem_em: Optional[datetime] = None
    nao_lidas: int = 0


# ─── Desafio ────────────────────────────────────────────────────────────────

class DesafioCreate(BaseModel):
    criador_id: str
    titulo: str = Field(..., min_length=3, max_length=200)
    descricao: str = ""
    skills_necessarias: list[str] = []
    tipo: str = "dupla"
    prazo: Optional[str] = None  # ISO datetime string


class DesafioOut(BaseModel):
    id: str
    criador_id: str
    titulo: str
    descricao: str
    skills_necessarias: list[str]
    tipo: str
    status: str
    prazo: Optional[datetime] = None
    criado_em: datetime

    model_config = ConfigDict(from_attributes=True)


class DesafioStatusUpdate(BaseModel):
    status: str = Field(..., pattern=r"^(aberto|em_andamento|concluido)$")


class ParticipanteDesafioOut(BaseModel):
    id: str
    desafio_id: str
    profissional_id: str
    profissional_nome: str = ""
    profissional_foto: str = ""
    criado_em: datetime

    model_config = ConfigDict(from_attributes=True)


# ─── Auth ──────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    email: str
    senha: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    profissional_id: str
    expira_em: int = 0
    profissional: Optional[ProfissionalOut] = None


# ─── Mentoria ────────────────────────────────────────────────────────────────

class MentoriaCreate(BaseModel):
    mentorado_id: str
    mentor_id: str
    area: str = ""
    objetivos: str = ""


class MentoriaOut(BaseModel):
    id: str
    mentor_id: str
    mentorado_id: str
    area: str
    objetivos: str
    status: str
    criado_em: datetime
    concluido_em: Optional[datetime] = None
    mentor_nome: str = ""
    mentor_foto: str = ""
    mentorado_nome: str = ""
    mentorado_foto: str = ""

    model_config = ConfigDict(from_attributes=True)


# ─── Oportunidade ────────────────────────────────────────────────────────────

class OportunidadeCreate(BaseModel):
    criador_id: str
    titulo: str = Field(..., min_length=3, max_length=200)
    descricao: str = ""
    tipo: str = "vaga"
    skills_necessarias: list[str] = []
    contato: str = ""


class OportunidadeOut(BaseModel):
    id: str
    criador_id: str
    titulo: str
    descricao: str
    tipo: str
    skills_necessarias: list[str]
    contato: str
    status: str
    criado_em: datetime
    criador_nome: str = ""
    criador_foto: str = ""

    model_config = ConfigDict(from_attributes=True)


class OportunidadeStatusUpdate(BaseModel):
    status: str = Field(..., pattern=r"^(aberta|preenchida)$")


# ─── Reputação ───────────────────────────────────────────────────────────────

class ReputacaoOut(BaseModel):
    profissional_id: str
    score_contribuicao: int
    breakdown: dict[str, int]