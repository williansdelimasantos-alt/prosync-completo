"""Testes da v2: IA, feed inteligente, dashboard, notificacoes e salvos."""
import json
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.database import ProfissionalDB
from app.services import ai
from app.services.ai import ResultadoMatch


# ═══════════════════════════════════════════════════════════════════════════
# Servico de IA (funcoes puras)
# ═══════════════════════════════════════════════════════════════════════════

class TestServicoIA:
    def test_heuristica_recompensa_complementaridade(self, criar_profissional):
        dev = criar_profissional(skills=json.dumps(["Python", "FastAPI"]), objetivos=json.dumps(["colaborar"]))
        designer = criar_profissional(skills=json.dumps(["Figma", "UX"]), objetivos=json.dumps(["colaborar"]))

        resultado = ai.analisar_local(dev, designer)

        assert 0 <= resultado.score <= 100
        assert resultado.fonte == "heuristica"
        assert resultado.motivo
        assert set(resultado.skills_complementares) >= {"python", "fastapi", "figma", "ux"}

    def test_heuristica_mentoria_junior_senior(self, criar_profissional):
        junior = criar_profissional(senioridade="junior", objetivos=json.dumps(["aprender"]))
        senior = criar_profissional(senioridade="senior", objetivos=json.dumps(["mentorar"]))

        resultado = ai.analisar_local(junior, senior)

        assert resultado.score >= 20
        assert any("mentor" in f.lower() for f in (resultado.forcas or []))

    def test_score_sempre_na_faixa(self, criar_profissional):
        a = criar_profissional(skills=json.dumps([f"skill{i}" for i in range(20)]), cidade="Recife", estado="PE")
        b = criar_profissional(skills=json.dumps(["nada"]), cidade="Recife", estado="PE")
        assert 0 <= ai.analisar_local(a, b).score <= 100

    @pytest.mark.asyncio
    async def test_analisar_match_sem_chave_usa_heuristica(self, criar_profissional, monkeypatch):
        monkeypatch.setattr(ai.settings, "gemini_api_key", "")
        a = criar_profissional()
        b = criar_profissional()
        resultado = await ai.analisar_match(a, b)
        assert resultado.fonte == "heuristica"

    @pytest.mark.asyncio
    async def test_analisar_match_com_gemini_mockado(self, criar_profissional, monkeypatch):
        monkeypatch.setattr(ai.settings, "gemini_api_key", "fake-key")
        monkeypatch.setattr(ai.settings, "ai_enabled", True)
        ai.match_cache.clear()

        resposta = json.dumps(
            {
                "score": 92,
                "skills_complementares": ["Python", "UX"],
                "motivo": "Perfis muito complementares para um produto completo.",
                "forcas": ["Stack complementar", "Mesma cidade"],
            }
        )

        a = criar_profissional(cidade="Fortaleza", estado="CE")
        b = criar_profissional(cidade="Fortaleza", estado="CE")

        with patch.object(ai, "_chamar_gemini", new=AsyncMock(return_value=resposta)):
            resultado = await ai.analisar_match(a, b)

        assert resultado.fonte == "gemini"
        assert resultado.motivo.startswith("Perfis muito complementares")
        assert resultado.skills_complementares == ["Python", "UX"]
        assert 0 <= resultado.score <= 100

    @pytest.mark.asyncio
    async def test_gemini_com_resposta_invalida_cai_para_heuristica(self, criar_profissional, monkeypatch):
        monkeypatch.setattr(ai.settings, "gemini_api_key", "fake-key")
        monkeypatch.setattr(ai.settings, "ai_enabled", True)
        ai.match_cache.clear()

        a = criar_profissional()
        b = criar_profissional()

        with patch.object(ai, "_chamar_gemini", new=AsyncMock(return_value="isso nao e json")):
            resultado = await ai.analisar_match(a, b)

        assert resultado.fonte == "heuristica"

    @pytest.mark.asyncio
    async def test_gemini_com_score_fora_da_faixa_cai_para_heuristica(self, criar_profissional, monkeypatch):
        monkeypatch.setattr(ai.settings, "gemini_api_key", "fake-key")
        monkeypatch.setattr(ai.settings, "ai_enabled", True)
        ai.match_cache.clear()

        a = criar_profissional()
        b = criar_profissional()

        with patch.object(ai, "_chamar_gemini", new=AsyncMock(return_value='{"score": 9999}')):
            resultado = await ai.analisar_match(a, b)

        assert resultado.fonte == "heuristica"

    @pytest.mark.asyncio
    async def test_cache_evita_chamadas_repetidas(self, criar_profissional, monkeypatch):
        monkeypatch.setattr(ai.settings, "gemini_api_key", "fake-key")
        monkeypatch.setattr(ai.settings, "ai_enabled", True)
        ai.match_cache.clear()

        a = criar_profissional()
        b = criar_profissional()
        resposta = '{"score": 70, "skills_complementares": [], "motivo": "ok", "forcas": []}'

        mock = AsyncMock(return_value=resposta)
        with patch.object(ai, "_chamar_gemini", new=mock):
            await ai.analisar_match(a, b)
            await ai.analisar_match(a, b)

        assert mock.await_count == 1

    def test_ia_status_reflete_configuracao(self, monkeypatch):
        monkeypatch.setattr(ai.settings, "gemini_api_key", "")
        assert ai.ia_status()["mode"] == "heuristica"

        monkeypatch.setattr(ai.settings, "gemini_api_key", "abc")
        monkeypatch.setattr(ai.settings, "ai_enabled", True)
        status = ai.ia_status()
        assert status["mode"] == "gemini"
        assert status["configured"] is True


