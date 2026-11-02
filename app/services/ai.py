"""Servico de IA - integracao real com o Gemini + fallback heuristico.

Objetivos:
- Uma unica porta de entrada para toda a inteligencia do produto.
- Funcionar 100% sem chave de API (fallback local determinista), garantindo
  que o app nunca quebre em ambientes offline/testes.
- Cache em memoria com TTL para nao gastar quota da API em chamadas repetidas.
- Nunca expor o `email` dos profissionais no prompt enviado a terceiros.
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from typing import Optional

import httpx

from app.core.config import settings
from app.models.database import ProfissionalDB

_GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


# ─── Cache simples em memoria ──────────────────────────────────────────────
class _TTLCache:
    def __init__(self, ttl_seconds: int = 900, max_items: int = 500):
        self._ttl = ttl_seconds
        self._max = max_items
        self._data: dict[str, tuple[float, object]] = {}

    def get(self, key: str):
        item = self._data.get(key)
        if not item:
            return None
        ts, value = item
        if time.time() - ts > self._ttl:
            self._data.pop(key, None)
            return None
        return value

    def set(self, key: str, value) -> None:
        if len(self._data) >= self._max:
            # descarta a entrada mais antiga (FIFO suficiente aqui)
            self._data.pop(next(iter(self._data)), None)
        self._data[key] = (time.time(), value)

    def clear(self) -> None:
        self._data.clear()


match_cache = _TTLCache(ttl_seconds=900)
resumo_cache = _TTLCache(ttl_seconds=3600)


@dataclass
class ResultadoMatch:
    score: float
    skills_complementares: list[str]
    motivo: str
    fonte: str  # "gemini" | "heuristica"
    forcas: list[str] | None = None


# ─── Helpers ───────────────────────────────────────────────────────────────
def _json_load(val: str) -> list:
    if not val:
        return []
    try:
        data = json.loads(val)
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


def _norm(s: str) -> str:
    return (s or "").strip().lower()


def _perfil_publico(p: ProfissionalDB) -> dict:
    """Snapshot do perfil SEM dados sensiveis (email, id, senha)."""
    return {
        "skills": _json_load(p.skills),
        "senioridade": p.senioridade or "junior",
        "objetivos": _json_load(p.objetivos),
        "cidade": p.cidade or "",
        "estado": p.estado or "",
        "bio": (p.bio or "")[:600],
        "areas_interesse": _json_load(p.areas_interesse),
    }


def _parse_json_da_resposta(texto: str) -> Optional[dict]:
    """Extrai o primeiro objeto JSON de um texto de resposta do modelo."""
    if not texto:
        return None
    match = re.search(r"\{.*\}", texto, re.DOTALL)
    if not match:
        return None
    try:
        data = json.loads(match.group())
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        return None


async def _chamar_gemini(prompt: str, temperature: float = 0.4) -> Optional[str]:
    """Chama a API do Gemini. Retorna o texto ou None em qualquer falha."""
    if not settings.ai_enabled or not settings.gemini_configured:
        return None

    url = _GEMINI_URL.format(model=settings.gemini_model)
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": 800,
            "responseMimeType": "application/json",
        },
    }
    try:
        async with httpx.AsyncClient(timeout=settings.gemini_timeout) as client:
            resp = await client.post(
                url,
                params={"key": settings.gemini_api_key},
                json=body,
            )
        if resp.status_code != 200:
            return None
        data = resp.json()
        return (
            data.get("candidates", [{}])[0]
            .get("content", {})
            .get("parts", [{}])[0]
            .get("text", "")
        )
    except (httpx.HTTPError, ValueError, IndexError, KeyError):
        return None


# ─── Analise de compatibilidade ────────────────────────────────────────────
def analisar_local(prof_a: ProfissionalDB, prof_b: ProfissionalDB) -> ResultadoMatch:
    """Heuristica deterministica - usada como fallback e como baseline."""
    skills_a = {_norm(s) for s in _json_load(prof_a.skills) if s}
    skills_b = {_norm(s) for s in _json_load(prof_b.skills) if s}

    comuns = skills_a & skills_b
    complementares = sorted((skills_a ^ skills_b))
    total = len(skills_a | skills_b) or 1

    score = 0.0

    # Skills: complementaridade pesa mais que sobreposicao, mas ambos somam.
    score += (len(complementares) / total) * 35
    score += min(len(comuns), 3) * 5

    # Localizacao
    if prof_a.cidade and prof_b.cidade:
        if _norm(prof_a.cidade) == _norm(prof_b.cidade):
            score += 15
        elif prof_a.estado and _norm(prof_a.estado) == _norm(prof_b.estado):
            score += 8

    # Senioridade: mesma faixa colabora bem; dupla junior+senior vira mentoria.
    if prof_a.senioridade == prof_b.senioridade:
        score += 12
    elif {prof_a.senioridade, prof_b.senioridade} == {"junior", "senior"}:
        score += 14  # mentoria natural

    # Objetivos
    obj_a = {_norm(o) for o in _json_load(prof_a.objetivos)}
    obj_b = {_norm(o) for o in _json_load(prof_b.objetivos)}
    if obj_a & obj_b:
        score += len(obj_a & obj_b) * 8
    if ("mentorar" in obj_a and "aprender" in obj_b) or (
        "aprender" in obj_a and "mentorar" in obj_b
    ):
        score += 12

    # Areas de interesse em comum
    if {_norm(a) for a in _json_load(prof_a.areas_interesse)} & {
        _norm(a) for a in _json_load(prof_b.areas_interesse)
    }:
        score += 6

    score = round(min(100.0, max(0.0, score)), 1)

    if complementares:
        motivo = (
            f"Vocês se complementam em {', '.join(complementares[:3])}"
            + (" e mais." if len(complementares) > 3 else ".")
        )
    elif comuns:
        motivo = f"Vocês atuam na mesma área ({', '.join(sorted(comuns)[:3])})."
    else:
        motivo = "Perfis com potencial de troca de experiência."

    forcas = []
    if comuns:
        forcas.append("Skills em comum: " + ", ".join(sorted(comuns)[:3]))
    if complementares:
        forcas.append("Skills complementares: " + ", ".join(complementares[:3]))
    if prof_a.cidade and _norm(prof_a.cidade) == _norm(prof_b.cidade):
        forcas.append(f"Mesma cidade ({prof_a.cidade})")
    if ("mentorar" in obj_a and "aprender" in obj_b) or (
        "aprender" in obj_a and "mentorar" in obj_b
    ):
        forcas.append("Um quer mentorar e o outro quer aprender")
    if prof_a.senioridade != prof_b.senioridade:
        forcas.append("Níveis de senioridade complementares")

    return ResultadoMatch(
        score=score,
        skills_complementares=complementares[:6],
        motivo=motivo,
        fonte="heuristica",
        forcas=forcas,
    )


def _prompt_match(a: ProfissionalDB, b: ProfissionalDB) -> str:
    return (
        "Voce e um especialista em matching de carreira para profissionais de "
        "tecnologia remotos no Brasil. Avalie a compatibilidade de colaboracao "
        "entre dois perfis.\n\n"
        f"PERFIL A: {json.dumps(_perfil_publico(a), ensure_ascii=False)}\n\n"
        f"PERFIL B: {json.dumps(_perfil_publico(b), ensure_ascii=False)}\n\n"
        "Responda SOMENTE com um objeto JSON valido, sem markdown, com as chaves:\n"
        '{"score": <inteiro 0-100>, "skills_complementares": [<ate 6 strings>], '
        '"motivo": "<frase curta, maximo 140 caracteres, em portugues do Brasil>", '
        '"forcas": [<2 ou 3 frases curtas em portugues do Brasil>]}\n'
        "O score deve refletir o potencial real de colaboracao/mentoria "
        "(nao apenas sobreposicao de skills)."
    )


async def analisar_match(a: ProfissionalDB, b: ProfissionalDB) -> ResultadoMatch:
    """Analisa compatibilidade usando Gemini (com cache) ou heuristica."""
    local = analisar_local(a, b)

    if not settings.ai_enabled or not settings.gemini_configured:
        return local

    cache_key = "|".join(
        sorted([f"{a.id}:{a.skills}:{a.objetivos}", f"{b.id}:{b.skills}:{b.objetivos}"])
    )
    cacheado = match_cache.get(cache_key)
    if isinstance(cacheado, ResultadoMatch):
        return cacheado

    texto = await _chamar_gemini(_prompt_match(a, b), temperature=0.3)
    if not texto:
        return local

    data = _parse_json_da_resposta(texto)
    if not data:
        return local

    try:
        score = float(data.get("score", local.score))
    except (TypeError, ValueError):
        return local

    # Sanidade: se o modelo devolver algo fora da faixa, confia na heuristica.
    if not 0 <= score <= 100:
        return local

    skills = data.get("skills_complementares") or local.skills_complementares
    if not isinstance(skills, list):
        skills = local.skills_complementares
    skills = [str(s) for s in skills][:6]

    motivo = str(data.get("motivo") or local.motivo)[:200]
    forcas = data.get("forcas")
    if not isinstance(forcas, list):
        forcas = local.forcas
    forcas = [str(f)[:160] for f in forcas][:3] if forcas else local.forcas

    # Blend: 70% IA + 30% heuristica -> evita outliers e mantem sinal explicavel.
    score_blend = round(score * 0.7 + local.score * 0.3, 1)

    resultado = ResultadoMatch(
        score=score_blend,
        skills_complementares=skills,
        motivo=motivo,
        fonte="gemini",
        forcas=forcas,
    )
    match_cache.set(cache_key, resultado)
    return resultado


# ─── Resumo de perfil gerado por IA ────────────────────────────────────────
def _resumo_local(p: ProfissionalDB) -> str:
    skills = _json_load(p.skills)
    objetivos = _json_load(p.objetivos)
    partes = []
    if skills:
        partes.append(f"{p.nome} atua com {', '.join(skills[:3])}")
    else:
        partes.append(f"{p.nome} está construindo seu perfil na ProSync")
    if p.senioridade and p.senioridade != "junior":
        partes[0] += f" (nível {p.senioridade})"
    if p.cidade:
        partes[0] += f" e está em {p.cidade}"
    if objetivos:
        partes.append("Busca " + ", ".join(objetivos))
    return ". ".join(partes) + "."


async def gerar_resumo_perfil(p: ProfissionalDB) -> str:
    """Resumo curto e amigavel do perfil (usado no card/SEO)."""
    if not settings.ai_enabled or not settings.gemini_configured:
        return _resumo_local(p)

    cacheado = resumo_cache.get(p.id)
    if isinstance(cacheado, str):
        return cacheado

    prompt = (
        "Escreva um resumo profissional de 1 a 2 frases (maximo 200 caracteres) "
        "em portugues do Brasil, tom acolhedor e objetivo, para exibir em um card "
        f"de rede profissional. Perfil: {json.dumps(_perfil_publico(p), ensure_ascii=False)}\n"
        'Responda SOMENTE JSON: {"resumo": "<texto>"}'
    )
    texto = await _chamar_gemini(prompt, temperature=0.6)
    data = _parse_json_da_resposta(texto or "")
    if data and data.get("resumo"):
        resumo = str(data["resumo"])[:220]
        resumo_cache.set(p.id, resumo)
        return resumo

    return _resumo_local(p)


def ia_status() -> dict:
    """Diagnostico de IA exposto em /api/health."""
    return {
        "enabled": settings.ai_enabled,
        "provider": "google-gemini",
        "model": settings.gemini_model,
        "configured": settings.gemini_configured,
        "mode": "gemini" if settings.gemini_configured and settings.ai_enabled else "heuristica",
    }
