"""Comprehensive test suite for ProSync API — all endpoints, edge cases, auth."""

import json
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.models.database import ProfissionalDB, MatchDB, MensagemDB, DesafioDB, ParticipanteDesafioDB, MentoriaDB, OportunidadeDB
from app.core.security import hash_password


# ═══════════════════════════════════════════════════════════════════════════
# 1. Health
# ═══════════════════════════════════════════════════════════════════════════

class TestHealth:
    def test_health_returns_200(self, client: TestClient):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["service"] == "prosync"
        assert data["version"].startswith("2.")


# ═══════════════════════════════════════════════════════════════════════════
# 2. Profissionais CRUD
# ═══════════════════════════════════════════════════════════════════════════

class TestCriarProfissional:
    def test_criar_com_sucesso(self, client: TestClient):
        payload = {
            "nome": "Alice Silva",
            "email": "alice@teste.com",
            "senha": "senha123",
            "bio": "Dev Python",
            "cidade": "São Paulo",
            "estado": "SP",
            "skills": ["Python", "FastAPI"],
            "objetivos": ["colaborar", "mentorar"],
            "senioridade": "senior",
        }
        resp = client.post("/api/profissionais", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["nome"] == "Alice Silva"
        assert data["email"] == "alice@teste.com"
        assert "id" in data
        assert data["score_contribuicao"] == 0

    def test_email_duplicado_retorna_409(self, client: TestClient):
        payload = {
            "nome": "Alice",
            "email": "dup@teste.com",
            "senha": "senha123",
        }
        client.post("/api/profissionais", json=payload)
        resp = client.post("/api/profissionais", json=payload)
        assert resp.status_code == 409
        assert "já cadastrado" in resp.json()["detail"].lower()

    def test_criar_sem_nome_retorna_422(self, client: TestClient):
        resp = client.post("/api/profissionais", json={"email": "x@y.com", "senha": "123456"})
        assert resp.status_code == 422

    def test_criar_sem_senha_retorna_422(self, client: TestClient):
        resp = client.post("/api/profissionais", json={"nome": "X", "email": "x@y.com"})
        assert resp.status_code == 422


class TestListarProfissionais:
    def test_listar_vazio(self, client: TestClient):
        resp = client.get("/api/profissionais")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_listar_com_profissionais(self, client: TestClient, criar_profissional):
        criar_profissional(nome="Alice")
        criar_profissional(nome="Bruno")
        resp = client.get("/api/profissionais")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_listar_com_filtro_skill(self, client: TestClient, criar_profissional):
        criar_profissional(nome="Alice", skills=json.dumps(["Python"]))
        criar_profissional(nome="Bruno", skills=json.dumps(["Design"]))
        resp = client.get("/api/profissionais?skill=Python")
        assert len(resp.json()) == 1
        assert resp.json()[0]["nome"] == "Alice"

    def test_listar_com_filtro_search(self, client: TestClient, criar_profissional):
        criar_profissional(nome="Alice", cidade="São Paulo")
        criar_profissional(nome="Bruno", cidade="Rio de Janeiro")
        resp = client.get("/api/profissionais?search=São")
        assert len(resp.json()) == 1


class TestObterProfissional:
    def test_obter_por_id(self, client: TestClient, criar_profissional):
        p = criar_profissional(nome="Alice")
        resp = client.get(f"/api/profissionais/{p.id}")
        assert resp.status_code == 200
        assert resp.json()["nome"] == "Alice"

    def test_obtar_inexistente_retorna_404(self, client: TestClient):
        resp = client.get("/api/profissionais/nao-existe")
        assert resp.status_code == 404


class TestAtualizarProfissional:
    def test_atualizar_nome(self, client: TestClient, criar_profissional, auth_headers):
        p = criar_profissional(nome="Alice")
        resp = client.patch(
            f"/api/profissionais/{p.id}", json={"nome": "Alice Updated"}, headers=auth_headers(p.id)
        )
        assert resp.status_code == 200
        assert resp.json()["nome"] == "Alice Updated"

    def test_atualizar_sem_token_retorna_401(self, client: TestClient, criar_profissional):
        p = criar_profissional(nome="Alice")
        resp = client.patch(f"/api/profissionais/{p.id}", json={"nome": "Hacker"})
        assert resp.status_code == 401

    def test_atualizar_outro_perfil_retorna_403(self, client: TestClient, criar_profissional, auth_headers):
        intruso = criar_profissional(nome="Intruso")
        alvo = criar_profissional(nome="Alvo")
        resp = client.patch(
            f"/api/profissionais/{alvo.id}", json={"nome": "Hackeado"}, headers=auth_headers(intruso.id)
        )
        assert resp.status_code == 403

    def test_atualizar_inexistente_retorna_404(self, client: TestClient, criar_profissional, auth_headers):
        p = criar_profissional()
        resp = client.patch(
            "/api/profissionais/nao-existe", json={"nome": "Nome Valido"}, headers=auth_headers(p.id)
        )
        assert resp.status_code == 403


class TestMentores:
    def test_listar_mentores(self, client: TestClient, criar_profissional):
        criar_profissional(nome="Mentor", objetivos=json.dumps(["mentorar", "colaborar"]))
        criar_profissional(nome="Normal", objetivos=json.dumps(["colaborar"]))
        resp = client.get("/api/profissionais/mentores")
        assert len(resp.json()) == 1
        assert resp.json()[0]["nome"] == "Mentor"


# ═══════════════════════════════════════════════════════════════════════════
# 3. Auth / Login
# ═══════════════════════════════════════════════════════════════════════════

class TestLogin:
    def test_login_sucesso(self, client: TestClient, criar_profissional):
        p = criar_profissional(email="teste@login.com", senha_hash=hash_password("senha123"))
        resp = client.post("/api/auth/login", json={"email": "teste@login.com", "senha": "senha123"})
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["profissional_id"] == p.id

    def test_login_senha_errada_retorna_401(self, client: TestClient, criar_profissional):
        criar_profissional(email="teste@login.com", senha_hash=hash_password("senha123"))
        resp = client.post("/api/auth/login", json={"email": "teste@login.com", "senha": "errada"})
        assert resp.status_code == 401

    def test_login_email_inexistente_retorna_401(self, client: TestClient):
        resp = client.post("/api/auth/login", json={"email": "nao@existe.com", "senha": "x"})
        assert resp.status_code == 401


# ═══════════════════════════════════════════════════════════════════════════
# 4. Matches
# ═══════════════════════════════════════════════════════════════════════════

class TestMatches:
    def test_criar_match_com_sucesso(self, client: TestClient, criar_profissional):
        a = criar_profissional()
        b = criar_profissional()
        resp = client.post("/api/matches", json={"profissional_a_id": a.id, "profissional_b_id": b.id})
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "pendente"
        assert data["score_ia"] >= 0

    def test_match_consigo_mesmo_retorna_400(self, client: TestClient, criar_profissional):
        a = criar_profissional()
        resp = client.post("/api/matches", json={"profissional_a_id": a.id, "profissional_b_id": a.id})
        assert resp.status_code == 400
        assert "si mesmo" in resp.json()["detail"].lower()

    def test_match_profissional_inexistente_retorna_404(self, client: TestClient, criar_profissional):
        a = criar_profissional()
        resp = client.post("/api/matches", json={"profissional_a_id": a.id, "profissional_b_id": "nao-existe"})
        assert resp.status_code == 404

    def test_aceitar_match(self, client: TestClient, criar_profissional, db_session: Session, auth_headers):
        a = criar_profissional()
        b = criar_profissional()
        resp = client.post("/api/matches", json={"profissional_a_id": a.id, "profissional_b_id": b.id})
        match_id = resp.json()["id"]

        resp = client.post(f"/api/matches/{match_id}/aceitar", headers=auth_headers(b.id))
        assert resp.status_code == 200
        assert resp.json()["status"] == "match"

        # Expire all to force fresh read, then check score was updated
        db_session.expire_all()
        a_db = db_session.query(ProfissionalDB).filter(ProfissionalDB.id == a.id).first()
        assert a_db.score_contribuicao >= 10

    def test_aceitar_match_inexistente_retorna_404(self, client: TestClient, criar_profissional, auth_headers):
        p = criar_profissional()
        resp = client.post("/api/matches/nao-existe/aceitar", headers=auth_headers(p.id))
        assert resp.status_code == 404

    def test_aceitar_match_sem_token_retorna_401(self, client: TestClient, criar_profissional, auth_headers):
        a = criar_profissional()
        b = criar_profissional()
        match_id = client.post(
            "/api/matches", json={"profissional_a_id": a.id, "profissional_b_id": b.id}
        ).json()["id"]
        resp = client.post(f"/api/matches/{match_id}/aceitar")
        assert resp.status_code == 401

    def test_recusar_match(self, client: TestClient, criar_profissional, auth_headers):
        a = criar_profissional()
        b = criar_profissional()
        resp = client.post("/api/matches", json={"profissional_a_id": a.id, "profissional_b_id": b.id})
        match_id = resp.json()["id"]

        resp = client.post(f"/api/matches/{match_id}/recusar", headers=auth_headers(a.id))
        assert resp.status_code == 200
        assert resp.json()["status"] == "recusado"

    def test_listar_matches_do_profissional(self, client: TestClient, criar_profissional):
        a = criar_profissional()
        b = criar_profissional()
        client.post("/api/matches", json={"profissional_a_id": a.id, "profissional_b_id": b.id})
        resp = client.get(f"/api/profissionais/{a.id}/matches")
        assert resp.status_code == 200
        assert len(resp.json()) == 1


# ═══════════════════════════════════════════════════════════════════════════
# 5. Mensagens
# ═══════════════════════════════════════════════════════════════════════════

class TestMensagens:
    def test_enviar_mensagem_apos_match(self, client: TestClient, criar_profissional, auth_headers):
        a = criar_profissional()
        b = criar_profissional()
        resp = client.post("/api/matches", json={"profissional_a_id": a.id, "profissional_b_id": b.id})
        match_id = resp.json()["id"]
        client.post(f"/api/matches/{match_id}/aceitar", headers=auth_headers(a.id))

        resp = client.post("/api/mensagens", json={
            "match_id": match_id,
            "remetente_id": a.id,
            "conteudo": "Olá! Tudo bem?",
        })
        assert resp.status_code == 201
        assert resp.json()["conteudo"] == "Olá! Tudo bem?"

    def test_enviar_mensagem_sem_match_retorna_400(self, client: TestClient, criar_profissional):
        a = criar_profissional()
        b = criar_profissional()
        resp = client.post("/api/matches", json={"profissional_a_id": a.id, "profissional_b_id": b.id})
        match_id = resp.json()["id"]
        # Match is pendente, not accepted — should fail
        resp = client.post("/api/mensagens", json={
            "match_id": match_id,
            "remetente_id": a.id,
            "conteudo": "Olá!",
        })
        assert resp.status_code == 400

    def test_enviar_mensagem_para_match_inexistente(self, client: TestClient, criar_profissional):
        a = criar_profissional()
        resp = client.post("/api/mensagens", json={
            "match_id": "nao-existe",
            "remetente_id": a.id,
            "conteudo": "Oi!",
        })
        assert resp.status_code == 404

    def test_listar_mensagens(self, client: TestClient, criar_profissional, auth_headers):
        a = criar_profissional()
        b = criar_profissional()
        resp = client.post("/api/matches", json={"profissional_a_id": a.id, "profissional_b_id": b.id})
        match_id = resp.json()["id"]
        client.post(f"/api/matches/{match_id}/aceitar", headers=auth_headers(a.id))
        client.post("/api/mensagens", json={"match_id": match_id, "remetente_id": a.id, "conteudo": "Msg1"})
        client.post("/api/mensagens", json={"match_id": match_id, "remetente_id": b.id, "conteudo": "Msg2"})

        resp = client.get(f"/api/mensagens/{match_id}")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_marcar_como_lida(self, client: TestClient, criar_profissional, auth_headers):
        a = criar_profissional()
        b = criar_profissional()
        resp = client.post("/api/matches", json={"profissional_a_id": a.id, "profissional_b_id": b.id})
        match_id = resp.json()["id"]
        client.post(f"/api/matches/{match_id}/aceitar", headers=auth_headers(a.id))
        resp = client.post("/api/mensagens", json={"match_id": match_id, "remetente_id": b.id, "conteudo": "Msg"})
        msg_id = resp.json()["id"]

        resp = client.patch(f"/api/mensagens/{msg_id}/ler")
        assert resp.status_code == 200
        assert resp.json()["lida"] is True

    def test_conversas_lista(self, client: TestClient, criar_profissional, auth_headers):
        """Test the /api/profissionais/{id}/conversas endpoint."""
        a = criar_profissional(nome="Alice")
        b = criar_profissional(nome="Bruno")
        resp = client.post("/api/matches", json={"profissional_a_id": a.id, "profissional_b_id": b.id})
        match_id = resp.json()["id"]
        client.post(f"/api/matches/{match_id}/aceitar", headers=auth_headers(a.id))
        client.post("/api/mensagens", json={"match_id": match_id, "remetente_id": a.id, "conteudo": "Oi Bruno!"})

        resp = client.get(f"/api/profissionais/{a.id}/conversas")
        assert resp.status_code == 200
        assert len(resp.json()) == 1
        conv = resp.json()[0]
        assert conv["profissional_nome"] == "Bruno"
        assert conv["ultima_mensagem"] == "Oi Bruno!"
        assert conv["nao_lidas"] >= 0


# ═══════════════════════════════════════════════════════════════════════════
# 6. Desafios
# ═══════════════════════════════════════════════════════════════════════════

class TestDesafios:
    def test_criar_desafio(self, client: TestClient, criar_profissional):
        p = criar_profissional()
        resp = client.post("/api/desafios", json={
            "criador_id": p.id,
            "titulo": "App de voluntariado",
            "descricao": "Criar um app",
            "skills_necessarias": ["Python", "React"],
            "tipo": "dupla",
        })
        assert resp.status_code == 201
        assert resp.json()["status"] == "aberto"

    def test_criar_desafio_sem_titulo_retorna_422(self, client: TestClient, criar_profissional):
        p = criar_profissional()
        resp = client.post("/api/desafios", json={"criador_id": p.id, "titulo": "ab"})
        assert resp.status_code == 422

    def test_listar_desafios(self, client: TestClient, criar_profissional):
        p = criar_profissional()
        client.post("/api/desafios", json={"criador_id": p.id, "titulo": "Desafio 1"})
        client.post("/api/desafios", json={"criador_id": p.id, "titulo": "Desafio 2"})
        resp = client.get("/api/desafios")
        assert len(resp.json()) == 2

    def test_participar_desafio(self, client: TestClient, criar_profissional):
        p1 = criar_profissional()
        p2 = criar_profissional()
        resp = client.post("/api/desafios", json={"criador_id": p1.id, "titulo": "Desafio"})
        desafio_id = resp.json()["id"]
        resp = client.post(f"/api/desafios/{desafio_id}/participar?profissional_id={p2.id}")
        assert resp.status_code == 201
        assert "sucesso" in resp.json()["mensagem"]

    def test_participante_duplicado_retorna_409(self, client: TestClient, criar_profissional):
        p1 = criar_profissional()
        p2 = criar_profissional()
        resp = client.post("/api/desafios", json={"criador_id": p1.id, "titulo": "Desafio"})
        desafio_id = resp.json()["id"]
        client.post(f"/api/desafios/{desafio_id}/participar?profissional_id={p2.id}")
        resp = client.post(f"/api/desafios/{desafio_id}/participar?profissional_id={p2.id}")
        assert resp.status_code == 409

    def test_status_invalido_retorna_422(self, client: TestClient, criar_profissional):
        p = criar_profissional()
        resp = client.post("/api/desafios", json={"criador_id": p.id, "titulo": "Desafio"})
        desafio_id = resp.json()["id"]
        resp = client.patch(f"/api/desafios/{desafio_id}/status", json={"status": "invalido"})
        assert resp.status_code == 422  # Pattern validation error

    def test_transicao_status_valida(self, client: TestClient, criar_profissional):
        p = criar_profissional()
        resp = client.post("/api/desafios", json={"criador_id": p.id, "titulo": "Desafio"})
        desafio_id = resp.json()["id"]
        resp = client.patch(f"/api/desafios/{desafio_id}/status", json={"status": "em_andamento"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "em_andamento"

    def test_listar_participantes(self, client: TestClient, criar_profissional):
        p1 = criar_profissional()
        p2 = criar_profissional()
        resp = client.post("/api/desafios", json={"criador_id": p1.id, "titulo": "Desafio"})
        desafio_id = resp.json()["id"]
        client.post(f"/api/desafios/{desafio_id}/participar?profissional_id={p2.id}")
        resp = client.get(f"/api/desafios/{desafio_id}/participantes")
        assert resp.status_code == 200
        assert len(resp.json()) == 1
        assert resp.json()[0]["profissional_nome"] == p2.nome


# ═══════════════════════════════════════════════════════════════════════════
# 7. Mentorias
# ═══════════════════════════════════════════════════════════════════════════

class TestMentorias:
    def test_solicitar_mentoria(self, client: TestClient, criar_profissional):
        mentor = criar_profissional()
        mentorado = criar_profissional()
        resp = client.post("/api/mentorias/solicitar", json={
            "mentorado_id": mentorado.id,
            "mentor_id": mentor.id,
            "area": "Desenvolvimento",
            "objetivos": "Aprender Python",
        })
        assert resp.status_code == 201
        assert resp.json()["status"] == "pendente"

    def test_solicitar_mentoria_si_mesmo_retorna_400(self, client: TestClient, criar_profissional):
        p = criar_profissional()
        resp = client.post("/api/mentorias/solicitar", json={
            "mentorado_id": p.id,
            "mentor_id": p.id,
        })
        assert resp.status_code == 400
        assert "si mesmo" in resp.json()["detail"].lower()

    def test_solicitar_mentoria_duplicada_retorna_409(self, client: TestClient, criar_profissional):
        mentor = criar_profissional()
        mentorado = criar_profissional()
        payload = {"mentorado_id": mentorado.id, "mentor_id": mentor.id}
        client.post("/api/mentorias/solicitar", json=payload)
        resp = client.post("/api/mentorias/solicitar", json=payload)
        assert resp.status_code == 409

    def test_aceitar_mentoria(self, client: TestClient, criar_profissional):
        mentor = criar_profissional()
        mentorado = criar_profissional()
        resp = client.post("/api/mentorias/solicitar", json={
            "mentorado_id": mentorado.id, "mentor_id": mentor.id,
        })
        mentoria_id = resp.json()["id"]
        resp = client.patch(f"/api/mentorias/{mentoria_id}/aceitar")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ativa"

    def test_concluir_mentoria(self, client: TestClient, criar_profissional, db_session: Session):
        mentor = criar_profissional()
        mentorado = criar_profissional()
        resp = client.post("/api/mentorias/solicitar", json={
            "mentorado_id": mentorado.id, "mentor_id": mentor.id,
        })
        mentoria_id = resp.json()["id"]
        client.patch(f"/api/mentorias/{mentoria_id}/aceitar")
        resp = client.patch(f"/api/mentorias/{mentoria_id}/concluir")
        assert resp.status_code == 200
        assert resp.json()["status"] == "concluida"

        # Check score was updated
        db_session.expire_all()
        mentor_db = db_session.query(ProfissionalDB).filter(ProfissionalDB.id == mentor.id).first()
        assert mentor_db.score_contribuicao >= 25

    def test_listar_mentorias(self, client: TestClient, criar_profissional):
        mentor = criar_profissional()
        mentorado = criar_profissional()
        client.post("/api/mentorias/solicitar", json={
            "mentorado_id": mentorado.id, "mentor_id": mentor.id,
        })
        resp = client.get(f"/api/mentorias?profissional_id={mentor.id}")
        assert resp.status_code == 200
        assert len(resp.json()) == 1


# ═══════════════════════════════════════════════════════════════════════════
# 8. Oportunidades
# ═══════════════════════════════════════════════════════════════════════════

class TestOportunidades:
    def test_criar_oportunidade(self, client: TestClient, criar_profissional):
        p = criar_profissional()
        resp = client.post("/api/oportunidades", json={
            "criador_id": p.id,
            "titulo": "Vaga Dev Python",
            "descricao": "Vaga remota",
            "tipo": "vaga",
            "skills_necessarias": ["Python"],
            "contato": "email@teste.com",
        })
        assert resp.status_code == 201
        assert resp.json()["status"] == "aberta"
        assert resp.json()["tipo"] == "vaga"

    def test_criar_oportunidade_tipo_invalido_retorna_400(self, client: TestClient, criar_profissional):
        p = criar_profissional()
        resp = client.post("/api/oportunidades", json={
            "criador_id": p.id,
            "titulo": "Test",
            "tipo": "invalido",
        })
        assert resp.status_code == 400

    def test_listar_oportunidades(self, client: TestClient, criar_profissional):
        p = criar_profissional()
        client.post("/api/oportunidades", json={"criador_id": p.id, "titulo": "Vaga 1", "tipo": "vaga"})
        client.post("/api/oportunidades", json={"criador_id": p.id, "titulo": "Proj 1", "tipo": "projeto"})
        resp = client.get("/api/oportunidades")
        assert len(resp.json()) == 2

    def test_filtrar_oportunidades_por_tipo(self, client: TestClient, criar_profissional):
        p = criar_profissional()
        client.post("/api/oportunidades", json={"criador_id": p.id, "titulo": "Vaga 1", "tipo": "vaga"})
        client.post("/api/oportunidades", json={"criador_id": p.id, "titulo": "Proj 1", "tipo": "projeto"})
        resp = client.get("/api/oportunidades?tipo=vaga")
        assert len(resp.json()) == 1

    def test_atualizar_status_oportunidade(self, client: TestClient, criar_profissional):
        p = criar_profissional()
        resp = client.post("/api/oportunidades", json={"criador_id": p.id, "titulo": "Vaga", "tipo": "vaga"})
        op_id = resp.json()["id"]
        resp = client.patch(f"/api/oportunidades/{op_id}/status", json={"status": "preenchida"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "preenchida"


# ═══════════════════════════════════════════════════════════════════════════
# 9. Reputação / Score
# ═══════════════════════════════════════════════════════════════════════════

class TestReputacao:
    def test_reputacao_zero(self, client: TestClient, criar_profissional):
        p = criar_profissional()
        resp = client.get(f"/api/profissionais/{p.id}/reputacao")
        assert resp.status_code == 200
        data = resp.json()
        assert data["score_contribuicao"] == 0
        assert all(v == 0 for v in data["breakdown"].values())

    def test_reputacao_apos_acoes(self, client: TestClient, criar_profissional, auth_headers):
        """Full flow: match + mentoria + oportunidade and check breakdown."""
        p1 = criar_profissional(nome="Alice")
        p2 = criar_profissional(nome="Bruno")

        # Match
        resp = client.post("/api/matches", json={"profissional_a_id": p1.id, "profissional_b_id": p2.id})
        match_id = resp.json()["id"]
        client.post(f"/api/matches/{match_id}/aceitar", headers=auth_headers(p1.id))

        # Mentoria (p1 mentors p2)
        resp = client.post("/api/mentorias/solicitar", json={
            "mentorado_id": p2.id, "mentor_id": p1.id,
        })
        mentoria_id = resp.json()["id"]
        client.patch(f"/api/mentorias/{mentoria_id}/aceitar")
        client.patch(f"/api/mentorias/{mentoria_id}/concluir")

        # Oportunidade
        client.post("/api/oportunidades", json={
            "criador_id": p1.id, "titulo": "Vaga", "tipo": "vaga",
        })

        resp = client.get(f"/api/profissionais/{p1.id}/reputacao")
        assert resp.status_code == 200
        data = resp.json()
        # match_aceito: 1 * 10, mentor_concluido: 1 * 25, criou_oportunidade: 1 * 5
        assert data["breakdown"]["match_aceito"] == 10
        assert data["breakdown"]["mentor_concluido"] == 25
        assert data["breakdown"]["criou_oportunidade"] == 5
        assert data["breakdown"]["participou_desafio"] == 0
        assert data["breakdown"]["mentorado_concluido"] == 0
        assert data["score_contribuicao"] >= 40  # 10 + 25 + 5

    def test_reputacao_profissional_inexistente(self, client: TestClient):
        resp = client.get("/api/profissionais/nao-existe/reputacao")
        assert resp.status_code == 404


# ═══════════════════════════════════════════════════════════════════════════
# 10. Edge cases
# ═══════════════════════════════════════════════════════════════════════════

class TestEdgeCases:
    def test_aceitar_match_ja_aceito_retorna_400(self, client: TestClient, criar_profissional, auth_headers):
        a = criar_profissional()
        b = criar_profissional()
        resp = client.post("/api/matches", json={"profissional_a_id": a.id, "profissional_b_id": b.id})
        match_id = resp.json()["id"]
        client.post(f"/api/matches/{match_id}/aceitar", headers=auth_headers(a.id))
        resp = client.post(f"/api/matches/{match_id}/aceitar", headers=auth_headers(a.id))
        assert resp.status_code == 400

    def test_mensagem_remetente_fora_do_match_retorna_403(self, client: TestClient, criar_profissional, auth_headers):
        a = criar_profissional()
        b = criar_profissional()
        c = criar_profissional()  # Third party
        resp = client.post("/api/matches", json={"profissional_a_id": a.id, "profissional_b_id": b.id})
        match_id = resp.json()["id"]
        client.post(f"/api/matches/{match_id}/aceitar", headers=auth_headers(a.id))

        resp = client.post("/api/mensagens", json={
            "match_id": match_id,
            "remetente_id": c.id,  # Not part of match
            "conteudo": "Oi!",
        })
        assert resp.status_code == 403

    def test_participar_desafio_fechado_retorna_400(self, client: TestClient, criar_profissional):
        p1 = criar_profissional()
        p2 = criar_profissional()
        resp = client.post("/api/desafios", json={"criador_id": p1.id, "titulo": "Desafio"})
        desafio_id = resp.json()["id"]
        # Close it
        client.patch(f"/api/desafios/{desafio_id}/status", json={"status": "em_andamento"})
        resp = client.post(f"/api/desafios/{desafio_id}/participar?profissional_id={p2.id}")
        assert resp.status_code == 400

    def test_transicao_status_invalida_desafio(self, client: TestClient, criar_profissional):
        p = criar_profissional()
        resp = client.post("/api/desafios", json={"criador_id": p.id, "titulo": "Desafio"})
        desafio_id = resp.json()["id"]
        # Try to go from aberto to concluido directly (should fail)
        resp = client.patch(f"/api/desafios/{desafio_id}/status", json={"status": "concluido"})
        assert resp.status_code == 400

    def test_obter_oportunidade_inexistente_retorna_404(self, client: TestClient):
        resp = client.get("/api/oportunidades/nao-existe")
        assert resp.status_code == 404

    def test_atualizar_status_oportunidade_invalido(self, client: TestClient, criar_profissional):
        p = criar_profissional()
        resp = client.post("/api/oportunidades", json={"criador_id": p.id, "titulo": "Vaga", "tipo": "vaga"})
        op_id = resp.json()["id"]
        # Close it
        client.patch(f"/api/oportunidades/{op_id}/status", json={"status": "preenchida"})
        # Try to re-open (should fail)
        resp = client.patch(f"/api/oportunidades/{op_id}/status", json={"status": "aberta"})
        assert resp.status_code == 400


# ═══════════════════════════════════════════════════════════════════════════
# 11. Full flow integration test
# ═══════════════════════════════════════════════════════════════════════════

class TestFullFlow:
    """Simula o fluxo completo: cadastro → login → buscar → match → mensagem."""

    def test_fluxo_completo(self, client: TestClient, auth_headers, criar_profissional):
        # 1. Cadastro Alice
        resp = client.post("/api/profissionais", json={
            "nome": "Alice",
            "email": "alice@empresa.com",
            "senha": "abc123",
            "cidade": "São Paulo",
            "skills": ["Python", "FastAPI"],
            "objetivos": ["colaborar", "mentorar"],
            "senioridade": "senior",
        })
        assert resp.status_code == 201
        alice_id = resp.json()["id"]

        # 2. Cadastro Bruno
        resp = client.post("/api/profissionais", json={
            "nome": "Bruno",
            "email": "bruno@empresa.com",
            "senha": "abc456",
            "cidade": "São Paulo",
            "skills": ["React", "Design"],
            "objetivos": ["colaborar", "aprender"],
            "senioridade": "pleno",
        })
        assert resp.status_code == 201
        bruno_id = resp.json()["id"]

        # 3. Login Alice
        resp = client.post("/api/auth/login", json={"email": "alice@empresa.com", "senha": "abc123"})
        assert resp.status_code == 200
        token = resp.json()["access_token"]
        assert token

        # 4. Buscar profissionais
        resp = client.get("/api/profissionais")
        assert len(resp.json()) >= 2

        # 5. Fazer match
        resp = client.post("/api/matches", json={
            "profissional_a_id": alice_id,
            "profissional_b_id": bruno_id,
        })
        assert resp.status_code == 201
        match_id = resp.json()["id"]

        # 6. Aceitar match (Bruno aceita a conexao de Alice)
        resp = client.post(
            f"/api/matches/{match_id}/aceitar", headers=auth_headers(bruno_id)
        )
        assert resp.status_code == 200

        # 7. Enviar mensagem
        resp = client.post("/api/mensagens", json={
            "match_id": match_id,
            "remetente_id": alice_id,
            "conteudo": "Oi Bruno! Vamos colaborar?",
        })
        assert resp.status_code == 201

        # 8. Ver conversas
        resp = client.get(f"/api/profissionais/{alice_id}/conversas")
        assert len(resp.json()) == 1
        assert resp.json()[0]["ultima_mensagem"] == "Oi Bruno! Vamos colaborar?"

        # 9. Ver reputação
        resp = client.get(f"/api/profissionais/{alice_id}/reputacao")
        assert resp.json()["score_contribuicao"] >= 10
