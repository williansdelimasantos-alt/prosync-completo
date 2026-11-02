"""SQLAlchemy ORM models."""
import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    String,
    Float,
    Boolean,
    DateTime,
    Text,
    Integer,
    ForeignKey,
    UniqueConstraint,
)
from sqlalchemy import Text as SQLiteText  # TEXT portatil (SQLite + Postgres)
from app.core.database import Base


def _uuid():
    return str(uuid.uuid4())


def _utcnow():
    return datetime.now(timezone.utc)


class ProfissionalDB(Base):
    __tablename__ = "profissionais"

    id = Column(String, primary_key=True, default=_uuid)
    nome = Column(String(150), nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    senha_hash = Column(String(255), nullable=False)
    foto_url = Column(String(500), default="")
    bio = Column(Text, default="")
    cidade = Column(String(100), default="", index=True)
    estado = Column(String(50), default="")
    skills = Column(SQLiteText, default="[]")  # JSON array stored as text
    objetivos = Column(SQLiteText, default="[]")
    senioridade = Column(String(20), default="junior", index=True)
    disponibilidade = Column(SQLiteText, default="[]")
    areas_interesse = Column(SQLiteText, default="[]")
    score_contribuicao = Column(Integer, default=0)
    # v2: campos de produto
    headline = Column(String(200), default="")
    github = Column(String(200), default="")
    linkedin = Column(String(200), default="")
    portfolio = Column(String(300), default="")
    onboarding_concluido = Column(Boolean, default=False)
    perfil_publico = Column(Boolean, default=True)
    criado_em = Column(DateTime, default=_utcnow)
    ultimo_acesso = Column(DateTime, default=_utcnow)


class MatchDB(Base):
    __tablename__ = "matches"

    id = Column(String, primary_key=True, default=_uuid)
    profissional_a_id = Column(String(36), nullable=False, index=True)
    profissional_b_id = Column(String(36), nullable=False, index=True)
    status = Column(String(20), default="pendente", index=True)
    score_ia = Column(Float, default=0.0)
    skills_match = Column(SQLiteText, default="[]")
    # v2: explicabilidade da IA + quem iniciou a conexao
    motivo_ia = Column(Text, default="")
    forcas_ia = Column(SQLiteText, default="[]")
    fonte_ia = Column(String(20), default="heuristica")
    iniciado_por = Column(String(36), nullable=True)
    criado_em = Column(DateTime, default=_utcnow)
    atualizado_em = Column(DateTime, default=_utcnow, onupdate=_utcnow)


class MensagemDB(Base):
    __tablename__ = "mensagens"

    id = Column(String, primary_key=True, default=_uuid)
    match_id = Column(String(36), nullable=False, index=True)
    remetente_id = Column(String(36), nullable=False, index=True)
    conteudo = Column(Text, nullable=False)
    lida = Column(Boolean, default=False)
    criado_em = Column(DateTime, default=_utcnow)


class DesafioDB(Base):
    __tablename__ = "desafios"

    id = Column(String, primary_key=True, default=_uuid)
    criador_id = Column(String(36), nullable=False, index=True)
    titulo = Column(String(200), nullable=False)
    descricao = Column(Text, default="")
    skills_necessarias = Column(SQLiteText, default="[]")
    tipo = Column(String(20), default="dupla")
    status = Column(String(20), default="aberto", index=True)
    prazo = Column(DateTime, nullable=True)
    criado_em = Column(DateTime, default=_utcnow)


class ParticipanteDesafioDB(Base):
    __tablename__ = "participantes_desafio"

    id = Column(String, primary_key=True, default=_uuid)
    desafio_id = Column(String(36), nullable=False, index=True)
    profissional_id = Column(String(36), nullable=False, index=True)
    criado_em = Column(DateTime, default=_utcnow)


class MentoriaDB(Base):
    __tablename__ = "mentorias"

    id = Column(String, primary_key=True, default=_uuid)
    mentor_id = Column(String(36), nullable=False, index=True)
    mentorado_id = Column(String(36), nullable=False, index=True)
    area = Column(String(200), default="")
    objetivos = Column(Text, default="")
    status = Column(String(20), default="pendente", index=True)
    criado_em = Column(DateTime, default=_utcnow)
    concluido_em = Column(DateTime, nullable=True)


class OportunidadeDB(Base):
    __tablename__ = "oportunidades"

    id = Column(String, primary_key=True, default=_uuid)
    criador_id = Column(String(36), nullable=False, index=True)
    titulo = Column(String(200), nullable=False)
    descricao = Column(Text, default="")
    tipo = Column(String(20), default="vaga", index=True)
    skills_necessarias = Column(SQLiteText, default="[]")
    contato = Column(String(255), default="")
    status = Column(String(20), default="aberta", index=True)
    criado_em = Column(DateTime, default=_utcnow)


class ConexaoSalvaDB(Base):
    """"Salvos" / bookmarks: perfis que o usuario quer ver depois."""

    __tablename__ = "conexoes_salvas"
    __table_args__ = (UniqueConstraint("profissional_id", "salvo_id", name="uq_conexao_salva"),)

    id = Column(String, primary_key=True, default=_uuid)
    profissional_id = Column(String(36), nullable=False, index=True)
    salvo_id = Column(String(36), nullable=False, index=True)
    criado_em = Column(DateTime, default=_utcnow)


class NotificacaoDB(Base):
    """Feed de notificacoes in-app (novo match, mensagem, mentoria...)."""

    __tablename__ = "notificacoes"

    id = Column(String, primary_key=True, default=_uuid)
    profissional_id = Column(String(36), nullable=False, index=True)
    tipo = Column(String(30), default="info", index=True)
    titulo = Column(String(200), default="")
    mensagem = Column(Text, default="")
    link = Column(String(300), default="")
    lida = Column(Boolean, default=False, index=True)
    criado_em = Column(DateTime, default=_utcnow)