# ═══════════════════════════════════════════════════════════════════════════
# Feed inteligente
# ═══════════════════════════════════════════════════════════════════════════

def _desligar_ia(monkeypatch):
    monkeypatch.setattr(ai.settings, "gemini_api_key", "")


class TestFeedInteligente:
    def test_feed_ordena_por_score(self, client: TestClient, criar_profissional, monkeypatch):
        _desligar_ia(monkeypatch)
        eu = criar_profissional(nome="Eu", skills=json.dumps(["Python"]), cidade="Recife", estado="PE")
        criar_profissional(nome="Compativel", skills=json.dumps(["Python", "React"]), cidade="Recife", estado="PE")
        criar_profissional(nome="Distante", skills=json.dumps(["Jardinagem"]), cidade="Manaus", estado="AM")

        resp = client.get(f"/api/feed?profissional_id={eu.id}")
        assert resp.status_code == 200
        data = resp.json()

        assert data["modo"] == "heuristica"
        assert data["total"] == 2
        scores = [s["score"] for s in data["sugestoes"]]
        assert scores == sorted(scores, reverse=True)
        assert data["sugestoes"][0]["profissional"]["nome"] == "Compativel"
        assert data["sugestoes"][0]["motivo"]

    def test_feed_nao_inclui_proprio_perfil(self, client: TestClient, criar_profissional, monkeypatch):
        _desligar_ia(monkeypatch)
        eu = criar_profissional()
        resp = client.get(f"/api/feed?profissional_id={eu.id}")
        assert all(s["profissional"]["id"] != eu.id for s in resp.json()["sugestoes"])

    def test_feed_exclui_ja_conectados_por_padrao(self, client: TestClient, criar_profissional, monkeypatch):
        _desligar_ia(monkeypatch)
        eu = criar_profissional()
        outro = criar_profissional()
        client.post("/api/matches", json={"profissional_a_id": eu.id, "profissional_b_id": outro.id})

        resp = client.get(f"/api/feed?profissional_id={eu.id}")
        assert resp.json()["total"] == 0

        resp = client.get(f"/api/feed?profissional_id={eu.id}&incluir_ja_conectados=true")
        assert resp.json()["total"] == 1
        assert resp.json()["sugestoes"][0]["match_status"] == "pendente"

    def test_feed_profissional_inexistente_404(self, client: TestClient):
        resp = client.get("/api/feed?profissional_id=nao-existe")
        assert resp.status_code == 404

    def test_feed_respeita_limit(self, client: TestClient, criar_profissional, monkeypatch):
        _desligar_ia(monkeypatch)
        eu = criar_profissional()
        for _ in range(5):
            criar_profissional()
        resp = client.get(f"/api/feed?profissional_id={eu.id}&limit=2")
        assert len(resp.json()["sugestoes"]) == 2

    def test_feed_com_gemini_mockado(self, client: TestClient, criar_profissional, monkeypatch):
        monkeypatch.setattr(ai.settings, "gemini_api_key", "fake-key")
        monkeypatch.setattr(ai.settings, "ai_enabled", True)
        ai.match_cache.clear()

        eu = criar_profissional()
        criar_profissional()

        resposta = '{"score": 88, "skills_complementares": ["X"], "motivo": "IA diz que combina", "forcas": ["a"]}'
        with patch.object(ai, "_chamar_gemini", new=AsyncMock(return_value=resposta)):
            resp = client.get(f"/api/feed?profissional_id={eu.id}")

        data = resp.json()
        assert data["modo"] == "gemini"
        assert data["sugestoes"][0]["fonte"] == "gemini"
        assert data["sugestoes"][0]["motivo"] == "IA diz que combina"


