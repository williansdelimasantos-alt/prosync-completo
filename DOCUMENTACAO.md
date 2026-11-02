# ProSync — Documentação da API

Plataforma de conexão profissional para remotos brasileiros.

**Base URL (desenvolvimento):** `http://localhost:8015`
**Stack:** FastAPI + SQLAlchemy + SQLite + JWT

---

## Índice

1. [Visão Geral](#1-visão-geral)
2. [Endpoints](#2-endpoints)
   - [Health Check](#21-health-check)
   - [Profissionais CRUD](#22-profissionais-crud)
   - [Autenticação (JWT)](#23-autenticação-jwt)
   - [Matches](#24-matches)
   - [Mensagens / Chat](#25-mensagens--chat)
   - [Desafios Colaborativos](#26-desafios-colaborativos)
   - [Mentorias](#27-mentorias)
   - [Mural de Oportunidades](#28-mural-de-oportunidades)
   - [Reputação / Score](#29-reputação--score)
3. [Fluxo de Uso](#3-fluxo-de-uso)
4. [Instruções de Deploy](#4-instruções-de-deploy)
5. [Testes](#5-testes)

---

## 1. Visão Geral

ProSync permite que profissionais remotos brasileiros se conectem com base em habilidades complementares. O sistema usa um algoritmo de compatibilidade local (com fallback para API Gemini) para sugerir matches inteligentes.

### Convenções

- Todos os endpoints que recebem body usam `Content-Type: application/json`.
- Respostas de erro seguem o formato `{"detail": "mensagem de erro"}`.
- Códigos HTTP: `200` sucesso, `201` criado, `400` requisição inválida, `401` não autorizado, `403` proibido, `404` não encontrado, `409` conflito, `422` erro de validação.

---

## 2. Endpoints

### 2.1. Health Check

#### `GET /api/health`

Verifica se o servidor está rodando.

```bash
curl -s http://localhost:8015/api/health | python3 -m json.tool
```

**Resposta:**
```json
{
  "status": "ok",
  "service": "prosync",
  "version": "0.1.0"
}
```

---

### 2.2. Profissionais CRUD

#### `POST /api/profissionais` — Cadastrar profissional

```bash
curl -s -X POST http://localhost:8015/api/profissionais \
  -H "Content-Type: application/json" \
  -d '{
    "nome": "Alice Silva",
    "email": "alice@exemplo.com",
    "senha": "minha-senha-segura",
    "bio": "Desenvolvedora Python apaixonada por IA",
    "cidade": "São Paulo",
    "estado": "SP",
    "skills": ["Python", "FastAPI", "React", "PostgreSQL"],
    "objetivos": ["colaborar", "mentorar"],
    "senioridade": "senior",
    "disponibilidade": ["segunda-feira", "quarta-feira"],
    "areas_interesse": ["Tech", "Educação"]
  }' | python3 -m json.tool
```

**Campos obrigatórios:** `nome` (min 2), `email`, `senha` (min 6).
**Resposta:** `201 Created` com o perfil criado.

---

#### `GET /api/profissionais` — Listar profissionais

```bash
# Listar todos
curl -s http://localhost:8015/api/profissionais | python3 -m json.tool

# Com filtros
curl -s "http://localhost:8015/api/profissionais?skill=Python&cidade=São Paulo&senioridade=senior&search=Alice&limit=10&offset=0" | python3 -m json.tool
```

**Parâmetros opcionais:** `skill`, `cidade`, `senioridade`, `search` (busca em nome/bio/cidade/skills), `limit` (1-200, default 50), `offset` (default 0).

**Resposta:** Array de `ProfissionalCard` (sem email).

---

#### `GET /api/profissionais/{id}` — Obter perfil completo

```bash
curl -s http://localhost:8015/api/profissionais/ID_DO_PROFISSIONAL | python3 -m json.tool
```

**Resposta:** `ProfissionalOut` com email.

---

#### `PATCH /api/profissionais/{id}` — Atualizar perfil

```bash
curl -s -X PATCH http://localhost:8015/api/profissionais/ID_DO_PROFISSIONAL \
  -H "Content-Type: application/json" \
  -d '{"nome": "Alice Souza", "bio": "Dev Full-stack"}' | python3 -m json.tool
```

Apenas campos enviados serão atualizados.

---

#### `GET /api/profissionais/mentores` — Listar mentores disponíveis

```bash
curl -s http://localhost:8015/api/profissionais/mentores | python3 -m json.tool

# Filtrar por skill
curl -s "http://localhost:8015/api/profissionais/mentores?skill=Python" | python3 -m json.tool
```

Retorna profissionais que têm "mentorar" em seus objetivos.

---

### 2.3. Autenticação (JWT)

#### `POST /api/auth/login` — Login

```bash
curl -s -X POST http://localhost:8015/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "alice@exemplo.com", "senha": "minha-senha-segura"}' | python3 -m json.tool
```

**Resposta:**
```json
{
  "access_token": "eyJ...",
  "token_type": "bearer",
  "profissional_id": "uuid-do-profissional"
}
```

O token JWT expira em 24 horas. Use o `profissional_id` retornado para identificar o usuário logado nas requisições subsequentes.

> **Nota:** O frontend atual gerencia o login via ID do profissional (armazenado em localStorage). A autenticação JWT está implementada para uso futuro em aplicações mobile/third-party.

---

### 2.4. Matches

#### `POST /api/matches` — Sugerir match

```bash
curl -s -X POST http://localhost:8015/api/matches \
  -H "Content-Type: application/json" \
  -d '{
    "profissional_a_id": "ID_ALICE",
    "profissional_b_id": "ID_BRUNO"
  }' | python3 -m json.tool
```

Retorna `201` se criado, ou o match existente se já sugerido anteriormente.
O match inicia com status `"pendente"`.

**Regras:**
- Não é possível criar match consigo mesmo (`400`).
- Profissionais precisam existir (`404`).

---

#### `POST /api/matches/{id}/aceitar` — Aceitar match

```bash
curl -s -X POST http://localhost:8015/api/matches/ID_DO_MATCH/aceitar | python3 -m json.tool
```

Muda status para `"match"` e adiciona **+10 pontos de reputação** para ambos os profissionais.

---

#### `POST /api/matches/{id}/recusar` — Recusar match

```bash
curl -s -X POST http://localhost:8015/api/matches/ID_DO_MATCH/recusar | python3 -m json.tool
```

Muda status para `"recusado"`.

---

#### `GET /api/profissionais/{id}/matches` — Listar matches do profissional

```bash
curl -s http://localhost:8015/api/profissionais/ID_DO_PROFISSIONAL/matches | python3 -m json.tool
```

Retorna todos os matches (pendentes, aceitos, recusados) ordenados do mais recente.

---

### 2.5. Mensagens / Chat

#### `POST /api/mensagens` — Enviar mensagem

```bash
curl -s -X POST http://localhost:8015/api/mensagens \
  -H "Content-Type: application/json" \
  -d '{
    "match_id": "ID_DO_MATCH",
    "remetente_id": "ID_DO_REMETENTE",
    "conteudo": "Olá! Vamos colaborar nesse projeto?"
  }' | python3 -m json.tool
```

**Requisitos:**
- Match precisa estar com status `"match"` (aceito).
- Remetente precisa fazer parte do match.

---

#### `GET /api/mensagens/{match_id}` — Listar mensagens

```bash
curl -s http://localhost:8015/api/mensagens/ID_DO_MATCH | python3 -m json.tool
```

Retorna mensagens ordenadas por data (ascendente).

---

#### `PATCH /api/mensagens/{id}/ler` — Marcar como lida

```bash
curl -s -X PATCH http://localhost:8015/api/mensagens/ID_DA_MSG/ler | python3 -m json.tool
```

---

#### `GET /api/profissionais/{id}/conversas` — Listar conversas

```bash
curl -s http://localhost:8015/api/profissionais/ID_DO_PROFISSIONAL/conversas | python3 -m json.tool
```

Retorna matches com última mensagem, contagem de não lidas e dados do outro profissional.

---

### 2.6. Desafios Colaborativos

#### `POST /api/desafios` — Criar desafio

```bash
curl -s -X POST http://localhost:8015/api/desafios \
  -H "Content-Type: application/json" \
  -d '{
    "criador_id": "ID_DO_CRIADOR",
    "titulo": "App de Voluntariado",
    "descricao": "Criar um MVP de app para conectar voluntários a ONGs",
    "skills_necessarias": ["Python", "React", "UX"],
    "tipo": "dupla",
    "prazo": "2025-12-31T23:59:59"
  }' | python3 -m json.tool
```

**Campos:** `criador_id`, `titulo` (min 3), `descricao`, `skills_necessarias`, `tipo` ("dupla" ou "grupo"), `prazo` (ISO string opcional).
**Status inicial:** `"aberto"`.

---

#### `GET /api/desafios` — Listar desafios

```bash
curl -s "http://localhost:8015/api/desafios?status=aberto&tipo=dupla&skill=React" | python3 -m json.tool
```

**Filtros opcionais:** `status`, `tipo`, `skill`, `limit`, `offset`.

---

#### `GET /api/desafios/{id}` — Obter desafio

```bash
curl -s http://localhost:8015/api/desafios/ID_DO_DESAFIO | python3 -m json.tool
```

---

#### `POST /api/desafios/{id}/participar?profissional_id=ID` — Participar

```bash
curl -s -X POST "http://localhost:8015/api/desafios/ID_DO_DESAFIO/participar?profissional_id=ID_DO_PROFISSIONAL" | python3 -m json.tool
```

Adiciona **+15 pontos de reputação** ao profissional.

---

#### `GET /api/desafios/{id}/participantes` — Listar participantes

```bash
curl -s http://localhost:8015/api/desafios/ID_DO_DESAFIO/participantes | python3 -m json.tool
```

---

#### `PATCH /api/desafios/{id}/status` — Atualizar status

```bash
curl -s -X PATCH http://localhost:8015/api/desafios/ID_DO_DESAFIO/status \
  -H "Content-Type: application/json" \
  -d '{"status": "em_andamento"}' | python3 -m json.tool
```

**Transições válidas:** `aberto → em_andamento → concluido`.

---

### 2.7. Mentorias

#### `POST /api/mentorias/solicitar` — Solicitar mentoria

```bash
curl -s -X POST http://localhost:8015/api/mentorias/solicitar \
  -H "Content-Type: application/json" \
  -d '{
    "mentorado_id": "ID_MENTORADO",
    "mentor_id": "ID_MENTOR",
    "area": "Desenvolvimento Web",
    "objetivos": "Aprender React e boas práticas de frontend"
  }' | python3 -m json.tool
```

**Status inicial:** `"pendente"`.

---

#### `GET /api/mentorias?profissional_id=ID` — Listar mentorias

```bash
curl -s "http://localhost:8015/api/mentorias?profissional_id=ID_DO_PROFISSIONAL" | python3 -m json.tool

# Filtrar por status
curl -s "http://localhost:8015/api/mentorias?profissional_id=ID&status=ativa" | python3 -m json.tool
```

---

#### `PATCH /api/mentorias/{id}/aceitar` — Aceitar mentoria

```bash
curl -s -X PATCH http://localhost:8015/api/mentorias/ID_DA_MENTORIA/aceitar | python3 -m json.tool
```

Muda status para `"ativa"`.

---

#### `PATCH /api/mentorias/{id}/concluir` — Concluir mentoria

```bash
curl -s -X PATCH http://localhost:8015/api/mentorias/ID_DA_MENTORIA/concluir | python3 -m json.tool
```

Adiciona **+25 pontos** para o mentor e **+10 pontos** para o mentorado.

---

### 2.8. Mural de Oportunidades

#### `POST /api/oportunidades` — Criar oportunidade

```bash
curl -s -X POST http://localhost:8015/api/oportunidades \
  -H "Content-Type: application/json" \
  -d '{
    "criador_id": "ID_CRIADOR",
    "titulo": "Vaga para Dev Python Sênior",
    "descricao": "Empresa remota brasileira busca dev Python para equipe de dados",
    "tipo": "vaga",
    "skills_necessarias": ["Python", "SQL", "Machine Learning"],
    "contato": "rh@empresa.com"
  }' | python3 -m json.tool
```

**Tipos válidos:** `"vaga"`, `"projeto"`, `"parceria"`.
Adiciona **+5 pontos de reputação** ao criador.

---

#### `GET /api/oportunidades` — Listar oportunidades

```bash
curl -s "http://localhost:8015/api/oportunidades?tipo=vaga&skill=Python&status=aberta" | python3 -m json.tool
```

**Filtros opcionais:** `tipo`, `skill`, `status`, `limit`, `offset`.

---

#### `GET /api/oportunidades/{id}` — Obter oportunidade

```bash
curl -s http://localhost:8015/api/oportunidades/ID_DA_OPORTUNIDADE | python3 -m json.tool
```

---

#### `PATCH /api/oportunidades/{id}/status` — Atualizar status

```bash
curl -s -X PATCH http://localhost:8015/api/oportunidades/ID_DA_OPORTUNIDADE/status \
  -H "Content-Type: application/json" \
  -d '{"status": "preenchida"}' | python3 -m json.tool
```

**Transição:** `aberta → preenchida` (não é possível reabrir).

---

### 2.9. Reputação / Score

#### `GET /api/profissionais/{id}/reputacao` — Ver score e breakdown

```bash
curl -s http://localhost:8015/api/profissionais/ID_DO_PROFISSIONAL/reputacao | python3 -m json.tool
```

**Resposta:**
```json
{
  "profissional_id": "uuid",
  "score_contribuicao": 40,
  "breakdown": {
    "match_aceito": 10,
    "participou_desafio": 15,
    "mentor_concluido": 25,
    "mentorado_concluido": 0,
    "criou_oportunidade": 5
  }
}
```

**Como ganhar pontos:**

| Ação | Pontos |
|------|--------|
| Match aceito | +10 (cada um) |
| Participar de desafio | +15 (cada um) |
| Mentoria concluída (como mentor) | +25 (cada uma) |
| Mentoria concluída (como mentorado) | +10 (cada uma) |
| Criar oportunidade | +5 (cada uma) |

---

## 3. Fluxo de Uso

### Fluxo completo: cadastro → login → buscar → match → mensagem

```bash
# 1. CADASTRO
curl -s -X POST http://localhost:8015/api/profissionais \
  -H "Content-Type: application/json" \
  -d '{"nome":"Alice","email":"alice@exemplo.com","senha":"123456","skills":["Python","FastAPI"],"objetivos":["colaborar","mentorar"],"senioridade":"senior","cidade":"São Paulo"}' > /tmp/alice.json
ALICE_ID=$(python3 -c "import json; print(json.load(open('/tmp/alice.json'))['id'])")

curl -s -X POST http://localhost:8015/api/profissionais \
  -H "Content-Type: application/json" \
  -d '{"nome":"Bruno","email":"bruno@exemplo.com","senha":"123456","skills":["React","Design"],"objetivos":["colaborar","aprender"],"senioridade":"pleno","cidade":"São Paulo"}' > /tmp/bruno.json
BRUNO_ID=$(python3 -c "import json; print(json.load(open('/tmp/bruno.json'))['id'])")

# 2. LOGIN (opcional — o frontend usa o ID direto)
curl -s -X POST http://localhost:8015/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"alice@exemplo.com","senha":"123456"}'
# → Retorna access_token e profissional_id

# 3. BUSCAR PROFISSIONAIS
curl -s "http://localhost:8015/api/profissionais?skill=React"

# 4. FAZER MATCH
curl -s -X POST http://localhost:8015/api/matches \
  -H "Content-Type: application/json" \
  -d "{\"profissional_a_id\": \"$ALICE_ID\", \"profissional_b_id\": \"$BRUNO_ID\"}" > /tmp/match.json
MATCH_ID=$(python3 -c "import json; print(json.load(open('/tmp/match.json'))['id'])")

# Aceitar o match
curl -s -X POST "http://localhost:8015/api/matches/$MATCH_ID/aceitar"

# 5. ENVIAR MENSAGEM
curl -s -X POST http://localhost:8015/api/mensagens \
  -H "Content-Type: application/json" \
  -d "{\"match_id\": \"$MATCH_ID\", \"remetente_id\": \"$ALICE_ID\", \"conteudo\": \"Olá Bruno! Vamos colaborar?\"}"

# 6. VER CONVERSAS
curl -s "http://localhost:8015/api/profissionais/$ALICE_ID/conversas"

# 7. VER REPUTAÇÃO
curl -s "http://localhost:8015/api/profissionais/$ALICE_ID/reputacao"
```

### Fluxo de mentorias

```bash
# Alice (mentor) e Bruno (mentorado)
curl -s -X POST http://localhost:8015/api/mentorias/solicitar \
  -H "Content-Type: application/json" \
  -d "{\"mentorado_id\": \"$BRUNO_ID\", \"mentor_id\": \"$ALICE_ID\", \"area\": \"Desenvolvimento\", \"objetivos\": \"Aprender Python\"}" > /tmp/mentoria.json
MENTORIA_ID=$(python3 -c "import json; print(json.load(open('/tmp/mentoria.json'))['id'])")

# Aceitar (como mentor)
curl -s -X PATCH "http://localhost:8015/api/mentorias/$MENTORIA_ID/aceitar"

# Concluir
curl -s -X PATCH "http://localhost:8015/api/mentorias/$MENTORIA_ID/concluir"
```

---

## 4. Instruções de Deploy

### Desenvolvimento

```bash
# 1. Clonar o repositório
git clone <url-do-repo> && cd prosync

# 2. Instalar dependências
pip install -e .

# 3. Iniciar servidor (porta 8015)
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8015 --reload
```

O servidor estará em `http://localhost:8015`. O frontend estático é servido automaticamente na raiz.

### Produção

```bash
# Usando Gunicorn + Uvicorn (recomendado)
pip install gunicorn uvicorn
gunicorn app.main:app --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8015 --workers 4 --timeout 120
```

### Variáveis de Ambiente

| Variável | Descrição | Default |
|----------|-----------|---------|
| `DATABASE_URL` | URL de conexão SQLAlchemy | `sqlite:///./prosync.db` |
| `SECRET_KEY` | Chave secreta para JWT | `prosync-dev-secret-key-change-in-prod` |
| `GEMINI_API_KEY` | Chave da API Gemini (opcional) | `""` (usa fallback local) |

> **⚠ Importante:** Para produção, altere `SECRET_KEY` para um valor seguro e configure um banco PostgreSQL.

### Docker (exemplo)

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY . .
RUN pip install .
EXPOSE 8015
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8015"]
```

---

## 5. Testes

```bash
cd /root/prosync
python3 -m pytest tests/ -v
```

59 testes que cobrem:

- ✅ Health check
- ✅ CRUD de profissionais (criar, listar, obter, atualizar, filtros)
- ✅ Casos de borda (email duplicado, match consigo mesmo, status inválido)
- ✅ Autenticação (login, token JWT, senha errada)
- ✅ Matches (criar, aceitar, recusar, listar)
- ✅ Mensagens (enviar, listar, marcar como lida, conversas)
- ✅ Desafios (criar, participar, status, participantes, validações)
- ✅ Mentorias (solicitar, aceitar, concluir, listar)
- ✅ Oportunidades (CRUD, tipos, status)
- ✅ Reputação com breakdown
- ✅ Fluxo completo integrado