# ═══════════════════════════════════════════════════════════════════════════
# Match com explicabilidade
# ═══════════════════════════════════════════════════════════════════════════

class TestMatchExplicavel:
    def test_match_traz_motivo_e_fonte(self, client: TestClient, criar_profissional, monkeypatch):
        _desligar_ia(monkeypatch)
        a = criar_profissional(skills=json.dumps(["Python"]))
        b = criar_profissional(skills=json.dumps(["React"]))

        resp = client.post("/api/matches", json={"profissional_a_id": a.id, "profissional_b_id": b.id})
        assert resp.status_code == 201
        data = resp.json()

        assert data["motivo_ia"]
        assert data["fonte_ia"] == "heuristica"
        assert data["iniciado_por"] == a.id
        assert isinstance(data["forcas_ia"], list)

    def test_aceitar_gera_notificacao_para_o_outro(self, client: TestClient, criar_profissional, auth_headers):
        a = criar_profissional(nome="Ana")
        b = criar_profissional(nome="Bia")
        match_id = client.post(
            "/api/matches", json={"profissional_a_id": a.id, "profissional_b_id": b.id}
        ).json()["id"]

        client.post(f"/api/matches/{match_id}/aceitar", headers=auth_headers(b.id))

        resp = client.get(f"/api/notificacoes?profissional_id={a.id}", headers=auth_headers(a.id))
        tipos = [n["tipo"] for n in resp.json()["itens"]]
        assert "match_aceito" in tipos

    def test_aceitar_match_de_outra_pessoa_403(self, client: TestClient, criar_profissional, auth_headers):
        a = criar_profissional()
        b = criar_profissional()
        intruso = criar_profissional()
        match_id = client.post(
            "/api/matches", json={"profissional_a_id": a.id, "profissional_b_id": b.id}
        ).json()["id"]

        resp = client.post(f"/api/matches/{match_id}/aceitar", headers=auth_headers(intruso.id))
        assert resp.status_code == 403

    def test_analise_match_endpoint(self, client: TestClient, criar_profissional, monkeypatch):
        _desligar_ia(monkeypatch)
        a = criar_profissional()
        b = criar_profissional()
        match_id = client.post(
            "/api/matches", json={"profissional_a_id": a.id, "profissional_b_id": b.id}
        ).json()["id"]

        resp = client.get(f"/api/matches/{match_id}/analise")
        assert resp.status_code == 200
        data = resp.json()
        assert "score" in data and "motivo" in data and "modo_ia" in data


# ═══════════════════════════════════════════════════════════════════════════
# Salvos
# ═══════════════════════════════════════════════════════════════════════════

class TestSalvos:
    def test_salvar_e_listar(self, client: TestClient, criar_profissional, auth_headers):
        eu = criar_profissional()
        alvo = criar_profissional(nome="Alvo")

        resp = client.post(
            f"/api/profissionais/{eu.id}/salvos/{alvo.id}", headers=auth_headers(eu.id)
        )
        assert resp.status_code == 201
        assert resp.json()["profissional"]["nome"] == "Alvo"

        resp = client.get(f"/api/profissionais/{eu.id}/salvos", headers=auth_headers(eu.id))
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_salvar_duas_vezes_e_idempotente(self, client: TestClient, criar_profissional, auth_headers):
        eu = criar_profissional()
        alvo = criar_profissional()

        client.post(f"/api/profissionais/{eu.id}/salvos/{alvo.id}", headers=auth_headers(eu.id))
        resp = client.post(f"/api/profissionais/{eu.id}/salvos/{alvo.id}", headers=auth_headers(eu.id))
        assert resp.status_code == 201

        lista = client.get(f"/api/profissionais/{eu.id}/salvos", headers=auth_headers(eu.id)).json()
        assert len(lista) == 1

    def test_remover_salvo(self, client: TestClient, criar_profissional, auth_headers):
        eu = criar_profissional()
        alvo = criar_profissional()
        client.post(f"/api/profissionais/{eu.id}/salvos/{alvo.id}", headers=auth_headers(eu.id))

        resp = client.delete(f"/api/profissionais/{eu.id}/salvos/{alvo.id}", headers=auth_headers(eu.id))
        assert resp.status_code == 200
        assert client.get(f"/api/profissionais/{eu.id}/salvos", headers=auth_headers(eu.id)).json() == []

    def test_salvar_proprio_perfil_400(self, client: TestClient, criar_profissional, auth_headers):
        eu = criar_profissional()
        resp = client.post(f"/api/profissionais/{eu.id}/salvos/{eu.id}", headers=auth_headers(eu.id))
        assert resp.status_code == 400

    def test_salvar_sem_token_401(self, client: TestClient, criar_profissional):
        eu = criar_profissional()
        alvo = criar_profissional()
        resp = client.post(f"/api/profissionais/{eu.id}/salvos/{alvo.id}")
        assert resp.status_code == 401

    def test_listar_salvos_de_outro_403(self, client: TestClient, criar_profissional, auth_headers):
        eu = criar_profissional()
        outro = criar_profissional()
        resp = client.get(f"/api/profissionais/{outro.id}/salvos", headers=auth_headers(eu.id))
        assert resp.status_code == 403


# ═══════════════════════════════════════════════════════════════════════════
# Dashboard e notificacoes
# ═══════════════════════════════════════════════════════════════════════════

class TestDashboard:
    def test_dashboard_traz_metricas_e_passos(self, client: TestClient, criar_profissional, auth_headers, monkeypatch):
        _desligar_ia(monkeypatch)
        eu = criar_profissional(nome="Eu", bio="", skills=json.dumps([]), cidade="")
        criar_profissional(nome="Sugestao")

        resp = client.get(f"/api/dashboard/{eu.id}", headers=auth_headers(eu.id))
        assert resp.status_code == 200
        data = resp.json()

        assert data["profissional"]["id"] == eu.id
        assert data["matches_pendentes"] == 0
        assert len(data["sugestoes"]) >= 1
        # Perfil incompleto gera orientacoes de proximo passo
        assert any("bio" in p.lower() for p in data["proximos_passos"])

    def test_dashboard_de_outro_403(self, client: TestClient, criar_profissional, auth_headers):
        eu = criar_profissional()
        outro = criar_profissional()
        resp = client.get(f"/api/dashboard/{outro.id}", headers=auth_headers(eu.id))
        assert resp.status_code == 403

    def test_dashboard_sem_token_401(self, client: TestClient, criar_profissional):
        eu = criar_profissional()
        resp = client.get(f"/api/dashboard/{eu.id}")
        assert resp.status_code == 401


class TestNotificacoes:
    def test_cadastro_gera_notificacao_de_boas_vindas(self, client: TestClient):
        resp = client.post(
            "/api/profissionais",
            json={"nome": "Novato", "email": "novato@teste.com", "senha": "senha123"},
        )
        pid = resp.json()["id"]

        login = client.post("/api/auth/login", json={"email": "novato@teste.com", "senha": "senha123"})
        token = login.json()["access_token"]

        resp = client.get(
            f"/api/notificacoes?profissional_id={pid}",
            headers={"Authorization": f"Bearer {token}"},
        )
        data = resp.json()
        assert data["nao_lidas"] == 1
        assert data["itens"][0]["tipo"] == "boas_vindas"

    def test_marcar_notificacao_como_lida(self, client: TestClient, criar_profissional, auth_headers):
        p = criar_profissional()
        client.patch(f"/api/profissionais/{p.id}", json={"bio": "x"}, headers=auth_headers(p.id))

        from app.core.database import SessionLocal
        from app.api.notificacoes import criar_notificacao

        db: Session = SessionLocal()
        n = criar_notificacao(db, p.id, "teste", "Titulo")
        db.commit()
        nid = n.id
        db.close()

        resp = client.patch(f"/api/notificacoes/{nid}/lida", headers=auth_headers(p.id))
        assert resp.status_code == 200
        assert resp.json()["lida"] is True

        client.post(f"/api/notificacoes/marcar-todas-lidas?profissional_id={p.id}", headers=auth_headers(p.id))
        resumo = client.get(f"/api/notificacoes?profissional_id={p.id}", headers=auth_headers(p.id)).json()
        assert resumo["nao_lidas"] == 0

    def test_notificacao_de_outro_usuario_403(self, client: TestClient, criar_profissional, auth_headers):
        dono = criar_profissional()
        intruso = criar_profissional()

        from app.core.database import SessionLocal
        from app.api.notificacoes import criar_notificacao

        db = SessionLocal()
        n = criar_notificacao(db, dono.id, "teste", "Titulo")
        db.commit()
        nid = n.id
        db.close()

        resp = client.patch(f"/api/notificacoes/{nid}/lida", headers=auth_headers(intruso.id))
        assert resp.status_code == 403


# ═══════════════════════════════════════════════════════════════════════════
# Auth / sessao
# ═══════════════════════════════════════════════════════════════════════════

class TestAuthV2:
    def test_login_retorna_perfil_e_expiracao(self, client: TestClient):
        client.post(
            "/api/profissionais",
            json={"nome": "Login Teste", "email": "login@teste.com", "senha": "senha123"},
        )
        resp = client.post("/api/auth/login", json={"email": "login@teste.com", "senha": "senha123"})
        data = resp.json()

        assert data["access_token"]
        assert data["expira_em"] > 0
        assert data["profissional"]["email"] == "login@teste.com"
        assert "senha_hash" not in data["profissional"]

    def test_auth_me_com_token(self, client: TestClient, criar_profissional, auth_headers):
        p = criar_profissional(nome="Eu Mesmo")
        resp = client.get("/api/auth/me", headers=auth_headers(p.id))
        assert resp.status_code == 200
        assert resp.json()["id"] == p.id

    def test_auth_me_sem_token_401(self, client: TestClient):
        assert client.get("/api/auth/me").status_code == 401

    def test_token_invalido_401(self, client: TestClient):
        resp = client.get("/api/auth/me", headers={"Authorization": "Bearer lixo.invalido.aqui"})
        assert resp.status_code == 401

    def test_token_expirado_401(self, client: TestClient, criar_profissional):
        from jose import jwt
        from datetime import datetime, timedelta, timezone
        from app.core.security import SECRET_KEY, ALGORITHM

        p = criar_profissional()
        expirado = jwt.encode(
            {"sub": p.id, "exp": datetime.now(timezone.utc) - timedelta(minutes=5)},
            SECRET_KEY,
            algorithm=ALGORITHM,
        )
        resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {expirado}"})
        assert resp.status_code == 401

    def test_login_normaliza_email(self, client: TestClient):
        client.post(
            "/api/profissionais",
            json={"nome": "Case Teste", "email": "Maiusculo@Teste.com", "senha": "senha123"},
        )
        resp = client.post("/api/auth/login", json={"email": "maiusculo@teste.com", "senha": "senha123"})
        assert resp.status_code == 200

    def test_login_senha_errada_401(self, client: TestClient, criar_profissional):
        criar_profissional(email="x@teste.com")
        resp = client.post("/api/auth/login", json={"email": "x@teste.com", "senha": "errada"})
        assert resp.status_code == 401


# ═══════════════════════════════════════════════════════════════════════════
# Stats e health
# ═══════════════════════════════════════════════════════════════════════════

class TestStatsEHealth:
    def test_stats_publicas(self, client: TestClient, criar_profissional, monkeypatch):
        _desligar_ia(monkeypatch)
        criar_profissional(skills=json.dumps(["Python"]), cidade="Natal")
        criar_profissional(skills=json.dumps(["Python", "React"]), cidade="Natal")

        resp = client.get("/api/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["profissionais"] == 2
        assert data["cidades"] == 1
        assert data["skills_top"][0] == "Python"
        assert data["modo_ia"] in ("gemini", "heuristica")

    def test_health_detalhado(self, client: TestClient):
        resp = client.get("/api/health/detalhado")
        assert resp.status_code == 200
        data = resp.json()
        assert data["database"]["ok"] is True
        assert data["ia"]["provider"] == "google-gemini"
